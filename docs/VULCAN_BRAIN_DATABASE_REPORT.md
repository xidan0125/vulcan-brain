# Vulcan Brain 后端数据库梳理报告

**生成时间**: 2025-11-30
**数据库**: MongoDB (vulcan_brain)
**总集合数**: 17

---

## 📊 集合统计概览

| 集合名称 | 文档数 | 用途 | 访问层 | 状态 |
|---------|--------|------|--------|------|
| `users` | 3 | 用户账户 | VulcanStore | ✅ 正常 |
| `user_souls` | 3 | 用户灵魂配置 | VulcanStore | ✅ 正常 |
| `user_genesis` | 2 | Genesis 校准数据 | VulcanStore + 直接 | ⚠️ 双重访问 |
| `user_constitution` | 1 | 用户宪法（红线/价值观） | VulcanStore | ✅ 正常 |
| `soul_twin` | 2 | 灵魂孪生体 | VulcanStore | ✅ 正常 |
| `soul_user_stats` | 4 | Soul 用户统计 | 直接 pymongo | ⚠️ 待迁移 |
| `soul_interactions` | 5 | Soul 交互记录 | 混合 | ⚠️ 双重访问 |
| `sandbox_questions` | 8 | 沙盒决策题库 | 混合 | ⚠️ 双重访问 |
| `chat_sessions` | 7 | 对话会话 | VulcanStore | ✅ 正常 |
| `agent_sessions` | 0 | Agent 会话 | VulcanStore | ✅ 正常 |
| `memories` | 0 | 用户记忆 | VulcanStore | ✅ 正常 |
| `alignment_feedback` | 3 | 对齐反馈 | VulcanStore | ✅ 正常 |
| `user_alignments` | 0 | 对齐响应 | VulcanStore | ✅ 正常 |
| `news_cache` | 2 | 新闻缓存 | 直接 pymongo | ⚠️ 待迁移 |
| `pm_projects` | 1 | 项目管理-项目 | ProjectStore | ✅ 独立 |
| `pm_tasks` | 1 | 项目管理-任务 | ProjectStore | ✅ 独立 |
| `pm_employees` | 1 | 项目管理-员工 | ProjectStore | ✅ 独立 |
| `pm_reports` | 0 | 项目管理-汇报 | ProjectStore | ✅ 独立 |

---

## 🔗 数据关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER DOMAIN                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐     1:1      ┌─────────────┐                      │
│  │  users   │─────────────►│ user_souls  │                      │
│  │          │              │             │                      │
│  │ username │              │ core_values │                      │
│  │ password │              │ redlines    │                      │
│  │ email    │              │ dimensions  │                      │
│  │ role     │              │ sync_rate   │                      │
│  └────┬─────┘              └─────────────┘                      │
│       │                                                          │
│       │ 1:1                                                      │
│       ▼                                                          │
│  ┌──────────────┐    1:1    ┌─────────────────┐                 │
│  │ user_genesis │◄─────────►│   soul_twin     │                 │
│  │              │           │                 │                 │
│  │ current_genome          │ genesis_genome  │                 │
│  │ initial_genome          │ genome          │                 │
│  │ questions_answered      │ evolution_count │                 │
│  └──────────────┘           └─────────────────┘                 │
│       │                                                          │
│       │ 1:1                                                      │
│       ▼                                                          │
│  ┌──────────────────┐                                           │
│  │ user_constitution │                                          │
│  │                   │                                          │
│  │ items: [         │                                          │
│  │   {category,     │                                          │
│  │    content}      │                                          │
│  │ ]                │                                          │
│  └──────────────────┘                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       SOUL DOMAIN                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────┐        ┌────────────────────┐            │
│  │ soul_user_stats   │   N:1  │ sandbox_questions  │            │
│  │                   │◄───────│                    │            │
│  │ user_id           │        │ _id (ObjectId)     │            │
│  │ streak_days       │        │ category           │            │
│  │ sync_progress     │        │ scenario           │            │
│  │ dimensions (6)    │        │ options[3]         │            │
│  │ data_points       │        │   - id, text       │            │
│  └─────────┬─────────┘        │   - weights (6)    │            │
│            │                  └──────────┬─────────┘            │
│            │ 1:N                         │                      │
│            ▼                             │ N:1                  │
│  ┌───────────────────┐                   │                      │
│  │ soul_interactions │◄──────────────────┘                      │
│  │                   │                                          │
│  │ user_id           │                                          │
│  │ type: "sandbox"   │                                          │
│  │ question_id       │───► FK to sandbox_questions              │
│  │ selected_option   │                                          │
│  │ weights_applied   │                                          │
│  │ dimension_changes │                                          │
│  └───────────────────┘                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       CHAT DOMAIN                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────┐        ┌───────────────────┐             │
│  │   chat_sessions   │        │  agent_sessions   │             │
│  │                   │        │                   │             │
│  │ user_id           │        │ user_id           │             │
│  │ provider          │        │ session_id        │             │
│  │ title             │        │ agent_type        │             │
│  │ messages[]        │        │ messages[]        │             │
│  │ message_count     │        │                   │             │
│  └───────────────────┘        └───────────────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      PM DOMAIN (独立)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      1:N     ┌─────────────┐                  │
│  │ pm_projects  │─────────────►│  pm_tasks   │                  │
│  │              │              │             │                  │
│  │ id           │              │ project_id  │                  │
│  │ owner_id     │              │ assignee_*  │                  │
│  └──────────────┘              └──────┬──────┘                  │
│                                       │ 1:N                     │
│                                       ▼                         │
│  ┌──────────────┐              ┌─────────────┐                  │
│  │ pm_employees │              │ pm_reports  │                  │
│  │              │              │             │                  │
│  │ feishu_open_id             │ task_id     │                  │
│  │ name         │              │ status      │                  │
│  └──────────────┘              │ notes       │                  │
│                                └─────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 详细 Schema 定义

