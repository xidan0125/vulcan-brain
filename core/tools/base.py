"""
Vulcan Brain - Tool Layer Base Classes
基于 Google Agent Whitepaper 设计

v2: 增加 Gemini 建议的改进
- 异步支持 (arun)
- 路径安全检查 (sanitize_path)
- 输出截断 (防止 Context 溢出)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, List
from pydantic import BaseModel, Field
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)

# 输出最大长度 (防止撑爆 LLM Context)
MAX_OUTPUT_LENGTH = 4000


class ToolDomain(str, Enum):
    """工具分类域"""
    SYSTEM = "system"       # 文件/系统操作
    FEISHU = "feishu"       # 飞书集成
    ANALYSIS = "analysis"   # 计算/代码执行
    MEMORY = "memory"       # 记忆系统
    EXTERNAL = "external"   # 外部服务


class ToolContext(BaseModel):
    """
    运行时上下文，传递给每个工具

    类似 MCP 的 Request Context，包含执行工具所需的环境信息
    """
    user_id: str = "anonymous"
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    working_directory: str = "/tmp"  # 文件操作的根目录限制
    permissions: List[str] = Field(default_factory=list)  # 用户权限

    def has_permission(self, perm: str) -> bool:
        """检查是否有指定权限"""
        return perm in self.permissions or "admin" in self.permissions

    def sanitize_path(self, path: str) -> str:
        """
        安全检查：确保路径在工作目录内

        防止路径遍历攻击 (Path Traversal)

        Args:
            path: 相对或绝对路径

        Returns:
            安全的绝对路径

        Raises:
            PermissionError: 如果路径逃逸出工作目录
        """
        # 解析绝对路径
        abs_working = os.path.abspath(self.working_directory)

        # 如果是绝对路径，直接检查；否则相对于 working_directory
        if os.path.isabs(path):
            abs_target = os.path.abspath(path)
        else:
            abs_target = os.path.abspath(os.path.join(abs_working, path))

        # 检查是否逃逸 (使用 commonpath 避免符号链接绕过)
        try:
            common = os.path.commonpath([abs_working, abs_target])
            if common != abs_working:
                raise PermissionError(
                    f"Access denied: Path '{path}' is outside working directory '{self.working_directory}'"
                )
        except ValueError:
            # Windows 上不同驱动器会抛出 ValueError
            raise PermissionError(
                f"Access denied: Path '{path}' is on a different drive"
            )

        return abs_target


class ToolResult(BaseModel):
    """
    统一工具返回格式

    遵循 Google Whitepaper: 错误消息要有指导性
    """
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_llm_string(self, max_length: int = MAX_OUTPUT_LENGTH) -> str:
        """
        转换为 LLM 可读的字符串

        Args:
            max_length: 最大输出长度，超过截断
        """
        if self.success:
            if isinstance(self.result, dict):
                import json
                output = json.dumps(self.result, ensure_ascii=False, indent=2)
            else:
                output = str(self.result)
        else:
            output = f"Error: {self.error}"

        # 截断过长输出
        if len(output) > max_length:
            truncated = output[:max_length]
            output = f"{truncated}\n\n...(truncated, {len(output) - max_length} chars omitted)"

        return output

    @classmethod
    def ok(cls, result: Any) -> "ToolResult":
        """成功返回"""
        return cls(success=True, result=result)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        """失败返回"""
        return cls(success=False, error=error)


class BaseTool(ABC):
    """
    工具基类

    所有工具必须继承此类并实现 run 方法

    Attributes:
        name: 工具名称 (唯一标识)
        description: 工具描述 (给 LLM 看，要详细)
        args_schema: 输入参数 Pydantic Model
        domain: 工具分类
        is_destructive: 是否为破坏性操作 (需要权限)
        is_idempotent: 是否幂等
        tags: 额外标签 (用于筛选)
    """

    # 必须在子类中定义
    name: str
    description: str
    args_schema: Type[BaseModel]

    # 可选配置
    domain: ToolDomain = ToolDomain.SYSTEM
    is_destructive: bool = False
    is_idempotent: bool = True
    tags: List[str] = []

    @abstractmethod
    def run(self, params: BaseModel, context: ToolContext) -> ToolResult:
        """
        同步执行工具逻辑

        Args:
            params: 经过 Pydantic 验证的参数
            context: 运行时上下文

        Returns:
            ToolResult: 统一返回格式
        """
        pass

    async def arun(self, params: BaseModel, context: ToolContext) -> ToolResult:
        """
        异步执行工具逻辑

        默认实现：在线程池中运行同步 run，防止阻塞 Event Loop
        子类可以覆盖此方法实现真正的异步逻辑

        Args:
            params: 经过 Pydantic 验证的参数
            context: 运行时上下文

        Returns:
            ToolResult: 统一返回格式
        """
        import asyncio

        loop = asyncio.get_running_loop()
        # 使用 run_in_executor 包装同步调用
        return await loop.run_in_executor(None, self.run, params, context)

    def get_schema(self) -> Dict[str, Any]:
        """
        生成 OpenAI Function Calling 格式的 Schema

        这个格式同时兼容 OpenAI 和 vLLM
        """
        schema = self.args_schema.model_json_schema()

        # 清理 Pydantic v2 额外字段
        if "title" in schema:
            del schema["title"]

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            }
        }

    def validate_params(self, args: Dict[str, Any]) -> BaseModel:
        """验证并解析参数"""
        return self.args_schema(**args)

    def __repr__(self):
        return f"<Tool:{self.name} domain={self.domain.value} destructive={self.is_destructive}>"


class EmptyInput(BaseModel):
    """空输入参数 (用于无参数工具)"""
    pass


def clean_json_string(s: str) -> str:
    """
    清理 JSON 字符串

    LLM 经常返回带 Markdown 代码块的 JSON，这里做清理
    """
    import re

    # 去除 ```json ... ``` 包裹
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', s, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果不是 Markdown 格式，直接返回
    return s.strip()
