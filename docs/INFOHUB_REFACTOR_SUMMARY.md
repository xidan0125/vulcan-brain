# InfoHub 重构总结

## 概述

InfoHub 是 Vulcan Brain 的核心功能模块，为 CEO 提供五维度企业信息一览 dashboard。

本次重构完成时间：2025-12-10

## 架构变更

### 后端 API (Python/FastAPI)

**改进前：** 单文件 `info_hub_api.py` (685行)

**改进后：** 模块化架构
```
api/info_hub/
├── __init__.py          # 主路由注册
├── schemas/             # Pydantic 数据模型
│   ├── common.py        # 通用模型 (APIResponse, PaginatedResponse)
│   ├── daily.py         # 日报统一结构 (DailyReport)
│   ├── chat.py          # 聊天模型
│   ├── email.py         # 邮件模型
│   ├── people.py        # 人员模型 (含活跃度评分)
│   └── approval.py      # 审批模型
├── daily.py             # 日报 API
├── chat.py              # 聊天 API
├── email.py             # 邮件 API
├── people.py            # 人员 API (含活跃度算法)
└── approval.py          # 审批 API
```

### 前端 (TypeScript/Next.js)

**新增：**
```
vulcan-ui/src/
├── types/
│   └── info-hub.ts      # TypeScript 类型定义
├── hooks/
│   └── useInfoHub.ts    # React Hooks (useDailyReport等)
└── components/info-hub/
    ├── index.ts
    ├── DimensionCard.tsx    # 维度卡片
    ├── StatCard.tsx         # 统计卡片
    ├── AIInsightCard.tsx    # AI 洞察卡片
    ├── ItemList.tsx         # 通用列表
    ├── DateNavigator.tsx    # 日期导航
    └── ChatSummaryCard.tsx  # 聊天摘要
```

## API 端点

### 日报 API `/api/info-hub/daily`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/daily/{date}` | 获取指定日期日报 |
| GET | `/daily/latest` | 获取最新日报 |
| POST | `/daily/generate` | 生成日报 (支持 force 覆盖) |
| GET | `/daily/overview` | 获取日报概览 |

### 聊天 API `/api/info-hub/chat`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/chat/list` | 聊天列表 |
| GET | `/chat/{chat_id}` | 聊天详情 |
| GET | `/chat/{chat_id}/messages` | 原始消息 |
| POST | `/chat/{chat_id}/analyze` | 触发分析 |

### 人员 API `/api/info-hub/people`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/people/dashboard` | 人员仪表盘 |
| GET | `/people/list` | 人员列表 (含活跃度评分) |
| GET | `/people/{user_id}` | 人员详情 |
| PATCH | `/people/{user_id}` | 更新人员信息 |
| POST | `/people/sync` | 同步 MS365 |
| GET | `/people/stats/activity` | 活跃度统计 |

### 审批 API `/api/info-hub/approval`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/approval/dashboard` | 审批仪表盘 |
| GET | `/approval/list` | 审批列表 |
| GET | `/approval/{instance_code}` | 审批详情 |
| POST | `/approval/collect` | 收集飞书审批 |
| POST | `/approval/analyze` | AI 分析 |

### 邮件 API `/api/info-hub/email`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/email/list` | 邮件列表 |
| GET | `/email/{email_id}` | 邮件详情 |
| GET | `/email/contacts` | 高频联系人 |
| POST | `/email/sync` | 同步 MS365 |

## 活跃度评分算法

```python
def calculate_activity_score(person):
    """
    评分范围: 0-100

    权重分配:
    - 邮件发送量: 40% (主动沟通能力)
    - 邮件接收量: 30% (被动沟通参与)
    - 最近活跃度: 30% (时效性)

    活跃等级:
    - high: >= 70分
    - medium: 40-69分
    - low: 10-39分
    - inactive: < 10分
    """
```

## 数据统一格式

日报返回统一结构 `DailyReport`:
```typescript
interface DailyReport {
  date: string;
  generated_at?: string;
  chat: ChatDimensionData;
  email: EmailDimensionData;
  people: PeopleDimensionData;
  approval: ApprovalDimensionData;
  project: ProjectDimensionData;
  overview: DimensionOverview;
}
```

## 归档文件

- `_archive/api_legacy/info_hub_api.py.bak` - 旧版单文件 API

## 访问地址

- 前端: https://vsg-brain.com/info-hub/daily-report
- API: https://api.vsg-brain.com/api/info-hub/

## 待办事项

- [ ] 项目维度 (Phase 2)
- [ ] 搜索/LightRAG 功能 (未来)
