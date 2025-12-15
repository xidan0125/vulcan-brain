# 全息数据底座架构设计 (Claude独立版)

> 作者: Claude  
> 日期: 2025-12-13  
> 状态: 初稿

---

## 1. 技术栈选型决策

### 1.1 存储方案: MongoDB (保留现有) + 新增事件集合

**决策**: 不引入新的图数据库，继续使用 MongoDB

**理由**:
1. **已有基础**: vulcan_brain 已在 MongoDB 运行，56,868封邮件已存储
2. **运维简单**: 离线环境下减少组件数量是关键，Neo4j/KùzuDB都是额外运维负担
3. **文档模型适配**: Event-Fact结构天然是嵌套文档，MongoDB的JSON存储完美匹配
4. **向量支持**: MongoDB Atlas Search支持向量索引（虽然我们离线，但可用社区方案）
5. **事务支持**: MongoDB 4.0+支持多文档事务，足够保证一致性

**新增集合**:
```
vulcan_brain.email_events     # V3事件集合
vulcan_brain.entities         # 实体主数据
vulcan_brain.attachment_cache # 附件内容缓存
```

### 1.2 推理引擎: vLLM (保留现有)

**决策**: 继续使用已部署的 vLLM + Qwen3-VL

**理由**:
1. **已部署运行**: Qwen3-VL-30B已在Docker运行，切换SGLang有迁移成本
2. **够用原则**: 虽然SGLang结构化输出更快，但我们是批处理场景，不追求实时
3. **稳定优先**: vLLM生态更成熟，问题更容易排查

**结构化输出方案**: 通过Prompt约束 + 后处理JSON解析，而非引擎层约束

### 1.3 向量检索: Qdrant (保留现有)

**决策**: 继续使用已部署的 Qdrant

**理由**:
1. V2已部署Qdrant，语义搜索已可用
2. 可为附件内容新建collection

### 1.4 编排: 纯Python脚本 (不引入Dagster/Airflow)

**决策**: 使用简单的Python脚本 + MongoDB状态标记

**理由**:
1. 我们的流程是"一次性批处理 + 增量更新"，不是复杂DAG
2. Dagster/Airflow对于当前规模过于重型
3. 用MongoDB的processing_status字段跟踪进度更直接

---

## 2. 数据模型设计

### 2.1 核心理念

- **Event-Centric**: 每封邮件 = 一个Event
- **Fact as Subdocument**: Facts嵌入Event内，不独立存储
- **Provenance First**: 每个Fact必须有来源证据

### 2.2 Event Schema

```json
{
  "_id": "EVT-2024-07-15-001",
  "event_type": "QuoteRevision",
  "timestamp": "2024-07-15T10:30:00Z",
  
  "source": {
    "type": "email",
    "email_id": "AAMkAGE1M2IyNGM2...",
    "subject": "RE: SpaceX 3K碳纤维报价V3",
    "from": "zhang@company.com",
    "to": ["procurement@spacex.com"],
    "thread_id": "THREAD-2024-06-001"
  },
  
  "state": {
    "current": "NEGOTIATING",
    "previous": "QUOTING",
    "changed_at": "2024-07-15T10:30:00Z"
  },
  
  "entities": [
    {
      "id": "ENT-ORG-SPACEX",
      "type": "Organization",
      "name": "SpaceX",
      "role": "CLIENT",
      "confidence": 0.99
    },
    {
      "id": "ENT-MAT-3KCF",
      "type": "Material",
      "name": "3K碳纤维复合材料",
      "role": "SUBJECT",
      "confidence": 0.95
    }
  ],
  
  "facts": [
    {
      "fact_id": "FACT-001",
      "attribute": "unit_price",
      "value": 350.00,
      "unit": "USD/kg",
      "data_type": "number",
      
      "conditions": [
        {"field": "annual_volume", "op": ">=", "value": 5000, "unit": "kg"},
        {"field": "incoterms", "op": "==", "value": "FOB Shanghai"}
      ],
      
      "confidence": {
        "level": "LLM_Reasoned",
        "score": 0.92,
        "reason": "正文和附件PDF一致"
      },
      
      "provenance": [
        {
          "source_type": "email_body",
          "snippet": "价格调整为350美元/公斤",
          "char_offset": [145, 168]
        },
        {
          "source_type": "attachment",
          "file_name": "Quote_V3.pdf",
          "file_hash": "sha256:abc123...",
          "page": 1,
          "bbox": {"x": 120, "y": 340, "w": 80, "h": 15},
          "ocr_text": "Unit Price: $350/kg"
        }
      ],
      
      "supersedes": "FACT-OLD-001",
      "superseded_by": null
    }
  ],
  
  "attachments_processed": [
    {
      "file_name": "Quote_V3.pdf",
      "file_hash": "sha256:abc123...",
      "content_type": "application/pdf",
      "size": 245760,
      "pages": 3,
      "processing_status": "COMPLETED",
      "extracted_at": "2024-12-13T10:00:00Z"
    }
  ],
  
  "chain": {
    "previous_event": "EVT-2024-07-08-003",
    "next_event": null,
    "root_thread": "EVT-2024-06-01-001"
  },
  
  "meta": {
    "created_at": "2024-12-13T10:00:00Z",
    "created_by": "VLM-Pipeline-v1",
    "version": 1
  }
}
```

