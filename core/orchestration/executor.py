"""
Vulcan Nexus - Agent Executor
核心编排器，协调 Router、Agent、Briefcase
"""

import asyncio
import httpx
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, AsyncIterator, Any, Callable
from enum import Enum
import logging

from .router import IntentRouter, RoutingDecision, Intent, ModelTier, get_tools_for_intent
from .briefcase import Briefcase, BriefcaseManager, Artifact, ArtifactType
from .session_context import SessionContext, AgentType
from .cpu_tool_handler import CPUToolHandler
from .thinking_parser import ThinkingStreamParser, clean_response

logger = logging.getLogger(__name__)


# === Agent 配置 ===

@dataclass
class AgentConfig:
    """Agent 配置"""
    id: str
    name: str
    agent_type: AgentType  # conversational / task
    model_tier: ModelTier
    system_prompt: str
    tools: List[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2048
    
    @property
    def model_endpoint(self) -> str:
        """获取模型端点"""
        if self.model_tier == ModelTier.CPU:
            return "http://localhost:8002/v1"
        elif self.model_tier == ModelTier.GPU:
            return "http://localhost:8000/v1"
        else:
            return "gemini"  # Gemini 特殊处理


# 预定义 Agent 配置
AGENT_CONFIGS: Dict[str, AgentConfig] = {
    # 对话型 Agent
    "general": AgentConfig(
        id="general",
        name="通用助手",
        agent_type=AgentType.CONVERSATIONAL,
        model_tier=ModelTier.GPU,
        system_prompt="你是 Vulcan Brain，一个智能助手。请简洁、专业地回答问题。",
        tools=[],
        temperature=0.7
    ),
    
    # 任务型 Agent
    "feishu": AgentConfig(
        id="feishu",
        name="飞书助手",
        agent_type=AgentType.TASK,
        model_tier=ModelTier.CPU,  # 飞书用 CPU，快
        system_prompt="""你是飞书消息助手。你的任务是帮用户发送飞书消息。

规则:
1. 先确认收件人 (用 feishu_search_user 搜索)
2. 然后发送消息 (用 feishu_send_message)
3. 完成后报告结果""",
        tools=["feishu_send_message", "feishu_search_user", "feishu_create_chat"],
        temperature=0.3,
        max_tokens=1024
    ),
    
    "data": AgentConfig(
        id="data",
        name="数据分析师",
        agent_type=AgentType.TASK,
        model_tier=ModelTier.GPU,  # 数据分析用 GPU
        system_prompt="""你是数据分析专家。帮用户查询和分析数据。

可用工具:
- sql_query: 执行 SQL 查询
- python_exec: 执行 Python 代码进行分析

请先理解用户需求，然后查询数据，最后给出分析结论。""",
        tools=["sql_query", "python_exec", "rag_search"],
        temperature=0.5,
        max_tokens=4096
    ),
    
    "finance": AgentConfig(
        id="finance",
        name="财务助手",
        agent_type=AgentType.TASK,
        model_tier=ModelTier.GPU,
        system_prompt="你是财务分析助手。帮用户处理财务相关查询和报告。",
        tools=["sql_query", "finance_report"],
        temperature=0.3,
        max_tokens=2048
    ),
}


# === Event Types ===

class EventType(str, Enum):
    """事件类型"""
    ROUTING = "routing"       # 路由决策
    THINKING = "thinking"     # 思考过程
    TOKEN = "token"           # 内容 token
    TOOL_CALL = "tool_call"   # 工具调用
    TOOL_RESULT = "tool_result"  # 工具结果
    ANSWER = "answer"         # 最终回答
    ERROR = "error"           # 错误
    DONE = "done"             # 完成


@dataclass
class StreamEvent:
    """流式事件"""
    type: EventType
    content: Any = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "content": self.content,
            **self.metadata
        }


# === Agent Executor ===

