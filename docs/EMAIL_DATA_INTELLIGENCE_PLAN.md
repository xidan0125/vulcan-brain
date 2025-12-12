# 📧 邮件数据智能化开发计划 (2025)

> 创建时间: 2025-12-03
> 更新时间: 2025-12-03
> 状态: Phase 2 完成，准备 Phase 4

## 一、完整流程架构（业界最佳实践）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         邮件数据智能化流水线                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐│
│  │ 数据采集 │ → │ 数据清洗 │ → │ 实体抽取 │ → │ 向量化  │ → │ 索引  ││
│  │ (已完成) │    │ & 预处理 │    │ & NER   │    │Embedding│    │ 存储  ││
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └────────┘│
│       ↓                                                              ↓      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐│
│  │ 知识图谱 │ ← │ 关系抽取 │ ← │ 实体链接 │ ← │ 实体消歧│ ← │去重聚合││
│  │ 构建    │    │Relation  │    │ Linking │    │Resolution│    │Dedup   ││
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └────────┘│
│       ↓                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ GraphRAG │ → │ 语义搜索 │ → │ Agent   │ → │ 业务洞察 │             │
│  │/LightRAG│    │ Hybrid  │    │ 问答    │    │ Dashboard│             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、2025年最佳工具选型

| 阶段 | 推荐工具 | 备选 | 说明 |
|------|---------|------|------|
| **实体抽取 (NER)** | GLiNER | spaCy + LLM | 零样本NER，比ChatGPT快且便宜，<500M参数 |
| **关系抽取** | Relik | OpenNRE | 轻量级关系抽取框架 |
| **向量化** | text-embedding-3-small | BGE-M3, Jina | OpenAI性价比最高 |
| **向量数据库** | Qdrant | pgvector | 开源最佳性能+过滤能力 |
| **知识图谱** | Neo4j + LLM Builder | FalkorDB | 生态成熟，有LLM集成 |
| **GraphRAG** | LightRAG | MS GraphRAG | 成本仅1/100，速度快10x |
| **RAG框架** | LlamaIndex | LangChain | 数据框架更适合企业 |
| **邮件处理** | 自研 + LangGraph | - | 邮件分类、线程聚合 |

### 关键GitHub仓库
- https://github.com/microsoft/graphrag - Microsoft GraphRAG
- https://github.com/HKUDS/LightRAG - 轻量级替代方案
- https://github.com/urchade/GLiNER - 零样本NER
- https://github.com/run-llama/llama_index - RAG框架
- https://github.com/qdrant/qdrant - 向量数据库

---

## 三、分阶段开发计划

### **Phase 0: 数据准备层** ✅ 完成
- [x] MS365邮件同步
- [x] MongoDB存储
- [x] 邮件线程聚合（将回复链合并）
- [x] 去除签名/免责声明/转发历史
- [x] 历史邮件全量同步

**当前状态**: 
- 邮件数: 56,868 封
- 时间范围: 2023-01 至今 (2年)

### **Phase 1: 语义搜索层** ✅ 完成
目标: 实现找所有关于SpaceX的邮件这类查询

| 任务 | 工具 | 产出 |
|------|------|------|
| 1.1 邮件Embedding | text-embedding-3-small | ✅ 向量化50K+邮件 |
| 1.2 向量存储 | Qdrant (Docker) | ✅ 语义索引 |
| 1.3 混合搜索API | 关键词 + 向量 | ✅ /api/email/semantic-search |
| 1.4 前端集成 | Info Hub | ✅ 语义搜索框 |

### **Phase 2: 实体抽取层** ✅ 完成
目标: 从邮件中提取人名、公司、项目、金额、日期

| 任务 | 工具 | 产出 |
|------|------|------|
| 2.1 零样本NER | GLiNER (GPU) | ✅ 人名/公司/项目/金额 |
| 2.2 邮件分类 | 规则+关键词 | ✅ 销售/采购/HR/内部等 |
| 2.3 实体消歧 | 规则 + 正则化 | ✅ 合并SpaceX/Space X |
| 2.4 实体存储 | MongoDB | ✅ entities集合 |

**完成统计 (2025-12-03)**:
- 处理邮件数: 50,137 封
- 实体类型:
  - person: 83,507 (7,019 unique)
  - company: 49,663 (6,289 unique)
  - location: 34,382 (4,384 unique)
  - product: 29,047 (6,924 unique)
  - date: 27,124 (6,483 unique)
  - money: 13,073 (4,643 unique)
  - phone_number: 6,379 (1,708 unique)
  - email_address: 5,247 (1,283 unique)
  - project: 1,588 (479 unique)
- 邮件分类:
  - external: 17,505
  - internal: 10,054
  - finance: 7,701
  - sales: 6,550
  - technical: 2,914
  - hr: 2,145
  - legal: 1,975
  - marketing: 676
  - procurement: 617

**API接口**:
- GET /api/info-hub/entities/stats
- GET /api/info-hub/entities/search
- GET /api/info-hub/entities/email/{email_id}
- POST /api/info-hub/entities/extract

### **Phase 3: 知识图谱层** (待定)
目标: 构建人员-公司-项目关系网络

| 任务 | 工具 | 产出 |
|------|------|------|
| 3.1 关系抽取 | Relik / LLM | 谁联系谁、谁负责什么 |
| 3.2 图谱构建 | Neo4j | 节点+边 |
| 3.3 图谱可视化 | D3.js / Neo4j Bloom | 关系网络图 |
| 3.4 时序关系 | 边属性 | 关系演变时间线 |

### **Phase 4: GraphRAG智能层** 🔜 下一步
目标: 实现复杂问答和业务洞察

| 任务 | 工具 | 产出 |
|------|------|------|
| 4.1 LightRAG部署 | LightRAG | 图+向量混合检索 |
| 4.2 问答接口 | LlamaIndex | 上次和SpaceX谈的价格？ |
| 4.3 自动摘要 | LLM | 每日/每周邮件智能总结 |
| 4.4 洞察Dashboard | React | 客户360、销售漏斗 |

### **Phase 5: Agent自动化层** (待定)
目标: 邮件智能助手

| 任务 | 工具 | 产出 |
|------|------|------|
| 5.1 任务提取 | LangGraph Agent | 从邮件自动创建待办 |
| 5.2 智能提醒 | 规则 + LLM | 未回复重要邮件提醒 |
| 5.3 回复草稿 | RAG + 风格学习 | 基于历史风格生成回复 |
| 5.4 异常检测 | 时序分析 | 投诉升级/客户流失预警 |

---

## 四、技术架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Vulcan Brain 邮件智能                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Next.js   │  │   FastAPI   │  │   LangGraph │              │
│  │   前端      │  │   后端API   │  │   Agent     │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ┌──────┴────────────────┴────────────────┴──────┐              │
│  │              LlamaIndex / LightRAG             │              │
│  │         (RAG编排 + 知识检索 + 问答)            │              │
│  └──────┬────────────────┬────────────────┬──────┘              │
│         │                │                │                      │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐              │
│  │   Qdrant    │  │    Neo4j    │  │   MongoDB   │              │
│  │  向量存储   │  │  知识图谱   │  │  原始数据   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
│  ┌─────────────────────────────────────────────────┐            │
│  │              处理管道 (Pipeline)                 │            │
│  │  GLiNER(NER) → Relik(关系) → Embedding → Index  │            │
│  └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、优先级路线

**推荐路线**: Phase 1 → Phase 2 → Phase 4 → Phase 3 → Phase 5

(先语义搜索出效果 → 再实体抽取 → 直接上LightRAG问答 → 补知识图谱可视化)

**当前进度**: Phase 1 ✅ → Phase 2 ✅ → Phase 4 🔜

---

## 六、参考资源

- Microsoft GraphRAG: https://github.com/microsoft/graphrag
- LightRAG: https://lightrag.github.io/
- Neo4j LLM Knowledge Graph Builder: https://neo4j.com/blog/developer/llm-knowledge-graph-builder-release/
- GLiNER (零样本NER): https://github.com/urchade/GLiNER
- IBM Zshot: https://github.com/IBM/zshot
- Vector DB Comparison 2025: https://liquidmetal.ai/casesAndBlogs/vector-comparison/
- Enterprise RAG Guide 2025: https://datanucleus.dev/rag-and-agentic-ai/what-is-rag-enterprise-guide-2025
