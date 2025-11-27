# 🧠 Vulcan Brain

> **Executive AI Operating System** - 为高净值决策者打造的私有化 AI 操作系统

## 🎯 核心理念

- **Executive Precision (高管级精密)**: Bloomberg Terminal 级别的暗黑硬朗 UI
- **Soul Loop (灵魂闘环)**: 点火仪式 → 数字孪生 → 决策推演 → 前瞻洞察
- **LOD Architecture**: 按需加载工具和记忆，减少 Context 压力
- **CodeAct**: 能写代码解决的，绝不生成文本

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| Frontend | Next.js 15 + TailwindCSS + Framer Motion |
| Backend | FastAPI + Uvicorn |
| LLM | Ollama (Qwen3-thinking 30B) |
| Database | MongoDB |
| Process | PM2 |

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/vulcan-brain.git
cd vulcan-brain

# 后端环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 前端环境
cd vulcan-ui
npm install
npm run build
cd ..

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写实际配置
```

### 2. 启动服务

```bash
# 使用 PM2 (推荐)
pm2 start ecosystem.config.js
pm2 save
pm2 startup

# 或手动启动
# 后端
source venv/bin/activate
python -m uvicorn api_server:app --host 0.0.0.0 --port 8001

# 前端 (新终端)
cd vulcan-ui && npm start
```

### 3. 访问系统

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8001
- **API 文档**: http://localhost:8001/docs

## 📁 项目结构

```
vulcan_brain_v2/
├── api_server.py      # 主 API 服务器
├── soul_api.py        # 灵魂系统 API
├── kernel_codeact.py  # CodeAct 执行引擎
├── kernel_mcp_v5.py   # MCP 协议内核
├── auth_api.py        # 认证系统
├── chat_api.py        # 对话 API
├── vulcan-ui/         # Next.js 前端
│   └── src/app/
│       ├── calibration/  # 点火仪式
│       ├── soul/         # 灵魂面板
│       └── ...
├── tools/             # 工具函数
├── vulcan_libs/       # 核心库
├── data/              # 数据存储
└── ecosystem.config.js # PM2 配置
```

## 🔐 安全注意

- `.env` 文件包含敏感信息，**永不提交到 Git**
- 生产环境务必更改 `JWT_SECRET`
- 建议使用 Cloudflare Tunnel 而非直接暴露端口

## 📜 License

Private - All Rights Reserved

---

Built with 🔥 by Vulcan Brain Team
