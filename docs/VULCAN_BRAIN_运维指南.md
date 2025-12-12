# Vulcan Brain 运维指南

> 最后更新: 2025-12-03
> 适用于: 无代码背景的 AI Agent 协作开发者

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [服务器连接](#2-服务器连接)
3. [项目文件结构](#3-项目文件结构)
4. [PM2 进程管理](#4-pm2-进程管理)
5. [常用运维命令](#5-常用运维命令)
6. [数据库操作](#6-数据库操作)
7. [日志查看](#7-日志查看)
8. [故障排查](#8-故障排查)
9. [代码修改与部署](#9-代码修改与部署)
10. [安全注意事项](#10-安全注意事项)
11. [定期维护任务](#11-定期维护任务)
12. [AI Agent 协作规范](#12-ai-agent-协作规范)

---

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      互联网用户                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloudflare Tunnel (零信任网关)                   │
│  • vsg-brain.com → localhost:3000 (前端)                     │
│  • api.vsg-brain.com → localhost:8001 (后端API)              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Vulcan 服务器 (本地)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ vulcan-ui    │  │vulcan-backend│  │   Ollama     │       │
│  │ (Next.js)    │  │  (FastAPI)   │  │ (qwen3:30b)  │       │
│  │ Port: 3000   │  │  Port: 8001  │  │ Port: 11434  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────┐       │
│  │              MongoDB (本地数据库)                  │       │
│  │              数据库: vulcan_brain                 │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  硬件: 双 RTX 5090 (64GB VRAM) + AMD Threadripper           │
└─────────────────────────────────────────────────────────────┘
```

### 核心服务说明

| 服务 | 技术栈 | 端口 | 作用 |
|------|--------|------|------|
| vulcan-ui | Next.js 15 + React 19 | 3000 | 前端界面 |
| vulcan-backend | FastAPI + Python | 8001 | 后端 API |
| Ollama | qwen3:30b-a3b | 11434 | 本地大模型 |
| MongoDB | v7.x | 27017 | 数据存储 |
| Cloudflare Tunnel | cloudflared | - | 安全网关 |

---

## 2. 服务器连接

### 2.1 SSH 配置

你的 Mac 上已配置好 SSH，可以直接使用：

```bash
# 方式1: 通过 Tailscale (任何网络都能连)
ssh vulcan

# 方式2: 局域网直连 (同一WiFi下更快)
ssh vulcan-lan
```

### 2.2 SSH 配置文件位置

```
~/.ssh/config.d/vulcan.conf
```

内容：
```
Host vulcan
  HostName 100.83.218.7
  User xinyue

Host vulcan-lan
  HostName 192.168.10.33
  User xinyue
```

### 2.3 常用连接命令

```bash
# 连接服务器
ssh vulcan

# 直接执行命令（不进入交互模式）
ssh vulcan "pm2 list"

# 传输文件到服务器
scp local_file.txt vulcan:~/vulcan-brain/

# 从服务器下载文件
scp vulcan:~/vulcan-brain/file.txt ./
```

### 2.4 重要提醒

> ⚠️ **PM2 命令需要设置 PATH**
>
> 由于 Node.js 通过 NVM 安装，直接 ssh 执行 pm2 会找不到命令。
> 必须先设置 PATH：

```bash
# 正确写法
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 list"

# 或者先进入服务器再操作
ssh vulcan
pm2 list  # 交互模式下直接可用
```

---

## 3. 项目文件结构

### 3.1 后端结构 (`~/vulcan-brain/`)

```
~/vulcan-brain/
├── api_server.py          # 🔴 主入口！FastAPI 应用
├── kernel_codeact.py      # 🔴 AI 内核（LOD架构）
├── auth_api.py            # 用户认证
├── soul_api.py            # 灵魂系统 API
├── info_hub_api.py        # 信息中心 API
├── feishu_api.py          # 飞书集成
├── email_api.py           # 邮件集成
├── pm_api.py              # 项目管理 API
├── message_api.py         # 消息收集 API
│
├── config.py              # 配置（读取 .env）
├── .env                   # 🔒 环境变量（密钥，不要泄露！）
│
├── services/              # 业务服务层
│   ├── message_store.py   # 飞书消息存储
│   ├── chat_summarizer.py # AI 聊天汇总
│   ├── daily_report.py    # 日报生成
│   ├── email_store.py     # 邮件存储
│   └── project_store.py   # 项目存储
│
├── vulcan_libs/           # 核心库
│   ├── store.py           # 🔴 数据库统一接口
│   ├── rag.py             # RAG 检索
│   ├── logger.py          # 日志系统
│   └── registry.py        # 工具注册
│
├── tools/                 # AI 工具
│   ├── code_executor.py   # 代码执行沙箱
│   ├── memory_tools.py    # 记忆工具
│   ├── search_tools.py    # 搜索工具
│   └── rag_tools.py       # RAG 工具
│
├── logs/                  # 日志目录
│   ├── api.log            # API 请求日志
│   └── kernel.log         # AI 内核日志
│
├── kb_storage/            # 知识库文件
├── rag_storage/           # RAG 索引
├── venv/                  # Python 虚拟环境
└── vulcan-ui/             # 前端项目（见下）
```

### 3.2 前端结构 (`~/vulcan-brain/vulcan-ui/`)

```
vulcan-ui/
├── src/
│   ├── app/                    # Next.js App Router 页面
│   │   ├── page.tsx            # 首页
│   │   ├── layout.tsx          # 全局布局
│   │   ├── login/              # 登录页
│   │   ├── calibration/        # 校准页
│   │   ├── gemini/             # AI 对话
│   │   ├── info-hub/           # 信息中心
│   │   │   ├── daily-report/   # 日报
│   │   │   ├── chat/           # 聊天摘要
│   │   │   ├── email/          # 邮件
│   │   │   └── projects/       # 项目
│   │   ├── soul/               # 灵魂系统
│   │   ├── memory/             # 记忆系统
│   │   ├── knowledge/          # 知识库
│   │   └── settings/           # 设置
│   │
│   ├── components/             # React 组件
│   │   ├── layout/
│   │   │   ├── DashboardLayout.tsx
│   │   │   └── Sidebar.tsx
│   │   └── ui/                 # 通用UI组件
│   │
│   ├── contexts/               # React Context
│   │   ├── AuthContext.tsx     # 认证状态
│   │   └── ThemeContext.tsx    # 主题
│   │
│   └── i18n/                   # 国际化
│       ├── locales/
│       │   ├── zh-CN.json
│       │   └── en-US.json
│       └── index.ts
│
├── public/                     # 静态资源
├── package.json                # 依赖配置
└── next.config.ts              # Next.js 配置
```

### 3.3 关键配置文件

| 文件 | 位置 | 作用 |
|------|------|------|
| `.env` | `~/vulcan-brain/.env` | 后端密钥配置 |
| `config.py` | `~/vulcan-brain/config.py` | Python 配置读取 |
| `ecosystem.config.js` | `~/vulcan-brain/` | PM2 配置 |
| `/etc/cloudflared/config.yml` | 系统目录 | Cloudflare 隧道配置 |

---

## 4. PM2 进程管理

### 4.1 PM2 是什么

PM2 是 Node.js 进程管理器，用于：
- 保持服务持续运行
- 自动重启崩溃的服务
- 查看日志
- 管理多个服务

### 4.2 核心命令速查

```bash
# ⚠️ 所有命令前都需要设置 PATH（SSH 直接执行时）
export PATH=$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin

# 查看所有服务状态
pm2 list

# 重启后端
pm2 restart vulcan-backend

# 重启前端
pm2 restart vulcan-frontend

# 停止服务
pm2 stop vulcan-backend

# 启动服务
pm2 start vulcan-backend

# 查看实时日志（Ctrl+C 退出）
pm2 logs vulcan-backend

# 查看最近50行日志（不阻塞）
pm2 logs vulcan-backend --lines 50 --nostream

# 查看所有服务日志
pm2 logs

# 清空日志
pm2 flush

# 保存当前服务列表（重启后自动恢复）
pm2 save
```

### 4.3 一键命令（从 Mac 执行）

```bash
# 查看状态
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 list"

# 重启后端
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 restart vulcan-backend"

# 重启前端
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 restart vulcan-frontend"

# 查看后端日志
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-backend --lines 50 --nostream"
```

### 4.4 PM2 服务配置

当前运行的服务：

| ID | 名称 | 类型 | 端口 | 说明 |
|----|------|------|------|------|
| 0 | vulcan-backend | Python/FastAPI | 8001 | 后端 API |
| 1 | vulcan-ui | Node.js/Next.js | 3000 | 前端界面 |

---

## 5. 常用运维命令

### 5.1 服务健康检查

```bash
# 检查后端 API
curl https://api.vsg-brain.com/api/health
# 或本地
ssh vulcan "curl -s http://localhost:8001/api/health"

# 检查前端
curl -I https://vsg-brain.com

# 检查 Ollama（AI 模型）
ssh vulcan "curl -s http://localhost:11434/api/tags"

# 检查 MongoDB
ssh vulcan "mongosh --eval 'db.adminCommand(\"ping\")'"

# 检查 Cloudflare 隧道
ssh vulcan "systemctl status cloudflared"
```

### 5.2 系统资源检查

```bash
# GPU 状态
ssh vulcan "nvidia-smi"

# GPU 简洁信息
ssh vulcan "nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu --format=csv"

# 内存使用
ssh vulcan "free -h"

# 磁盘空间
ssh vulcan "df -h"

# CPU 使用
ssh vulcan "top -bn1 | head -5"

# 查看端口占用
ssh vulcan "lsof -i :8001"  # 后端端口
ssh vulcan "lsof -i :3000"  # 前端端口
```

### 5.3 Cloudflare 隧道管理

```bash
# 查看隧道状态
ssh vulcan "systemctl status cloudflared"

# 重启隧道
ssh vulcan "sudo systemctl restart cloudflared"

# 查看隧道配置
ssh vulcan "cat /etc/cloudflared/config.yml"

# 查看隧道日志
ssh vulcan "journalctl -u cloudflared -n 50"
```

---

## 6. 数据库操作

### 6.1 MongoDB 基础

```bash
# 进入 MongoDB Shell
ssh vulcan "mongosh vulcan_brain"

# 或从 Mac 直接执行查询
ssh vulcan "mongosh vulcan_brain --eval 'db.users.find()'"
```

### 6.2 常用查询

```bash
# 查看所有集合（表）
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.getCollectionNames()'"

# 统计用户数
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.users.countDocuments()'"

# 查看最近5条聊天消息
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.feishu_messages.find().sort({timestamp:-1}).limit(5).toArray()'"

# 查看日报
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.daily_reports.find().sort({date:-1}).limit(3).toArray()'"
```

### 6.3 数据库集合说明

| 集合名 | 用途 |
|--------|------|
| `users` | 用户账号 |
| `user_souls` | 用户灵魂配置 |
| `chat_sessions` | 对话历史 |
| `memories` | 用户记忆 |
| `feishu_messages` | 飞书消息 |
| `daily_reports` | 日报数据 |
| `emails` | 邮件数据 |

### 6.4 备份数据库

```bash
# 备份整个数据库
ssh vulcan "mongodump --db vulcan_brain --out ~/backup/mongo/\$(date +%Y%m%d)"

# 备份单个集合
ssh vulcan "mongodump --db vulcan_brain --collection users --out ~/backup/"

# 恢复备份
ssh vulcan "mongorestore --db vulcan_brain ~/backup/mongo/20251203/vulcan_brain/"
```

---

## 7. 日志查看

### 7.1 日志位置

| 日志类型 | 位置 |
|----------|------|
| PM2 日志 | `~/.pm2/logs/` |
| API 日志 | `~/vulcan-brain/logs/api.log` |
| 内核日志 | `~/vulcan-brain/logs/kernel.log` |
| Cloudflare 日志 | `journalctl -u cloudflared` |

### 7.2 查看日志命令

```bash
# PM2 实时日志
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs"

# 后端最近日志
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-backend --lines 100 --nostream"

# 前端最近日志
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-ui --lines 50 --nostream"

# API 结构化日志
ssh vulcan "tail -100 ~/vulcan-brain/logs/api.log"

# 只看错误
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-backend --err --lines 50 --nostream"
```

### 7.3 日志关键词搜索

```bash
# 搜索错误
ssh vulcan "grep -i error ~/.pm2/logs/vulcan-backend-error.log | tail -20"

# 搜索特定关键词
ssh vulcan "grep '用户登录' ~/vulcan-brain/logs/api.log"
```

---

## 8. 故障排查

### 8.1 快速诊断清单

```bash
# 1. 服务是否运行
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 list"

# 2. API 是否响应
curl https://api.vsg-brain.com/api/health

# 3. 查看错误日志
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-backend --err --lines 30 --nostream"

# 4. 检查端口
ssh vulcan "lsof -i :8001"
```

### 8.2 常见问题及解决

#### 问题1: 网站打不开

```bash
# 检查 Cloudflare 隧道
ssh vulcan "systemctl status cloudflared"

# 如果 inactive，重启隧道
ssh vulcan "sudo systemctl restart cloudflared"
```

#### 问题2: 后端 API 无响应

```bash
# 检查服务状态
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 list"

# 如果 stopped 或 errored，重启
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 restart vulcan-backend"

# 查看错误原因
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-backend --err --lines 50 --nostream"
```

#### 问题3: 端口被占用

```bash
# 查看谁占用了端口
ssh vulcan "lsof -i :8001"

# 强制杀掉占用进程
ssh vulcan "kill -9 <PID>"

# 重启服务
ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 restart vulcan-backend"
```

#### 问题4: AI 回复很慢或无响应

```bash
# 检查 Ollama 状态
ssh vulcan "curl -s http://localhost:11434/api/tags"

# 检查 GPU 状态
ssh vulcan "nvidia-smi"

# 重启 Ollama（如果需要）
ssh vulcan "systemctl restart ollama"
```

#### 问题5: 数据库连接失败

```bash
# 检查 MongoDB 状态
ssh vulcan "systemctl status mongod"

# 如果没运行，启动它
ssh vulcan "sudo systemctl start mongod"
```

### 8.3 紧急恢复流程

如果一切都挂了：

```bash
# 1. SSH 进入服务器
ssh vulcan

# 2. 重启所有服务
export PATH=$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin
pm2 restart all

# 3. 重启 Cloudflare 隧道
sudo systemctl restart cloudflared

# 4. 检查状态
pm2 list
curl http://localhost:8001/api/health
```

---

## 9. 代码修改与部署

### 9.1 后端代码修改流程

```bash
# 1. SSH 进入服务器
ssh vulcan
cd ~/vulcan-brain

# 2. 让 AI Agent 修改代码（或手动编辑）
# nano api_server.py  # 手动编辑

# 3. 测试语法是否正确
python3 -m py_compile api_server.py

# 4. 重启服务
export PATH=$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin
pm2 restart vulcan-backend

# 5. 检查日志确认无错误
pm2 logs vulcan-backend --lines 20 --nostream

# 6. 测试 API
curl http://localhost:8001/api/health
```

### 9.2 前端代码修改流程

```bash
# 1. SSH 进入服务器
ssh vulcan
cd ~/vulcan-brain/vulcan-ui

# 2. 修改代码后，重新构建
export PATH=$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin
npm run build

# 3. 重启前端服务
pm2 restart vulcan-ui

# 4. 清除浏览器缓存后访问验证
```

### 9.3 Git 版本管理

```bash
# 查看修改了哪些文件
ssh vulcan "cd ~/vulcan-brain && git status"

# 查看具体改动
ssh vulcan "cd ~/vulcan-brain && git diff api_server.py"

# 提交修改
ssh vulcan "cd ~/vulcan-brain && git add -A && git commit -m '描述你的修改'"

# 查看历史提交
ssh vulcan "cd ~/vulcan-brain && git log --oneline -10"

# 回滚到上一个版本（危险操作！）
ssh vulcan "cd ~/vulcan-brain && git checkout HEAD~1 -- api_server.py"
```

---

## 10. 安全注意事项

### 10.1 绝对不要做的事

```
❌ 把 .env 文件提交到 Git
❌ 在代码中硬编码密码
❌ 把密钥发给任何人
❌ 在公开场合展示终端（可能泄露密钥）
❌ 使用弱密码
❌ 关闭 Cloudflare 隧道直接暴露端口
```

### 10.2 密钥管理

```bash
# .env 文件权限（只有所有者可读写）
ssh vulcan "chmod 600 ~/vulcan-brain/.env"

# 检查 .env 是否被 Git 跟踪（不应该被跟踪）
ssh vulcan "cd ~/vulcan-brain && git ls-files | grep .env"
# 如果有输出，说明有问题！

# .gitignore 应该包含 .env
ssh vulcan "grep '.env' ~/vulcan-brain/.gitignore"
```

### 10.3 定期安全检查

```bash
# 检查是否有未加密的密码
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.users.find({password_hash: /^[a-f0-9]{64}\$/}).count()'"
# 如果 > 0，说明还有旧的 SHA256 密码需要用户登录后自动升级

# 检查日志中是否有敏感信息
ssh vulcan "grep -i password ~/vulcan-brain/logs/*.log"
```

---

## 11. 定期维护任务

### 11.1 每日任务

- [ ] 检查服务状态：`pm2 list`
- [ ] 检查错误日志：`pm2 logs --err --lines 50 --nostream`

### 11.2 每周任务

- [ ] 备份数据库
- [ ] 检查磁盘空间：`df -h`
- [ ] 清理旧日志：`pm2 flush`

### 11.3 每月任务

- [ ] 更新依赖（谨慎操作）
- [ ] 检查安全配置
- [ ] 审查用户权限

### 11.4 自动备份设置

```bash
# SSH 进入服务器
ssh vulcan

# 编辑 crontab
crontab -e

# 添加以下内容：
# 每天凌晨3点备份 MongoDB
0 3 * * * mongodump --db vulcan_brain --out /home/xinyue/backup/mongo/$(date +\%Y\%m\%d) --gzip

# 每周日清理30天前的备份
0 4 * * 0 find /home/xinyue/backup/mongo -mtime +30 -type d -exec rm -rf {} +
```

---

## 12. AI Agent 协作规范

### 12.1 给 AI Agent 的指令模板

当让 AI Agent（如 Claude Code）帮你操作时，可以这样说：

```
请帮我 [具体任务]。

服务器连接方式：ssh vulcan
项目位置：~/vulcan-brain
PM2 命令需要先设置 PATH：
export PATH=$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin

修改后请：
1. 测试语法是否正确
2. 重启对应服务
3. 检查日志确认无错误
4. 提交 Git
```

### 12.2 AI Agent 应该遵守的规范

```
✅ 修改前先备份（或用 Git）
✅ 修改后验证功能正常
✅ 提交有意义的 Git commit 信息
✅ 不要硬编码密钥
✅ 使用环境变量
✅ 添加必要的错误处理
✅ 添加日志记录
```

### 12.3 验收清单

每次 AI Agent 完成修改后，检查：

- [ ] 服务是否正常运行 (`pm2 list`)
- [ ] API 是否响应 (`curl .../api/health`)
- [ ] 功能是否正常（手动测试）
- [ ] 日志是否有错误
- [ ] Git 是否已提交

---

## 附录 A: 快捷命令速查表

| 操作 | 命令 |
|------|------|
| 连接服务器 | `ssh vulcan` |
| 查看服务状态 | `ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 list"` |
| 重启后端 | `ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 restart vulcan-backend"` |
| 重启前端 | `ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 restart vulcan-frontend"` |
| 查看后端日志 | `ssh vulcan "export PATH=\$PATH:/home/xinyue/.nvm/versions/node/v20.19.6/bin && pm2 logs vulcan-backend --lines 50 --nostream"` |
| 检查 API | `curl https://api.vsg-brain.com/api/health` |
| 检查 GPU | `ssh vulcan "nvidia-smi"` |
| 检查磁盘 | `ssh vulcan "df -h"` |
| 备份数据库 | `ssh vulcan "mongodump --db vulcan_brain --out ~/backup/mongo/\$(date +%Y%m%d)"` |

---

## 附录 B: 重要联系方式和资源

| 资源 | 地址 |
|------|------|
| 前端访问 | https://vsg-brain.com |
| API 访问 | https://api.vsg-brain.com |
| API 文档 | https://api.vsg-brain.com/docs |
| Cloudflare 控制台 | https://dash.cloudflare.com |

---

*文档由 Claude Code 生成，如有问题可随时让 AI Agent 更新此文档。*
