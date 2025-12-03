# vulcan_libs/ai_service.py
"""
Vulcan Brain - 统一AI服务层

职责:
1. 封装所有AI调用（直接LLM + Kernel）
2. 统一配置管理（从config.py读取）
3. 统一Think标签过滤
4. 提供简单和复杂两种调用模式

设计原则:
- 简单任务用 generate() - 直接LLM，快速无状态
- 复杂任务用 kernel_call() - 完整Agent能力
- 所有调用者只需依赖此模块
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, AsyncIterator
import httpx

# 从统一配置读取
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
from config import LLM_MODEL_NAME, LLM_BASE_URL, LLM_API_URL

logger = logging.getLogger("AIService")


class ThinkTagFilter:
    """
    Think标签过滤器 - 处理qwen3的思考输出

    支持两种模式:
    1. 完整文本过滤 - filter(text)
    2. 流式过滤 - process_chunk(chunk)
    """

    THINK_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL)

    def __init__(self):
        self.buffer = ""
        self.inside_think = False

    def filter(self, text: str) -> str:
        """过滤完整文本中的think标签"""
        return self.THINK_PATTERN.sub('', text).strip()

    def process_chunk(self, chunk: str) -> str:
        """
        流式处理chunk，返回可输出的内容

        用于流式响应时实时过滤think内容
        """
        self.buffer += chunk
        outputs = []

        while True:
            if self.inside_think:
                close_idx = self.buffer.find('</think>')
                if close_idx == -1:
                    self.buffer = ""
                    break
                else:
                    self.buffer = self.buffer[close_idx + 8:]
                    self.inside_think = False
            else:
                open_idx = self.buffer.find('<think>')
                if open_idx == -1:
                    safe_len = self._find_safe_length(self.buffer)
                    if safe_len > 0:
                        outputs.append(self.buffer[:safe_len])
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    if open_idx > 0:
                        outputs.append(self.buffer[:open_idx])
                    self.buffer = self.buffer[open_idx + 7:]
                    self.inside_think = True

        return ''.join(outputs)

    def _find_safe_length(self, text: str) -> int:
        """找到可以安全输出的长度（避免截断标签）"""
        if len(text) < 10:
            return 0
        for i in range(len(text) - 1, max(len(text) - 10, -1), -1):
            if text[i] == '<':
                return i
        return len(text)

    def flush(self) -> str:
        """刷新缓冲区（流结束时调用）"""
        if self.inside_think:
            return ""
        result = self.buffer
        self.buffer = ""
        return result

    def reset(self):
        """重置状态"""
        self.buffer = ""
        self.inside_think = False


class AIService:
    """
    统一AI服务 - Vulcan Brain的AI调用入口

    使用示例:
    ```python
    from vulcan_libs.ai_service import get_ai_service

    ai = get_ai_service()

    # 简单生成
    result = await ai.generate("翻译成英文: 你好")

    # JSON输出
    data = await ai.generate_json(prompt, schema={"summary": str, "items": list})

    # 聊天分析（预设模板）
    analysis = await ai.analyze_chat(messages, chat_name="产品群")
    ```
    """

    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        timeout: int = 180
    ):
        self.model = model or LLM_MODEL_NAME
        self.base_url = base_url or LLM_BASE_URL
        self.timeout = timeout
        self.filter = ThinkTagFilter()

        logger.info(f"[AIService] 初始化: model={self.model}, base_url={self.base_url}")

    # ========== 基础调用 ==========

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: str = None
    ) -> str:
        """
        单次生成（带think过滤）

        Args:
            prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大token数
            system: 系统提示词（可选）

        Returns:
            生成的文本（已过滤think标签）
        """
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )
            result = resp.json()
            response = result.get("response", "")

            # 过滤think标签
            return self.filter.filter(response)

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4000
    ) -> Dict:
        """
        生成JSON输出

        Args:
            prompt: 提示词（应包含JSON格式要求）
            temperature: 温度（JSON生成建议用低温度）
            max_tokens: 最大token数

        Returns:
            解析后的JSON对象
        """
        response = await self.generate(prompt, temperature, max_tokens)
        return self._parse_json(response)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> str:
        """
        多轮对话

        Args:
            messages: 消息列表 [{"role": "user/assistant", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            助手回复（已过滤think标签）
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )
            result = resp.json()
            response = result.get("message", {}).get("content", "")

            return self.filter.filter(response)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> AsyncIterator[str]:
        """
        流式生成（带实时think过滤）

        Args:
            prompt: 用户提示词

        Yields:
            过滤后的文本片段
        """
        self.filter.reset()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("response", "")
                            if chunk:
                                filtered = self.filter.process_chunk(chunk)
                                if filtered:
                                    yield filtered
                        except json.JSONDecodeError:
                            continue

                # 刷新剩余内容
                final = self.filter.flush()
                if final:
                    yield final

    # ========== 高级调用 ==========

    async def analyze_chat(
        self,
        messages: List[Dict],
        chat_name: str,
        date: str = None
    ) -> Dict:
        """
        聊天分析（预设prompt模板）

        Args:
            messages: 消息列表
            chat_name: 群聊名称
            date: 日期

        Returns:
            分析结果JSON
        """
        from datetime import datetime

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # 格式化消息
        formatted = self._format_chat_messages(messages)

        prompt = f"""你是一个专业的企业沟通分析助手。请分析以下群聊消息，提取关键信息。

群聊: {chat_name}
日期: {date}
消息数: {len(messages)}

---消息内容---
{formatted}
---消息结束---

请按以下JSON格式输出（只输出JSON，不要其他内容）:
{{
  "summary": "一句话概括今日讨论重点",
  "decisions": ["做出的决策1", "决策2"],
  "action_items": ["待办事项1", "待办事项2"],
  "risks": ["风险/问题/阻塞点"],
  "topics": ["讨论的主要话题"],
  "activity_level": "high/medium/low",
  "key_participants": ["活跃参与者"],
  "sentiment": "positive/neutral/negative"
}}

注意:
- 只提取工作相关内容，忽略闲聊
- 如果某项无内容，返回空数组[]
- activity_level根据消息频率和讨论深度判断"""

        return await self.generate_json(prompt, temperature=0.3, max_tokens=4000)

    async def kernel_call(
        self,
        user_query: str,
        session_id: str = None
    ) -> str:
        """
        通过Kernel调用（完整Agent能力）

        用于需要工具调用、记忆系统的复杂任务

        Args:
            user_query: 用户请求
            session_id: 会话ID（可选）

        Returns:
            Agent响应
        """
        # TODO: 集成 VulcanCodeActKernel
        # 当前先返回提示，后续实现
        logger.warning("[AIService] kernel_call 尚未实现，使用 generate 替代")
        return await self.generate(user_query)

    # ========== 工具方法 ==========

    def _format_chat_messages(self, messages: List[Dict], max_chars: int = 8000) -> str:
        """格式化消息列表用于分析"""
        from datetime import datetime

        lines = []
        total = 0

        # 按时间排序
        sorted_msgs = sorted(messages, key=lambda x: x.get("timestamp", datetime.min))

        for msg in sorted_msgs:
            sender = msg.get("sender", {})
            sender_id = sender.get("open_id", "")[-6:] if sender.get("open_id") else "???"
            sender_name = sender.get("name", sender_id)
            content = msg.get("content", "")

            ts = msg.get("timestamp")
            time_str = ts.strftime("%H:%M") if isinstance(ts, datetime) else ""

            line = f"[{time_str}] {sender_name}: {content}"

            if total + len(line) > max_chars:
                lines.append("... (更多消息省略)")
                break

            lines.append(line)
            total += len(line)

        return "\n".join(lines)

    def _parse_json(self, text: str) -> Dict:
        """解析AI返回的JSON"""
        text = text.strip()

        # 处理markdown代码块
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"[AIService] JSON解析失败: {e}")
            return {
                "summary": text[:200] if text else "解析失败",
                "decisions": [],
                "action_items": [],
                "risks": [],
                "topics": [],
                "activity_level": "medium",
                "key_participants": [],
                "sentiment": "neutral",
                "parse_error": True,
                "raw_response": text[:500]
            }


# ========== 全局实例 ==========

_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """获取AI服务单例"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


# ========== 便捷函数 ==========

async def generate(prompt: str, **kwargs) -> str:
    """快捷生成函数"""
    return await get_ai_service().generate(prompt, **kwargs)


async def generate_json(prompt: str, **kwargs) -> Dict:
    """快捷JSON生成函数"""
    return await get_ai_service().generate_json(prompt, **kwargs)


async def chat(messages: List[Dict], **kwargs) -> str:
    """快捷对话函数"""
    return await get_ai_service().chat(messages, **kwargs)


async def analyze_chat(messages: List[Dict], chat_name: str, **kwargs) -> Dict:
    """快捷聊天分析函数"""
    return await get_ai_service().analyze_chat(messages, chat_name, **kwargs)
