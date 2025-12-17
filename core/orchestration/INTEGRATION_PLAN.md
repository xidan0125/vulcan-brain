# Vulcan Nexus 集成方案

> 日期: 2025-12-17
> 目标: 将 Multi-Agent 编排层集成到现有聊天系统

---

## 一、现有系统分析

### 1.1 核心组件 (保留不动)

| 组件 | 文件 | 功能 | 集成方式 |
|------|------|------|----------|
| SessionManager | services/session_manager.py | 会话 CRUD + 持久化 | **保留** |
| ContextManager | services/context_manager.py | Token 预算 + 滑动窗口 | **保留** |
| MemoryService | services/memory_service.py | 三层记忆系统 | **保留** |
| ToolExecutor | core/tools/ | 工具注册和执行 | **保留** |

### 1.2 需要修改的组件

| 组件 | 修改点 |
|------|--------|
| chat_router.py | 加入 IntentRouter，工具物理隔离 |
| llm_client.py | 已支持 CPU/GPU，无需大改 |

### 1.3 前端 SSE 事件 (已支持)

```typescript
type: 'session' | 'thinking' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error'
```

**新增事件**: `routing` - 显示路由决策

---

## 二、集成点详解

### 2.1 chat_router.py 修改

**修改前流程:**
```
用户输入 → 构建上下文 → 调用 LLM (带所有工具) → 返回
```

**修改后流程:**
```
用户输入 
    ↓
1. IntentRouter.route() ← 新增
    ↓
2. 发送 routing 事件 ← 新增
    ↓
3. 构建上下文 (保留)
    ↓
4. 根据 intent 注入工具 ← 修改 (物理隔离)
    ↓
5. 选择模型 (CPU/GPU) ← 新增
    ↓
6. 调用 LLM
    ↓
7. 返回
```

### 2.2 工具物理隔离

```python
# 当前: 所有工具都注入
tools = get_tool_schemas()  # 返回所有工具

# 修改后: 按意图注入
from core.orchestration import get_tools_for_intent

decision = await router.route(user_input)

if decision.use_tools:
    tools = get_tools_for_intent(decision.intent)  # 只返回相关工具
else:
    tools = []  # CHAT 模式不给任何工具!
```

### 2.3 模型选择

```python
# 根据路由决策选择模型
if decision.model_tier == ModelTier.CPU:
    # 简单任务 (飞书发消息) → CPU 8B
    base_url = "http://localhost:8002/v1"
else:
    # 复杂任务 (数据分析) → GPU 30B
    base_url = "http://localhost:8000/v1"
```

---

## 三、代码修改清单

### 3.1 chat_router.py

```python
# === 新增导入 ===
from core.orchestration import (
    IntentRouter, 
    RoutingDecision,
    get_tools_for_intent,
    ModelTier
)

# === 新增全局 Router ===
_router = None
def get_router():
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router

# === 修改 react_chat_stream_with_history ===

async def react_chat_stream_with_history(
    request: ChatRequest,
    history: List[dict],
    user_input: str  # 新增参数
) -> AsyncGenerator[dict, None]:
    
    # Step 0: 路由决策 (新增)
    router = get_router()
    decision = await router.route(user_input)
    
    # 发送 routing 事件 (新增)
    yield {
        "type": "routing",
        "intent": decision.intent.value,
        "model": decision.model_tier.value,
        "use_tools": decision.use_tools
    }
    
    # Step 1: 工具物理隔离 (修改)
    if decision.use_tools:
        tools = filter_tools_by_intent(decision.intent)
    else:
        tools = []  # CHAT 不给工具!
    
    # Step 2: 选择模型端点 (新增)
    if decision.model_tier == ModelTier.CPU:
        base_url = "http://localhost:8002/v1"
    else:
        base_url = QWEN3_BASE_URL
    
    # Step 3: 后续流程保持不变...
```

### 3.2 新增辅助函数

```python
def filter_tools_by_intent(intent) -> List[dict]:
    """根据意图过滤工具 schema"""
    from core.orchestration import get_tools_for_intent
    from core.tools import get_tool_schemas
    
    allowed_tool_names = get_tools_for_intent(intent)
    all_schemas = get_tool_schemas()
    
    return [
        s for s in all_schemas 
        if s.get("function", {}).get("name") in allowed_tool_names
    ]
```

---

## 四、前端适配 (可选)

### 4.1 显示路由信息

```typescript
// unifiedChatApi.ts - 更新 StreamEvent 类型
export interface StreamEvent {
  type: 'session' | 'routing' | 'thinking' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error';
  // routing 事件专用字段
  intent?: string;
  model?: string;
  use_tools?: boolean;
  // ...
}

// 前端处理
if (event.type === 'routing') {
  console.log(`[路由] 意图: ${event.intent}, 模型: ${event.model}`);
  // 可以显示一个小提示: "正在使用飞书助手..."
}
```

---

## 五、测试计划

### 5.1 Sticky Tool 测试

```
1. 发送: "发消息给 xinyue 说今天开会"
   - 预期: intent=feishu, 调用 feishu_send_message
   
2. 发送: "前端有什么推荐"
   - 预期: intent=chat, use_tools=false
   - 关键: 不应该调用任何工具!
```

### 5.2 模型切换测试

```
1. 发送: "你好"
   - 预期: CPU 模型 (快速响应)
   
2. 发送: "分析一下公司的销售数据"
   - 预期: GPU 模型 (深度思考)
```

### 5.3 上下文保持测试

```
1. 发送: "介绍一下 React"
2. 发送: "发给 xinyue"  (切换到飞书)
3. 发送: "继续聊 Vue"   (切换回对话)
   - 预期: 上下文保持，知道之前讨论了 React
```

---

## 六、风险控制

### 6.1 回滚方案

```python
# 在 chat_router.py 顶部添加开关
ENABLE_ORCHESTRATION = os.getenv("ENABLE_ORCHESTRATION", "true") == "true"

async def react_chat_stream_with_history(...):
    if ENABLE_ORCHESTRATION:
        # 新流程
        decision = await router.route(user_input)
        ...
    else:
        # 旧流程 (回滚)
        tools = get_tool_schemas()
        ...
```

### 6.2 监控指标

```python
# 记录路由决策到日志
logger.info(f"[Routing] input='{user_input[:50]}' intent={decision.intent} model={decision.model_tier}")
```

---

## 七、实施步骤

### Phase 1: 最小可行集成 (今天)

1. [x] 创建 core/orchestration/ 模块
2. [ ] 修改 chat_router.py 加入 IntentRouter
3. [ ] 实现工具物理隔离
4. [ ] 测试 Sticky Tool 场景

### Phase 2: 模型切换 (明天)

1. [ ] 实现 CPU/GPU 动态切换
2. [ ] 测试简单任务走 CPU
3. [ ] 测试复杂任务走 GPU

### Phase 3: 完善 (后续)

1. [ ] 前端显示路由信息
2. [ ] 任务型 Agent 的 Briefcase 模式
3. [ ] 性能优化

---

*集成方案 v1.0 - 2025-12-17*
