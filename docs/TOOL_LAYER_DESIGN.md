# Vulcan Brain Tool Layer 架构设计

> 版本: v1.0
> 日期: 2024-12-14
> 基于: Google Agent Whitepaper + MCP 最佳实践

---

## 0. 设计理念

- **标准化**: 所有工具通过 Pydantic Schema 定义输入/输出
- **原子化**: 工具功能尽可能精细 (如 `send_message` 而非 `manage_feishu`)
- **上下文感知**: 工具执行需要 `ToolContext` (User ID, Permissions)
- **安全优先**: 破坏性操作需标记并审批

---

## 1. 核心架构

```
core/tools/
├── base.py          # BaseTool, ToolContext, ToolResult
├── registry.py      # ToolRegistry + @register_tool
├── executor.py      # 统一执行器 + 安全检查
└── discovery.py     # 动态工具发现

tools/
├── system/          # read_file, write_file, list_dir
├── feishu/          # send_message, create_task, get_approval
├── analysis/        # python_interpreter, calculator
└── memory/          # remember, recall (已完成 v3)
```

---

## 2. 基础类定义

### 2.1 ToolContext (运行时上下文)

```python
from pydantic import BaseModel

class ToolContext(BaseModel):
    """运行时上下文，传递给每个工具"""
    user_id: str
    conversation_id: str
    working_directory: str  # 文件操作的根目录限制
    permissions: list[str]  # 用户权限列表
```

### 2.2 BaseTool (工具基类)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Type
from pydantic import BaseModel

class BaseTool(ABC):
    # 元数据
    name: str                      # 工具名称 (唯一)
    description: str               # 描述 (给 LLM 看)
    args_schema: Type[BaseModel]   # 输入参数 Schema
    
    # 安全标记 (来自 Google Whitepaper)
    is_destructive: bool = False   # 是否破坏性操作
    is_idempotent: bool = True     # 是否幂等
    
    # 分类标签
    domain: str = "system"         # system/feishu/analysis/memory
    tags: list[str] = []           # 额外标签

    @abstractmethod
    def run(self, params: BaseModel, context: ToolContext) -> Dict[str, Any]:
        """执行工具逻辑"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """生成 OpenAI Function Calling 格式的 Schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            }
        }
```

### 2.3 ToolResult (统一返回格式)

```python
class ToolResult(BaseModel):
    success: bool
    result: Any = None
    error: str = None
    
    def to_llm_string(self) -> str:
        """转换为 LLM 可读的字符串"""
        if self.success:
            return f"Tool Output: {self.result}"
        else:
            # 关键: 错误信息要有指导性
            return f"Tool Error: {self.error}. Please check your input and try again."
```

---

## 3. 工具注册机制

### 3.1 ToolRegistry (注册中心)

```python
class ToolRegistry:
    _tools: Dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool):
        if tool.name in cls._tools:
            raise ValueError(f"Tool {tool.name} already registered")
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> BaseTool:
        return cls._tools.get(name)

    @classmethod
    def list_all(cls) -> list[Dict]:
        return [t.get_schema() for t in cls._tools.values()]
    
    @classmethod
    def list_by_domain(cls, domain: str) -> list[Dict]:
        return [t.get_schema() for t in cls._tools.values() if t.domain == domain]
```

### 3.2 @register_tool 装饰器

```python
def register_tool(cls):
    """装饰器: 自动实例化并注册工具"""
    instance = cls()
    ToolRegistry.register(instance)
    return cls
```

---

## 4. 工具分类体系

| Domain | 描述 | 工具示例 | is_destructive |
|--------|------|----------|----------------|
| **system** | 文件/系统操作 | read_file, write_file, list_dir | write_file: True |
| **feishu** | 飞书集成 | send_message, create_task, get_approval | send_message: True |
| **analysis** | 计算/代码 | calculator, python_interpreter | python_interpreter: True |
| **memory** | 记忆系统 | remember, recall, forget | remember: True |
| **external** | 外部服务 | web_search | False |

---

## 5. 安全控制

### 5.1 破坏性操作检查

```python
def execute_tool(tool_name: str, args: dict, context: ToolContext) -> ToolResult:
    tool = ToolRegistry.get(tool_name)
    
    if not tool:
        return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

    # 破坏性操作需要权限
    if tool.is_destructive:
        if "execute_destructive" not in context.permissions:
            return ToolResult(
                success=False, 
                error="Permission denied: This action requires approval."
            )

    # 参数验证
    try:
        validated = tool.args_schema(**args)
    except Exception as e:
        return ToolResult(success=False, error=f"Invalid arguments: {e}")

    # 执行
    try:
        result = tool.run(validated, context)
        return ToolResult(success=True, result=result)
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