### 2.3 Entity主数据Schema

```json
{
  "_id": "ENT-ORG-SPACEX",
  "type": "Organization",
  "canonical_name": "SpaceX",
  "aliases": ["Space X", "SpaceX Inc.", "SPACEX"],
  
  "attributes": {
    "industry": "Aerospace",
    "country": "USA"
  },
  
  "first_seen": "EVT-2023-01-15-001",
  "last_seen": "EVT-2024-07-15-001",
  "event_count": 156,
  
  "relations": [
    {
      "type": "CUSTOMER_OF",
      "target": "ENT-ORG-SELF",
      "since": "2023-01-15"
    }
  ]
}
```

### 2.4 置信度体系

| Level | Score Range | 定义 | 处理方式 |
|-------|-------------|------|----------|
| `OCR_Raw` | 0.0 - 0.6 | 仅OCR提取，未验证 | 标记待审核 |
| `LLM_Reasoned` | 0.6 - 0.9 | LLM跨源验证通过 | 可用于查询 |
| `Human_Verified` | 0.9 - 1.0 | 人工确认 | 最终可信 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    全息数据底座 V3 架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                               │
│  │ MS365 邮件   │ ──(已有)──▶ MongoDB.emails (56K)              │
│  └──────────────┘                    │                          │
│                                      │ 筛选 v2_extracted=true   │
│                                      ▼                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Phase 3: 提取流水线                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │  │
│  │  │ 附件下载器  │─▶│ 文档解析器  │─▶│ VLM 提取器  │        │  │
│  │  │ (MS Graph)  │  │ (PyMuPDF)   │  │ (Qwen3-VL)  │        │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │  │
│  │         │                │                │                │  │
│  │         ▼                ▼                ▼                │  │
│  │  ┌─────────────────────────────────────────────┐          │  │
│  │  │              融合 & 仲裁模块                 │          │  │
│  │  │  - 正文 vs 附件冲突检测                     │          │  │
│  │  │  - 来源优先级判定                           │          │  │
│  │  │  - 置信度计算                               │          │  │
│  │  └─────────────────────────────────────────────┘          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Phase 4: 构建层                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │  │
│  │  │ 实体对齐    │  │ 时序链构建  │  │ 状态机推演  │        │  │
│  │  │ (去重合并)  │  │ (prev/next) │  │ (FSM)       │        │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      存储层                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                 │  │
│  │  │ MongoDB         │  │ Qdrant          │                 │  │
│  │  │ - email_events  │  │ - event_vectors │                 │  │
│  │  │ - entities      │  │ - fact_vectors  │                 │  │
│  │  └─────────────────┘  └─────────────────┘                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Phase 5: 应用层                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │  │
│  │  │ FastAPI     │  │ RAG 查询    │  │ Streamlit   │        │  │
│  │  │ REST API    │  │ 引擎        │  │ 看板        │        │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 模块设计

