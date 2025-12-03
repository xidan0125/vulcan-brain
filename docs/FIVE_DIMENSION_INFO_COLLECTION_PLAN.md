# Vulcan Brain 五维度信息收集系统 - 总体规划

> 版本: v1.0
> 创建日期: 2025-12-02
> 状态: 规划中

---

## 一、项目背景

### 1.1 目标
构建一个以"员工为传感器"的企业信息数字化收集系统，通过AI大脑对收集的数据进行结构化、分析和呈现，辅助管理者决策。

### 1.2 核心理念
- **员工是传感器**：通过员工的日常工作行为自动采集信息
- **AI是大脑**：对原始信息进行结构化、分析、关联
- **管理者是决策者**：通过看板和自然语言交互获取洞察

### 1.3 适用场景
- 公司规模：30-50人
- 管理层级：3层（管理者 → 项目负责人 → 项目人员）
- 主要工具：飞书（聊天、任务、审批）+ Outlook邮箱
- 目标用户：CEO/管理者

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         【呈现层】管理者驾驶舱                             │
│   日报/周报 │ 项目看板 │ 员工画像 │ 风险预警 │ 自然语言查询                │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│                         【AI处理层】Vulcan Brain                          │
│   结构化提取 │ 实体识别 │ 情感分析 │ 关联分析 │ 风险识别 │ 报告生成        │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│                         【数据层】MongoDB                                  │
│   feishu_messages │ tasks │ emails │ approvals │ employees │ summaries   │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
┌──────────┬──────────┬───────────┴───────────┬──────────┬──────────┐
│ 项目管理  │ 聊天记录  │        邮件          │ 行政审批  │ 人员管理  │
│ 飞书任务  │ 飞书群聊  │     Outlook         │ 飞书审批  │ 通讯录    │
└──────────┴──────────┴───────────────────────┴──────────┴──────────┘
                     【信息收集层】
