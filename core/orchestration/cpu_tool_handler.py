"""
Vulcan Nexus - CPU Tool Handler
为 llama-server (无原生 function calling) 提供 ReAct 风格工具调用
"""

import re
import json
import httpx
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, AsyncIterator
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """工具调用"""
    name: str
    params: Dict[str, Any]
    raw_text: str = ""


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    result: Any
    error: Optional[str] = None


class CPUToolHandler:
    """
    为 llama-server 提供 ReAct 风格工具调用
    
    格式:
    思考: [分析当前情况]
    动作: [工具名称]
    参数: ```json
    {"param1": "value1"}
    ```
    
    观察: [工具结果]
    
    最终回答: [给用户的回复]
    """
    
    SYSTEM_PROMPT = """你是一个任务执行助手。当需要调用工具时，使用以下格式：

思考: [分析当前情况和需要做什么]
动作: [工具名称]
参数: ```json
{{"param1": "value1", "param2": "value2"}}
```

当你收到工具结果后，会以「观察:」开头展示给你。

完成任务后，使用以下格式直接回复：
最终回答: [给用户的回复]

重要规则:
1. 每次只调用一个工具
2. 等待工具结果后再继续
3. 参数必须是有效的 JSON
4. 完成后必须给出「最终回答」

可用工具:
{tool_descriptions}
"""

    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        model: str = "qwen3-8b",
        tools: Dict[str, Callable] = None,
        max_iterations: int = 5
    ):
        self.base_url = base_url
        self.model = model
        self.tools = tools or {}
        self.max_iterations = max_iterations
        self.tool_descriptions = self._build_tool_descriptions()
    
    def register_tool(self, name: str, func: Callable, description: str = None):
        """注册工具"""
        self.tools[name] = func
        if description:
            func.__doc__ = description
        self.tool_descriptions = self._build_tool_descriptions()
    
    def _build_tool_descriptions(self) -> str:
        """构建工具描述 - 包含 core.tools 的工具"""
        descriptions = []
        
        # 本地注册的工具
        for name, func in self.tools.items():
            doc = getattr(func, "__doc__", None) or "无描述"
            descriptions.append(f"- {name}: {doc}")
        
        # 从 core.tools 获取
        try:
            from core.tools import get_tool_schemas
            schemas = get_tool_schemas()
            for schema in schemas:
                func_def = schema.get("function", {})
                name = func_def.get("name", "")
                desc = func_def.get("description", "无描述")
                if name and name not in self.tools:
                    descriptions.append(f"- {name}: {desc[:100]}...")
        except Exception as e:
            logger.warning(f"Failed to get core.tools schemas: {e}")
        
        return "\n".join(descriptions) if descriptions else "无可用工具"

    def get_system_prompt(self) -> str:
        """获取系统提示"""
        return self.SYSTEM_PROMPT.format(tool_descriptions=self.tool_descriptions)
    
    def parse_tool_call(self, response: str) -> Optional[ToolCall]:
        """从模型响应中解析工具调用"""
        
        # 匹配 "动作: xxx"
        action_match = re.search(r'动作:\s*(\w+)', response)
        if not action_match:
            return None
        
        tool_name = action_match.group(1)
        
        # 匹配 "参数: ```json ... ```"
        params_match = re.search(
            r'参数:\s*```(?:json)?\s*(\{.*?\})\s*```',
            response,
            re.DOTALL
        )
        
        params = {}
        if params_match:
            try:
                params = json.loads(params_match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse params JSON: {e}")
                # 尝试修复常见问题
                try:
                    # 处理单引号
                    fixed = params_match.group(1).replace("'", '"')
                    params = json.loads(fixed)
                except:
                    pass
        
        return ToolCall(
            name=tool_name,
            params=params,
            raw_text=response
        )
    
    def parse_final_answer(self, response: str) -> Optional[str]:
        """解析最终回答"""
        match = re.search(r'最终回答:\s*(.+?)(?:\n\n|$)', response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具 - 使用 core.tools 执行"""
        tool_name = tool_call.name
        params = tool_call.params
        
        # 先检查本地注册的工具
        if tool_name in self.tools:
            try:
                func = self.tools[tool_name]
                import asyncio
                if asyncio.iscoroutinefunction(func):
                    result = await func(**params)
                else:
                    result = func(**params)
                return ToolResult(success=True, result=result)
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return ToolResult(success=False, result=None, error=str(e))
        
        # 尝试使用 core.tools 执行
        try:
            from core.tools import ToolExecutor
            from core.tools.base import ToolContext
            
            context = ToolContext(user_id="system", permissions=["execute_destructive"])
            params_json = json.dumps(params, ensure_ascii=False)
            
            result_obj = await ToolExecutor.execute_async(tool_name, params_json, context)
            result_str = result_obj.to_llm_string() if hasattr(result_obj, "to_llm_string") else str(result_obj)
            
            return ToolResult(success=True, result=result_str)
        except Exception as e:
            logger.error(f"core.tools execution error: {e}")
            return ToolResult(success=False, result=None, error=str(e))
    
    def format_tool_result(self, result: ToolResult) -> str:
        """格式化工具结果"""
        if result.success:
            result_str = json.dumps(result.result, ensure_ascii=False, indent=2)
            return f"\n观察: {result_str}\n\n请根据观察结果继续。如果任务完成，请给出最终回答。"
        else:
            return f"\n观察: 工具执行失败 - {result.error}\n\n请尝试其他方法或给出最终回答。"
    
    async def run_react_loop(
        self,
        user_input: str,
        context: str = ""
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        运行 ReAct 循环
        
        Yields:
            {"type": "thinking", "content": "..."}
            {"type": "tool_call", "name": "...", "params": {...}}
            {"type": "tool_result", "name": "...", "result": ...}
            {"type": "answer", "content": "..."}
            {"type": "error", "content": "..."}
        """
        
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
        ]
        
        if context:
            messages.append({"role": "system", "content": f"背景信息:\n{context}"})
        
        messages.append({"role": "user", "content": user_input})
        
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # 调用 LLM
            try:
                response = await self._call_llm(messages)
            except Exception as e:
                yield {"type": "error", "content": str(e)}
                return
            
            # 检查是否有最终回答
            final_answer = self.parse_final_answer(response)
            if final_answer:
                yield {"type": "answer", "content": final_answer}
                return
            
            # 检查是否有工具调用
            tool_call = self.parse_tool_call(response)
            if tool_call:
                # 提取思考过程
                thinking_match = re.search(r'思考:\s*(.+?)(?=动作:|$)', response, re.DOTALL)
                if thinking_match:
                    yield {"type": "thinking", "content": thinking_match.group(1).strip()}
                
                yield {
                    "type": "tool_call",
                    "name": tool_call.name,
                    "params": tool_call.params
                }
                
                # 执行工具
                result = await self.execute_tool(tool_call)
                
                yield {
                    "type": "tool_result",
                    "name": tool_call.name,
                    "result": result.result if result.success else result.error,
                    "success": result.success
                }
                
                # 将结果添加到对话
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": self.format_tool_result(result)
                })
            else:
                # 没有工具调用也没有最终回答，把响应作为回答
                yield {"type": "answer", "content": response}
                return
        
        yield {"type": "error", "content": f"达到最大迭代次数 ({self.max_iterations})"}
    
    async def _call_llm(self, messages: List[Dict]) -> str:
        """调用 LLM"""
        # 转换为 prompt 格式 (llama-server completions API)
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt_parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                prompt_parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                prompt_parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        
        prompt_parts.append("<|im_start|>assistant\n")
        prompt = "\n".join(prompt_parts)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/completions",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "max_tokens": 1024,
                    "temperature": 0.3,
                    "stop": ["<|im_end|>", "<|im_start|>"]
                }
            )
            
            data = response.json()
            return data["choices"][0]["text"].strip()


