# Vulcan Brain 系统审计报告
> 生成时间: 2025-12-14

## 一、运行服务状态

| 服务 | 状态 | 说明 |
|------|------|------|
| vulcan-backend | ✅ 运行中 | FastAPI 后端 (port 8001) |
| vulcan-ui | ✅ 运行中 | Next.js 前端 (port 3000) |
| vulcan-upload | ✅ 运行中 | 文件上传服务 |

## 二、API Router 加载清单

### 新模块化架构 (api/routers/)
| Router | 说明 | 状态 |
|--------|------|------|
| system_router | 系统健康检查 | ✅ 活跃 |
| code_execution_router | 代码执行 | ✅ 活跃 |
| core_router | 核心功能 | ✅ 活跃 |
| memory_router | 记忆系统 | ✅ 活跃 |
| agent_router | Agent 功能 | ✅ 活跃 |
| knowledge_router | 知识库 | ✅ 活跃 |
| soul_router | 灵魂系统 | ✅ 活跃 |

### 独立 API 模块
| 模块 | 前缀 | 状态 | 说明 |
|------|------|------|------|
| auth_api | /api | ✅ 活跃 | 认证授权 |
| chat_api | /api | ✅ 活跃 | 基础聊天 |
| unified_chat_api | /api | ✅ 活跃 | 统一聊天 (ReAct) |
| info_hub_api | /api | ✅ 活跃 | 信息中心 (五维) |
| pm_api | - | ✅ 活跃 | 项目管理 |
| soul_api | /api | ✅ 活跃 | 灵魂系统扩展 |
| memory_api | /api | ✅ 活跃 | 记忆系统 v3 |
| email_api | /api | ✅ 活跃 | 邮件基础 |
| email_intel_api | /api | ✅ 活跃 | 邮件智能 |
| approval_api | /api | ✅ 活跃 | 审批系统 |
| feishu_router | - | ✅ 活跃 | 飞书集成 |
| message_api | /api | ✅ 活跃 | 消息收集 |
| acontext_integration | /api | ❓ 待确认 | AContext 集成 |
| mcp_server | /api | ❓ 待确认 | MCP 服务 |
| bicameral_api | /api | ⚠️ 疑似废弃 | 双脑架构 |

## 三、疑似废弃代码

### 🔴 建议移至 _deprecated/

```
# 双脑架构相关 (用户确认废弃)
vulcan_libs/bicameral_graph.py (673行)
vulcan_libs/bicameral_graph_v6.py (470行)
vulcan_libs/bicameral_stream.py (202行)
vulcan_libs/bicameral_types.py (297行)
vulcan_libs/ceo_soul.py
vulcan_libs/cto_executor.py
bicameral_api.py
kernel_bicameral_v5.py

# .bak 备份文件
vulcan_libs/bicameral_graph.py.v5.0.bak
vulcan_libs/bicameral_graph.py.v5.1.bak
vulcan_libs/bicameral_graph.py.v6.0.bak
vulcan_libs/bicameral_graph.py.v52.bak
vulcan_libs/bicameral_types.py.v6.0.bak
vulcan_libs/ceo_soul.py.v52.bak
vulcan_libs/cto_executor.py.v52.bak
services/email_intelligence_service.py.bak
```

### 🟡 需确认状态

```
# 可能是实验性/一次性脚本
ai_deep_research.py
ai_engineer_skill_design.py
analyze_llm_architecture.py
consult_gemini.py
gemini_consult.py
run_product_analysis.py
soul_calibration_design.py
soul_design_consultation.py
system_snapshot.py
create_slim_snapshot.py
vulcan_gemini_audit.py
```

### 🟢 已归档 (_archive/)
```
_archive/
├── api_legacy/
├── plans/
├── reports/
├── v4_legacy/
└── *.md (历史文档)
```

## 四、当前核心功能模块

### 信息中心 (info_hub_api.py) - 44KB
- 五维聚合: chat, email, projects, approval, people
- 日报生成
- 搜索功能

### 统一聊天 (unified_chat_api.py) - 16KB
- ReAct 工具调用
- 多模型支持 (Gemini/Qwen3)
- Session 持久化

### 灵魂系统 (soul_api.py + core/soul/) - 25KB+
- 6维画像
- AI 情景题
- 新架构: core/soul/

### 记忆系统 (memory_api.py + services/memory_service.py)
- 显式记忆 CRUD
- 对话摘要

### 邮件智能 (email_intel_api.py + services/email_intelligence_v2/)
- Command Center
- Action Center
- 实体抽取 (v2 架构)

### 项目管理 (pm_api.py) - 25KB
- Project/Task CRUD
- 飞书通知

### 飞书集成 (feishu/)
- SDK, Gateway, Handlers
- 定时调度
- 通知服务

## 五、清理建议

### 立即执行
```bash
# 1. 移动双脑架构到 _deprecated
mkdir -p ~/vulcan-brain/_deprecated/bicameral
mv ~/vulcan-brain/vulcan_libs/bicameral*.py ~/vulcan-brain/_deprecated/bicameral/
mv ~/vulcan-brain/bicameral_api.py ~/vulcan-brain/_deprecated/bicameral/
mv ~/vulcan-brain/kernel_bicameral_v5.py ~/vulcan-brain/_deprecated/bicameral/
mv ~/vulcan-brain/vulcan_libs/ceo_soul.py ~/vulcan-brain/_deprecated/bicameral/
mv ~/vulcan-brain/vulcan_libs/cto_executor.py ~/vulcan-brain/_deprecated/bicameral/

# 2. 删除 .bak 文件
find ~/vulcan-brain/vulcan_libs -name "*.bak" -delete

# 3. 从 api_server.py 移除 bicameral_api
# (需手动编辑)
```

### 后续整理
1. 确认 acontext_integration, mcp_server 是否还在用
2. 整理 scripts/ 下的一次性脚本
3. 归档 docs/ 下的实验性代码

---
*此报告由 Claude Code 生成，请人工确认后再执行清理操作*