### 5.2 文件系统沙箱 (Roots)

```python
import os

def validate_path(file_path: str, root_dir: str) -> str:
    """确保路径在允许的范围内"""
    absolute = os.path.abspath(os.path.join(root_dir, file_path))
    if not absolute.startswith(os.path.abspath(root_dir)):
        raise PermissionError(f"Access denied: {file_path} is outside sandbox")
    return absolute
```

---

## 6. 错误处理规范

### 6.1 错误消息要求

根据 Google Whitepaper，错误消息应该:
- 说明发生了什么错误
- 指导如何修正
- 提供重试建议

**Bad:**
```
Error: 404
```

**Good:**
```
Error: User 'john@example.com' not found in Feishu. 
Please verify the email address or use open_id instead.
```

### 6.2 重试策略

| 错误类型 | 策略 |
|----------|------|
| 参数错误 | 不重试，返回详细校验信息 |
| API 限流 | 自动重试 1 次，间隔 5 秒 |
| 网络超时 | 自动重试 1 次，间隔 2 秒 |
| 权限错误 | 不重试，提示用户 |

---

## 7. 实现计划

### Phase 2.1: 基础架构 (P0)

- [ ] 创建 `core/tools/` 目录结构
- [ ] 实现 `BaseTool`, `ToolContext`, `ToolResult`
- [ ] 实现 `ToolRegistry` + `@register_tool`
- [ ] 实现 `execute_tool` 统一执行器
- [ ] 迁移现有工具到新架构

### Phase 2.2: 飞书工具 (P1)

- [ ] 重构 `feishu_tools.py` (43KB)
- [ ] 拆分为原子工具:
  - `feishu_send_message` (destructive)
  - `feishu_get_messages`
  - `feishu_create_task` (destructive)
  - `feishu_get_approvals`

### Phase 2.3: 文件工具 (P2)

- [ ] `read_file` (支持 txt/pdf/excel/word)
- [ ] `write_file` (destructive)
- [ ] `list_directory`
- [ ] 实现路径沙箱验证

### Phase 2.4: 代码执行 (P3)

- [ ] 完善 `python_interpreter`
- [ ] Docker 沙箱集成
- [ ] 执行超时控制

---

## 8. 工具实现示例

### 飞书发送消息

```python
from pydantic import BaseModel, Field
from core.tools.base import BaseTool, ToolContext
from core.tools.registry import register_tool

class SendMessageInput(BaseModel):
    receive_id: str = Field(..., description="收件人 open_id 或邮箱")
    receive_id_type: str = Field("open_id", description="ID类型: open_id/email")
    content: str = Field(..., description="消息内容")
    msg_type: str = Field("text", description="消息类型: text/post")

@register_tool
class FeishuSendMessage(BaseTool):
    name = "feishu_send_message"
    description = "发送飞书消息给指定用户"
    args_schema = SendMessageInput
    domain = "feishu"
    is_destructive = True

    def run(self, params: SendMessageInput, context: ToolContext):
        # 实际调用飞书 API
        from services.feishu_client import feishu_client
        
        result = feishu_client.send_message(
            receive_id=params.receive_id,
            receive_id_type=params.receive_id_type,
            content=params.content,
            msg_type=params.msg_type
        )
        
        return {"message_id": result.message_id, "status": "sent"}
```

---

## 附录: 现有工具清单

| 工具 | 文件 | 状态 | 迁移优先级 |
|------|------|------|------------|
| web_search | search_tools.py | 需迁移 | P1 |
| calculator | function_tools.py | 需迁移 | P2 |
| remember/recall | memory_tools.py | v3 完成 | - |
| code_executor | code_executor.py | 需重构 | P3 |
| feishu_* | feishu_tools.py | 需拆分 | P1 |
