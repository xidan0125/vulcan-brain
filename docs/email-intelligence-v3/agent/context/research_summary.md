# 研究文档精华摘要

## 文档1: 全息数据底座理论 (学术派)

### 核心观点
- 数据不是二维表，而是具有"相位(时空)"和"振幅(置信度)"的全息投影
- 传统SPO三元组过于扁平，需要超图(Hypergraph)表达N元关系

### 推荐技术栈
| 组件 | 推荐 | 理由 |
|------|------|------|
| 推理引擎 | SGLang | 结构化输出比vLLM快3倍 |
| 视觉模型 | Qwen2.5-VL-72B | 开源文档理解SOTA |
| 图数据库 | KùzuDB | 嵌入式，比Neo4j快18-20倍 |
| 逻辑验证 | Clingo (ASP) | 神经符号架构的符号层 |
| 编排 | Dagster | 数据资产导向 |

### 关键设计
1. **事实节点化(Reification)**: 将"报价"提升为节点，挂载条件和元数据
2. **双时态建模**: Valid Time(合同生效时间) + Transaction Time(系统记录时间)
3. **确定性分层**: 认识论层(谁说了什么) + 本体论层(什么是真的)

---

## 文档2: 架构方案设计 (工程派)

### 核心观点
- 采用Docs2KG框架思路: 分模态提取 → 语义融合
- 三层知识图谱: MetaKG(元数据) + LayoutKG(文档结构) + SemanticKG(业务语义)

### 推荐技术栈
| 组件 | 推荐 | 理由 |
|------|------|------|
| 图数据库 | Neo4j | 生态成熟，Cypher查询强大 |
| 向量库 | FAISS/Milvus | 开源高性能 |
| 框架 | LangChain/LlamaIndex | RAG编排 |
| 模型 | Llama-3 + Qwen-VL | 文本+视觉双轨 |

### JSON Schema示例
```json
{
  "fact_id": "FACT_1001",
  "type": "MaterialProperty",
  "entity": "Alloy_X",
  "attribute": "heat_resistance",
  "value": 1200,
  "unit": "℃",
  "conditions": {"environment": "A"},
  "state": "draft",
  "confidence": "LLM_Reasoned",
  "evidence": [{
    "source_id": "EMAIL_2023_05_01_007",
    "file_name": "Spec_v1.pdf",
    "page": 5,
    "bbox": [100, 230, 400, 260]
  }],
  "event_id": "EVT_20230501_1"
}
```

---

## 文档3: Schema详细设计 (实战派)

### 核心观点
- Event-Centric: 每封邮件/每次修订 = 一个Event
- Facts作为Event的子文档，而非独立节点
- Provenance必须精确到页码和坐标

### 最终Schema模板
```json
{
  "event_id": "EVT-2024-07-001",
  "event_type": "ContractRevision",
  "timestamp": "2024-07-15T10:30:00Z",
  "state": "谈判中",
  "entities": [
    {"role": "客户", "name": "SpaceX"},
    {"role": "供应商", "name": "我方公司"},
    {"role": "材料", "id": "MAT-3KCarbonFiber"}
  ],
  "facts": [
    {
      "fact_id": "EVT-2024-07-001#PRICE",
      "attribute": "报价单价",
      "value": 350.00,
      "unit": "USD/kg",
      "confidence": "LLM_Reasoned",
      "provenance": [
        {"source": "email", "file": "Email_2024-07-15.txt", "snippet": "报价为350美元每千克"},
        {"source": "attachment", "file": "Contract_v3.pdf", "page": 2, "coords": "x:100,y:200,w:50,h:10"}
      ]
    }
  ],
  "previous_event": "EVT-2024-05-002",
  "next_event": null
}
```

### 三级置信度
1. `OCR_Raw`: 仅OCR直接提取，未经验证
2. `LLM_Reasoned`: LLM跨证据推理确认
3. `Human_Verified`: 人工审核或签署合同背书

### 冲突仲裁策略
1. 来源优先级: 签署合同 > 合同草稿 > 邮件正文 > 口头
2. 时间序列: 最新事件覆盖旧事件
3. LLM辅助: 让模型分析"哪个值在最新上下文中有效"
4. 人工兜底: 高风险字段强制人工确认

### 业务状态机
```
意向沟通 → 报价中 → 谈判中 → 待批准 → 已签约 → 已履行 → 已终止
```

---

## 三份文档的分歧点

| 维度 | 文档1 | 文档2 | 文档3 |
|------|-------|-------|-------|
| 图数据库 | KùzuDB (嵌入式) | Neo4j (服务器) | 未指定 |
| 推理引擎 | SGLang | vLLM/Transformers | 未指定 |
| Fact存储 | 独立节点 | 独立节点 | Event子文档 |
| 向量库 | KùzuDB原生 | FAISS/Milvus | 未指定 |

## 需要架构师决策的问题

1. **图数据库选型**: KùzuDB (性能) vs Neo4j (生态) vs MongoDB (已有)
2. **Fact建模**: 独立节点 vs Event子文档
3. **推理引擎**: SGLang vs vLLM (已部署)
4. **向量存储**: 独立向量库 vs 图数据库原生 vs MongoDB Atlas Search
5. **编排框架**: Dagster vs Airflow vs 纯Python脚本
