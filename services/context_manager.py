"""
Vulcan Brain - 上下文工程管理器
实现对话历史的截断和压缩

基于 Google/Kaggle 白皮书 Context Engineering:
- Truncation: 保留最后 N 轮对话
- Compaction: 使用 LLM 摘要压缩旧对话
"""

import os
import logging
import httpx
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger("ContextManager")

# ==================== 配置 ====================

# Qwen3 本地模型配置
QWEN3_BASE_URL = os.getenv("QWEN3_BASE_URL", "http://localhost:8000/v1")
QWEN3_MODEL = os.getenv("QWEN3_MODEL", "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8")

# 上下文工程参数
MAX_HISTORY_TURNS = 20          # 最大保留轮数
COMPACTION_THRESHOLD = 30       # 触发压缩的消息数阈值
COMPACTION_KEEP_RECENT = 10     # 压缩后保留最近几条


# ==================== 摘要提示词 ====================

SUMMARY_PROMPT = """请将以下对话历史压缩成一段简洁的摘要。

要求:
1. 保留关键信息：用户的主要问题、重要决定、关键结论
2. 保留上下文：用户身份、偏好、正在进行的任务
3. 简洁明了：控制在 200 字以内
4. 使用第三人称：如"用户询问了..."、"助手建议..."

对话历史:
{conversation}

请输出摘要:"""


# ==================== 核心函数 ====================

def truncate_history(history: List[Dict], max_turns: int = MAX_HISTORY_TURNS) -> List[Dict]:
    """
    截断历史到最后 N 轮

    Args:
        history: 消息列表 [{role, content, ...}]
        max_turns: 最大保留轮数

    Returns:
        截断后的消息列表
    """
    if len(history) <= max_turns:
        return history

    truncated = history[-max_turns:]
    logger.info(f"Truncated history: {len(history)} -> {len(truncated)} messages")
    return truncated


def should_compact(message_count: int, is_compacted: bool = False) -> bool:
    """
    判断是否需要压缩

    Args:
        message_count: 当前消息数量
        is_compacted: 是否已经压缩过

    Returns:
        是否需要压缩
    """
    # 如果已经压缩过，用更高的阈值
    threshold = COMPACTION_THRESHOLD * 2 if is_compacted else COMPACTION_THRESHOLD
    return message_count >= threshold


def format_history_for_summary(history: List[Dict], exclude_recent: int = COMPACTION_KEEP_RECENT) -> str:
    """
    将历史格式化为用于摘要的文本

    Args:
        history: 消息列表
        exclude_recent: 排除最近几条（这些不需要摘要）

    Returns:
        格式化的对话文本
    """
    # 只摘要旧消息
    messages_to_summarize = history[:-exclude_recent] if len(history) > exclude_recent else []

    if not messages_to_summarize:
        return ""

    lines = []
    for msg in messages_to_summarize:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "user":
            lines.append(f"用户: {content}")
        elif role == "assistant":
            lines.append(f"助手: {content}")
        elif role == "system":
            lines.append(f"[系统] {content}")
        elif role == "tool":
            tool_name = msg.get("name", "工具")
            lines.append(f"[工具调用: {tool_name}] {content[:100]}...")

    return "\n".join(lines)


async def generate_summary(history: List[Dict]) -> Optional[str]:
    """
    使用 Qwen3 本地模型生成对话摘要

    Args:
        history: 消息历史

    Returns:
        摘要文本，失败返回 None
    """
    # 格式化对话
    conversation_text = format_history_for_summary(history)

    if not conversation_text:
        logger.info("No messages to summarize")
        return None

    prompt = SUMMARY_PROMPT.format(conversation=conversation_text)

    payload = {
        "model": QWEN3_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,  # 低温度保证稳定输出
        "max_tokens": 500
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QWEN3_BASE_URL}/chat/completions",
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            summary = result["choices"][0]["message"]["content"]

            # 清理输出
            summary = summary.strip()
            if summary.startswith("摘要:") or summary.startswith("摘要："):
                summary = summary[3:].strip()

            logger.info(f"Generated summary: {len(summary)} chars")
            return summary

    except httpx.TimeoutException:
        logger.error("Summary generation timed out")
        return None
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return None


