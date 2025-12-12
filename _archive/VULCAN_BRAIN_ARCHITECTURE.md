# Vulcan Brain 系统架构文档
> 基于 2024-11-27 实际代码分析，代码为准

## 1. 系统概述

Vulcan Brain 是一个基于 CodeAct 范式的 AI Agent 系统，核心特点：
- **CodeAct 执行**：模型生成 Python 代码，由 Kernel 执行
- **LOD 动态加载**：根据查询按需加载工具，减少 Context 压力
- **三层记忆**：宪法(Constitution) + 对齐记忆(Alignment) + 用户记忆(Memory)

## 2. 五层汉堡架构

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Frontend (vulcan-ui/)                 │
│  - Next.js 15 + TailwindCSS                     │
│  - 点火仪式、灵魂面板、对话界面                    │
│  - 访问: dash.vsg-brain.com                     │
├─────────────────────────────────────────────────┤
│  Layer 2: API Server (api_server.py)            │
│  - FastAPI + Uvicorn                            │
│  - SSE 流式输出                                  │
│  - 端口: 8001, 访问: api.vsg-brain.com          │
├─────────────────────────────────────────────────┤
│  Layer 3: Kernel (kernel_codeact.py)            │
│  - VulcanCodeActKernel 类                       │
│  - 代码提取 + 执行 + 结果反馈循环                 │
│  - OptimizedStreamingThinkFilter 过滤器          │
├─────────────────────────────────────────────────┤
│  Layer 4: Tools & Libs                          │
│  - tools/: 工具函数 (FunctionTool 封装)          │
│  - vulcan_libs/: 核心库 (Memory, RAG, Alignment) │
├─────────────────────────────────────────────────┤
│  Layer 5: Infrastructure                        │
│  - Ollama (qwen3-thinking 模型)                 │
│  - MongoDB (记忆存储)                            │
│  - AContext (6容器会话管理)                      │
│  - SearXNG (联网搜索)                            │
└─────────────────────────────────────────────────┘
```

## 3. 核心文件清单

### 3.1 根目录 (~/vulcan-brain/ 或 ~/vulcan_brain_v2/)

| 文件 | 职责 |
|------|------|
| `api_server.py` | 主 API 服务器，所有端点定义 |
| `kernel_codeact.py` | CodeAct 执行引擎，核心循环 |
| `config.py` | 全局配置 (模型名、端口等) |
| `auth_api.py` | JWT 认证系统 |
| `chat_api.py` | 对话历史 API |
| `soul_api.py` | 灵魂系统 API |
| `acontext_integration.py` | AContext 会话记忆集成 |
| `agent_prompts.py` | Agent 角色 Prompt 定义 |
| `mcp_server.py` | MCP 协议支持 |

### 3.2 tools/ 目录 - 工具函数

| 文件 | 工具 | 说明 |
|------|------|------|
| `function_tools.py` | `get_time_tool` | 获取当前时间 |
| `memory_tools.py` | `remember_tool`, `recall_tool`, `forget_tool` | 用户记忆CRUD |
| `rag_tools.py` | `add_document_tool`, `search_knowledge_tool` | 知识库管理 |
| `alignment_tools.py` | `record_boss_feedback_tool`, `get_alignment_summary_tool` | Boss反馈对齐 |
| `boss_insight_tool.py` | `save_boss_insight_tool` | 快速记录Boss观点 |
| `code_executor.py` | `create_code_execution_tool()` | 安全代码沙箱 |
| `__init__.py` | 导出所有工具函数 | CodeAct 执行环境需要 |

### 3.3 vulcan_libs/ 目录 - 核心库

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `memory.py` | `VulcanMemoryV2`, `remember()`, `recall()`, `forget()` | MongoDB 记忆管理 |
| `alignment.py` | `AlignmentManager`, `record_feedback()`, `load_constitution()` | 价值观对齐系统 |
| `rag.py` | `VulcanRAG`, `get_rag_instance()` | 双索引知识库 (Vector + Summary) |
| `registry.py` | `ToolRegistry`, `ToolPackage` | 工具注册表 (LOD核心) |
| `tool_retriever.py` | `ToolRetriever` | 工具语义检索 |
| `store.py` | 数据存储抽象 | |
| `singleton.py` | 单例模式工具 | |

## 4. API 端点清单

### 4.1 核心对话
- `POST /api/chat/stream` - SSE 流式对话 (主要入口)

### 4.2 系统状态
- `GET /api/health` - 健康检查
- `GET /api/system/status` - GPU/VRAM/性能指标

### 4.3 记忆系统
- `GET /api/memory/profile` - 用户画像
- `GET /api/memory/timeline` - 对话历史

### 4.4 知识库
- `POST /api/knowledge/upload` - 上传文档
- `GET /api/knowledge/list` - 列出文档
- `DELETE /api/knowledge/{id}` - 删除文档

### 4.5 灵魂系统
- `GET /api/soul/config` - 获取灵魂配置
- `POST /api/soul/update` - 更新配置
- `POST /api/soul/reset` - 重置默认

### 4.6 Agent 系统
- `GET /api/agents/list` - 列出所有 Agent
- `POST /api/agents/{type}/chat` - Agent 对话
- `POST /api/agents/{type}/chat/stream` - Agent 流式对话
- `POST /api/agents/{type}/chat/lod` - LOD Kernel 对话
- `POST /api/agents/{type}/chat/lod/stream` - LOD 流式对话

### 4.7 代码执行
- `POST /api/execute` - 代码沙箱执行

### 4.8 认证
- `POST /api/auth/login` - 登录 (admin/vulcan2024)
- `POST /api/auth/logout` - 登出
- `GET /api/auth/me` - 当前用户

## 5. 工具加载机制

### 5.1 api_server.py 中的工具注册

```python
# 核心包（常驻内存）
registry.register(ToolPackage(
    name='core_tools',
    tools=[get_time_tool, remember_tool, recall_tool, forget_tool],
    is_core=True
))

