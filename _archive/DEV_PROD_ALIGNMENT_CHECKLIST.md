# Vulcan Brain 开发/生产对齐清单
> 给本地 Agent 的功能验证指南

## 一、开发环境前端现状分析

### 1.1 页面结构 (`~/Desktop/vulcan-ui/src/app/`)

| 页面 | 路由 | 组件 | 状态 |
|------|------|------|------|
| Chat | `/` | `ChatWindow.tsx` | Mock API (TODO) |
| Soul | `/soul` | `SoulConfig.tsx` | Mock API (TODO) |
| Knowledge | `/knowledge` | `KnowledgeBase.tsx` | Mock API (TODO) |
| Memory | `/memory` | `MemoryVisualization.tsx` | Mock Data |
| Settings | `/settings` | **不存在** | 需创建 |

### 1.2 关键发现

1. **所有 API 调用都是 Mock 的** - 代码中有 `// TODO: Replace with actual API call` 注释
2. **SSE 流式未实现** - ChatWindow 使用 `setTimeout` 模拟，不是真正的 EventSource
3. **路由未真正工作** - Sidebar 使用 `setActiveItem` 状态而非 `<Link>` 组件
4. **无 Agent/Gemini 分离** - 只有一个统一的 Chat 界面

---

## 二、按页面的功能对齐清单

### 2.1 Chat 页面 (`/`)

**开发环境代码**: `src/components/chat/ChatWindow.tsx`

**当前实现**:
```typescript
// 第42行 - Mock 响应
setTimeout(() => {
  addMessage({
    role: "assistant",
    content: `收到你的消息："${userMessage}"\n\n这是一个模拟回复...`,
    isStreaming: false,
  });
  setLoading(false);
}, 1000);
```

**需要实现的功能**:

| 功能 | 描述 | 后端 API | 状态 |
|------|------|----------|------|
| SSE 流式对话 | 真正的流式输出 | `POST /api/chat/stream` | ❌ 未实现 |
| 代码块高亮 | 展示 CodeAct 代码 | SSE `code` 事件 | ❌ 未实现 |
| 工具输出显示 | 展示工具执行结果 | SSE `tool_output` 事件 | ❌ 未实现 |
| 消息反馈 | 点赞/踩功能 | `POST /api/feedback` | ❌ 未实现 |
| 对话历史加载 | 加载历史消息 | `GET /api/chat/history` | ❌ 未实现 |
| 记忆提取 | 自动提取用户偏好 | 后端自动 | 需验证 |
| 对话保存 | 保存对话到 MongoDB | 后端自动 | 需验证 |

**生产环境验证命令**:
```bash
# 测试 SSE 端点
curl -N -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "stream": true}'

# 检查对话历史 API
curl http://localhost:8001/api/chat/history
```

---

### 2.2 Soul 页面 (`/soul`)

**开发环境代码**: `src/components/soul/SoulConfig.tsx`

**当前实现**:
```typescript
// 第43-48行 - Mock 保存
const handleSave = async () => {
  // TODO: Call API to save settings
  console.log("Saving settings:", settings);
  setSaved(true);
  setTimeout(() => setSaved(false), 2000);
};
```

**需要实现的功能**:

| 功能 | 描述 | 后端 API | 状态 |
|------|------|----------|------|
| 获取配置 | 加载当前 Soul 配置 | `GET /api/soul/config` | ❌ 未实现 |
| 保存配置 | 保存 System Prompt + 参数 | `POST /api/soul/update` | ❌ 未实现 |
| 重置默认 | 恢复默认配置 | `POST /api/soul/reset` | ❌ 未实现 |
| 参数映射 | Creativity → Temperature | 需设计 | ❌ 未实现 |

**参数说明**:
- `creativity` (70%) → 控制 `temperature`
- `reasoningDepth` (80%) → 控制 `<think>` 输出详细程度
- `toolUsePreference` (60%) → 控制工具调用倾向
- `memoryRetention` (75%) → 控制记忆检索强度

**生产环境验证命令**:
```bash
# 获取配置
curl http://localhost:8001/api/soul/config

# 更新配置
curl -X POST http://localhost:8001/api/soul/update \
  -H "Content-Type: application/json" \
  -d '{"systemPrompt": "测试", "creativity": 70}'
```

