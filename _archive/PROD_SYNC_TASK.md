# 生产环境同步任务说明
> 给本地 Agent 的执行指南

## 背景

远程 Agent (MacBook) 无法直接 SSH 到生产服务器 192.168.10.33，需要本地 Agent 协助完成以下任务。

## 环境信息

| 项目 | 开发环境 | 生产环境 |
|------|----------|----------|
| 主机 | 100.79.150.62 (Tailscale) | 192.168.10.33 (内网) |
| 用户 | xinyueyu | xinyueyu |
| 项目路径 | ~/vulcan_brain_v2/ | ~/vulcan-brain/ |
| 前端域名 | - | dash.vsg-brain.com |
| API域名 | - | api.vsg-brain.com |
| 密码 | - | 373901045 |

## 紧急任务 1: 重启后端

之前修改了 `tools/__init__.py` 添加了 web_search 导出，需要重启生效：

```bash
cd ~/vulcan-brain
pkill -9 -f "uvicorn api_server"
source venv/bin/activate
nohup python -m uvicorn api_server:app --host 0.0.0.0 --port 8001 > /tmp/vulcan_api.log 2>&1 &
sleep 3
pgrep -f "uvicorn api_server" && echo "Backend started" || echo "FAILED"
```

## 紧急任务 2: 检查并补全缺失文件

### 2.1 首先检查生产环境现有文件

```bash
echo "=== tools/ 目录 ==="
ls -la ~/vulcan-brain/tools/

echo "=== vulcan_libs/ 目录 ==="
ls -la ~/vulcan-brain/vulcan_libs/

echo "=== 根目录关键文件 ==="
ls -la ~/vulcan-brain/*.py | head -20
```

### 2.2 开发环境应有的 tools/ 文件清单

| 文件 | 必须存在 | 说明 |
|------|---------|------|
| `__init__.py` | ✅ | 导出所有工具函数供 CodeAct 使用 |
| `function_tools.py` | ✅ | get_time_tool |
| `memory_tools.py` | ✅ | remember/recall/forget |
| `rag_tools.py` | ✅ | 知识库工具 |
| `alignment_tools.py` | ✅ | Boss反馈对齐 |
| `boss_insight_tool.py` | ✅ | 快速记录Boss观点 |
| `code_executor.py` | ✅ | 代码执行沙箱 |
| `search_tools.py` | ✅ | 联网搜索 (新增) |

### 2.3 开发环境应有的 vulcan_libs/ 文件清单

| 文件 | 必须存在 | 说明 |
|------|---------|------|
| `__init__.py` | ✅ | |
| `memory.py` | ✅ | MongoDB 记忆管理 |
| `alignment.py` | ✅ | 价值观对齐系统 |
| `rag.py` | ✅ | 双索引知识库 |
| `registry.py` | ✅ | 工具注册表 (LOD) |
| `tool_retriever.py` | ✅ | 工具语义检索 |
| `store.py` | ✅ | 数据存储抽象 |
| `singleton.py` | ✅ | 单例模式 |
| `monitor.py` | 可选 | GPU监控 |

### 2.4 根目录关键文件清单

| 文件 | 必须存在 | 说明 |
|------|---------|------|
| `api_server.py` | ✅ | 主 API 服务器 |
| `kernel_codeact.py` | ✅ | CodeAct 执行引擎 |
| `config.py` | ✅ | 全局配置 |
| `auth_api.py` | ✅ | JWT 认证 |
| `chat_api.py` | ✅ | 对话历史 |
| `soul_api.py` | ✅ | 灵魂系统 |
| `acontext_integration.py` | ✅ | AContext 集成 |
| `agent_prompts.py` | ✅ | Agent Prompt |
| `mcp_server.py` | ✅ | MCP 协议 |
| `boss_constitution.yaml` | ✅ | 静态价值观 |

## 任务 3: 从开发环境同步缺失文件

如果发现缺失文件，从开发环境复制：

```bash
# 方法1: 通过 scp 从开发机拉取 (假设可以SSH到开发机)
scp xinyueyu@100.79.150.62:~/vulcan_brain_v2/tools/rag_tools.py ~/vulcan-brain/tools/
scp xinyueyu@100.79.150.62:~/vulcan_brain_v2/tools/alignment_tools.py ~/vulcan-brain/tools/
# ... 其他缺失文件

# 方法2: 如果开发机不可达，让远程Agent提供文件内容，本地创建
```

