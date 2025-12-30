"""
飞书机器人 LLM 客户端 (vLLM 版本)
- 封装 vLLM API 调用
- 支持同步和异步接口
"""

import os
import httpx
from typing import List, Dict

# vLLM 配置
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = 120.0
DEFAULT_TEMPERATURE = 0.7


def _get_model_name() -> str:
    """动态获取 vLLM 模型名"""
    try:
        resp = httpx.get(f"{VLLM_BASE_URL}/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return "default-model"


class LLMClient:
    """轻量 LLM 客户端 (vLLM)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.base_url = VLLM_BASE_URL
        self.model = _get_model_name()
        self.timeout = DEFAULT_TIMEOUT
        self.temperature = DEFAULT_TEMPERATURE
        self._initialized = True
        print(f"[LLMClient] 初始化完成: model={self.model}")
    
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        异步聊天接口
        messages: [{"role": "system/user/assistant", "content": "..."}]
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": 2048,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def complete(self, prompt: str) -> str:
        """简单补全接口"""
        return await self.chat([{"role": "user", "content": prompt}])


# 单例获取
_llm_client = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
