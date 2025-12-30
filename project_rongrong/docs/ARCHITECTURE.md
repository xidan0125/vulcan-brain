# Project Rongrong 架构文档

> 最后更新: 2025-12-26
> 状态: 开发中

---

## 一、项目概述

**Project Rongrong** 是企业微信邮件智能日报系统 v4.0，采用 Filter + 6 Agent 架构。

### 核心理念
- **Filter**: 按业务意图分类（7类），使用 Coder 模型 (Port 8003)
- **Agent**: 按分类提取结构化事件，使用 VL 模型 (Port 8000) 支持图片识别
- **1:1 映射**: 每封邮件生成一个事件，后续再聚合

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
│   services/wecom_email_collector.py                         │
│   IMAP 同步 → wecom_emails 集合                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Filter 层 (Coder 8003)                  │
│   project_rongrong/services/filter.py                       │
│   7 分类: CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MANAGEMENT/       │
│          ADMIN/FILE/FILTER                                   │
│   输出 → rongrong_filter_runs.filter_result                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Agent 层 (VL 8000)                      │
│   project_rongrong/agents/                                  │
│   6 个 Agent 并行处理各自分类的邮件                          │
│   支持多模态: 邮件正文 + 附件图片 → 结构化 JSON              │
│   输出 → rongrong_filter_runs.agent_results                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      API 层                                  │
│   复用 /api/wecom-email/report-v2 路由                      │
│   数据源切换到 rongrong 输出                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      前端展示                                │
│   /wecom-report 页面                                        │
│   卡片式事件展示 (待重构)                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、目录结构

### 目标结构
```
project_rongrong/
├── __init__.py
├── config.py                    # ✅ 配置
├── pipeline.py                  # ❌ 待开发 - 主调度入口
│
├── services/
│   ├── __init__.py
│   ├── filter.py                # ✅ Filter v15 (7分类)
│   ├── vllm_client.py           # ✅ vLLM 封装
│   └── attachment_processor.py  # ❌ 待迁移 - VLM 附件处理
│
├── agents/
│   ├── __init__.py
│   ├── base.py                  # ❌ 待开发 - Agent 基类
│   ├── customer.py              # 🔨 开发中 - CUSTOMER Agent
│   ├── supply_chain.py          # ❌ 待开发
│   ├── logistics.py             # ❌ 待开发
│   ├── management.py            # ❌ 待开发
│   ├── admin.py                 # ❌ 待开发
│   └── file.py                  # ❌ 待开发
│
├── api/
│   └── router.py                # ❌ 待开发 - API 路由
│
├── tests/
│   └── test_customer.py         # ✅ 测试脚本 (原 test_customer_agent.py)
│
├── _archive/                    # 归档参考代码
│   ├── daily_report_v2.py
│   ├── daily_report_v3.py
│   └── email_threading.py
│
└── docs/
    └── ARCHITECTURE.md          # 本文档
```

---

## 四、数据模型

### 4.1 输入: wecom_emails 集合
```json
{
  "email_id": "15b42a52457c...",
  "company": "shanghai",
  "subject": "客户需求信息确认表-北京石墨烯1225",
  "from": "\"董雪瑞\" <dongxuerui@rongrongnm.com>",
  "body": "附件为氧化铝纤维针刺毯确认表，烦请备货...",
  "received_at": "2025-12-25T...",
  "is_filtered": false,
  "attachments": [
    {
      "filename": "客户需求信息确认表-北京石墨烯1225.png",
      "file_path": "shanghai/2025-12/15b42a52.../xxx.png"
    }
  ]
}
```