---

### 2.3 Knowledge 页面 (`/knowledge`)

**开发环境代码**: `src/components/knowledge/KnowledgeBase.tsx`

**当前实现**:
```typescript
// 第58-93行 - Mock 上传
const handleFileUpload = async (e) => {
  // TODO: Replace with actual API call to /api/knowledge/upload
  // Mock upload simulation
  ...
};
```

**需要实现的功能**:

| 功能 | 描述 | 后端 API | 状态 |
|------|------|----------|------|
| 文件上传 | 上传 PDF/TXT/MD | `POST /api/knowledge/upload` | ❌ 未实现 |
| 文档列表 | 列出所有文档 | `GET /api/knowledge/list` | ❌ 未实现 |
| 删除文档 | 删除指定文档 | `DELETE /api/knowledge/{id}` | ❌ 未实现 |
| 处理状态 | 显示 chunking/embedding 进度 | WebSocket 或轮询 | ❌ 未实现 |
| 统计信息 | 文档数、chunks 数、大小 | `GET /api/knowledge/stats` | ❌ 未实现 |

**后端依赖**:
- `vulcan_libs/rag.py` - VulcanRAG 类
- `tools/rag_tools.py` - add_document_tool, search_knowledge_tool

**生产环境验证命令**:
```bash
# 列出文档
curl http://localhost:8001/api/knowledge/list

# 上传测试
curl -X POST http://localhost:8001/api/knowledge/upload \
  -F "file=@test.txt"

# 搜索测试
curl "http://localhost:8001/api/knowledge/search?q=测试"
```

---

### 2.4 Memory 页面 (`/memory`)

**开发环境代码**: `src/components/memory/MemoryVisualization.tsx`

**当前实现**: 完全使用硬编码的 Mock 数据

```typescript
// 第37-48行 - 硬编码的用户画像
const userProfile: UserProfile = {
  name: "Chief Architect",
  role: "技术负责人",
  expertise: ["系统架构", "Python开发", "AI Engineering", "DevOps"],
  ...
};
```

**需要实现的功能**:

| 功能 | 描述 | 后端 API | 状态 |
|------|------|----------|------|
| 用户画像 | 从记忆中提取的用户特征 | `GET /api/memory/profile` | ❌ 未实现 |
| 对话时间线 | 历史对话摘要 | `GET /api/memory/timeline` | ❌ 未实现 |
| 记忆搜索 | 搜索特定记忆 | `GET /api/memory/search?q=xxx` | ❌ 未实现 |
| 记忆删除 | 删除特定记忆 | `DELETE /api/memory/{id}` | ❌ 未实现 |

**后端依赖**:
- `vulcan_libs/memory.py` - VulcanMemoryV2 类
- `tools/memory_tools.py` - remember_tool, recall_tool, forget_tool

**生产环境验证命令**:
```bash
# 获取用户画像
curl http://localhost:8001/api/memory/profile

# 获取对话时间线
curl http://localhost:8001/api/memory/timeline

# 搜索记忆
curl "http://localhost:8001/api/memory/search?q=技术栈"
```

---

### 2.5 Settings 页面 (`/settings`)

**开发环境状态**: Sidebar 中有链接，但**页面不存在**

**需要创建**:

| 功能 | 描述 | 组件 |
|------|------|------|
| 系统状态 | GPU/VRAM/性能监控 | 复用 `Inspector.tsx` |
| API 配置 | 后端 URL 配置 | 新组件 |
| 用户设置 | 主题、语言等 | 新组件 |

---

## 三、后端 API 完整性检查

### 3.1 必须存在的 API 端点

在生产服务器执行:
```bash
# 检查 api_server.py 中的路由定义
grep -E "@app\.(get|post|delete|put)" ~/vulcan-brain/api_server.py
```

预期端点:
```
✅ GET  /api/health
✅ POST /api/chat/stream
❓ GET  /api/chat/history
❓ GET  /api/soul/config
❓ POST /api/soul/update
❓ POST /api/soul/reset
❓ POST /api/knowledge/upload
❓ GET  /api/knowledge/list
❓ DELETE /api/knowledge/{id}
❓ GET  /api/memory/profile
❓ GET  /api/memory/timeline
❓ GET  /api/system/status
```

