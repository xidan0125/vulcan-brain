# 榕融日报 数据管道架构报告

> 生成日期: 2025-12-29
> 版本: v1.0

---

## 一、数据流程总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           榕融日报 数据管道                                  │
└─────────────────────────────────────────────────────────────────────────────┘

[企业微信邮箱]
    │
    │ IMAP (每15分钟)
    ▼
┌─────────────────────────────────────┐
│  wecom_emails 集合                   │  ← 原始邮件存储
│  字段: email_id, subject, body...   │
└─────────────────────────────────────┘
    │
    │ filter_binary.py (手动触发)
    ▼
┌─────────────────────────────────────┐
│  rongrong_filter_runs 集合           │
│  └─ binary_filter_result            │  ← KEEP/FILTER 列表
│      ├─ KEEP: [email_id, ...]       │
│      ├─ FILTER: [email_id, ...]     │
│      └─ stats: {total, keep, filter}│
└─────────────────────────────────────┘
    │
    │ extractor_v3.py (手动触发)
    ▼
┌─────────────────────────────────────┐
│  rongrong_filter_runs 集合           │
│  └─ extraction_results              │  ← 提取的事件
│      ├─ SALES: [{tag, summary...}]  │
│      ├─ GOVERNANCE: [...]           │
│      ├─ DELIVERY: [...]             │
│      ├─ OPERATIONS: [...]           │
│      ├─ ADMIN: [...]                │
│      └─ FILE: [...]                 │
│  └─ extraction_processed_ids        │  ← 已处理的email_id
│  └─ extraction_failed_ids           │  ← 失败的email_id
└─────────────────────────────────────┘
    │
    │ insight_agent_v6.py (手动触发)
    ▼
┌─────────────────────────────────────┐
│  rongrong_filter_runs 集合           │
│  └─ insights_v6                     │  ← CEO洞察报告
│      ├─ executive_summary           │
│      ├─ tension_points              │
│      ├─ financial_summary           │
│      ├─ key_people                  │
│      └─ watchlist                   │
└─────────────────────────────────────┘
    │
    │ API (rongrong_router.py)
    ▼
┌─────────────────────────────────────┐
│  前端页面                            │
│  https://vsg-brain.com/wecom-report │
└─────────────────────────────────────┘
```

---

## 二、存储位置详解

### 2.1 wecom_emails 集合

**用途**: 存储从企业微信邮箱同步的原始邮件

**写入者**: `services/wecom_email_collector.py`

**触发方式**: Cron 每15分钟 (`sync_wecom_emails.sh`)

**关键字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `email_id` | string | 邮件唯一标识 (MD5 hash) |
| `company` | string | 公司标识 (shanghai/guangxi) |
| `subject` | string | 邮件主题 |
| `body` | string | 邮件正文 |
| `from` | object | 发件人 {name, address} |
| `received_at` | ISODate | 接收时间 |
| `attachments` | array | 附件元数据 |
| `processed_assets` | array | 预处理后的附件 (图片等) |

**数据量**: ~400封/公司 (滚动窗口)

---

### 2.2 rongrong_filter_runs 集合

**用途**: 存储每日处理流水线的所有中间结果

**主键**: `{company, date}`

**关键字段**:

| 字段 | 写入者 | 说明 |
|------|--------|------|
| `binary_filter_result` | filter_binary.py | 过滤结果 {KEEP, FILTER, stats} |
| `binary_filter_at` | filter_binary.py | 过滤时间 |
| `extraction_results` | extractor_v3.py | 提取结果 {SALES:[], GOVERNANCE:[], ...} |
| `extraction_processed_ids` | extractor_v3.py | 已处理的email_id列表 |
| `extraction_failed_ids` | extractor_v3.py | 处理失败的email_id列表 |
| `extraction_at` | extractor_v3.py | 提取时间 |
| `insights_v6` | insight_agent_v6.py | CEO洞察报告 |
| `insights_v6_at` | insight_agent_v6.py | 洞察生成时间 |
| `deduped_extraction` | insight_agent | 去重后的提取结果 (可选) |

---

## 三、当前问题清单

### 3.1 代码版本混乱

| 问题 | 描述 | 建议 |
|------|------|------|
| 多版本extractor | `extractor_v3.py` (根目录) vs `project_rongrong/extractor.py` | 统一为一个版本 |
| 多版本insight | v4/v6/v7 同时存在 | 归档旧版本 |
| 废弃文件未清理 | extractor_retry*.py 等 | 移到_archive |

### 3.2 数据规范问题

| 问题 | 描述 | 影响 |
|------|------|------|
| source_id vs email_id | extraction_results里是source_id，wecom_emails里是email_id | 语义不一致 |
| category不一致 | extractor输出CUSTOMER/SUPPLY_CHAIN, 但前端期望SALES/GOVERNANCE | 需要映射 |
| style字段缺失 | ADMIN/FILE的style是null或undefined | 前端显示异常 |

### 3.3 Extractor过度提取

| 问题 | 数据 | 影响 |
|------|------|------|
| 一封邮件多个events | 平均2.8个events/邮件 | 数据冗余 |
| 同义tag重复 | 样件申请/申请通过/样件通过 | CEO日报杂乱 |

---

## 四、文件清理计划

### 4.1 需要归档的文件

```bash
# 根目录
insight_agent_v4.py          # 被v7取代
insight_agent_v6.py          # 被v7取代