### 4.1 附件下载模块

```python
# attachment_downloader.py
class AttachmentDownloader:
    """从MS Graph API下载邮件附件"""
    
    def download(self, email_id: str) -> List[Attachment]:
        """下载指定邮件的所有附件"""
        pass
    
    def cache_to_disk(self, attachment: Attachment) -> str:
        """缓存到本地磁盘，返回路径"""
        pass
```

### 4.2 文档解析模块

```python
# document_parser.py
class DocumentParser:
    """解析PDF/Excel/图片"""
    
    def parse_pdf(self, path: str) -> ParsedDocument:
        """PDF解析，返回页面+文本+坐标"""
        pass
    
    def parse_excel(self, path: str) -> ParsedDocument:
        """Excel解析，返回表格结构"""
        pass
    
    def render_page_image(self, path: str, page: int) -> bytes:
        """渲染PDF页面为图片供VLM处理"""
        pass
```

### 4.3 VLM提取模块

```python
# vlm_extractor.py
class VLMExtractor:
    """调用Qwen3-VL提取结构化信息"""
    
    def extract_facts(self, 
                      email_body: str, 
                      attachments: List[ParsedDocument]) -> List[RawFact]:
        """提取原始事实"""
        pass
    
    def _build_prompt(self, context: str) -> str:
        """构建提取Prompt"""
        pass
```

### 4.4 融合仲裁模块

```python
# fusion_arbitrator.py
class FusionArbitrator:
    """处理多源冲突"""
    
    def detect_conflicts(self, facts: List[RawFact]) -> List[Conflict]:
        """检测同一属性的不同值"""
        pass
    
    def resolve(self, conflict: Conflict) -> ResolvedFact:
        """按优先级规则解决冲突"""
        # 规则: signed_contract > draft > email_body > verbal
        pass
    
    def compute_confidence(self, fact: RawFact) -> float:
        """计算置信度分数"""
        pass
```

### 4.5 事件构建模块

```python
# event_builder.py
class EventBuilder:
    """构建完整Event文档"""
    
    def build(self, 
              email: Email, 
              facts: List[ResolvedFact],
              entities: List[Entity]) -> Event:
        """组装Event"""
        pass
    
    def link_chain(self, event: Event) -> None:
        """链接前后事件"""
        pass
    
    def update_state(self, event: Event) -> None:
        """推演业务状态"""
        pass
```

---

## 5. 核心API设计

### 5.1 事件查询

```
GET /api/v3/events/{event_id}
GET /api/v3/events?entity={entity_id}&from={date}&to={date}
GET /api/v3/events/timeline/{thread_id}
```

### 5.2 事实查询

```
GET /api/v3/facts?entity={entity_id}&attribute={attr}
GET /api/v3/facts/{fact_id}/provenance  # 返回原始证据
```

### 5.3 实体查询

```
GET /api/v3/entities/{entity_id}
GET /api/v3/entities/{entity_id}/events
GET /api/v3/entities/search?q={query}
```

### 5.4 RAG问答

```
POST /api/v3/ask
{
  "question": "SpaceX 3K碳纤维的最新报价是多少？",
  "context_limit": 10
}
```

---

## 6. 与Gemini方案的主要分歧点

| 维度 | Gemini方案 | Claude方案 | 理由 |
|------|-----------|-----------|------|
| 图数据库 | KùzuDB | MongoDB | 减少组件，Event嵌套足够 |
| 推理引擎 | 迁移SGLang | 保留vLLM | 已部署稳定，迁移有风险 |
| 编排 | Dagster | 纯Python | 规模不需要重型编排 |
| Fact存储 | 节点化 | 子文档 | 查询模式以Event为主 |

**核心原则**: 最小变更、够用即可、稳定优先