class AgentExecutor:
    """
    Vulcan Nexus 核心执行器
    
    职责:
    1. 意图路由 (Router)
    2. Agent 选择和执行
    3. 上下文管理 (对话型/任务型)
    4. Briefcase 协议
    """
    
    def __init__(
        self,
        tool_registry: Dict[str, Callable] = None
    ):
        self.router = IntentRouter()
        self.session = SessionContext()
        self.briefcase_manager = BriefcaseManager()
        self.thinking_parser = ThinkingStreamParser()
        
        # 工具注册
        self.tool_registry = tool_registry or {}
        
        # CPU 工具处理器 (用于无原生 function calling 的模型)
        self.cpu_handler = CPUToolHandler(tools=self.tool_registry)
    
    def register_tool(self, name: str, func: Callable, description: str = None):
        """注册工具"""
        self.tool_registry[name] = func
        self.cpu_handler.register_tool(name, func, description)
    
    async def process(
        self,
        user_input: str,
        session_id: str = None
    ) -> AsyncIterator[StreamEvent]:
        """
        处理用户输入
        
        流程:
        1. Router 意图分类
        2. 选择 Agent
        3. 根据 Agent 类型执行:
           - 对话型: 共享历史
           - 任务型: Briefcase 隔离
        4. 更新会话状态
        """
        
        # 1. 路由决策
        decision = await self.router.route(user_input)
        
        yield StreamEvent(
            type=EventType.ROUTING,
            content=decision.intent.value,
            metadata={
                "model_tier": decision.model_tier.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "use_tools": decision.use_tools
            }
        )
        
        # 2. 获取 Agent 配置
        agent_config = self._get_agent_config(decision)
        
        # 3. 记录用户消息
        self.session.add_message("user", user_input)
        
        # 4. 根据 Agent 类型执行
        full_response = ""
        
        try:
            if agent_config.agent_type == AgentType.CONVERSATIONAL:
                # 对话型: 共享历史
                async for event in self._run_conversational(user_input, agent_config, decision):
                    if event.type == EventType.TOKEN:
                        full_response += event.content or ""
                    yield event
            else:
                # 任务型: Briefcase 隔离
                async for event in self._run_task_agent(user_input, agent_config, decision):
                    if event.type in [EventType.TOKEN, EventType.ANSWER]:
                        full_response += event.content or ""
                    yield event
        except Exception as e:
            logger.exception("Agent execution failed")
            yield StreamEvent(type=EventType.ERROR, content=str(e))
        
        # 5. 记录助手回复
        if full_response:
            self.session.add_message(
                "assistant",
                full_response,
                agent_type=agent_config.id,
                is_task_result=(agent_config.agent_type == AgentType.TASK)
            )
        
        self.session.record_agent_execution(agent_config.id)
        
        yield StreamEvent(type=EventType.DONE)
    
    def _get_agent_config(self, decision: RoutingDecision) -> AgentConfig:
        """根据路由决策获取 Agent 配置"""
        
        intent_to_agent = {
            Intent.CHAT: "general",
            Intent.FEISHU: "feishu",
            Intent.DATA: "data",
            Intent.FINANCE: "finance",
            Intent.CODE: "general",  # 暂时用通用
            Intent.WEB_SEARCH: "general",  # Gemini 处理
        }
        
        agent_id = intent_to_agent.get(decision.intent, "general")
        return AGENT_CONFIGS.get(agent_id, AGENT_CONFIGS["general"])
    
    async def _run_conversational(
        self,
        user_input: str,
        config: AgentConfig,
        decision: RoutingDecision
    ) -> AsyncIterator[StreamEvent]:
        """运行对话型 Agent"""
        
        messages = self.session.get_messages_for_llm()
        
        # 添加 system prompt
        if config.system_prompt:
            messages.insert(0, {"role": "system", "content": config.system_prompt})
        
        # 调用模型
        if config.model_tier == ModelTier.GPU:
            async for event in self._call_gpu_stream(messages, config, decision):
                yield event
        elif config.model_tier == ModelTier.CPU:
            async for event in self._call_cpu_stream(messages, config, decision):
                yield event
        else:
            # Gemini - 暂不实现流式
            yield StreamEvent(type=EventType.ERROR, content="Gemini not implemented in executor")
    
    async def _run_task_agent(
        self,
        user_input: str,
        config: AgentConfig,
        decision: RoutingDecision
    ) -> AsyncIterator[StreamEvent]:
        """运行任务型 Agent (Briefcase 模式)"""
        
        # 创建 Briefcase
        briefcase = self.briefcase_manager.create(
            task=user_input,
            session_summary=self.session.session_summary
        )
        
        # 构建 Agent 输入
        agent_input = briefcase.build_agent_input()
        
        messages = [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": agent_input}
        ]
        
        artifacts = []
        full_response = ""
        
        # 根据模型层级选择执行方式
        if config.model_tier == ModelTier.CPU:
            # CPU: 使用 ReAct 工具调用
            async for event in self.cpu_handler.run_react_loop(agent_input, context=config.system_prompt):
                if event["type"] == "thinking":
                    yield StreamEvent(type=EventType.THINKING, content=event["content"])
                elif event["type"] == "tool_call":
                    yield StreamEvent(
                        type=EventType.TOOL_CALL,
                        content=event["name"],
                        metadata={"params": event["params"]}
                    )
                elif event["type"] == "tool_result":
                    yield StreamEvent(
                        type=EventType.TOOL_RESULT,
                        content=event["result"],
                        metadata={"name": event["name"], "success": event.get("success", True)}
                    )
                    # 记录工件
                    artifacts.append(Artifact(
                        type=ArtifactType.MESSAGE_SENT if "send" in event["name"] else ArtifactType.QUERY_RESULT,
                        content=event["result"],
                        metadata={"tool": event["name"]}
                    ))
                elif event["type"] == "answer":
                    full_response = event["content"]
                    yield StreamEvent(type=EventType.ANSWER, content=event["content"])
                elif event["type"] == "error":
                    yield StreamEvent(type=EventType.ERROR, content=event["content"])
        else:
            # GPU: 使用原生工具调用
            async for event in self._call_gpu_with_tools(messages, config, decision):
                if event.type == EventType.TOKEN:
                    full_response += event.content or ""
                yield event
        
        # 封装 Briefcase
        self.briefcase_manager.finalize(
            briefcase=briefcase,
            final_answer=full_response,
            artifacts=artifacts,
            agent_id=config.id
        )
    
    async def _call_gpu_stream(
        self,
        messages: List[Dict],
        config: AgentConfig,
        decision: RoutingDecision
    ) -> AsyncIterator[StreamEvent]:
        """调用 GPU 模型 (流式)"""
        
        self.thinking_parser.reset()
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": "auto",  # vLLM 自动选择
                "messages": messages,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "stream": True
            }
            
            # 工具注入
            if decision.use_tools:
                tools = self._get_tool_schemas(decision.intent)
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
            
            async with client.stream(
                "POST",
                f"{config.model_endpoint}/chat/completions",
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(data)
                        parsed = self.thinking_parser.parse_chunk(chunk)
                        
                        if parsed:
                            if parsed.thinking:
                                yield StreamEvent(type=EventType.THINKING, content=parsed.thinking)
                            if parsed.content:
                                yield StreamEvent(type=EventType.TOKEN, content=parsed.content)
                            if parsed.tool_calls:
                                for tc in parsed.tool_calls:
                                    yield StreamEvent(
                                        type=EventType.TOOL_CALL,
                                        content=tc.get("function", {}).get("name"),
                                        metadata={"tool_call": tc}
                                    )
                    except json.JSONDecodeError:
                        continue
    
    async def _call_gpu_with_tools(
        self,
        messages: List[Dict],
        config: AgentConfig,
        decision: RoutingDecision
    ) -> AsyncIterator[StreamEvent]:
        """调用 GPU 模型并处理工具调用"""
        
        tools = self._get_tool_schemas(decision.intent)
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": "auto",
                    "messages": messages,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "stream": False
                }
                
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                
                response = await client.post(
                    f"{config.model_endpoint}/chat/completions",
                    json=payload
                )
                
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                # 检查工具调用
                tool_calls = message.get("tool_calls", [])
                
                if tool_calls:
                    # 有工具调用
                    content = message.get("content", "")
                    if content:
                        yield StreamEvent(type=EventType.THINKING, content=content)
                    
                    messages.append(message)
                    
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        tool_name = func.get("name")
                        tool_args = func.get("arguments", "{}")
                        
                        yield StreamEvent(
                            type=EventType.TOOL_CALL,
                            content=tool_name,
                            metadata={"arguments": tool_args}
                        )
                        
                        # 执行工具
                        result = await self._execute_tool(tool_name, tool_args)
                        
                        yield StreamEvent(
                            type=EventType.TOOL_RESULT,
                            content=result,
                            metadata={"name": tool_name}
                        )
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "name": tool_name,
                            "content": str(result)
                        })
                else:
                    # 无工具调用，返回内容
                    content = message.get("content", "")
                    content = clean_response(content)
                    
                    yield StreamEvent(type=EventType.TOKEN, content=content)
                    return
        
        yield StreamEvent(type=EventType.ERROR, content="达到最大工具调用轮数")
    
    async def _call_cpu_stream(
        self,
        messages: List[Dict],
        config: AgentConfig,
        decision: RoutingDecision
    ) -> AsyncIterator[StreamEvent]:
        """调用 CPU 模型 (流式)"""
        
        # CPU 简单对话，不带工具
        prompt = self._messages_to_prompt(messages)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": "qwen3-8b",
                "prompt": prompt,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "stream": True,
                "stop": ["<|im_end|>"]
            }
            
            async with client.stream(
                "POST",
                f"{config.model_endpoint}/completions",
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(data)
                        text = chunk["choices"][0].get("text", "")
                        if text:
                            yield StreamEvent(type=EventType.TOKEN, content=text)
                    except:
                        continue
    
    def _messages_to_prompt(self, messages: List[Dict]) -> str:
        """转换消息为 prompt"""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)
    
    def _get_tool_schemas(self, intent: Intent) -> List[Dict]:
        """获取工具 schema"""
        tool_names = get_tools_for_intent(intent)
        
        # 从 core.tools 获取 schema
        try:
            from core.tools import get_tool_schemas
            all_schemas = get_tool_schemas()
            return [s for s in all_schemas if s.get("function", {}).get("name") in tool_names]
        except:
            return []
    
    async def _execute_tool(self, name: str, args: str) -> Any:
        """执行工具"""
        if name in self.tool_registry:
            try:
                params = json.loads(args) if isinstance(args, str) else args
                func = self.tool_registry[name]
                
                if asyncio.iscoroutinefunction(func):
                    return await func(**params)
                else:
                    return func(**params)
            except Exception as e:
                return f"Error: {str(e)}"
        else:
            # 尝试从 core.tools 执行
            try:
                from core.tools import execute_tool
                from core.tools.base import ToolContext
                context = ToolContext(user_id="system", permissions=["execute_destructive"])
                result = await execute_tool(name, args, context)
                return result.to_llm_string() if hasattr(result, 'to_llm_string') else str(result)
            except Exception as e:
                return f"Error: {str(e)}"


# === 便捷函数 ===

_executor: Optional[AgentExecutor] = None

def get_executor() -> AgentExecutor:
    """获取全局执行器"""
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor
