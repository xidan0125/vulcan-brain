# Project Rongrong 工程圣经 v2.0

> 创建时间: 2025-12-26
> 状态: 开发中
> 这是项目开发的唯一权威文档，所有开发必须参照此文档执行

---

## 一、项目概述

**Project Rongrong v4.0** 是企业微信邮件智能日报系统，采用 **Filter + 2 Agent (Map-Reduce)** 架构。

### 核心设计理念
- **Filter**: 按业务意图分类（7类），使用 Coder 模型 (Port 8003)
- **Extraction Agent**: 统一提取结构化事件，使用 VL 模型 (Port 8000) 支持图片识别
- **Insight Agent**: 全局洞察聚合，生成板块总结和高管视角
- **1:1 映射**: 每封邮件（或线程）生成一个事件

### 架构演进
- v1.0: 6 Agent 分流架构（已废弃）
- **v2.0**: 2 Agent Map-Reduce 架构（当前）

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
│   IMAP 同步 → wecom_emails 集合                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Filter 层 (Coder 8003)                  │
│   7 分类: CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MANAGEMENT/       │
│          ADMIN/FILE/FILTER                                   │
│   输出 → rongrong_filter_runs.filter_result                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Map Phase: Extraction Agent (VL 8000)       │
│   单一 Agent + 通用 Prompt + category 参数                   │
│   ├── 分析型输出 (CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MGMT)     │
│   │   → {source_id, tag, style, summary, highlights}        │
│   └── 记录型输出 (ADMIN/FILE)                                │
│       → {source_id, tag, summary}                           │
│   输出 → rongrong_filter_runs.extraction_results            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Reduce Phase: Insight Agent (VL 8000)       │
│   输入: 所有结构化事件                                       │
│   输出:                                                      │
│   ├── 各板块智能总结 (module_summaries)                      │
│   └── 全局洞察 (executive_insights)                          │
│   输出 → rongrong_daily_reports                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      API + 前端展示                          │
│   复用 /api/wecom-email/* 路由                               │
│   卡片式事件展示                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、已确认的技术决策

| 决策项 | 确认方案 | 状态 | 备注 |
|--------|----------|------|------|
| Agent 架构 | 2 Agent Map-Reduce | ✅ 确认 | 替代原 6+2 方案 |
| 模型切换 | vLLM 官方 Sleep Mode API | ✅ 已验证 | 详见下方说明 |
| 附件预处理 | 批量预处理模式 | ✅ 已完成 | Phase 1 完成 |
| 预处理存储 | MongoDB (wecom_emails.processed_assets) | ✅ 已完成 | 方便前端溯源 |
| 线程聚合 | EmailLoader.get_emails_by_category_threaded() | ✅ 已完成 | 解决邮件链重复 |
| Excel转换 | libreoffice --headless | ✅ 已安装 | 服务器已配置 |
| PDF处理 | fitz (PyMuPDF) | ✅ 已验证 | email-intelligence-v3 方法 |
| API路由 | 复用 /api/wecom-email/* | 📋 设计中 | 不新建路由 |

### 处理模式：逐封处理 (2025-12-26 确认)

**设计决策**: Extraction Agent 逐封处理邮件，不做批量

**理由**:
1. 质量优先 - 每封独立分析，不受上下文干扰
2. 多模态友好 - VL 看图需要专注，批量塞图容易混乱
3. 错误隔离 - 一封出错不影响其他
4. 调试方便 - 出问题容易定位

**实现方式**:
```python
for email in emails:
    result = await extraction_agent.process_single(email, category)
    results.append(result)
```

---

### 架构决策依据 (Gemini Frontiers 2025-12-26)

**为什么从 6 Agent 简化为 2 Agent？**
1. Agent 边界应由「工具/能力」划分，而非「数据标签」
2. 6 个 Agent 输出格式完全一致，本质是同一 Agent 的不同 Prompt 策略
3. Filter 已完成分类，Agent 再分开价值减半
4. 维护 6 套 Prompt 成本高于收益

**Map-Reduce 模式优势：**
1. Map 阶段：统一提取，按需切换输出格式
2. Reduce 阶段：拥有全局视野，自然生成洞察
3. 可扩展：新增分类只需调整 Prompt，不加 Agent

### 模型切换机制 (vLLM Sleep Mode)

**官方文档**: https://docs.vllm.ai/en/latest/features/sleep_mode.html

**API 端点**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `/sleep?level=1` | POST | 卸载权重到 CPU，清 KV cache |
| `/wake_up` | POST | 唤醒模型 |
| `/is_sleeping` | GET | 返回 `{"is_sleeping": bool}` |

**关键约束**:
- ⚠️ **两模型共享 GPU，同时只能有一个 awake**
- 切换前必须先 sleep 当前模型，再 wake 目标模型
- 启动 vLLM 时需添加 `--enable-sleep-mode` 参数

---

## 四、两类输出格式

### 分析型 (CUSTOMER, SUPPLY_CHAIN, LOGISTICS, MANAGEMENT)

```json
{
  "source_id": "email_id",
  "tag": "样件申请",
  "style": "GAIN",
  "summary": "**张三** 为 **北京石墨烯** 申请 **1kg** 氧化铝纤维样件，已获批准。",
  "highlights": {
    "entities": ["张三", "北京石墨烯研究院"],
    "numbers": ["1kg"]
  }
}
```

### 记录型 (ADMIN, FILE)

```json
{
  "source_id": "email_id",
  "tag": "差旅审批",
  "summary": "张三北京出差申请已通过"
}
```

**区别：** 记录型不需要 style 和 highlights，只需列出事项。

---

## 五、数据存储设计

### 5.1 数据层级

```
wecom_emails (原始数据)
├── email_id, subject, body, from, received_at
├── attachments: [{ filename, file_path, content_type }]
└── processed_assets: [{ ... }]  ← 已实现

rongrong_filter_runs (流程数据)
├── date, company, stage
├── filter_result: { CUSTOMER: [...], ... }
└── extraction_results: { CUSTOMER: [...], ... }  ← 新结构

rongrong_daily_reports (最终产出)
├── date, company
├── module_summaries: { CUSTOMER: "...", ... }  ← 板块总结
├── executive_insights: [...]  ← 高管洞察
└── all_events: [...]  ← 所有事件
```

### 5.2 processed_assets 字段 (已实现)

```json
{
  "processed_assets": [
    {
      "source_attachment": "客户需求确认表.xlsx",
      "asset_type": "image",
      "asset_path": "email_id/xxx_page1.jpg",
      "page_number": 1,
      "width": 724,
      "height": 1024,
      "size_bytes": 61099,
      "created_at": "2025-12-26T16:14:17Z"
    }
  ],
  "processed_at": "2025-12-26T16:14:18Z"
}
```

---

## 六、开发阶段规划

### Phase 0: 基建验证 ✅ 已完成

- [x] 模型服务验证 (Coder 8003, VL 8000)
- [x] sleep/wake API 验证
- [x] 转换工具验证 (libreoffice, fitz)
- [x] 数据库验证

---

### Phase 1: Filter + 附件预处理 ✅ 已完成

- [x] Filter v15 (7分类)
- [x] AttachmentPreprocessor (Excel/PDF → PNG)
- [x] EmailLoader (含线程聚合)
- [x] processed_assets 写入 MongoDB

---

### Phase 2: Extraction Agent + Insight Agent 🔨 进行中

**目标**: 实现 Map-Reduce 架构的两个 Agent

#### 2.1 Extraction Agent
```python
class ExtractionAgent:
    """单一提取 Agent，处理所有分类"""

    async def process(
        self,
        emails: List[ThreadedEmail],
        category: str
    ) -> List[Dict]:
        """
        根据 category 切换输出格式：
        - 分析型: {source_id, tag, style, summary, highlights}
        - 记录型: {source_id, tag, summary}
        """
        pass
```

**Prompt 设计要点：**
- 单一通用 Prompt + category 参数
- 公司背景介绍（榕融新材料）
- Tag 规则：4字业务动作，禁止实体名
- 分析型 vs 记录型输出格式切换

#### 2.2 Insight Agent
```python
class InsightAgent:
    """全局洞察 Agent (Reduce 阶段)"""

    async def generate(
        self,
        all_events: Dict[str, List[Dict]]
    ) -> Dict:
        """
        输入: 各分类的事件列表
        输出: {
            "module_summaries": {"CUSTOMER": "...", ...},
            "executive_insights": ["...", "..."]
        }
        """
        pass
```

**验收标准：**
1. Extraction Agent 能处理所有 6 个分类
2. 分析型输出有 style/highlights，记录型没有
3. Insight Agent 生成有价值的板块总结和洞察

---

### Phase 3: Pipeline 主调度

**目标**: 串联所有步骤，实现端到端自动化

```python
class RongrongPipeline:
    async def run(self, company: str, date_str: str):
        # Step 1: 切换 Coder，运行 Filter
        # Step 2: 附件预处理（如有新邮件）
        # Step 3: 切换 VL，运行 Extraction Agent (6 分类)
        # Step 4: 运行 Insight Agent
        # Step 5: 写入 rongrong_daily_reports
        pass
```

**验收标准：**
1. 一键运行完整流程
2. 每步有清晰的进度输出
3. 异常有完整的错误日志

---

### Phase 4: API + 前端

**目标**: 复用现有 API，重构前端展示

- [ ] GET /api/wecom-email/report-v2?source=rongrong
- [ ] 卡片式事件展示
- [ ] 按 Style 颜色渲染
- [ ] 附件溯源功能

---

## 七、分类定义 (Filter v15)

| 分类 | 意图 | 输出类型 | 典型邮件 |
|------|------|----------|----------|
| **CUSTOMER** | 创收流 | 分析型 | 询价报价、客户需求确认表、样件申请 |
| **SUPPLY_CHAIN** | 交付流 | 分析型 | 审厂、采购订单、生产排期、品质 |
| **LOGISTICS** | 物流流 | 分析型 | 订舱、报关、货物追踪 |
| **MANAGEMENT** | 决策流 | 分析型 | 财务报表、部门预算、人力成本 |
| **ADMIN** | 行政流 | 记录型 | 机票审批、报销、用章、请假 |
| **FILE** | 文件流 | 记录型 | 扫描件、PPT分享、合同文档 |
| **FILTER** | 过滤流 | 跳过 | 系统通知、营销推广、招聘 |

---

## 八、事件样式 (Style) - 仅分析型

| Style | 含义 | 颜色 | 场景 |
|-------|------|------|------|
| **RISK** | 风险/阻碍 | 🔴 红色 | 投诉、延误、拒付、竞争威胁 |
| **GAIN** | 增长/突破 | 🟢 绿色 | 样件申请、新订单、收款、审核通过 |
| **INSIGHT** | 洞察/情报 | 🔵 蓝色 | 规格确认、市场趋势、战略调整 |
| **LOG** | 日常/流程 | ⚪ 灰色 | 物流更新、常规排期 |

---

## 九、模型配置

| 阶段 | 模型 | 端口 | 用途 |
|------|------|------|------|
| Filter | Qwen3-Coder-30B | 8003 | 文本分类，快速 |
| Extraction/Insight | Qwen3-VL-30B-Thinking | 8000 | 多模态，看图+推理 |

---

## 十、目录结构

```
project_rongrong/
├── __init__.py
├── config.py                    # ✅ 配置
├── pipeline.py                  # ❌ 待开发 - 主调度入口
│
├── services/
│   ├── __init__.py
│   ├── filter.py                # ✅ Filter v15
│   ├── vllm_client.py           # ✅ vLLM 封装 (含 sleep/wake)
│   ├── email_loader.py          # ✅ 邮件加载器 (含线程聚合)
│   └── attachment_processor.py  # ✅ 附件预处理
│
├── agents/
│   ├── __init__.py
│   ├── extraction_agent.py      # ❌ 待开发 - 统一提取 Agent
│   └── insight_agent.py         # ❌ 待开发 - 洞察 Agent
│
├── tests/
│   └── test_extraction.py       # ❌ 待开发
│
├── _archive/                    # 归档旧代码
│   ├── agents_v1/               # v1.0 架构的 Agent (已废弃)
│   │   ├── supply_chain.py
│   │   ├── logistics.py
│   │   └── management.py
│   ├── daily_report_v2.py
│   ├── daily_report_v3.py
│   └── email_threading.py
│
└── docs/
    ├── ARCHITECTURE.md
    └── ENGINEERING_BIBLE.md     # 本文档
```

---

## 十一、开发原则

### 11.1 稳健开发
- **每个 Phase 必须验收通过才能进入下一个 Phase**
- 不跳步，不抢进度
- 遇到问题先记录，解决后再继续

### 11.2 简洁优先
- 能用一个 Agent 解决就不用两个
- 能用参数切换就不用多套代码
- 复杂度是成本，简洁是收益

### 11.3 文档同步
- 代码改动同步更新本文档
- 新的技术决策先记录再实施

---

## 十二、FAQ

**Q: 为什么从 6 Agent 改为 2 Agent？**
A: 经 Gemini Frontiers 专家分析，6 Agent 是过度设计。Agent 边界应由能力划分，不是数据标签。6 个 Agent 输出格式完全一致，本质是同一 Agent 的不同 Prompt。

**Q: 分析型和记录型有什么区别？**
A: 分析型（CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MANAGEMENT）需要智能提炼，输出含 style 和 highlights。记录型（ADMIN/FILE）只需列出事项，不需要深度分析。

**Q: Insight Agent 什么时候运行？**
A: 在 Extraction Agent 处理完所有分类后运行（Reduce 阶段）。此时拥有全局视野，可以生成跨分类的洞察。

**Q: 为什么用 sleep/wake 而不是 docker stop/start？**
A: sleep/wake 是 vLLM 官方 API，切换更快（秒级），docker 操作需要分钟级。

---

## 十三、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2025-12-26 | v1.0 | 初始版本，6 Agent 架构 |
| 2025-12-26 | v1.1 | 修正模型切换机制为 vLLM 官方 Sleep Mode API |
| 2025-12-26 | v1.2 | Phase 1 完成：AttachmentPreprocessor + EmailLoader |
| 2025-12-26 | **v2.0** | **架构重构：6 Agent → 2 Agent (Map-Reduce)**；废弃原 6 个专业 Agent，改为 Extraction Agent + Insight Agent；线程聚合已完成；归档旧代码 |

