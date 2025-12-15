# Email Intelligence V3 - 数据库Schema设计

> 设计者: Gemini Email Intelligence Expert + Claude Code
> 评审: 架构师
> 日期: 2025-12-14
> 版本: v1.2 (统一提取架构)

---

## 1. 设计目标

- **统一提取**: 正文+附件由VLM一次性处理，输出统一结构
- **来源追溯**: 每个Fact标注来源（正文/附件/页码）
- **查询效率**: 邮件级存储，一次查询获取全部
- **图分析就绪**: Schema设计便于ETL到KùzuDB
- **事件驱动**: 支持Event→Fact→Evidence三层模型
- **双时态支持**: valid_time + transaction_time

---

## 2. 核心改动 (v1.1 → v1.2)

| 维度 | v1.1 | v1.2 |
|------|------|------|
| 存储位置 | `attachments[].v3_extracted` | `v3_unified_extraction` (邮件级) |
| 提取粒度 | 单个附件 | 正文+所有附件统一 |
| facts来源 | 无标注 | `source_type` + `source_file` + `source_page` |
| 输入方式 | 单附件图片 | 正文文本 + 多附件图片一起送VLM |

---

## 3. MongoDB统一提取Schema

### 3.1 存储位置

提取结果存储在 `emails.v3_unified_extraction` 字段（邮件级别）。

### 3.2 完整Schema定义 (Pydantic)

```python
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel

class FactSource(BaseModel):
    """事实来源信息"""
    source_type: Literal["body", "attachment"]  # 正文还是附件
    source_file: Optional[str] = None           # 附件文件名（正文时为null）
    source_page: Optional[int] = None           # 页码（正文时为null）
    coords: Optional[List[float]] = None        # 坐标 [x1,y1,x2,y2]（可选）

class Fact(BaseModel):
    """单个事实"""
    fact_id: str                    # 唯一ID: "{email_id}#{key}"
    type: str                       # Amount/Date/Identifier/Company/Product/Contact/Other
    key: str                        # 字段名: "Invoice No", "Total Price"
    value: Any                      # 值
    unit: Optional[str] = None      # 单位: "USD", "kg", "pcs"

    # 来源追溯 (v1.2新增)
    source: FactSource              # 来源信息

    # Identifier专用
    identifier_category: Optional[str] = None   # FINANCE/LOGISTICS/LEGAL/PRODUCT
    identifier_subtype: Optional[str] = None    # INVOICE_NUMBER/PO_NUMBER/...

    # 置信度
    confidence: str = "LLM_Extracted"  # LLM_Extracted/LLM_Reasoned/Human_Verified

class AttachmentMeta(BaseModel):
    """附件元数据（提取时记录）"""
    attachment_id: str
    filename: str
    file_type: str                  # pdf/xlsx/png/jpg
    pages_processed: int            # 处理了几页
    size_bytes: int

class V3UnifiedExtraction(BaseModel):
    """统一提取结果（邮件级别）"""
    # 状态
    status: str                     # success/failed/partial
    extracted_at: datetime
    extraction_version: str = "v3.8"

    # 邮件整体语义
    email_type: str                 # Quotation/Invoice/Contract/Inquiry/Notification/Other
    summary: str                    # 整封邮件的一句话摘要

    # 关键日期（邮件级别）
    document_date: Optional[str] = None      # 文档日期 YYYY-MM-DD
    valid_until: Optional[str] = None        # 有效期截止（报价单常见）

    # 事实列表（核心）
    facts: List[Fact]

    # 实体列表（去重后）
    entities: Dict[str, List[str]]
    # {
    #   "companies": ["Vulcan Shield", "SpaceX"],
    #   "products": ["M-99 900tex", "Falcon 9"],
    #   "persons": ["Alan Gao", "John Smith"]
    # }

    # 处理的附件元数据
    attachments_processed: List[AttachmentMeta]

    # 处理信息
    processing_meta: Dict[str, Any]
    # {
    #   "model": "Qwen3-VL-30B-A3B-Thinking-FP8",
    #   "total_images": 5,
    #   "body_chars": 1200,
    #   "duration_seconds": 25.3,
    #   "had_json_error": false
    # }

    # 错误信息
    error: Optional[str] = None
```

### 3.3 VLM输出Schema（Guided Decoding用）

```python
VLM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "email_type": {
            "type": "string",
            "description": "邮件类型: Quotation/Invoice/Contract/Inquiry/Notification/Other"
        },
        "summary": {
            "type": "string",
            "description": "整封邮件的一句话摘要"
        },
        "document_date": {
            "type": "string",
            "description": "文档日期 YYYY-MM-DD 或 null"
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["body", "attachment"]},
                    "source_file": {"type": "string"},
                    "source_page": {"type": "integer"}
                },
                "required": ["type", "key", "value", "source_type"]
            }
        },
        "companies": {"type": "array", "items": {"type": "string"}},
        "products": {"type": "array", "items": {"type": "string"}},
        "persons": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["email_type", "summary", "facts"]
}
```

### 3.4 MongoDB文档示例

```javascript
{
  "_id": ObjectId("692e92eceb21716e16bb27da"),
  "email_id": "AAMkADUzYmMx...",
  "subject": "RE: Quotation for M-99 900tex - Updated Price",
  "from": { "name": "Alan Gao", "address": "alan.gao@vulcanshield.com" },
  "to": [...],
  "body": "Dear John,\n\nPlease find attached our updated quotation.\nNote: The price has been revised to $320/kg (previously $350/kg).\nDelivery date remains 2025-03-01.\n\nBest regards,\nAlan",
  "received_at": ISODate("2024-12-10T10:30:00Z"),

  // 附件元数据（原有）
  "attachments": [
    {
      "id": "AAMkADUzYmMxYTg3...",
      "name": "Quotation_M99_Dec2024.pdf",
      "size": 156789,
      "content_type": "application/pdf"
    }
  ],

  // V3统一提取结果（新增）
  "v3_unified_extraction": {
    "status": "success",
    "extracted_at": ISODate("2025-12-14T04:00:00Z"),
    "extraction_version": "v3.8",

    "email_type": "Quotation",
    "summary": "Vulcan Shield向客户发送M-99 900tex产品的更新报价，单价从$350降至$320/kg，交期2025-03-01",
    "document_date": "2024-12-10",
    "valid_until": "2025-01-10",

    "facts": [
      {
        "fact_id": "692e92ec#UnitPrice",
        "type": "Amount",
        "key": "Unit Price",
        "value": "320",
        "unit": "USD/kg",
        "source": {
          "source_type": "body",
          "source_file": null,
          "source_page": null
        },
        "confidence": "LLM_Extracted"
      },
      {
        "fact_id": "692e92ec#PreviousPrice",
        "type": "Amount",
        "key": "Previous Price",
        "value": "350",
        "unit": "USD/kg",
        "source": {
          "source_type": "body",
          "source_file": null,
          "source_page": null
        },
        "confidence": "LLM_Extracted"
      },
      {
        "fact_id": "692e92ec#DeliveryDate",
        "type": "Date",
        "key": "Delivery Date",
        "value": "2025-03-01",
        "source": {
          "source_type": "body",
          "source_file": null,
          "source_page": null
        },
        "confidence": "LLM_Extracted"
      },
      {
        "fact_id": "692e92ec#QuotationNo",
        "type": "Identifier",
        "key": "Quotation No",
        "value": "QT-2024-1210-001",
        "identifier_category": "FINANCE",
        "identifier_subtype": "QUOTATION_NUMBER",
        "source": {
          "source_type": "attachment",
          "source_file": "Quotation_M99_Dec2024.pdf",
          "source_page": 1
        },
        "confidence": "LLM_Extracted"
      },
      {
        "fact_id": "692e92ec#TotalAmount",
        "type": "Amount",
        "key": "Total Amount",
        "value": "32000",
        "unit": "USD",
        "source": {
          "source_type": "attachment",
          "source_file": "Quotation_M99_Dec2024.pdf",
          "source_page": 1
        },
        "confidence": "LLM_Extracted"
      },
      {
        "fact_id": "692e92ec#Quantity",
        "type": "Quantity",
        "key": "Order Quantity",
        "value": "100",
        "unit": "kg",
        "source": {
          "source_type": "attachment",
          "source_file": "Quotation_M99_Dec2024.pdf",
          "source_page": 1
        },
        "confidence": "LLM_Extracted"
      },
      {
        "fact_id": "692e92ec#Incoterms",
        "type": "Other",
        "key": "Incoterms",
        "value": "DAP Singapore",
        "source": {
          "source_type": "attachment",
          "source_file": "Quotation_M99_Dec2024.pdf",
          "source_page": 2
        },
        "confidence": "LLM_Extracted"
      }
    ],

    "entities": {
      "companies": ["Vulcan Shield Global", "SpaceX"],
      "products": ["M-99 900tex"],
      "persons": ["Alan Gao", "John Smith"]
    },

    "attachments_processed": [
      {
        "attachment_id": "AAMkADUzYmMxYTg3...",
        "filename": "Quotation_M99_Dec2024.pdf",
        "file_type": "pdf",
        "pages_processed": 2,
        "size_bytes": 156789
      }
    ],

    "processing_meta": {
      "model": "Qwen3-VL-30B-A3B-Thinking-FP8",
      "total_images": 2,
      "body_chars": 245,
      "duration_seconds": 18.5,
      "had_json_error": false
    }
  },

  // 处理状态
  "processing_status": {
    "v2_extracted": true,
    "v2_extracted_at": ISODate("2024-12-12T04:09:34Z"),
    "v3_unified_extracted": true,
    "v3_unified_extracted_at": ISODate("2025-12-14T04:00:00Z")
  }
}
```

