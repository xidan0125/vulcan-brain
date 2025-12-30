"""
Vulcan Brain - 上下文工程管理器 v2
基于 Token 数量的上下文压缩

关键改进:
1. Token 估算（中文约 2 字符/token，英文约 4 字符/token）
2. 请求前检查并压缩，而不是请求后
3. 智能截断：保留最近对话 + 压缩旧对话
"""

import os
import logging
import httpx
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("ContextManager")

# ==================== 配置 ====================

# vLLM 配置
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")

# 上下文限制
MAX_CONTEXT_TOKENS = 40000      # 最大上下文 token (留 8K 给响应)
COMPRESS_THRESHOLD = 30000      # 超过这个就开始压缩
KEEP_RECENT_TOKENS = 8000       # 压缩后保留最近多少 token
MIN_MESSAGES_TO_COMPRESS = 6    # 至少有这么多消息才值得压缩


# ==================== Token 估算 ====================

def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量
    
    中文: ~1.5-2 字符/token
    英文: ~4 字符/token
    混合内容取折中值
    """
    if not text:
        return 0
    
    # 统计中文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    
    # 中文约 1.5 字符/token，其他约 4 字符/token
    chinese_tokens = chinese_chars / 1.5
    other_tokens = other_chars / 4
    
    return int(chinese_tokens + other_tokens) + 10  # +10 buffer


def estimate_messages_tokens(messages: List[Dict]) -> int:
    """估算消息列表的总 token 数"""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += estimate_tokens(content)
        total += 4  # role/formatting overhead
    return total


# ==================== 摘要生成 ====================

SUMMARY_PROMPT = """请将以下对话历史压缩成简洁的摘要。

要求:
1. 保留关键信息：用户的主要问题、重要决定、关键结论
2. 保留上下文：用户身份、偏好、正在进行的任务状态
3. 控制在 300 字以内
4. 使用第三人称

对话:
{conversation}

