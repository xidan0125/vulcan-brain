"""
Vulcan Brain - 统一 LLM 客户端
支持 Gemini (云端) 和 Qwen3-Coder (本地 vLLM)
新增: 思考内容分离流式输出
"""

import os
import json
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator, Literal, Union
from dataclasses import dataclass
from enum import Enum

# Gemini SDK
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class ModelType(str, Enum):
    GEMINI = "gemini"
    QWEN3 = "qwen3"


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class StreamChunk:
    """流式输出的单个块"""
    type: Literal["thinking", "content"]  # thinking = 思考内容, content = 正式输出
    text: str


def _get_vllm_model_name(base_url: str = "http://localhost:8000") -> str:
    """动态获取 vLLM 运行的模型名"""
    try:
        resp = httpx.get(f"{base_url}/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return os.getenv("QWEN3_MODEL", "default-model")


class UnifiedLLMClient:
    """
    统一 LLM 客户端

    支持两个后端:
    - gemini: Google Gemini (云端，支持联网搜索)
    - qwen3: Qwen3-Coder via vLLM (本地，快速)
    """

    def __init__(
        self,
        gemini_api_key: str = None,
        qwen3_base_url: str = "http://localhost:8000",
        qwen3_model: str = None,
        gemini_model: str = "gemini-3-pro-preview",
        default_model: ModelType = ModelType.QWEN3
    ):
        # Gemini 配置
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = gemini_model
        self._gemini_client = None

        # Qwen3 配置 (vLLM OpenAI 兼容)
        self.qwen3_base_url = qwen3_base_url
        self.qwen3_model = qwen3_model or _get_vllm_model_name(qwen3_base_url)

        # 默认模型
        self.default_model = default_model

        # HTTP 客户端
        self._http_client = None

    def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client

    def _get_gemini_client(self):
        """获取 Gemini 客户端"""
        if not GEMINI_AVAILABLE:
            raise ImportError("google-genai not installed. Run: pip install google-genai")
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=self.gemini_api_key)
        return self._gemini_client

    async def chat(
        self,
        messages: List[ChatMessage],
        model: ModelType = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: List[Dict] = None,
        enable_search: bool = False,  # Gemini 专用
        enable_thinking: bool = True,  # 启用思考内容分离
    ) -> ChatResponse | AsyncGenerator[Union[str, StreamChunk], None]:
        """
        统一聊天接口

        Args:
            messages: 消息列表
            model: 模型类型 (gemini/qwen3)
            stream: 是否流式输出
            temperature: 温度
            max_tokens: 最大 token 数
            tools: 工具定义 (function calling)
            enable_search: 启用联网搜索 (仅 Gemini)
            enable_thinking: 启用思考内容分离 (默认 True)
        """
        model = model or self.default_model

        if model == ModelType.GEMINI:
            if stream:
                return self._gemini_stream(messages, temperature, max_tokens, enable_search, enable_thinking)
            else:
                return await self._gemini_chat(messages, temperature, max_tokens, enable_search)
        else:  # QWEN3
            if stream:
                return self._qwen3_stream(messages, temperature, max_tokens, tools, enable_thinking)
            else:
                return await self._qwen3_chat(messages, temperature, max_tokens, tools)

    # ==================== Gemini ====================

    async def _gemini_chat(
        self,
        messages: List[ChatMessage],
        temperature: float,
        max_tokens: int,
        enable_search: bool
    ) -> ChatResponse:
        """Gemini 同步聊天"""
        client = self._get_gemini_client()

        # 转换消息格式
        contents = self._messages_to_gemini(messages)

        # 配置
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )

        # 添加搜索工具
        tools = []
        if enable_search:
            tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
            config = genai_types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=tools
            )

        response = client.models.generate_content(
            model=self.gemini_model,
            contents=contents,
            config=config
        )

        return ChatResponse(
            content=response.text,
            model=self.gemini_model,
            finish_reason="stop"
        )

    async def _gemini_stream(
        self,
        messages: List[ChatMessage],
        temperature: float,
        max_tokens: int,
        enable_search: bool,
        enable_thinking: bool = True
    ) -> AsyncGenerator[Union[str, StreamChunk], None]:
        """
        Gemini 流式聊天
        当 enable_thinking=True 时，返回 StreamChunk 对象区分思考和内容
        否则返回纯字符串 (向后兼容)
        """
        client = self._get_gemini_client()
        contents = self._messages_to_gemini(messages)

        # 基础配置
        config_dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens
        }

        # 启用思考模式
        if enable_thinking:
            config_dict["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget_tokens=8192  # 思考 token 预算
            )

        # 搜索工具
        if enable_search:
            config_dict["tools"] = [genai_types.Tool(google_search=genai_types.GoogleSearch())]

        config = genai_types.GenerateContentConfig(**config_dict)

        # Gemini 流式
        response = client.models.generate_content_stream(
            model=self.gemini_model,
            contents=contents,
            config=config
        )

        for chunk in response:
            # 检查是否有 candidates
            if not chunk.candidates:
                continue

            for candidate in chunk.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue

                for part in candidate.content.parts:
                    # Gemini 思考模式返回 thought 字段
                    if enable_thinking and hasattr(part, 'thought') and part.thought:
                        yield StreamChunk(type="thinking", text=part.text or "")
                    elif hasattr(part, 'text') and part.text:
                        if enable_thinking:
                            yield StreamChunk(type="content", text=part.text)
                        else:
                            yield part.text  # 向后兼容：直接返回字符串

    def _messages_to_gemini(self, messages: List[ChatMessage]) -> list:
        """
        转换消息格式为 Gemini 原生多轮对话格式
        Gemini 使用 role: 'user' | 'model', 不支持 'assistant'
        system 消息会合并到第一条 user 消息
        """
        contents = []
        system_prompt = None

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "user":
                # 如果有 system prompt，合并到第一条 user 消息
                if system_prompt and not contents:
                    text = f"[System Instructions]\n{system_prompt}\n\n[User Message]\n{msg.content}"
                    system_prompt = None
                else:
                    text = msg.content
                contents.append({"role": "user", "parts": [{"text": text}]})
            else:  # assistant -> model
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

        return contents

    # ==================== Qwen3 (vLLM) ====================

    async def _qwen3_chat(
        self,
        messages: List[ChatMessage],
        temperature: float,
        max_tokens: int,
        tools: List[Dict] = None
    ) -> ChatResponse:
        """Qwen3 同步聊天 (vLLM OpenAI API)"""
        client = self._get_http_client()

        # 构建请求
        payload = {
            "model": self.qwen3_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await client.post(
            f"{self.qwen3_base_url}/v1/chat/completions",
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        return ChatResponse(
            content=choice["message"]["content"],
            model=self.qwen3_model,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage")
        )

    async def _qwen3_stream(
        self,
        messages: List[ChatMessage],
        temperature: float,
        max_tokens: int,
        tools: List[Dict] = None,
        enable_thinking: bool = True
    ) -> AsyncGenerator[Union[str, StreamChunk], None]:
        """
        Qwen3 流式聊天
        使用 vLLM deepseek_r1 reasoning parser 区分思考和内容
        reasoning_content 字段包含思考过程
        content 字段包含正式回复
        """
        client = self._get_http_client()

        payload = {
            "model": self.qwen3_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with client.stream(
            "POST",
            f"{self.qwen3_base_url}/v1/chat/completions",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})

                        # vLLM deepseek_r1 parser 分离 reasoning_content 和 content
                        reasoning = delta.get("reasoning_content", "")
                        content = delta.get("content", "")

                        if enable_thinking:
                            if reasoning:
                                yield StreamChunk(type="thinking", text=reasoning)
                            if content:
                                yield StreamChunk(type="content", text=content)
                        else:
                            # 向后兼容：合并所有内容
                            if reasoning:
                                yield reasoning
                            if content:
                                yield content

                    except json.JSONDecodeError:
                        continue

    # ==================== 工具方法 ====================

    async def close(self):
        """关闭客户端"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# ==================== 全局实例 ====================

_client: Optional[UnifiedLLMClient] = None


def get_llm_client() -> UnifiedLLMClient:
    """获取全局 LLM 客户端"""
    global _client
    if _client is None:
        _client = UnifiedLLMClient(
            gemini_api_key=os.getenv("GEMINI_API_KEY", "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"),
            qwen3_base_url=os.getenv("QWEN3_BASE_URL", "http://localhost:8000"),
        )
    return _client


# ==================== 测试 ====================

async def test():
    """测试函数"""
    client = get_llm_client()

    messages = [
        ChatMessage(role="user", content="你好，请用一句话介绍自己")
    ]

    print("=== Qwen3 测试 ===")
    try:
        response = await client.chat(messages, model=ModelType.QWEN3)
        print(f"回复: {response.content[:200]}...")
    except Exception as e:
        print(f"错误: {e}")

    print("\n=== Qwen3 流式测试 (思考分离) ===")
    try:
        async for chunk in await client.chat(messages, model=ModelType.QWEN3, stream=True, enable_thinking=True):
            if isinstance(chunk, StreamChunk):
                prefix = "[思考] " if chunk.type == "thinking" else ""
                print(f"{prefix}{chunk.text}", end="", flush=True)
            else:
                print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"错误: {e}")

    print("\n=== Gemini 测试 ===")
    try:
        response = await client.chat(messages, model=ModelType.GEMINI)
        print(f"回复: {response.content[:200]}...")
    except Exception as e:
        print(f"错误: {e}")

    await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test())