## 任务 4: 验证 tools/__init__.py 内容

确保 `tools/__init__.py` 正确导出所有函数：

```python
# tools/__init__.py
"""
Vulcan Brain - Tools Package
"""

# Function Tools
from .function_tools import get_current_time

# Memory Tools
from .memory_tools import remember_info, recall_info, forget_info

# Alignment Tools
from .alignment_tools import record_boss_feedback, get_alignment_summary

# Boss Insight Tool
from .boss_insight_tool import save_boss_insight

# RAG Tools
from .rag_tools import add_document_to_kb, search_knowledge_base

# Search Tools (新增)
from .search_tools import searxng_search as web_search

__all__ = [
    'get_current_time',
    'remember_info', 'recall_info', 'forget_info',
    'record_boss_feedback', 'get_alignment_summary', 'save_boss_insight',
    'add_document_to_kb', 'search_knowledge_base',
    'web_search',
]
```

## 任务 5: 验证 api_server.py 工具导入

检查 `api_server.py` 顶部的导入是否完整：

```python
# 应该有这些导入:
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool, forget_tool
from tools.rag_tools import add_document_tool, search_knowledge_tool
from tools.alignment_tools import record_boss_feedback_tool, get_alignment_summary_tool
from tools.boss_insight_tool import save_boss_insight_tool
from tools.code_executor import create_code_execution_tool, VulcanCodeSandbox
from tools.search_tools import web_search_tool  # 新增
```

检查 `get_kernel()` 函数中的工具注册：
```python
# 核心包应该包含 web_search_tool
registry.register(ToolPackage(
    name='core_tools',
    tools=[get_time_tool, remember_tool, recall_tool, forget_tool, web_search_tool],  # 注意这里
    is_core=True
))
```

## 任务 6: 功能测试

### 6.1 测试 Web 搜索
```bash
curl -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "今天有什么新闻？", "stream": true}'
```

### 6.2 测试记忆功能
```bash
curl -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "记住我叫张三", "stream": true}'
```

### 6.3 测试时间查询
```bash
curl -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "现在几点了", "stream": true}'
```

### 6.4 检查基础设施
```bash
echo "=== Ollama ==="
curl -s localhost:11434/api/tags | head -5

echo "=== MongoDB ==="
mongosh --eval "db.stats()" --quiet | head -5

echo "=== SearXNG ==="
curl -s "localhost:8080/search?q=test&format=json" | head -3

echo "=== AContext ==="
curl -s localhost:8000/health
```

## 任务 7: 查看日志排错

```bash
# 后端日志
tail -100 /tmp/vulcan_api.log

# 查看报错
grep -i error /tmp/vulcan_api.log | tail -20
grep -i traceback /tmp/vulcan_api.log | tail -20
```

## 已知问题和修复

### 问题1: web_search ImportError
**症状**: `ImportError: cannot import name 'web_search' from 'tools'`
**原因**: `tools/__init__.py` 没有导出 web_search
**修复**: 在 `tools/__init__.py` 添加:
```python
from .search_tools import searxng_search as web_search
```

### 问题2: 模块找不到
**症状**: `ModuleNotFoundError: No module named 'xxx'`
**原因**: 文件缺失
**修复**: 从开发环境复制对应文件

### 问题3: MongoDB 连接失败
**症状**: `ServerSelectionTimeoutError`
**原因**: MongoDB 服务未运行
**修复**:
```bash
sudo systemctl start mongod
# 或者 Docker 方式
docker start vulcan-mongo
```

## 验收标准

完成后，以下功能必须正常工作：

1. ✅ `curl localhost:8001/api/health` 返回 healthy
2. ✅ 对话功能正常（流式输出）
3. ✅ 时间查询正常（不需要调用工具，直接从环境感知获取）
4. ✅ 记忆功能正常（remember/recall）
5. ✅ **联网搜索正常** - 这是上次缺失的关键功能！
6. ✅ 知识库功能正常（如果有 RAG 依赖安装的话）

---

**任务分配**: 生产服务器本地 Agent
**截止时间**: 尽快
**优先级**: P0 (阻塞用户测试)
