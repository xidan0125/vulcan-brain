"""
Vulcan Nexus - Thinking Stream Parser
处理 vLLM Qwen3 的流式输出，分离 thinking 和 content
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional, List, AsyncIterator, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedChunk:
    """解析后的流式块"""
    thinking: Optional[str] = None      # 思考内容 (不展示给用户)
    content: Optional[str] = None       # 最终回复
    tool_calls: Optional[List[Dict]] = None  # 工具调用
    is_complete: bool = False
    raw_delta: Dict = field(default_factory=dict)


class ThinkingStreamParser:
    """
    处理 vLLM Qwen3 的流式输出
    
    vLLM 使用 --reasoning-parser qwen3 时:
    - delta.reasoning_content: 思考内容
    - delta.content: 最终回复
    - delta.tool_calls: 工具调用 (如果有)
    """
    
    def __init__(self, strip_think_tags: bool = True):
        self.strip_think_tags = strip_think_tags
        self.thinking_buffer = ""
        self.content_buffer = ""
        self.tool_call_buffer = []
        self.hermes_buffer = ""  # Hermes 格式工具调用缓冲
    
    def reset(self):
        """重置解析器状态"""
        self.thinking_buffer = ""
        self.content_buffer = ""
        self.tool_call_buffer = []
        self.hermes_buffer = ""
    
    async def parse_stream(
        self,
        stream: AsyncIterator[str]
    ) -> AsyncIterator[ParsedChunk]:
        """
        解析 SSE 流式响应
        
        Args:
            stream: SSE 数据流 (每行格式: "data: {...}")
            
        Yields:
            ParsedChunk
        """
        async for line in stream:
            if not line.startswith("data: "):
                continue
                
            data = line[6:].strip()
            
            if data == "[DONE]":
                yield ParsedChunk(is_complete=True)
                break
            
            try:
                chunk = json.loads(data)
                parsed = self._parse_chunk(chunk)
                if parsed:
                    yield parsed
            except json.JSONDecodeError:
                continue
    
    def parse_chunk(self, chunk: Dict) -> Optional[ParsedChunk]:
        """解析单个 chunk (同步版本)"""
        return self._parse_chunk(chunk)
    
    def _parse_chunk(self, chunk: Dict) -> Optional[ParsedChunk]:
        """解析单个 OpenAI 格式的 chunk"""
        if not chunk.get("choices"):
            return None
        
        choice = chunk["choices"][0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")
        
        result = ParsedChunk(raw_delta=delta)
        
        # 1. 检查 reasoning_content (vLLM qwen3 parser)
        if "reasoning_content" in delta and delta["reasoning_content"]:
            reasoning = delta["reasoning_content"]
            self.thinking_buffer += reasoning
            result.thinking = reasoning
        
        # 2. 检查 content
        if "content" in delta and delta["content"]:
            content = delta["content"]
            
            # 检查是否是 Hermes 格式工具调用
            self.hermes_buffer += content
            if "<tool_call>" in self.hermes_buffer:
                # 等待完整的工具调用
                if "</tool_call>" in self.hermes_buffer:
                    tool_calls = self._parse_hermes_tool_calls(self.hermes_buffer)
                    if tool_calls:
                        result.tool_calls = tool_calls
                        self.tool_call_buffer.extend(tool_calls)
                    self.hermes_buffer = ""
                # 不输出内容，等待完整工具调用
                return result
            else:
                # 清理可能残留的 think 标签
                cleaned_content = self._clean_think_tags(content)
                if cleaned_content:
                    self.content_buffer += cleaned_content
                    result.content = cleaned_content
                self.hermes_buffer = ""  # 重置 Hermes 缓冲
        
        # 3. 检查原生 tool_calls
        if "tool_calls" in delta:
            result.tool_calls = delta["tool_calls"]
            self.tool_call_buffer.extend(delta["tool_calls"])
        
        # 4. 检查完成状态
        if finish_reason:
            result.is_complete = True
        
        return result
    
    def _clean_think_tags(self, text: str) -> str:
        """清理 think 标签"""
        if not self.strip_think_tags:
            return text
        
        # 移除完整的 <think>...</think>
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 移除单独的标签
        text = re.sub(r'</?think>', '', text)
        
        return text.strip()
    
    def _parse_hermes_tool_calls(self, text: str) -> List[Dict]:
        """解析 Hermes 格式的工具调用"""
        pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        matches = re.findall(pattern, text, re.DOTALL)
        
        tool_calls = []
        for match in matches:
            try:
                call = json.loads(match)
                tool_calls.append({
                    "id": f"call_{len(tool_calls)}",
                    "type": "function",
                    "function": {
                        "name": call.get("name"),
                        "arguments": json.dumps(call.get("arguments", {}))
                    }
                })
            except json.JSONDecodeError:
                continue
        
        return tool_calls
    
    def get_accumulated(self) -> Dict:
        """获取累积的内容"""
        return {
            "thinking": self.thinking_buffer,
            "content": self.content_buffer,
            "tool_calls": self.tool_call_buffer
        }
    
    def get_final_content(self) -> str:
        """获取最终内容 (清理后)"""
        content = self.content_buffer
        
        # 最终清理
        content = self._clean_think_tags(content)
        
        # 移除开头的空白行
        content = content.lstrip('\n')
        
        return content


def clean_response(text: str) -> str:
    """
    清理模型响应，移除 thinking 内容
    
    用于非流式响应的后处理
    """
    # 移除 <think>...</think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # 处理只有 </think> 的情况 (vLLM 有时会这样)
    if "</think>" in text and "<think>" not in text:
        parts = text.split("</think>", 1)
        if len(parts) > 1:
            text = parts[1]
    
    # 移除残留标签
    text = re.sub(r'</?think>', '', text)
    
    return text.strip()


# === 测试 ===

async def test_parser():
    """测试解析器"""
    parser = ThinkingStreamParser()
    
    # 模拟 vLLM 流式响应
    mock_chunks = [
        {"choices": [{"delta": {"reasoning_content": "让我思考一下..."}}]},
        {"choices": [{"delta": {"reasoning_content": "用户想要发送消息"}}]},
        {"choices": [{"delta": {"content": "好的"}}]},
        {"choices": [{"delta": {"content": "，我来帮你发送消息。"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ]
    
    for chunk in mock_chunks:
        parsed = parser.parse_chunk(chunk)
        if parsed:
            if parsed.thinking:
                print(f"[Thinking] {parsed.thinking}")
            if parsed.content:
                print(f"[Content] {parsed.content}")
            if parsed.is_complete:
                print("[Done]")
    
    print("\nAccumulated:")
    print(parser.get_accumulated())


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_parser())