### 1. `users` - 用户账户

```javascript
{
  _id: ObjectId,
  username: String,          // 唯一，用于登录
  password_hash: String,     // bcrypt 哈希 (⚠️ 有明文密码记录待清理)
  email: String,
  role_level: Number,        // 权限级别 (100=admin)
  display_name: String,
  feishu_open_id: String,    // 飞书 Open ID
  created_at: Date,
  last_login: Date
}

// 索引
{ username: 1 } // unique
```

### 2. `user_souls` - 灵魂配置

```javascript
{
  _id: ObjectId,
  user_id: String,           // FK → users.username
  redlines: [String],        // 红线列表
  core_values: [String],     // 核心价值观
  communication_style: {
    tone: String,            // "technical" | "casual"
    format: String,          // "bullet_points" | "prose"
    language: String         // "zh-CN" | "en-US"
  },
  risk_profile: {
    score: Number,           // 0-100
    label: String            // "保守型" | "激进型"
  },
  management_style: {
    score: Number,
    label: String
  },
  memory_namespace: String,  // 记忆命名空间
  genesis_completed: Boolean,
  sync_rate: Number,         // 同步率 0-100
  dimensions: {              // 6维度 (0-100)
    risk_appetite: Number,
    time_horizon: Number,
    strategic_drive: Number,
    people_philosophy: Number,
    control_style: Number,
    ethical_boundary: Number
  },
  created_at: Date,
  updated_at: Date
}

// 索引
{ user_id: 1 } // unique
```

### 3. `user_genesis` - Genesis 校准数据

```javascript
{
  _id: ObjectId,
  user_id: String,
  completed_at: Date,
  current_genome: {          // 当前基因组 (0-100)
    risk_appetite: Number,
    time_horizon: Number,
    strategic_drive: Number,
    people_philosophy: Number,
    control_style: Number,
    ethical_boundary: Number
  },
  initial_genome: {...},     // 初始基因组 (固定)
  questions_answered: Number,
  version: String            // "2.0"
}
```

### 4. `soul_twin` - 灵魂孪生体

```javascript
{
  _id: ObjectId,
  user_id: String,
  created_at: Date,
  evolution_count: Number,   // 进化次数
  genesis_genome: {...},     // Genesis 基因组
  genome: {...},             // 当前基因组
  last_calibrated: Date,
  sync_rate: Number          // 同步率
}
```

### 5. `soul_user_stats` - Soul 用户统计 ⚠️

