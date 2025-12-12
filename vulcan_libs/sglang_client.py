"""
SGLang Client for Vulcan Brain V5.1 Bicameral Architecture
CTO (Chief Technology Officer) - Code Execution Brain
"""

import re
import httpx
import json
from typing import Optional, Dict, Any, AsyncGenerator

class SGLangClient:
    """
    SGLang client for CTO brain - handles code generation with structured decoding.
    Supports AWQ quantized models with FP8 KV cache.
    """
    
    CODE_BLOCK_REGEX = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL)
    
    def __init__(
        self,
        base_url: str = "http://localhost:30000",
        model: str = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
        timeout: float = 120.0
    ):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> bool:
        """Check if SGLang server is healthy"""
        try:
            resp = await self.client.get("/v1/models")
            return resp.status_code == 200
        except Exception:
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,  # 优化：默认值降低
        stop: Optional[list] = None
    ) -> str:
        """
        Generate completion.
        
        Args:
            prompt: User prompt
            system_prompt: System instruction
            temperature: Sampling temperature (0 for deterministic)
            max_tokens: Maximum output tokens
            stop: Stop sequences
        
        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if stop:
            payload["stop"] = stop
        
        resp = await self.client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,  # 优化：默认值降低
        stop: Optional[list] = None
    ) -> AsyncGenerator[str, None]:
        """Stream generation token by token"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        if stop:
            payload["stop"] = stop
        
        async with self.client.stream("POST", "/v1/chat/completions", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    
    async def generate_code(
        self,
        task: str,
        language: str = "python",
        context: Optional[str] = None
    ) -> str:
        """
        Generate code with structured output.
        
        Args:
            task: Code task description
            language: Programming language
            context: Optional context (existing code, requirements)
        
        Returns:
            Generated code (with markdown wrapper for extraction)
        """
        system = f"""You are an expert {language} programmer.
Generate clean, efficient, well-documented code.
Always wrap your code in ```python ... ``` blocks.
Output the code, then briefly explain what it does."""
        
        prompt = task
        if context:
            prompt = f"Context:\n{context}\n\nTask: {task}"
        
        result = await self.generate(
            prompt=prompt,
            system_prompt=system,
            temperature=0.0,
            max_tokens=2048  # 平衡：简单任务够用，复杂任务也不会截断
        )
        
        return result  # Return full response, let caller extract code block
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
        
        Returns:
            Parsed JSON object
        """
        result = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt or "Output valid JSON only, no markdown wrapper.",
            temperature=0.0
        )
        
        # Try to extract JSON from markdown if present
        if "```json" in result:
            json_match = re.search(r"```json\s*(.*?)```", result, re.DOTALL)
            if json_match:
                result = json_match.group(1)
        elif "```" in result:
            json_match = re.search(r"```\s*(.*?)```", result, re.DOTALL)
            if json_match:
                result = json_match.group(1)
        
        return json.loads(result.strip())


# Singleton instance
_sglang_client: Optional[SGLangClient] = None

def get_sglang_client(
    base_url: str = "http://localhost:30000",
    model: str = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
) -> SGLangClient:
    """Get or create SGLang client singleton"""
    global _sglang_client
    if _sglang_client is None:
        _sglang_client = SGLangClient(base_url=base_url, model=model)
    return _sglang_client


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = get_sglang_client()
        
        # Health check
        healthy = await client.health_check()
        print(f"Server healthy: {healthy}")
        
        if healthy:
            # Test code generation
            result = await client.generate_code(
                task="Write a function to check if a number is prime",
                language="python"
            )
            print(f"Generated:\n{result}")
        
        await client.close()
    
    asyncio.run(test())