async def compact_session(
    session_manager,
    session_id: str,
    force: bool = False
) -> bool:
    """
    压缩会话历史

    流程:
    1. 检查是否需要压缩
    2. 生成摘要
    3. 保存摘要到 session
    4. 清理旧历史

    Args:
        session_manager: SessionManager 实例
        session_id: 会话 ID
        force: 是否强制压缩

    Returns:
        是否成功压缩
    """
    session = await session_manager.get_session(session_id)
    if not session:
        logger.error(f"Session not found: {session_id}")
        return False

    message_count = session.get("message_count", 0)
    is_compacted = session.get("is_compacted", False)
    history = session.get("history", [])

    # 检查是否需要压缩
    if not force and not should_compact(message_count, is_compacted):
        logger.debug(f"Session {session_id} does not need compaction (count={message_count})")
        return False

    logger.info(f"Starting compaction for session {session_id} (count={message_count})")

    # 生成摘要
    summary = await generate_summary(history)

    if not summary:
        logger.warning(f"Failed to generate summary for session {session_id}")
        return False

    # 合并旧摘要和新摘要
    old_summary = session.get("summary", "")
    if old_summary:
        summary = f"{old_summary}\n\n[后续对话摘要] {summary}"

    # 保存摘要
    await session_manager.set_summary(session_id, summary)

    # 清理旧历史
    await session_manager.clear_old_history(session_id, keep_last=COMPACTION_KEEP_RECENT)

    logger.info(f"Compaction complete for session {session_id}")
    return True


# ==================== 上下文构建 ====================

def build_context(
    history: List[Dict],
    summary: Optional[str] = None,
    system_prompt: Optional[str] = None,
    max_turns: int = MAX_HISTORY_TURNS
) -> List[Dict]:
    """
    构建 LLM 上下文

    Args:
        history: 原始对话历史
        summary: 压缩摘要
        system_prompt: 系统提示词
        max_turns: 最大轮数

    Returns:
        构建好的消息列表
    """
    context = []

    # 1. 系统提示词
    if system_prompt:
        context.append({"role": "system", "content": system_prompt})

    # 2. 历史摘要
    if summary:
        context.append({
            "role": "system",
            "content": f"[对话历史摘要]\n{summary}"
        })

    # 3. 最近对话 (截断)
    recent_history = truncate_history(history, max_turns)

    for msg in recent_history:
        context.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    return context


# ==================== 测试 ====================

if __name__ == "__main__":
    import asyncio

    async def test():
        # 模拟历史
        history = [
            {"role": "user", "content": "你好，我是张三"},
            {"role": "assistant", "content": "你好张三！有什么可以帮助你的？"},
            {"role": "user", "content": "我想了解一下 AI Agent 的架构"},
            {"role": "assistant", "content": "AI Agent 通常由三个核心组件组成：模型（大脑）、工具（双手）和编排层（神经系统）..."},
            {"role": "user", "content": "工具调用是怎么实现的？"},
            {"role": "assistant", "content": "工具调用主要通过 Function Calling 实现。模型会分析用户意图，决定是否需要调用工具..."},
        ]

        # 测试截断
        print("=== Truncation Test ===")
        truncated = truncate_history(history, max_turns=4)
        print(f"Original: {len(history)}, Truncated: {len(truncated)}")

        # 测试摘要生成
        print("\n=== Summary Test ===")
        summary = await generate_summary(history)
        print(f"Summary: {summary}")

        # 测试上下文构建
        print("\n=== Context Build Test ===")
        context = build_context(
            history=history,
            summary=summary,
            system_prompt="你是 Vulcan Brain AI 助手",
            max_turns=4
        )
        for msg in context:
            print(f"[{msg['role']}] {msg['content'][:50]}...")

    asyncio.run(test())