摘要:"""


async def generate_summary(messages: List[Dict], model: str = None) -> Optional[str]:
    """
    使用 vLLM 生成对话摘要
    """
    if not messages:
        return None
    
    # 格式化对话
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:500]  # 截断长内容
        
        if role == "user":
            lines.append(f"用户: {content}")
        elif role == "assistant":
            # 去掉 thinking 内容
            if "<think>" in content:
                content = content.split("</think>")[-1].strip()
            lines.append(f"助手: {content[:300]}")
        elif role == "system":
            lines.append(f"[系统] {content[:200]}")
    
    conversation_text = "\n".join(lines)
    prompt = SUMMARY_PROMPT.format(conversation=conversation_text)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 动态获取模型名
            if not model:
                resp = await client.get(f"{VLLM_BASE_URL}/models")
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    model = models[0]["id"] if models else "default"
            
            response = await client.post(
                f"{VLLM_BASE_URL}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            
            result = response.json()
            summary = result["choices"][0]["message"]["content"].strip()
            
            # 清理
            if summary.startswith("摘要:") or summary.startswith("摘要："):
                summary = summary[3:].strip()
            
            logger.info(f"Generated summary: {len(summary)} chars, ~{estimate_tokens(summary)} tokens")
            return summary
            
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return None


# ==================== 核心压缩逻辑 ====================

@dataclass
class ContextResult:
    """压缩结果"""
    messages: List[Dict]        # 最终消息列表
    token_count: int            # 估算 token 数
    was_compressed: bool        # 是否进行了压缩
    summary: Optional[str]      # 生成的摘要（如果有）


async def prepare_context(
    messages: List[Dict],
    system_prompt: Optional[str] = None,
    existing_summary: Optional[str] = None,
    max_tokens: int = MAX_CONTEXT_TOKENS,
    compress_threshold: int = COMPRESS_THRESHOLD
) -> ContextResult:
    """
    准备 LLM 上下文，必要时进行压缩
    
    策略:
    1. 如果 token < threshold，直接返回
    2. 如果 token >= threshold，压缩旧消息生成摘要
    3. 返回: [system_prompt] + [summary] + [recent_messages]
    
    Args:
        messages: 原始消息列表
        system_prompt: 系统提示词
        existing_summary: 已有的摘要
        max_tokens: 最大允许 token
        compress_threshold: 触发压缩的阈值
    
    Returns:
        ContextResult with prepared messages
    """
    # 1. 估算当前 token 数
    current_tokens = estimate_messages_tokens(messages)
    if system_prompt:
        current_tokens += estimate_tokens(system_prompt)
    if existing_summary:
        current_tokens += estimate_tokens(existing_summary)
    
    logger.info(f"Context tokens: {current_tokens} (threshold: {compress_threshold})")
    
    # 2. 如果不需要压缩，直接构建上下文
    if current_tokens < compress_threshold:
        final_messages = _build_messages(messages, system_prompt, existing_summary)
        return ContextResult(
            messages=final_messages,
            token_count=current_tokens,
            was_compressed=False,
            summary=existing_summary
        )
    
    # 3. 需要压缩
    logger.info(f"Compressing context: {current_tokens} tokens > {compress_threshold}")
    
    # 3.1 找到需要保留的最近消息
    recent_messages = []
    recent_tokens = 0
    
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.get("content", "")) + 4
        if recent_tokens + msg_tokens > KEEP_RECENT_TOKENS:
            break
        recent_messages.insert(0, msg)
        recent_tokens += msg_tokens
    
    # 至少保留最后一条用户消息
    if not recent_messages and messages:
        recent_messages = [messages[-1]]
    
    # 3.2 压缩旧消息
    old_messages = messages[:-len(recent_messages)] if len(recent_messages) < len(messages) else []
    
    new_summary = None
    if old_messages and len(old_messages) >= MIN_MESSAGES_TO_COMPRESS:
        new_summary = await generate_summary(old_messages)
        
        # 合并旧摘要
        if existing_summary and new_summary:
            new_summary = f"{existing_summary}\n\n[后续] {new_summary}"
        elif existing_summary:
            new_summary = existing_summary
    else:
        new_summary = existing_summary
    
    # 3.3 构建最终上下文
    final_messages = _build_messages(recent_messages, system_prompt, new_summary)
    final_tokens = estimate_messages_tokens(final_messages)
    
    logger.info(f"Compression done: {current_tokens} -> {final_tokens} tokens")
    
    return ContextResult(
        messages=final_messages,
        token_count=final_tokens,
        was_compressed=True,
        summary=new_summary
    )


def _build_messages(
    messages: List[Dict],
    system_prompt: Optional[str],
    summary: Optional[str]
) -> List[Dict]:
    """构建最终消息列表"""
    result = []
    
    # System prompt
    if system_prompt:
        result.append({"role": "system", "content": system_prompt})
    
    # Summary as system message
    if summary:
        result.append({
            "role": "system", 
            "content": f"[对话历史摘要]\n{summary}"
        })
    
    # Recent messages
    for msg in messages:
        result.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    return result


# ==================== 简单截断（备用方案）====================

def truncate_to_token_limit(
    messages: List[Dict],
    max_tokens: int = MAX_CONTEXT_TOKENS
) -> List[Dict]:
    """
    简单截断到 token 限制（不生成摘要）
    用于紧急情况或摘要生成失败时
    """
    total_tokens = 0
    result = []
    
    # 从后往前保留
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.get("content", "")) + 4
        if total_tokens + msg_tokens > max_tokens:
            break
        result.insert(0, msg)
        total_tokens += msg_tokens
    
    if not result and messages:
        # 至少保留最后一条，但截断内容
        last_msg = messages[-1].copy()
        content = last_msg.get("content", "")
        # 粗略截断到 max_tokens * 2 字符
        last_msg["content"] = content[:max_tokens * 2]
        result = [last_msg]
    
    return result


# ==================== 测试 ====================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 模拟长对话
        messages = []
        for i in range(30):
            messages.append({"role": "user", "content": f"这是第 {i+1} 条用户消息，包含一些测试内容。" * 10})
            messages.append({"role": "assistant", "content": f"这是第 {i+1} 条助手回复，也包含一些测试内容。" * 10})
        
        print(f"Original messages: {len(messages)}")
        print(f"Estimated tokens: {estimate_messages_tokens(messages)}")
        
        result = await prepare_context(
            messages=messages,
            system_prompt="你是 Vulcan Brain AI 助手",
            compress_threshold=5000  # 低阈值用于测试
        )
        
        print(f"\nAfter compression:")
        print(f"Messages: {len(result.messages)}")
        print(f"Tokens: {result.token_count}")
        print(f"Was compressed: {result.was_compressed}")
        if result.summary:
            print(f"Summary: {result.summary[:200]}...")
    
    asyncio.run(test())

# Stub functions for chat_router compatibility
MAX_HISTORY_TURNS = 20

def should_compact(message_count: int, is_compacted: bool) -> bool:
    """判断是否需要压缩会话"""
    return message_count > 50 and not is_compacted

async def compact_session(manager, session_id: str):
    """压缩会话 (stub - 暂未实现)"""
    pass

def build_context(messages):
    """构建上下文 (stub)"""
    return messages