```javascript
{
  _id: ObjectId,
  user_id: String,
  streak_days: Number,       // 连续打卡天数
  last_active_date: String,  // "YYYY-MM-DD"
  sync_progress: Number,     // 模型同步进度 0-1
  dimensions: {...},         // 6维度 (0-1)
  data_points_collected: Number,
  recent_topics: [String],
  created_at: Date
}

// ⚠️ 问题：与 user_souls.dimensions 数据重复
// ⚠️ 问题：直接使用 pymongo，未通过 VulcanStore
```

### 6. `sandbox_questions` - 沙盒决策题库

```javascript
{
  _id: ObjectId,
  category: String,          // "FUNDING" | "HR" | "STRATEGY" | "MARKET" | "CRISIS"
  scenario: String,          // 情境描述
  options: [{
    id: String,              // "A" | "B" | "C"
    text: String,            // 选项描述
    weights: {               // 6维度权重 (-0.3 ~ +0.3)
      risk_appetite: Number,
      time_horizon: Number,
      strategic_drive: Number,
      people_philosophy: Number,
      control_style: Number,
      ethical_boundary: Number
    }
  }],
  source_topic: String,      // 来源话题
  topic_tags: [String],
  is_active: Boolean,
  source: String,            // "seed_v2" | "ai_generated"
  created_at: Date
}
```

### 7. `soul_interactions` - Soul 交互记录

```javascript
{
  _id: ObjectId,
  user_id: String,
  type: String,              // "sandbox"
  question_id: String,       // FK → sandbox_questions._id
  selected_option: String,   // "A" | "B" | "C"
  weights_applied: {...},    // 应用的权重
  dimension_changes: {...},  // 维度变化
  created_at: Date
}
```

### 8. `chat_sessions` - 对话会话

```javascript
{
  _id: ObjectId,
  session_id: String,        // UUID
  user_id: String,
  provider: String,          // "vulcan_qwen"
  title: String,
  messages: [{
    role: String,            // "user" | "assistant"
    content: String,
    timestamp: Number        // Unix ms
  }],
  message_count: Number,
  created_at: Date,
  updated_at: Date
}

// 索引
{ user_id: 1, updated_at: -1 }
```

### 9. `agent_sessions` - Agent 会话

```javascript
{
  _id: ObjectId,
  user_id: String,
  session_id: String,
  agent_type: String,        // agent 类型
  messages: [Object],        // 最近 20 条
  created_at: Date,
  updated_at: Date
}
```

### 10. PM 集合（独立管理）

```javascript
// pm_projects
{
  _id: ObjectId,
  id: String,                // "proj-xxxx"
  name: String,
  description: String,
  owner_id: String,
  owner_name: String,
  deadline: Date,
  status: String,            // "in_progress" | "completed"
  progress: Number,
  health_score: Number,
  created_at: String
}

// pm_tasks
{
  _id: ObjectId,
  id: String,                // "task-xxxx"
  project_id: String,        // FK → pm_projects.id
  title: String,
  description: String,
  assignee_feishu_id: String,// FK → pm_employees.feishu_open_id
  assignee_name: String,
  deadline: Date,
  priority: Number,
  status: String,
  progress: Number,
  created_at: String
}

// pm_employees
{
  _id: ObjectId,
  feishu_open_id: String,    // unique
  name: String,
  department: String,
  role: String,
  created_at: String,
  updated_at: String
}

// pm_reports
{
  _id: ObjectId,
  task_id: String,           // FK → pm_tasks.id
  reporter_feishu_id: String,
  status: String,
  notes: String,
  message_id: String,
  reported_at: Date
}
```

---

## ⚠️ 发现的问题

### 1. 数据访问层不统一

| 问题 | 集合 | 现状 | 建议 |
|------|------|------|------|
| 双重访问 | `soul_user_stats` | soul_api.py 直接用 pymongo | 迁移到 VulcanStore |
| 双重访问 | `sandbox_questions` | VulcanStore + soul_api.py 直接用 | 统一使用 VulcanStore |
| 双重访问 | `soul_interactions` | VulcanStore + soul_api.py 直接用 | 统一使用 VulcanStore |
| 双重访问 | `user_genesis` | VulcanStore + soul_api.py 直接用 | 统一使用 VulcanStore |
| 未接入 | `news_cache` | soul_api.py 直接用 pymongo | 添加到 VulcanStore |