### 3.5 MongoDB索引

```javascript
// 查询未处理的邮件
db.emails.createIndex({"processing_status.v3_unified_extracted": 1})

// 按邮件类型查询
db.emails.createIndex({"v3_unified_extraction.email_type": 1})

// 按公司实体查询
db.emails.createIndex({"v3_unified_extraction.entities.companies": 1})

// 按产品实体查询
db.emails.createIndex({"v3_unified_extraction.entities.products": 1})

// 全文搜索facts
db.emails.createIndex({"v3_unified_extraction.facts.value": "text"})
```

---

## 4. 无附件邮件迁移

对于只有正文、没有附件的邮件，从旧的 `ai_extracted` 转换：

```python
def migrate_v2_to_v3_unified(email_doc: dict) -> dict:
    """将V2正文提取结果转换为V3统一格式"""
    ai = email_doc.get("ai_extracted", {})

    # 转换entities为facts
    facts = []
    for entity in ai.get("entities", []):
        facts.append({
            "fact_id": f"{email_doc['_id']}#{entity['type']}#{entity['value'][:20]}",
            "type": entity["type"],
            "key": entity.get("context", entity["type"]),
            "value": entity["value"],
            "source": {
                "source_type": "body",
                "source_file": None,
                "source_page": None
            },
            "confidence": "LLM_Extracted"
        })

    return {
        "status": "migrated_from_v2",
        "extracted_at": ai.get("extracted_at"),
        "extraction_version": "v2_migrated",

        "email_type": ai.get("intent", {}).get("primary", "Other"),
        "summary": ai.get("summary", ""),
        "document_date": None,

        "facts": facts,
        "entities": {
            "companies": [e["value"] for e in ai.get("entities", []) if e["type"] == "COMPANY"],
            "products": [e["value"] for e in ai.get("entities", []) if e["type"] == "PRODUCT"],
            "persons": [e["value"] for e in ai.get("entities", []) if e["type"] == "PERSON"]
        },

        "attachments_processed": [],
        "processing_meta": {
            "model": ai.get("model", "unknown"),
            "migrated_from": "v2",
            "original_version": ai.get("version", "2.0")
        }
    }
```

---

## 5. KùzuDB图数据库Schema

### 5.1 节点类型（与v1.1一致，增加source字段）

```sql
CREATE NODE TABLE Email (
    email_id STRING,
    subject STRING,
    email_type STRING,
    received_at TIMESTAMP,
    summary STRING,
    PRIMARY KEY (email_id)
);

CREATE NODE TABLE Event (
    event_id STRING,
    event_type STRING,
    timestamp TIMESTAMP,
    valid_time DATE,
    transaction_time TIMESTAMP,
    summary STRING,
    PRIMARY KEY (event_id)
);

CREATE NODE TABLE FactNode (
    fact_id STRING,
    attribute STRING,
    value STRING,
    unit STRING,
    confidence STRING,
    source_type STRING,      -- "body" / "attachment"
    source_file STRING,
    source_page INT32,
    valid_time DATE,
    transaction_time TIMESTAMP,
    PRIMARY KEY (fact_id)
);

CREATE NODE TABLE Company (
    company_id STRING,
    canonical_name STRING,
    aliases STRING[],
    PRIMARY KEY (company_id)
);

CREATE NODE TABLE Product (
    product_id STRING,
    canonical_name STRING,
    aliases STRING[],
    PRIMARY KEY (product_id)
);
```

### 5.2 边类型

```sql
-- Email → Event（一封邮件触发一个事件）
CREATE REL TABLE TRIGGERS_EVENT (FROM Email TO Event);

-- Event → Fact（事件产出事实）
CREATE REL TABLE EMITS_FACT (FROM Event TO FactNode);

-- Event → Company（事件涉及公司）
CREATE REL TABLE INVOLVES_COMPANY (FROM Event TO Company);

-- Event → Product（事件涉及产品）
CREATE REL TABLE INVOLVES_PRODUCT (FROM Event TO Product);

-- Fact → Fact（条件依赖/版本链）
CREATE REL TABLE HAS_CONDITION (FROM FactNode TO FactNode, condition_type STRING);
CREATE REL TABLE SUPERSEDES (FROM FactNode TO FactNode);
```

### 5.3 ETL转换函数

