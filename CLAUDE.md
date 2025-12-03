# ⚠️ 现在是2025年，搜索信息时请使用2025年关键词，避免过时数据

# Vulcan Brain 项目配置

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
- **集合**:
  - feishu_messages: 飞书消息存储
  - daily_reports: 每日日报

## AI模型
- **Ollama**: localhost:11434
- **模型**: qwen3:30b-a3b

## 前端部署流程
```bash
cd ~/vulcan-brain/vulcan-ui
npm run build
pm2 restart vulcan-frontend
```

## 五纬度信息系统数据流
1. 飞书消息 → Webhook/API收集 → MongoDB(feishu_messages)
2. ChatSummarizer读取 → 直连Ollama分析 → MongoDB(daily_reports)
3. InfoHub API → 前端展示

## SSH配置
从Mac连接: `ssh vulcan` (已配置~/.ssh/config)