# === 测试 ===

async def test_cpu_tool_handler():
    """测试 CPU 工具处理器"""
    
    # 模拟飞书工具
    async def feishu_send_message(user_id: str, message: str) -> Dict:
        """发送飞书消息给指定用户"""
        return {"success": True, "message_id": "msg_123", "sent_to": user_id}
    
    async def feishu_search_user(keyword: str) -> Dict:
        """搜索飞书用户"""
        return {"users": [{"id": "u_xinyue", "name": "xinyue"}]}
    
    handler = CPUToolHandler()
    handler.register_tool("feishu_send_message", feishu_send_message)
    handler.register_tool("feishu_search_user", feishu_search_user)
    
    print("System Prompt:")
    print(handler.get_system_prompt())
    print("\n" + "="*50 + "\n")
    
    # 测试工具调用
    async for event in handler.run_react_loop("发消息给 xinyue 说今天开会"):
        print(f"Event: {event['type']}")
        if event['type'] == 'thinking':
            print(f"  Thinking: {event['content'][:100]}...")
        elif event['type'] == 'tool_call':
            print(f"  Tool: {event['name']}, Params: {event['params']}")
        elif event['type'] == 'tool_result':
            print(f"  Result: {event['result']}")
        elif event['type'] == 'answer':
            print(f"  Answer: {event['content']}")
        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cpu_tool_handler())
