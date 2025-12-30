# vulcan_libs/ai_service.py
"""
Vulcan Brain - 统一AI服务层 (vLLM 版本)

职责:
1. 封装所有本地AI调用 (使用 vLLM)
2. 提供简单的调用接口
3. 统一配置管理

注意: 此模块现在使用 vLLM (http://localhost:8000) 替代 Ollama
"""

import json
import re
import os
import logging
from typing import Dict, List, Any, Optional, AsyncIterator
import httpx

logger = logging.getLogger("AIService")

# vLLM 配置
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")


def _get_vllm_model() -> str:
    """动态获取 vLLM 运行的模型名"""
    try:
        resp = httpx.get(f"{VLLM_BASE_URL}/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return "default-model"


class AIService:
    """
    统一AI服务 (vLLM后端)
    
    提供:
    - generate(): 单轮补全
    - generate_json(): JSON输出
    - chat(): 多轮对话
    - generate_stream(): 流式输出
    - analyze_chat(): 聊天分析
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        timeout: float = 120.0
    ):
        if self._initialized:
            return
            
        self.model = model or _get_vllm_model()
        self.base_url = base_url or VLLM_BASE_URL
        self.timeout = timeout
        self._initialized = True
        
        logger.info(f"[AIService] 初始化: model={self.model}, base_url={self.base_url}")
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        单轮文本生成
        
        Args:
            prompt: 提示词
            temperature: 温度
            max_tokens: 最大token数
            
        Returns:
            生成的文本
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Dict:
        """
        生成JSON输出
        
        Args:
            prompt: 提示词 (应包含JSON格式要求)
            temperature: 温度 (低温度保证稳定)
            max_tokens: 最大token数
            
        Returns:
            解析后的JSON对象
        """
        content = await self.generate(prompt, temperature=temperature, max_tokens=max_tokens)
        return self._parse_json(content)
    
    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        多轮对话
        
        Args:
            messages: [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度
            max_tokens: 最大token数
            
        Returns:
            助手回复
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        """
        流式文本生成
        
        Args:
            prompt: 提示词
            temperature: 温度
            max_tokens: 最大token数
            
        Yields:
            文本片段
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
    
    async def analyze_chat(
        self,
        messages: List[Dict],
        chat_name: str,
        date: str = None
    ) -> Dict:
        """
        聊天分析
        
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
    
    def _format_chat_messages(self, messages: List[Dict], max_chars: int = 8000) -> str:
        """格式化聊天消息"""
        lines = []
        total_chars = 0
        
        for msg in messages:
            sender = msg.get("sender", "Unknown")
            content = msg.get("content", "")
            time_str = msg.get("time", "")
            
            line = f"[{time_str}] {sender}: {content}"
            line_len = len(line)
            
            if total_chars + line_len > max_chars:
                lines.append("... (更多消息已截断)")
                break
            
            lines.append(line)
            total_chars += line_len
        
        return "\n".join(lines)
    
    def _parse_json(self, text: str) -> Dict:
        """从文本中解析JSON"""
        # 尝试从代码块提取
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            text = json_match.group(1)
        
        # 尝试从 { 到 } 提取
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            text = brace_match.group(0)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 原文: {text[:200]}")
            return {}


# ==================== 单例和便捷函数 ====================

_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """获取AIService单例"""
    global _service
    if _service is None:
        _service = AIService()
    return _service


async def generate(prompt: str, **kwargs) -> str:
    """便捷函数: 文本生成"""
    return await get_ai_service().generate(prompt, **kwargs)


async def generate_json(prompt: str, **kwargs) -> Dict:
    """便捷函数: JSON生成"""
    return await get_ai_service().generate_json(prompt, **kwargs)


async def chat(messages: List[Dict], **kwargs) -> str:
    """便捷函数: 多轮对话"""
    return await get_ai_service().chat(messages, **kwargs)


async def analyze_chat(messages: List[Dict], chat_name: str, **kwargs) -> Dict:
    """便捷函数: 聊天分析"""
    return await get_ai_service().analyze_chat(messages, chat_name, **kwargs)


# ==================== 测试 ====================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        service = get_ai_service()
        
        print("=== 测试 generate ===")
        result = await service.generate("用一句话介绍人工智能")
        print(f"结果: {result[:200]}...")
        
        print("\n=== 测试 generate_json ===")
        result = await service.generate_json("返回一个JSON对象，包含name和age字段")
        print(f"结果: {result}")
    
    asyncio.run(test())
