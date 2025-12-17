"""
Vulcan Nexus - Multi-Agent Orchestration Layer

核心组件:
- IntentRouter: 意图路由 (规则 + LLM)
- AgentExecutor: Agent 执行器
- BriefcaseManager: Briefcase 协议管理
- SessionContext: 会话上下文管理
- ThinkingStreamParser: GPU 输出解析
- CPUToolHandler: CPU ReAct 工具调用
"""

from .router import (
    IntentRouter,
    RoutingDecision,
    Intent,
    ModelTier,
    get_tools_for_intent
)

from .briefcase import (
    Briefcase,
    BriefcaseManager,
    Artifact,
    ArtifactType
)

from .session_context import (
    SessionContext,
    AgentType,
    Message
)

from .thinking_parser import (
    ThinkingStreamParser,
    ParsedChunk,
    clean_response
)

from .cpu_tool_handler import (
    CPUToolHandler,
    ToolCall,
    ToolResult
)

from .executor import (
    AgentExecutor,
    AgentConfig,
    AGENT_CONFIGS,
    StreamEvent,
    EventType,
    get_executor
)

__all__ = [
    # Router
    "IntentRouter",
    "RoutingDecision",
    "Intent",
    "ModelTier",
    "get_tools_for_intent",
    
    # Briefcase
    "Briefcase",
    "BriefcaseManager",
    "Artifact",
    "ArtifactType",
    
    # Session
    "SessionContext",
    "AgentType",
    "Message",
    
    # Parsers
    "ThinkingStreamParser",
    "ParsedChunk",
    "clean_response",
    
    # CPU Tools
    "CPUToolHandler",
    "ToolCall",
    "ToolResult",
    
    # Executor
    "AgentExecutor",
    "AgentConfig",
    "AGENT_CONFIGS",
    "StreamEvent",
    "EventType",
    "get_executor",
]