# RAG 扩展包
registry.register(ToolPackage(
    name='rag_pkg',
    tools=[add_document_tool, search_knowledge_tool],
    is_core=False
))

# 对齐扩展包
registry.register(ToolPackage(
    name='alignment_pkg',
    tools=[record_boss_feedback_tool, get_alignment_summary_tool, save_boss_insight_tool],
    is_core=False
))

# 代码执行扩展包
registry.register(ToolPackage(
    name='code_execution_pkg',
    tools=[create_code_execution_tool()],
    is_core=False
))
```

### 5.2 CodeAct 执行环境

`kernel_codeact.py` 的 `_execute_code()` 方法会将工具函数注入执行环境：
```python
self.execution_env: Dict[str, Callable] = self._build_execution_env(self.active_tools)
```

`tools/__init__.py` 必须正确导出函数名，供 exec() 调用。

## 6. 基础设施服务

### 6.1 必须运行的服务

| 服务 | 端口 | 检查命令 |
|------|------|---------|
| Ollama | 11434 | `curl localhost:11434/api/tags` |
| MongoDB | 27017 | `mongosh --eval "db.stats()"` |
| SearXNG | 8080 | `curl localhost:8080/search?q=test&format=json` |
| AContext API | 8000 | `curl localhost:8000/health` |
| Backend API | 8001 | `curl localhost:8001/api/health` |
| Frontend | 3000 | `curl localhost:3000` |

### 6.2 Docker 容器 (AContext)

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# 应该看到:
# acontext-server-api
# acontext-server-core
# acontext-server-pg
# acontext-server-redis
# acontext-server-rabbitmq
# acontext-server-seaweedfs
```

## 7. 配置文件

### 7.1 config.py
```python
LLM_MODEL_NAME = "qwen3-thinking"
LLM_BASE_URL = "http://localhost:11434"
SYSTEM_TEMPERATURE = 0.1
MAX_ITERATIONS = 20
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
```

### 7.2 关键配置文件
- `soul_config.json` - 灵魂配置 (System Prompt, 参数)
- `alignment_memory.json` - Boss 反馈记录
- `boss_constitution.yaml` - 静态价值观宪法
- `user_profile.json` - 用户画像

## 8. 数据存储路径

| 数据类型 | 开发环境 | 生产环境 (建议) |
|----------|----------|-----------------|
| MongoDB | Docker Volume | /data/fast/mongo |
| RAG 索引 | ./rag_storage | /data/fast/rag |
| KB 文档 | ./kb_storage | /data/storage/kb |
| AContext PG | ~/acontext_server/acontext_data/pg | /data/fast/acontext/pg |
| AContext SeaweedFS | ~/acontext_server/acontext_data/seaweedfs | /data/fast/acontext/seaweedfs |

---

**文档生成时间**: 2024-11-28
**基于代码版本**: 开发环境最新代码