### 4.2 Filter 输出: rongrong_filter_runs 集合
```json
{
  "date": "2025-12-25",
  "company": "shanghai",
  "stage": "filter",
  "total_emails": 101,
  "filter_result": {
    "CUSTOMER": ["email_id_1", "email_id_2", ...],
    "SUPPLY_CHAIN": [...],
    "LOGISTICS": [...],
    "MANAGEMENT": [...],
    "ADMIN": [...],
    "FILE": [...],
    "FILTER": [...]
  },
  "agent_results": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### 4.3 Agent 输出: rongrong_filter_runs.agent_results
```json
{
  "agent_results": {
    "CUSTOMER": [
      {
        "source_id": "15b42a52457c...",
        "tag": "需求确认",
        "style": "GAIN",
        "summary": "董雪瑞为北京石墨烯研究院申请的氧化铝纤维针刺毯样件已获批...",
        "highlights": {
          "entities": ["董雪瑞", "北京石墨烯研究院"],
          "numbers": ["1kg", "2025-12-26"]
        }
      }
    ],
    "SUPPLY_CHAIN": [...],
    ...
  }
}
```

---

## 五、分类定义 (Filter v15)

| 分类 | 意图 | 典型邮件 |
|------|------|----------|
| **CUSTOMER** | 创收流 - 拓展客户、推进订单 | 询价报价、客户需求确认表、样件申请 |
| **SUPPLY_CHAIN** | 交付流 - 采购+制造+质量 | 审厂、采购订单、生产排期、品质 |
| **LOGISTICS** | 物流流 - 运输进出口 | 订舱、报关、货物追踪 |
| **MANAGEMENT** | 决策流 - 高层经营 | 财务报表、部门预算、人力成本 |
| **ADMIN** | 行政流 - 运营活动 | 机票审批、报销、用章、请假 |
| **FILE** | 文件流 - 文档传输 | 扫描件、PPT分享、合同文档 |
| **FILTER** | 过滤流 - 噪音 | 系统通知、营销推广、招聘 |

---

## 六、事件样式 (Style)

| Style | 含义 | 颜色建议 |
|-------|------|----------|
| **RISK** | 风险/阻碍 | 红色 |
| **GAIN** | 增长/突破 | 绿色 |
| **INSIGHT** | 洞察/情报 | 蓝色 |
| **LOG** | 日常/流程 | 灰色 |

---

## 七、模型切换

| 阶段 | 模型 | 端口 | 说明 |
|------|------|------|------|
| Filter | Qwen3-Coder-30B | 8003 | 文本分类，快 |
| Agent | Qwen3-VL-30B-Thinking | 8000 | 多模态，能看图 |

**切换命令**:
```bash
# Filter 用 Coder
docker stop qwen3-vl && docker start qwen3-coder

# Agent 用 VL
docker stop qwen3-coder && docker start qwen3-vl
```

---

## 八、开发进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1: Filter v15 | ✅ 完成 | 7分类，已验证 |
| Phase 2: CUSTOMER Agent | ✅ 完成 | 多模态，已验证 |
| Phase 2: 其他 5 Agent | ❌ 待开发 | |
| Phase 3: Pipeline 调度 | ❌ 待开发 | 模型切换 + 并行 |
| Phase 4: API 层 | ❌ 待开发 | 替换数据源 |
| Phase 5: 前端重构 | ❌ 待开发 | 卡片式展示 |

---

## 九、历史代码归档

以下代码从 `services/` 移动到 `project_rongrong/_archive/`:

| 文件 | 原因 | 参考价值 |
|------|------|----------|
| daily_report_v2.py | 被 rongrong 替代 | Pipeline 流程 |
| daily_report_v3.py | 未完成的设计稿 | 多 Agent 架构思路 |
| email_threading.py | rongrong 不用线程聚合 | 邮件链算法 |

以下代码可删除:
- `daily_report.py` - 老版本
- `wecom_email_summarizer.py` - 功能重复
- `wecom_report_generator.py` - 只是包装

---

## 十、待办事项

1. [ ] 迁移 `attachment_processor.py` 到 `project_rongrong/services/`
2. [ ] 创建 `agents/base.py` Agent 基类
3. [ ] 开发其他 5 个 Agent (SUPPLY_CHAIN, LOGISTICS, MANAGEMENT, ADMIN, FILE)
4. [ ] 开发 `pipeline.py` 主调度
5. [ ] 开发 API 路由
6. [ ] 前端卡片重构
