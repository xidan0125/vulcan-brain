# ⚠️ 现在是2025年，搜索信息时请使用2025年关键词，避免过时数据

# Vulcan Brain 项目配置

## 📚 必读文档列表

> **重要**: 以下文档是理解和维护本项目的核心资料，新Agent必须优先阅读！

| 优先级 | 文档路径 | 内容说明 | 何时阅读 |
|--------|---------|---------|---------|
| 🔴 P0 | `docs/VULCAN_BRAIN_运维指南.md` | 完整运维手册(SSH/PM2/部署/故障排查) | **首次接手必读** |
| 🟡 P1 | `docs/VULCAN_BRAIN_DATABASE_REPORT.md` | 数据库结构与集合详解 | 涉及数据库操作时 |
| 🟡 P1 | `docs/FIVE_DIMENSION_INFO_COLLECTION_PLAN.md` | 五维度信息系统规划 | 开发新功能时 |
| 🟢 P2 | `docs/AGENT_SYSTEM_PROMPTS.md` | AI Agent提示词配置 | 修改Agent行为时 |
| 🟢 P2 | `docs/EMAIL_DATA_INTELLIGENCE_PLAN.md` | 邮件智能分析规划 | 开发邮件功能时 |

---

## 基础信息
- **项目路径**: ~/vulcan-brain
- **前端路径**: ~/vulcan-brain/vulcan-ui
- **域名**: vsg-brain.com (前端) / api.vsg-brain.com (后端API)

## 网络架构
- **网关**: Cloudflare Tunnel (不是nginx!)
- **配置文件**: /etc/cloudflared/config.yml
- **路由规则**:
  - vsg-brain.com → localhost:3000 (前端)
  - api.vsg-brain.com → localhost:8001 (后端)

## PM2 服务管理
⚠️ 使用PM2前必须先导出PATH:
```bash
export PATH=$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin
```

服务列表:
- **vulcan-backend**: Python FastAPI (端口8001)
- **vulcan-frontend**: Next.js生产模式 (端口3000)

常用命令:
```bash
pm2 list                    # 查看服务状态
pm2 restart vulcan-backend  # 重启后端
pm2 restart vulcan-frontend # 重启前端
pm2 logs vulcan-backend     # 查看后端日志
```

## 数据库
- **MongoDB**: localhost:27017
- **数据库名**: vulcan_brain
- **主要集合**: feishu_messages, daily_reports, chat_sessions, emails, user_souls

## AI模型
- **Ollama**: localhost:11434
- **模型**: qwen3:30b-a3b

## 前端部署流程
```bash
cd ~/vulcan-brain/vulcan-ui
npm run build
pm2 restart vulcan-frontend
```

## SSH配置
从Mac连接: `ssh vulcan` (已配置~/.ssh/config)

---

## 📁 归档说明
历史文档已归档至 `_archive/` 目录，包括:
- `_archive/reports/` - 历史部署和Sprint报告
- `_archive/plans/` - 已完成的重构计划