### 3.2 后端工具注册检查

```bash
# 检查工具注册
grep -A 5 "registry.register" ~/vulcan-brain/api_server.py
```

预期工具包:
```
core_tools: [get_time_tool, remember_tool, recall_tool, forget_tool, web_search_tool]
rag_pkg: [add_document_tool, search_knowledge_tool]
alignment_pkg: [record_boss_feedback_tool, get_alignment_summary_tool, save_boss_insight_tool]
code_execution_pkg: [create_code_execution_tool()]
```

---

## 四、前端修复任务清单

### 4.1 高优先级 (P0)

1. **实现 SSE 流式对话**
   - 修改 `ChatWindow.tsx` 使用 `EventSource` API
   - 处理 `token`, `code`, `tool_output`, `error`, `done` 事件

2. **修复路由系统**
   - Sidebar 改用 Next.js `<Link>` 组件
   - 或使用 `useRouter()` 进行编程式导航

3. **配置动态 API_BASE**
   - 创建环境变量 `NEXT_PUBLIC_API_URL`
   - 替换所有硬编码的 `http://localhost:8001`

### 4.2 中优先级 (P1)

4. **连接 Soul 配置 API**
5. **连接 Knowledge 上传 API**
6. **连接 Memory 画像 API**

### 4.3 低优先级 (P2)

7. **创建 Settings 页面**
8. **实现消息反馈功能**
9. **添加错误处理和 Loading 状态**

---

## 五、对齐验证流程

### Step 1: 后端 API 验证

```bash
# 在生产服务器执行
ssh xinyue@192.168.10.33

# 1. 检查后端进程
pgrep -a uvicorn

# 2. 测试健康检查
curl http://localhost:8001/api/health

# 3. 测试对话功能
curl -N -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "现在几点", "stream": true}'

# 4. 测试联网搜索
curl -N -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "今天有什么新闻", "stream": true}'

# 5. 测试记忆功能
curl -N -X POST http://localhost:8001/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "记住我最喜欢的颜色是蓝色", "stream": true}'
```

### Step 2: 前端部署验证

```bash
# 在生产服务器执行

# 1. 检查前端进程
pgrep -a node

# 2. 检查 Nginx/Caddy 配置
cat /etc/nginx/sites-enabled/vulcan-ui.conf
# 或
cat /etc/caddy/Caddyfile

# 3. 测试前端访问
curl -I http://localhost:3000
curl -I https://dash.vsg-brain.com
```

### Step 3: 端到端测试

1. 打开浏览器访问 `https://dash.vsg-brain.com`
2. 发送消息，验证流式响应
3. 访问 Soul 页面，验证配置加载
4. 访问 Knowledge 页面，测试文件上传
5. 访问 Memory 页面，验证画像数据

---

## 六、V4.0 架构目标对照

根据用户提供的 V4.0 架构图:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Vulcan Brain V4.0 目标                       │
├─────────────────────────────────────────────────────────────────┤
│ 前端页面:                                                        │
│  • Agent对话 - 记忆提取, 对话保存                                 │
│  • Gemini对话 - 对话保存, Soul集成                                │
│  • Soul页面 - 复杂记忆和知识提取                                  │
│  • Knowledge/数据库 - 自动上传, 向量化                            │
│  • Memory页面 - 从对话中提取                                      │
├─────────────────────────────────────────────────────────────────┤
│ 当前开发环境 vs 目标:                                            │
│  • Chat页面 ≈ Agent对话 (需实现真正API)                          │
│  • 无Gemini对话 (可能需新页面或切换模型)                          │
│  • Soul页面 ✓ (UI已有, API未连接)                                │
│  • Knowledge页面 ✓ (UI已有, API未连接)                           │
│  • Memory页面 ✓ (UI已有, 数据Mock)                               │
└─────────────────────────────────────────────────────────────────┘
```

**需与用户确认**:
1. Agent对话 vs Gemini对话 的区别是什么？
   - 不同的模型？(Ollama qwen3 vs Google Gemini)
   - 不同的工具集？
   - 不同的 System Prompt？

2. 是否需要创建两个独立的聊天页面？

---

**文档生成时间**: 2024-11-28
**状态**: 待本地 Agent 执行验证