```python
def transform_unified_to_graph(email_doc: dict) -> dict:
    """将统一提取结果转换为图数据"""
    v3 = email_doc.get("v3_unified_extraction")
    if not v3 or v3.get("status") not in ("success", "migrated_from_v2"):
        return None

    email_id = str(email_doc["_id"])
    event_id = f"{email_id}#EVENT"

    nodes = {
        "emails": [{
            "email_id": email_id,
            "subject": email_doc.get("subject"),
            "email_type": v3.get("email_type"),
            "received_at": email_doc.get("received_at"),
            "summary": v3.get("summary")
        }],
        "events": [{
            "event_id": event_id,
            "event_type": v3.get("email_type"),
            "timestamp": v3.get("extracted_at"),
            "valid_time": v3.get("document_date"),
            "summary": v3.get("summary")
        }],
        "facts": [],
        "companies": [],
        "products": []
    }

    edges = [("TRIGGERS_EVENT", email_id, event_id)]

    # Facts
    for fact in v3.get("facts", []):
        source = fact.get("source", {})
        nodes["facts"].append({
            "fact_id": fact["fact_id"],
            "attribute": fact["key"],
            "value": str(fact["value"]),
            "unit": fact.get("unit"),
            "confidence": fact.get("confidence", "LLM_Extracted"),
            "source_type": source.get("source_type"),
            "source_file": source.get("source_file"),
            "source_page": source.get("source_page")
        })
        edges.append(("EMITS_FACT", event_id, fact["fact_id"]))

    # Companies
    for company in v3.get("entities", {}).get("companies", []):
        company_id = normalize_name(company)
        nodes["companies"].append({
            "company_id": company_id,
            "canonical_name": company
        })
        edges.append(("INVOLVES_COMPANY", event_id, company_id))

    # Products
    for product in v3.get("entities", {}).get("products", []):
        product_id = normalize_name(product)
        nodes["products"].append({
            "product_id": product_id,
            "canonical_name": product
        })
        edges.append(("INVOLVES_PRODUCT", event_id, product_id))

    return {"nodes": nodes, "edges": edges}
```

---

## 6. Identifier分类规则（沿用v1.1）

| 类别 | 子类型 | 关键词 |
|------|--------|--------|
| FINANCE | INVOICE_NUMBER | invoice, inv no, 发票 |
| | QUOTATION_NUMBER | quotation, quote, 报价 |
| | ACCOUNT_NUMBER | account no, 账号 |
| LOGISTICS | PO_NUMBER | po no, purchase order |
| | BL_NUMBER | b/l, bl no, 提单 |
| | TRACKING_NUMBER | tracking, waybill |
| LEGAL | CONTRACT_NUMBER | contract, agreement |
| PRODUCT | SERIAL_NUMBER | serial, s/n |
| | MODEL_NUMBER | model, 型号 |

---

## 7. 提取流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                    V3.8 统一提取流程                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐                                                       │
│  │  邮件    │                                                       │
│  │ MongoDB  │                                                       │
│  └────┬─────┘                                                       │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. 准备VLM输入                                                │  │
│  │    - 正文文本                                                 │  │
│  │    - 附件图片（PDF/Excel转图片，每个最多3页）                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 2. VLM一次性提取（Guided Decoding）                           │  │
│  │    content = [                                                │  │
│  │      {"type": "text", "text": "【邮件正文】\n{body}"},        │  │
│  │      {"type": "image_url", ...},  # 附件页1                   │  │
│  │      {"type": "image_url", ...},  # 附件页2                   │  │
│  │      {"type": "text", "text": PROMPT}                         │  │
│  │    ]                                                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 3. 后处理                                                     │  │
│  │    - Identifier分类                                           │  │
│  │    - 生成fact_id                                              │  │
│  │    - 填充source信息                                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 4. 写入MongoDB                                                │  │
│  │    email.v3_unified_extraction = {...}                        │  │
│  │    email.processing_status.v3_unified_extracted = true        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. 数据处理计划

| 数据类型 | 数量 | 处理方式 |
|----------|------|----------|
| 有附件邮件 | ~8000 | VLM统一提取（正文+附件） |
| 无附件邮件 | ~5000 | 迁移V2数据 + 格式转换 |

---

## 9. 版本对比

| 维度 | v1.1 | v1.2 |
|------|------|------|
| 存储粒度 | 附件级 | 邮件级 |
| 提取方式 | 附件单独提取 | 正文+附件统一提取 |
| 来源追溯 | 无 | source_type/source_file/source_page |
| 无附件邮件 | 不处理 | V2迁移转换 |
| VLM调用 | 每个附件一次 | 每封邮件一次 |
| 上下文理解 | 无（附件孤立） | 有（正文+附件关联） |

---

*文档版本: v1.2 | 最后更新: 2025-12-14*
*统一提取架构，支持正文+附件一体化处理*
