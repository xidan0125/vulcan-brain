# Vulcan Brain API 接口规范

**后端**: FastAPI (Python)  
**前端**: Next.js 15 (TypeScript)  
**通信协议**: Server-Sent Events (SSE) + REST

---

## 1. 流式聊天接口 (SSE)

### `POST /api/chat/stream`

**用途**: 实时流式对话，支持思考过程、代码执行、工具调用的实时反馈

**请求体**:
```json
{
  "message": "用户输入的消息",
  "conversation_id": "可选的会话ID（用于恢复对话）"
}
```

**响应格式** (SSE Events):

每个事件为一行 `data: {JSON}\n\n`

#### Event Types:

1. **token** - 普通文本 token
```json
{
  "type": "token",
  "content": "增量文本",
  "is_thinking": false
}
```

2. **thinking** - 思考过程（<think> 标签内）
```json
{
  "type": "token",
  "content": "思考内容...",
  "is_thinking": true
}
```

3. **code** - 代码块检测到
```json
{
  "type": "code",
  "content": "完整的Python代码",
  "is_thinking": false
}
```

4. **tool_output** - 工具执行结果
```json
{
  "type": "tool_output",
  "content": "工具执行的输出结果",
  "is_thinking": false
}
```

5. **final_answer** - 最终答案
```json
{
  "type": "final_answer",
  "content": "清洗后的最终答案（无<think>标签）",
  "is_thinking": false
}
```

6. **error** - 错误信息
```json
{
  "type": "error",
  "content": "错误描述",
  "is_thinking": false
}
```

**示例流程**:
```
data: {"type":"token","content":"<think>","is_thinking":true}

data: {"type":"token","content":"Analyzing the query...","is_thinking":true}

data: {"type":"token","content":"</think>","is_thinking":false}

data: {"type":"code","content":"from tools import get_current_time\nprint(get_current_time())"}

data: {"type":"tool_output","content":"Current time: 2025-11-20 22:30:00"}

data: {"type":"final_answer","content":"当前时间是 2025-11-20 22:30:00"}
```

---

## 2. 知识库管理接口

### `POST /api/knowledge/upload`
**用途**: 上传文档到 RAG 知识库

**请求体** (multipart/form-data):
```
file: 文件（PDF/TXT/DOCX）
```

**响应**:
```json
{
  "doc_id": "uuid",
  "filename": "document.pdf",
  "status": "indexed",
  "chunks": 42,
  "tokens": 15230
}
```

### `GET /api/knowledge/list`
**用途**: 获取已索引的文档列表

**响应**:
```json
{
  "documents": [
    {
      "doc_id": "uuid",
      "filename": "Sprint4_Report.pdf",
      "upload_time": "2025-11-20T14:30:00Z",
      "chunks": 42,
      "status": "indexed"
    }
  ]
}
```

### `DELETE /api/knowledge/{doc_id}`
**用途**: 删除指定文档

---

## 3. 记忆系统接口

### `GET /api/memory/profile`
**用途**: 获取用户画像（长期记忆提取）

**响应**:
```json
{
  "profile": {
    "role": "Owner / Architect",
    "location": "Shanghai",
    "interests": ["Dota2", "AI", "Web3"],
    "tech_stack": ["Python", "TypeScript", "Solidity"],
    "preferences": {
      "communication_style": "Direct",
      "feedback_style": "Detailed"
    }
  },
  "memory_count": 127,
  "last_updated": "2025-11-20T14:30:00Z"
}
```

### `GET /api/memory/timeline`
**用途**: 获取记忆时间轴（过去对话的摘要）

**响应**:
```json
{
  "timeline": [
    {
      "date": "2025-11-20",
      "summary": "讨论了 Vulcan Brain 的流式重构，完成了 Sprint 4B",
      "key_topics": ["streaming", "performance", "LOD architecture"]
    },
    {
      "date": "2025-11-19",
      "summary": "设计了前端 UI 架构，确定使用 Next.js + Tailwind",
      "key_topics": ["frontend", "UI design", "Cyberpunk theme"]
    }
  ]
}
```

---

## 4. Soul (宪法) 配置接口

### `GET /api/soul/config`
**用途**: 获取当前的 Soul 配置

**响应**:
```json
{
  "constitution": "你是 Vulcan Brain - 一个有原则、有记忆、有灵魂的 AI 助手...",
  "alignment_lessons": [
    {
      "date": "2025-11-18",
      "lesson": "用户不喜欢过度工程，要保持简洁"
    }
  ],
  "tone_settings": {
    "creativity": 70,
    "safety": 85,
    "formality": 40
  }
}
```

### `POST /api/soul/update`
**用途**: 更新 Soul 配置

**请求体**:
```json
{
  "constitution": "新的宪法文本（可选）",
  "tone_settings": {
    "creativity": 80,
    "safety": 90,
    "formality": 50
  }
}
```

---

## 5. 系统状态接口

### `GET /api/system/status`
**用途**: 获取系统实时状态（GPU、VRAM、性能指标）

**响应**:
```json
{
  "gpus": [
    {"id": 0, "utilization": 98, "memory_used": 18000, "memory_total": 24000, "temperature": 72},
    {"id": 1, "utilization": 98, "memory_used": 18000, "memory_total": 24000, "temperature": 74}
  ],
  "performance": {
    "tokens_per_second": 93.9,
    "ttft_ms": 70,
    "avg_latency_ms": 5520
  },
  "context": {
    "active_tools": 4,
    "context_size_words": 205,
    "lod_enabled": true
  }
}
```

---

## 实现优先级

1. **P0 (立即)**: `/api/chat/stream` - 流式聊天（核心功能）
2. **P1 (本周)**: `/api/system/status` - 系统状态（Inspector 数据源）
3. **P2 (下周)**: `/api/memory/*` - 记忆系统
4. **P3 (下周)**: `/api/knowledge/*` - 知识库管理
5. **P4 (可选)**: `/api/soul/*` - Soul 配置

---

**后端同学请按此规范实现 FastAPI 接口。前端已准备好接收这些数据。** 🚀
