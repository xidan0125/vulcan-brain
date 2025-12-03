"""
飞书机器人 LLM 客户端
- 封装本地 Ollama 调用
- 支持同步和异步接口
"""

from typing import List, Dict, Any
from llama_index.llms.ollama import Ollama

# 默认模型配置
DEFAULT_MODEL = "qwen3:30b-a3b"
DEFAULT_TIMEOUT = 60.0
DEFAULT_TEMPERATURE = 0.7


class LLMClient:
    """轻量 LLM 客户端"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.llm = Ollama(
            model=DEFAULT_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            request_timeout=DEFAULT_TIMEOUT,
        )
        self._initialized = True
        print("[LLMClient] 初始化完成")
    
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        异步聊天接口
        messages: [{"role": "system/user/assistant", "content": "..."}]
        """
        # 构建提示
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
        
        # 调用 LLM
        response = await self.llm.acomplete(prompt)
        result = str(response).strip()
        
        # 清理 think 标签
        if "</think>" in result:
            result = result.split("</think>")[-1].strip()
        
        return result
    
    async def complete(self, prompt: str) -> str:
        """简单补全接口"""
        response = await self.llm.acomplete(prompt)
        result = str(response).strip()
        if "</think>" in result:
            result = result.split("</think>")[-1].strip()
        return result


# 单例获取
_llm_client = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