# project_rongrong/
extractor_retry.py           # 废弃的重试版本
extractor_retry_v2.py        # 废弃的重试版本
extractor_retry_stable.py    # 废弃的重试版本
test_customer_agent.py       # 测试文件
extractor.py                 # 被 extractor_v3.py 取代

# project_rongrong/services/
filter.py                    # 被 filter_binary.py 取代
filter_binary_v7.py          # 未启用的草稿
```

### 4.2 保留的文件

```bash
# 根目录 - 核心脚本
extractor_v3.py              # 当前Extractor (稳定增量版)
insight_agent_v7.py          # 最新Insight Agent (需修复)

# project_rongrong/services/ - 服务模块
filter_binary.py             # 当前Binary Filter
email_loader.py              # 邮件加载器
attachment_processor.py      # 附件处理器
vllm_client.py               # vLLM客户端

# api/routers/
rongrong_router.py           # API路由
```

---

## 五、数据规范建议

### 5.1 统一字段命名

```python
# extraction_results 中的每个event
{
    "email_id": "xxx",       # 统一用 email_id (不是 source_id)
    "category": "SALES",     # 统一四大业务类 + ADMIN + FILE
    "tag": "样件确认",
    "style": "GAIN",         # RISK/GAIN/INSIGHT/LOG, 非业务类用 null
    "summary": "...",
    "key_number": "1kg",     # 单个关键数字 (不是数组)
    "entities": ["北京石墨烯研究院"]  # 关键实体
}
```

### 5.2 Category 标准化

| Extractor输出 | 前端显示 | 说明 |
|---------------|----------|------|
| CUSTOMER | SALES | 客户/销售 |
| SUPPLY_CHAIN | OPERATIONS | 供应链/运营 |
| LOGISTICS | DELIVERY | 物流/交付 |
| MANAGEMENT | GOVERNANCE | 管理/治理 |
| ADMIN | (不显示) | 行政琐事 |
| FILE | (不显示) | 纯文件 |

### 5.3 去重规则

同一`email_id`只保留**一个**event，选择标准：
1. 优先保留有`style`的 (RISK > GAIN > INSIGHT > LOG)
2. 优先保留`summary`更长的
3. 优先保留有`key_number`的

---

## 六、下一步行动

1. **归档废弃文件** - 按4.1清单执行
2. **修复Extractor** - 改为每封邮件只输出1个event
3. **统一字段命名** - source_id → email_id
4. **添加去重步骤** - 在insight agent前加代码去重
5. **搭建自动化** - 串联 filter → extractor → insight

---

## 附录: 执行脚本位置

| 步骤 | 脚本 | 触发方式 |
|------|------|----------|
| IMAP同步 | `services/wecom_email_collector.py` | Cron 15分钟 |
| Binary Filter | `project_rongrong/services/filter_binary.py` | 手动 |
| Extractor | `extractor_v3.py` | 手动 |
| Insight Agent | `insight_agent_v7.py` | 手动 |
| API | `api/routers/rongrong_router.py` | FastAPI |
