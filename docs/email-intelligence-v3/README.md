# 📧 邮件智能 V3.0 - 全息数据底座

> 项目代号: Holographic Data Foundation  
> 创建时间: 2025-12-13  
> 状态: 规划阶段

---

## 📁 文档结构

```
email-intelligence-v3/
├── README.md                    # 本文档 - 项目总览
├── research/                    # 研究文档 (来自研究员)
│   ├── 01_holographic_foundation_theory.md   # 全息数据底座理论研究
│   ├── 02_architecture_proposal.md           # 架构方案设计
│   └── 03_schema_design.md                   # Schema详细设计
├── architecture/                # 工程架构文档
│   ├── data_model.md            # 数据模型设计
│   ├── tech_stack.md            # 技术栈选型
│   └── api_design.md            # API设计
├── progress/                    # 进度报告
│   ├── phase1_survey.md         # Phase 1: 调查阶段
│   ├── phase2_schema.md         # Phase 2: Schema设计
│   ├── phase3_extraction.md     # Phase 3: 提取实施
│   ├── phase4_construction.md   # Phase 4: 构建阶段
│   └── phase5_development.md    # Phase 5: 开发阶段
└── scripts/                     # 工具脚本
    └── attachment_profiler.py   # 附件扫描工具
```

---

## 🎯 项目目标

从 80,000+ 封历史邮件中构建**全息数据底座**：
- 不是简单的"邮件归档"，而是**知识资产化**
- 不是传统的CRUD，而是**事件溯源 + 时态建模**
- 不是扁平的三元组，而是**超图 + 条件性事实**

---

## 📊 数据概况 (Phase 1 调查结果)

| 指标 | 数值 | 说明 |
|------|------|------|
| V2已处理邮件 | 17,402 封 | 筛选后的业务邮件 |
| 有附件邮件 | 4,882 封 | 28% |
| 附件总数 | 28,724 个 | 平均每封5.9个 |
| PDF文档 | 3,823 个 | 核心目标 |
| Excel表格 | 481 个 | 结构化数据 |
| 需VLM处理 | ~5,571 个 | PDF + 大图片 |

---

## 🏗️ 五步策略

```
调查 → Schema → 提取 → 构建 → 开发
Survey → Schema → Extract → Build → Develop
```

### Phase 1: 调查 ✅ 完成
- [x] 附件地形扫描
- [x] 文件格式分布统计
- [x] 业务类型初步推断

### Phase 2: Schema ✅ 完成
- [ ] 研究员方案评审
- [ ] Event-Fact-Provenance模型定稿
- [ ] MongoDB Schema实现

### Phase 3: 提取 🚧 进行中
- [ ] Qwen3-VL管道搭建
- [ ] PDF结构化提取
- [ ] 跨模态冲突消解

### Phase 4: 构建 ⏳ 待开始
- [ ] 事实合并与消歧
- [ ] 时态链构建
- [ ] 状态机实现

### Phase 5: 开发 ⏳ 待开始
- [ ] RAG查询接口
- [ ] 溯源可视化
- [ ] Dashboard

---

## 🔧 基础设施

### 已部署
- **Vision Model**: Qwen3-VL-30B-A3B-Thinking-FP8 (Docker vLLM, port 8000)
- **Database**: MongoDB (vulcan_brain.emails)
- **Server**: vulcan (dual RTX 5090 + Threadripper)

### 待部署
- KùzuDB (嵌入式图数据库) 或 Neo4j
- SGLang (结构化输出推理引擎)

---

## 📚 核心概念

### Event-Centric Model (事件中心模型)
每封邮件/每次修订 = 一个Event，Event包含多个Facts

### Fact with Provenance (带溯源的事实)
```json
{
  "fact_id": "EVT-xxx#PRICE",
  "attribute": "报价单价",
  "value": 350.00,
  "confidence": "LLM_Reasoned",
  "provenance": {
    "file": "Contract_v3.pdf",
    "page": 2,
    "coords": "x:100,y:200,w:50,h:10"
  }
}
```

### Three-Tier Confidence (三级置信度)
1. `OCR_Raw` - 原始OCR提取
2. `LLM_Reasoned` - LLM推理确认
3. `Human_Verified` - 人工审核确认

---

## 📎 相关文档

- [V1计划文档](../EMAIL_DATA_INTELLIGENCE_PLAN.md) - 旧版Phase 1-5计划
- [数据库报告](../VULCAN_BRAIN_DATABASE_REPORT.md) - MongoDB结构
