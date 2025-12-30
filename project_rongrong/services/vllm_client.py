"""
vLLM Client - 统一封装 vLLM 调用

支持:
- 双模型调度 (Thinking vs Non-thinking)
- Sleep/Wake 控制
- VLM 图像输入
- Thinking 内容分离
"""
import asyncio
import base64
import httpx
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path


class ModelType(Enum):
    """模型类型"""
    FILTER = "filter"      # Non-thinking, Port 8003
    AGENT = "agent"        # Thinking + VL, Port 8000


@dataclass
class VLLMResponse:
    """vLLM 响应"""
    content: str                          # 主要内容
    reasoning: Optional[str] = None       # 思考过程 (仅 Thinking 模型)
    usage: Optional[Dict] = None          # Token 使用情况


class VLLMClient:
    """vLLM 统一客户端"""

    def __init__(
        self,
        filter_url: str = "http://localhost:8003/v1/chat/completions",
        filter_model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8",
        agent_url: str = "http://localhost:8000/v1/chat/completions",
        agent_model: str = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8",
        timeout: int = 120,
    ):
        self.filter_url = filter_url
        self.filter_model = filter_model
        self.agent_url = agent_url
        self.agent_model = agent_model
        self.timeout = timeout

        # Sleep/Wake 端点
        self._sleep_url_8000 = "http://localhost:8000/sleep?level=1"
        self._wake_url_8000 = "http://localhost:8000/wake_up"
        self._status_url_8000 = "http://localhost:8000/is_sleeping"
        self._sleep_url_8003 = "http://localhost:8003/sleep?level=1"
        self._wake_url_8003 = "http://localhost:8003/wake_up"
        self._status_url_8003 = "http://localhost:8003/is_sleeping"

    async def chat(
        self,
        prompt: str,
        model_type: ModelType = ModelType.AGENT,
        images: Optional[List[str]] = None,
        temperature: float = 0.3,
        max_tokens: int = 8000,
    ) -> VLLMResponse:
        """
        发送聊天请求

        Args:
            prompt: 用户提示
            model_type: 模型类型 (FILTER 或 AGENT)
            images: 图像路径或 base64 列表 (仅 AGENT 支持)
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            VLLMResponse
        """
        if model_type == ModelType.FILTER:
            url = self.filter_url
            model = self.filter_model
        else:
            url = self.agent_url
            model = self.agent_model

        # 构建消息
        messages = self._build_messages(prompt, images)

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return self._parse_response(data, model_type)

    def _build_messages(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
    ) -> List[Dict]:
        """构建消息列表"""
        if not images:
            return [{"role": "user", "content": prompt}]

        # VLM 格式: 多模态内容
        content = []

        # 添加图像
        for img in images:
            if img.startswith("data:image"):
                # 已经是 base64
                image_url = img
            elif Path(img).exists():
                # 文件路径，转 base64
                image_url = self._file_to_base64(img)
            else:
                # 假设是 URL
                image_url = img

            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        # 添加文本
        content.append({
            "type": "text",
            "text": prompt
        })

        return [{"role": "user", "content": content}]

    def _file_to_base64(self, file_path: str) -> str:
        """文件转 base64"""
        path = Path(file_path)
        suffix = path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
        }
        mime_type = mime_map.get(suffix, "application/octet-stream")

        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()

        return f"data:{mime_type};base64,{data}"

    def _parse_response(
        self,
        data: Dict,
        model_type: ModelType,
    ) -> VLLMResponse:
        """解析响应"""
        choice = data["choices"][0]
        message = choice["message"]

        # 提取内容
        content = message.get("content", "")
        reasoning = None

        # Thinking 模型有 reasoning_content
        if model_type == ModelType.AGENT:
            reasoning = message.get("reasoning_content")

        # 提取 usage
        usage = data.get("usage")

        return VLLMResponse(
            content=content,
            reasoning=reasoning,
            usage=usage,
        )

    # ========== Sleep/Wake 控制 ==========

    async def sleep(self, port: int = 8000) -> bool:
        """让模型休眠"""
        url = self._sleep_url_8000 if port == 8000 else self._sleep_url_8003
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url)
            return resp.status_code == 200

    async def wake(self, port: int = 8000) -> bool:
        """唤醒模型"""
        url = self._wake_url_8000 if port == 8000 else self._wake_url_8003
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url)
            return resp.status_code == 200

    async def is_sleeping(self, port: int = 8000) -> bool:
        """检查是否休眠"""
        url = self._status_url_8000 if port == 8000 else self._status_url_8003
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
            return data.get("is_sleeping", False)

    async def switch_to_filter(self) -> None:
        """切换到 Filter 模式: 唤醒 8003, 休眠 8000"""
        await asyncio.gather(
            self.wake(8003),
            self.sleep(8000),
        )

    async def switch_to_agent(self) -> None:
        """切换到 Agent 模式: 唤醒 8000, 休眠 8003"""
        await asyncio.gather(
            self.wake(8000),
            self.sleep(8003),
        )


# ========== 便捷函数 ==========

_client: Optional[VLLMClient] = None


def get_client() -> VLLMClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = VLLMClient()
    return _client


async def chat_filter(prompt: str, **kwargs) -> VLLMResponse:
    """快捷调用 Filter 模型"""
    return await get_client().chat(prompt, ModelType.FILTER, **kwargs)


async def chat_agent(prompt: str, images: Optional[List[str]] = None, **kwargs) -> VLLMResponse:
    """快捷调用 Agent 模型"""
    return await get_client().chat(prompt, ModelType.AGENT, images=images, **kwargs)


# ========== 测试 ==========

async def _test():
    """测试客户端"""
    client = VLLMClient()

    # 测试 Filter
    print("Testing Filter model...")
    resp = await client.chat("1+1=?", ModelType.FILTER)
    print(f"Filter response: {resp.content[:100]}")

    # 测试 Agent
    print("\nTesting Agent model...")
    resp = await client.chat("1+1=?", ModelType.AGENT)
    print(f"Agent response: {resp.content[:100]}")
    if resp.reasoning:
        print(f"Reasoning: {resp.reasoning[:100]}")


if __name__ == "__main__":
    asyncio.run(_test())