### 2. 数据冗余

| 冗余字段 | 位置1 | 位置2 | 建议 |
|---------|-------|-------|------|
| dimensions (6维度) | `user_souls` | `soul_user_stats` | 统一到 `user_souls` |
| dimensions (6维度) | `user_souls` | `user_genesis.current_genome` | 保留 genesis 作为初始值 |
| genome | `soul_twin` | `user_genesis` | 明确用途分离 |
| sync_rate | `user_souls` | `soul_twin` | 统一到一处 |

### 3. 数据一致性风险

```
问题：soul_user_stats.dimensions 使用 0-1 范围
     user_souls.dimensions 使用 0-100 范围
     user_genesis.current_genome 使用 0-100 范围

风险：不同模块读写时可能导致数据混乱

建议：统一使用 0-100 范围，在 API 层做转换
```

### 4. 安全问题 ⚠️

```javascript
// users 集合中存在明文密码
{
  "username": "admin",
  "password_hash": "vulcan2024"  // ⚠️ 这是明文！
}

建议：
1. 立即对所有明文密码进行 bcrypt 哈希
2. 字段名改为 password_hash 并确保全部为哈希值
```

### 5. 缺失索引

| 集合 | 建议添加的索引 |
|------|---------------|
| `soul_user_stats` | `{ user_id: 1 }` (unique) |
| `soul_interactions` | `{ user_id: 1, created_at: -1 }` |
| `sandbox_questions` | `{ is_active: 1, created_at: -1 }` |
| `news_cache` | `{ fetched_at: -1 }` |

---

## 📊 模块与集合访问关系

```
┌─────────────────┬────────────────────────────────────────────────────┐
│     模块        │                   访问的集合                        │
├─────────────────┼────────────────────────────────────────────────────┤
│ auth_api.py     │ users, user_souls, user_genesis                    │
│ soul_api.py     │ soul_user_stats, sandbox_questions,                │
│                 │ soul_interactions, user_genesis, news_cache        │
│ chat_api.py     │ chat_sessions                                      │
│ api_server.py   │ agent_sessions (通过 agent_session_store)          │
│ pm_api.py       │ pm_projects, pm_tasks                              │
│ project_store   │ pm_projects, pm_tasks, pm_employees, pm_reports    │
│ VulcanStore     │ users, user_souls, user_genesis, user_constitution,│
│                 │ soul_twin, chat_sessions, agent_sessions, memories,│
│                 │ alignment_feedback, user_alignments,               │
│                 │ soul_interactions, sandbox_questions               │
└─────────────────┴────────────────────────────────────────────────────┘
```

---

## ✅ 优化建议

### 短期（P0-P1）

1. **统一数据访问层**
   - 将 `soul_api.py` 中的直接 pymongo 调用迁移到 VulcanStore
   - 预计工作量：75 分钟（详见 SOUL_API_ASYNC_REFACTOR_PLAN.md）

2. **修复密码安全**
   - 对 `users` 集合中的明文密码进行哈希
   - 验证所有 password_hash 字段确实是哈希值

3. **添加缺失索引**
   - 创建上述建议的索引以提升查询性能

### 中期（P2）

4. **消除数据冗余**
   - 统一 dimensions 存储位置和数值范围
   - 明确 `soul_twin` vs `user_genesis` 的职责边界

5. **Schema 验证**
   - 为关键集合添加 MongoDB JSON Schema 验证
   - 防止无效数据写入

### 长期（P3）

6. **读写分离**
   - 考虑为高频读取集合（如 sandbox_questions）添加缓存层

7. **数据归档**
   - 对 `soul_interactions` 等增长型集合设计归档策略

---

## 📈 集合增长预估

| 集合 | 增长频率 | 预估月增量 | 归档建议 |
|------|---------|-----------|---------|
| `soul_interactions` | 高 | ~1000 docs/活跃用户 | 保留 90 天 |
| `chat_sessions` | 中 | ~100 docs/用户 | 保留 180 天 |
| `sandbox_questions` | 低 | ~50 docs (AI 生成) | 保留全部 |
| `news_cache` | 中 | ~300 docs | 保留 7 天 |

---

**报告完成** ✅