```

---

## 三、五维度概览

| 维度 | 数据来源 | 收集方式 | 核心价值 | 优先级 |
|------|---------|---------|---------|--------|
| 1. 项目管理 | 飞书任务 | API定时同步 + 聊天AI识别 | 进度追踪、卡点发现 | P0 |
| 2. 聊天记录 | 飞书群聊 | Webhook全量收集 | 业务信息提取、决策记录 | P0 |
| 3. 邮件 | Outlook | Graph API定时同步 | 外部沟通、合同/审批 | P1 |
| 4. 行政审批 | 飞书审批 | Webhook实时推送 | 流程统计、异常监控 | P1 |
| 5. 人员管理 | 飞书通讯录 + 行为聚合 | API同步 + 自动计算 | 员工画像、活跃度 | P2 |

---

## 四、各维度详细设计

### 4.1 项目管理（飞书任务）

#### 数据收集
| 数据类型 | 收集方式 | 频率 |
|---------|---------|------|
| 任务列表 | Task v2 API | 每天同步 |
| 任务状态变更 | Webhook事件订阅 | 实时 |
| 卡点/风险 | 聊天AI识别 + @机器人上报 | 实时 |
| 从消息创建任务 | AI识别待办 → 确认创建 | 实时 |

#### 数据结构
```javascript
tasks: {
  _id: ObjectId,
  task_guid: String,           // 飞书任务ID
  summary: String,             // 任务标题
  description: String,
  creator: {id, name},
  assignees: [{id, name}],     // 执行者
  due: {date, is_all_day},
  status: "todo" | "in_progress" | "done",
  completed_at: Date,
  origin: {type, message_id},  // 来源
  synced_at: Date
}
```

#### AI增强
- 从聊天识别待办事项，建议创建任务
- 自动关联任务与相关消息
- 识别卡点和风险

---

### 4.2 聊天记录

#### 数据收集
| 数据类型 | 收集方式 | 频率 |
|---------|---------|------|
| 群聊消息 | Webhook全量收集 | 实时 |
| 私聊消息 | 不收集（隐私） | - |
| 主动汇报 | @机器人触发 | 实时 |
| 日报提醒 | 定时推送 | 每天17:00 |

#### 数据结构
```javascript
feishu_messages: {
  _id: ObjectId,
  message_id: String,          // 飞书消息ID
  chat_id: String,             // 群聊ID
  chat_name: String,
  sender: {id, name},
  content: String,
  content_type: String,
  extracted: {                 // AI提取
    is_business: Boolean,
    topics: [String],
    entities: [String],
    intent: String,
    action_items: [String],
    related_task: String
  },
  timestamp: Date
}
```

#### AI增强
- 判断消息是否业务相关
- 提取话题、实体、待办
- 关联到任务/项目
- 情感分析

---

### 4.3 邮件

#### 数据收集
| 数据类型 | 收集方式 | 频率 |
|---------|---------|------|
| 收/发邮件 | Outlook Graph API | 每小时 |
| 紧急邮件 | 转发给机器人 | 实时 |

#### 数据结构
```javascript
emails: {
  _id: ObjectId,
  email_id: String,            // Outlook邮件ID
  from: {address, name},
  to: [{address, name}],
  subject: String,
  body_preview: String,
  has_attachments: Boolean,
  attachments: [{name, size}],
  is_internal: Boolean,
  extracted: {                 // AI提取
    summary: String,
    topics: [String],
    action_items: [String],
    urgency: String
  },
  received_at: Date
}
```

#### AI增强
- 自动生成邮件摘要
- 识别紧急程度
- 提取待办事项
- 关联到项目/任务

---

### 4.4 行政审批

#### 数据收集
| 数据类型 | 收集方式 | 频率 |
|---------|---------|------|
| 审批流程 | 飞书审批Webhook | 实时 |
| 审批结果 | Webhook回调 | 实时 |

#### 数据结构
```javascript
approvals: {
  _id: ObjectId,
  instance_id: String,         // 审批实例ID
  approval_code: String,       // 审批定义code
  type: "leave" | "expense" | "purchase" | "contract" | "other",
  title: String,
  applicant: {id, name},
  status: "pending" | "approved" | "rejected" | "cancelled",
  content: {                   // 根据类型不同
    // 请假
    leave_type, start_date, end_date, days, reason,
    // 报销
    amount, category,
    // 采购
    items: [{name, quantity, price}]
  },
  approvers: [{id, name, status, time}],
  created_at: Date,
  completed_at: Date
}
```

#### 统计分析
- 审批效率统计
- 费用汇总
- 异常审批预警

---

### 4.5 人员管理

#### 数据收集
| 数据类型 | 收集方式 | 频率 |
|---------|---------|------|
| 基础信息 | 飞书通讯录API | 每天同步 |
| 活跃度 | 从各维度数据聚合计算 | 每天计算 |
| 员工画像 | AI分析生成 | 每周更新 |

#### 数据结构
```javascript
employees: {
  _id: String,                 // 飞书用户ID
  name: String,
  email: String,
  department: String,
  position: String,
  leader_id: String,
  activity: {
    last_active: Date,
    week_stats: {
      messages_sent: Number,
      tasks_completed: Number,
      tasks_assigned: Number,
      approvals_submitted: Number
    },
    month_stats: {...}
  },
  profile: {                   // AI生成画像
    skills: [String],
    work_style: String,
    active_projects: [String],
    collaboration_score: Number
  },
  synced_at: Date
}
```

#### 员工画像维度
- 技能/专长（从任务类型推断）
- 工作风格（从活跃时间、回复速度推断）
- 协作关系（从@和任务分配推断）
- 活跃度趋势

---

## 五、AI呈现层

### 5.1 日报/周报自动生成

```javascript
daily_summaries: {
  date: String,
  type: "daily" | "weekly",
  projects: [{
    name, progress_change, updates, blockers, health
  }],
  team_activity: {
    most_active: [{id, name, score}],
    no_report: [{id, name}]
  },
  approvals: {
    pending, approved_today, total_expense
  },
  summary: String,             // AI生成摘要
  highlights: [String],
  risks: [String]
}
```

### 5.2 自然语言查询

支持的查询示例：
- "上周销售部完成了哪些任务？"
- "XX项目现在进展如何？"
- "本月报销总额是多少？"
- "谁最近比较忙？"

### 5.3 风险预警

预警类型：
- 任务逾期预警
- 项目卡点预警
- 审批超时预警
- 员工异常预警（突然不活跃）

---

## 六、开发计划

### 阶段一：基础设施（1周）
- [ ] MongoDB集合创建和索引
- [ ] 飞书机器人权限申请
- [ ] Outlook API配置

### 阶段二：聊天记录收集（3天）
- [ ] 飞书消息Webhook接收
- [ ] 消息存储到MongoDB
- [ ] 基础AI结构化提取

### 阶段三：项目管理（3天）
- [ ] 飞书任务API同步
- [ ] 任务状态变更监听
- [ ] 聊天→任务关联

### 阶段四：邮件收集（3天）
- [ ] Outlook Graph API对接
- [ ] 定时同步任务
- [ ] 邮件AI摘要

### 阶段五：审批数据（2天）
- [ ] 飞书审批Webhook
- [ ] 审批数据结构化

### 阶段六：人员管理（2天）
- [ ] 通讯录同步
- [ ] 活跃度计算
- [ ] 员工画像生成

### 阶段七：呈现层（5天）
- [ ] 日报/周报生成
- [ ] 管理者看板
- [ ] 自然语言查询
- [ ] 移动端适配

---

## 七、技术选型

| 组件 | 技术 | 说明 |
|------|-----|------|
| 后端 | Python FastAPI | 现有Vulcan Brain |
| 数据库 | MongoDB | 现有，存储在/data/fast |
| AI模型 | Qwen3:30b-a3b | 本地Ollama |
| 消息队列 | - | 暂不需要，数据量小 |
| 定时任务 | APScheduler | Python内置 |
| 前端 | Next.js | 现有vulcan-ui |

---

## 八、数据保留策略

| 数据类型 | 保留时间 | 说明 |
|---------|---------|------|
| 聊天记录 | 1年 | TTL索引自动清理 |
| 邮件 | 1年 | TTL索引自动清理 |
| 任务 | 永久 | 重要业务数据 |
| 审批 | 3年 | 合规要求 |
| 员工画像 | 永久 | 持续更新 |
| 日报/周报 | 2年 | 历史查询 |

---

## 九、隐私与权限

### 9.1 数据收集告知
- 员工需知情同意聊天记录收集
- 建议在群聊公告说明

### 9.2 权限控制
- 当前阶段：仅管理者可见
- 后期可扩展：按角色分权限

---

## 十、下一步行动

1. **确认本规划文档** ✅
2. **逐维度详细设计** - 每个维度开发前单独确认
3. **按优先级开发** - P0 → P1 → P2

---

## 变更记录

| 日期 | 版本 | 变更内容 |
|------|-----|---------|
| 2025-12-02 | v1.0 | 初始规划 |

