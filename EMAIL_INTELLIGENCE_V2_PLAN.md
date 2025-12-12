# Email Intelligence V2.0 - 领域驱动架构设计

> **项目代号**: Email Intelligence V2.0 (Domain-Driven Design)
> **创建日期**: 2025-12-11
> **最后更新**: 2025-12-11
> **架构模式**: DDD + Simplified Event Sourcing + GraphRAG
> **状态**: 设计阶段

---

## 一、设计哲学

### 1.1 核心原则

**"宁慢勿错，数据为王"**

我们采用 **领域驱动设计 (Domain-Driven Design)** 而非通用实体模型，原因是：

1. **B2B 业务是强状态机的** - Order 必须有 `Draft → Confirmed → Shipped → Paid` 的严格流转
2. **通用模型会变成垃圾场** - V1 的 `entities` 集合 90% 数据是 "unknown" 类型
3. **AI 需要强类型约束** - 告诉 LLM "提取一个 Fulfillment" 比 "提取一个 Entity" 准确率高数量级

### 1.2 架构决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据模型 | 领域对象 (非通用实体) | 业务语义清晰，查询高效 |
| 事件存储 | 简化版 (status_history 数组) | MongoDB 双写问题，避免过度设计 |
| 关系存储 | 内嵌引用 (refs 字段) | 减少 JOIN，查询性能好 |
| AI 提取 | 预定义类型 + 强 Schema | 参考 GraphRAG 最佳实践 |

### 1.3 参考资料

- [Microsoft GraphRAG](https://microsoft.github.io/graphrag/) - Entity Types 必须预定义
- [MongoDB Event Sourcing](https://www.mongodb.com/blog/post/event-sourcing-with-mongodb) - 简化版更适合 MongoDB
- [Azure DDD Domain Analysis](https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis) - Bounded Context 划分
- [Blue Yonder Supply Chain KG](https://www.businesswire.com/news/home/20250505924588/en/) - 供应链知识图谱实践

---

## 二、领域模型设计

### 2.1 Bounded Contexts (限界上下文)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Email Intelligence V2.0                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   PARTY     │    │   PRODUCT   │    │ COMPLIANCE  │             │
│  │   Context   │    │   Context   │    │   Context   │             │
│  │             │    │             │    │             │             │
│  │ • companies │    │ • products  │    │ • docs      │             │
│  │ • contacts  │    │ • specs     │    │ • expiry    │             │
│  │ • relations │    │ • aliases   │    │ • alerts    │             │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘             │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            │                                        │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    FULFILLMENT Context                       │   │
│  │                      (核心聚合根)                             │   │
│  │                                                              │   │
│  │   ┌─────────┐     ┌─────────┐     ┌─────────┐              │   │
│  │   │ Order   │────▶│Shipment │────▶│ Invoice │              │   │
│  │   │ (PO/SO) │     │ (物流)  │     │ (财务)  │              │   │
│  │   └─────────┘     └─────────┘     └─────────┘              │   │
│  │        │               │               │                    │   │
│  │        └───────────────┴───────────────┘                    │   │
│  │                        │                                    │   │
│  │                        ▼                                    │   │
│  │              ┌─────────────────┐                           │   │
│  │              │  status_history │  (简化版 Event Sourcing)  │   │
│  │              └─────────────────┘                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            │                                        │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    INTELLIGENCE Context                      │   │
│  │                                                              │   │
│  │   ┌──────────────┐    ┌──────────────┐                     │   │
│  │   │ email_events │    │ action_items │                     │   │
│  │   │ (邮件→对象)  │    │ (AI→人工)    │                     │   │
│  │   └──────────────┘    └──────────────┘                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 集合总览

| 集合名 | 类型 | 数量级 | 说明 |
|--------|------|--------|------|
| `parties` | 业务对象 | ~2,000 | 公司 + 核心联系人 |
| `products` | 业务对象 | ~500 | SKU + 规格 + 别名 |
| `fulfillments` | 聚合根 | ~5,000 | 订单/交付任务 (状态机) |
| `shipments` | 业务对象 | ~8,000 | 物流/运输记录 |
| `finance_docs` | 业务对象 | ~10,000 | 发票/付款单 |
| `compliance_docs` | 业务对象 | ~500 | 合规文档 (W-9等) |
| `email_events` | 事件流 | ~60,000 | 邮件→业务对象映射 |
| `action_items` | 待办 | ~1,000 | AI 提取的待办事项 |
| `entity_merge_queue` | 系统 | ~200 | 待人工确认的实体合并建议 |

---

## 三、Schema 详细设计

### 3.1 `parties` - 商业伙伴 (公司+联系人)

**设计决策**: 公司和联系人放在同一集合，用 `party_type` 区分。
**理由**: 避免跨表 JOIN，联系人天然属于公司。

```javascript
// Collection: parties
// 索引: party_type, domain, canonical_name, aliases
{
  "_id": ObjectId,
  "party_type": "COMPANY|PERSON",

  // ===== 基础信息 =====
  "canonical_name": "SpaceX",                    // 标准名称
  "aliases": ["Space X", "spacex.com", "SPACEX"], // 别名列表 (用于匹配)
  "domain": "spacex.com",                        // 邮箱域名

  // ===== 业务属性 (仅 COMPANY) =====
  "company_info": {
    "relationship": "CUSTOMER|SUPPLIER|LOGISTICS|PARTNER|INTERNAL",
    "industry": "aerospace|automotive|electronics|other",
    "tier": "STRATEGIC|KEY|NORMAL|INACTIVE",     // 客户分级
    "region": "US|JP|CN|EU|OTHER",
    "tax_id": "XX-XXXXXXX",                      // 税号 (敏感)
    "payment_terms": "NET30|NET60|PREPAID",
    "credit_limit": 100000,
    "currency": "USD"
  },

  // ===== 联系人信息 (仅 PERSON) =====
  "person_info": {
    "email": "john.doe@spacex.com",
    "title": "Procurement Manager",
    "department": "Supply Chain",
    "phone": "+1-xxx-xxx-xxxx",
    "belongs_to_company": ObjectId,              // 关联公司
    "is_primary_contact": true                   // 是否主要联系人
  },

  // ===== 健康度指标 =====
  "health": {
    "score": 85,                                 // 0-100 综合健康度
    "last_interaction": ISODate,
    "interaction_count_30d": 12,
    "open_issues_count": 2,
    "risk_flags": ["PAYMENT_DELAY", "COMPLIANCE_EXPIRING"]
  },

  // ===== Entity Resolution (实体消歧) =====
  "entity_resolution": {
    "canonical_id": ObjectId | null,             // 如果是别名记录，指向主记录
    "is_canonical": true,                        // 是否为主记录 (默认 true)
    "merge_history": [                           // 合并历史 (审计用)
      {
        "merged_from_id": ObjectId,
        "merged_at": ISODate,
        "merged_by": "auto|manual",
        "confidence": 0.92,
        "match_type": "DOMAIN_EXACT|NAME_FUZZY|AI_SUGGEST",
        "evidence": "domain match: spacex.com"
      }
    ],
    "resolution_status": "CANONICAL|ALIAS|PENDING_REVIEW"
  },

  // ===== 数据血缘 =====
  "provenance": {
    "source": "LEGACY_MIGRATION|EMAIL_EXTRACTION|MANUAL",
    "source_email_ids": [ObjectId],              // 数据来源邮件
    "confidence": 0.95,
    "last_verified": ISODate,
    "verified_by": "system|human"
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.parties.createIndex({ "party_type": 1, "canonical_name": 1 }, { unique: true })
db.parties.createIndex({ "aliases": 1 })
db.parties.createIndex({ "domain": 1 })
db.parties.createIndex({ "company_info.relationship": 1 })
db.parties.createIndex({ "company_info.tier": 1 })
db.parties.createIndex({ "person_info.email": 1 })
db.parties.createIndex({ "person_info.belongs_to_company": 1 })
db.parties.createIndex({ "health.score": -1 })
// Entity Resolution 索引
db.parties.createIndex({ "entity_resolution.canonical_id": 1 })
db.parties.createIndex({ "entity_resolution.is_canonical": 1 })
db.parties.createIndex({ "entity_resolution.resolution_status": 1 })
```

---

### 3.2 `products` - 产品/SKU

**设计决策**: 产品是独立实体，不嵌入订单。
**理由**: 产品需要独立维护规格、别名，支持跨订单复用。

```javascript
// Collection: products
// 索引: sku_code, canonical_name, aliases
{
  "_id": ObjectId,
  "sku_code": "B70-TI-3MM",                      // 内部SKU
  "canonical_name": "B70 Titanium Sheet 3mm",
  "aliases": ["B70", "B-70", "B70钛板"],         // 各种叫法

  // ===== 产品规格 =====
  "specs": {
    "category": "RAW_MATERIAL|COMPONENT|ASSEMBLY|SERVICE",
    "material": "Titanium Alloy",
    "thickness": "3mm",
    "temperature_rating": "1600°C",
    "certifications": ["AS9100", "NADCAP"],
    "custom_fields": {}                          // 灵活扩展
  },

  // ===== 供应链信息 =====
  "supply_chain": {
    "primary_supplier_id": ObjectId,             // 主供应商
    "lead_time_days": 45,
    "min_order_qty": 100,
    "unit": "sqm|pcs|kg",
    "hs_code": "8108.90",                        // 海关编码
    "export_controlled": true,                   // 是否出口管制
    "itar_controlled": true                      // ITAR 管制
  },

  // ===== 统计信息 =====
  "stats": {
    "total_orders": 156,
    "total_quantity": 50000,
    "last_ordered": ISODate,
    "avg_unit_price": 125.50,
    "top_customers": [ObjectId, ObjectId]
  },

  // ===== 数据血缘 =====
  "provenance": {
    "source": "LEGACY_MIGRATION|EMAIL_EXTRACTION|ERP_SYNC|MANUAL",
    "source_email_ids": [ObjectId],
    "confidence": 0.9,
    "last_verified": ISODate
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.products.createIndex({ "sku_code": 1 }, { unique: true })
db.products.createIndex({ "canonical_name": 1 })
db.products.createIndex({ "aliases": 1 })
db.products.createIndex({ "specs.category": 1 })
db.products.createIndex({ "supply_chain.export_controlled": 1 })
```

---

### 3.3 `fulfillments` - 交付任务 (核心聚合根)

**设计决策**: 这是系统的"脊梁"，串联订单、物流、财务。
**状态机**: `NEW → CONFIRMED → PRODUCING → SHIPPING → DELIVERED → INVOICED → PAID → CLOSED`

```javascript
// Collection: fulfillments
// 索引: current_status, customer_id, client_po, created_at
{
  "_id": ObjectId,

  // ===== 订单标识 =====
  "client_po": "PO-SPX-9988",                    // 客户PO号
  "internal_so": "SO-2025-001",                  // 内部SO号
  "quote_ref": "QT-2025-088",                    // 关联报价单

  // ===== 状态机 (核心!) =====
  "current_status": "SHIPPING",
  "current_stage": "LOGISTICS",                  // 大阶段: SALES→ENGINEERING→PRODUCTION→LOGISTICS→FINANCE
  "is_blocked": false,
  "block_reason": null,

  // ===== 状态历史 (简化版 Event Sourcing) =====
  "status_history": [
    {
      "status": "NEW",
      "stage": "SALES",
      "timestamp": ISODate("2025-10-01T08:00:00Z"),
      "changed_by": "system",
      "trigger_email_id": ObjectId,              // 触发此变更的邮件
      "reason": "收到客户询价",
      "evidence_snippet": "We would like to request a quote for..."
    },
    {
      "status": "CONFIRMED",
      "stage": "SALES",
      "timestamp": ISODate("2025-10-05T10:30:00Z"),
      "changed_by": "system",
      "trigger_email_id": ObjectId,
      "reason": "客户确认PO",
      "evidence_snippet": "Please find attached our PO#SPX-9988..."
    },
    {
      "status": "SHIPPING",
      "stage": "LOGISTICS",
      "timestamp": ISODate("2025-11-20T14:00:00Z"),
      "changed_by": "system",
      "trigger_email_id": ObjectId,
      "reason": "Expeditors 确认发货",
      "evidence_snippet": "Shipment dispatched, tracking#..."
    }
  ],

  // ===== 关联方 =====
  "refs": {
    "customer_id": ObjectId,                     // → parties (COMPANY)
    "customer_contact_id": ObjectId,             // → parties (PERSON)
    "sales_rep": "Alice",                        // 内部销售
    "project_code": "STARSHIP-2025"              // 项目代码
  },

  // ===== 产品明细 =====
  "line_items": [
    {
      "product_id": ObjectId,                    // → products
      "sku": "B70-TI-3MM",
      "description": "B70 Titanium Sheet",
      "quantity": 500,
      "unit": "sqm",
      "unit_price": 125.50,
      "currency": "USD",
      "total": 62750.00
    }
  ],

  // ===== 金额汇总 =====
  "financials": {
    "subtotal": 62750.00,
    "tax": 0,
    "shipping_cost": 1500.00,
    "total": 64250.00,
    "currency": "USD",
    "payment_terms": "NET30",
    "paid_amount": 0,
    "outstanding": 64250.00
  },

  // ===== 时间节点 =====
  "dates": {
    "order_date": ISODate,
    "required_date": ISODate,                    // 客户要求交期
    "promised_date": ISODate,                    // 我方承诺交期
    "actual_ship_date": ISODate,
    "actual_delivery_date": ISODate,
    "invoice_date": ISODate,
    "payment_due_date": ISODate,
    "closed_date": ISODate
  },

  // ===== 关联文档 =====
  "linked_docs": {
    "shipment_ids": [ObjectId],                  // → shipments
    "invoice_ids": [ObjectId],                   // → finance_docs
    "compliance_doc_ids": [ObjectId],            // → compliance_docs
    "attachment_ids": [ObjectId]                 // → GridFS 或 S3
  },

  // ===== 风险与合规 =====
  "compliance": {
    "export_license_required": true,
    "export_license_status": "APPROVED|PENDING|NOT_REQUIRED",
    "itar_controlled": true,
    "required_docs": ["W-9", "COO", "COA"],
    "missing_docs": ["COA"],
    "compliance_score": 80                       // 合规完整度
  },

  // ===== 数据血缘 =====
  "provenance": {
    "created_from_email_id": ObjectId,           // 首次创建来源
    "last_updated_from_email_id": ObjectId,
    "ai_confidence": 0.92,
    "human_verified": false,
    "verification_notes": ""
  },

  // ===== 元数据 =====
  "tags": ["urgent", "spacex", "q4-2025"],
  "notes": "客户要求空运，成本客户承担",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.fulfillments.createIndex({ "client_po": 1 })
db.fulfillments.createIndex({ "internal_so": 1 }, { unique: true, sparse: true })
db.fulfillments.createIndex({ "current_status": 1 })
db.fulfillments.createIndex({ "current_stage": 1 })
db.fulfillments.createIndex({ "is_blocked": 1 })
db.fulfillments.createIndex({ "refs.customer_id": 1 })
db.fulfillments.createIndex({ "dates.required_date": 1 })
db.fulfillments.createIndex({ "dates.payment_due_date": 1 })
db.fulfillments.createIndex({ "compliance.missing_docs": 1 })
db.fulfillments.createIndex({ "created_at": -1 })
```

**状态机定义**:
```
状态流转规则:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  NEW ─────▶ CONFIRMED ─────▶ PRODUCING ─────▶ READY_TO_SHIP        │
│   │             │                │                  │               │
│   │             │                │                  ▼               │
│   │             │                │            SHIPPING              │
│   │             │                │                  │               │
│   │             │                │                  ▼               │
│   │             │                │            DELIVERED             │
│   │             │                │                  │               │
│   │             │                │                  ▼               │
│   │             │                │            INVOICED              │
│   │             │                │                  │               │
│   │             │                │                  ▼               │
│   │             │                │              PAID                │
│   │             │                │                  │               │
│   │             │                │                  ▼               │
│   │             │                │             CLOSED               │
│   │             │                │                                  │
│   ▼             ▼                ▼                                  │
│ CANCELLED   CANCELLED       CANCELLED                               │
│                                                                     │
│ 任何状态都可以标记 is_blocked = true                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.4 `shipments` - 物流运输

**设计决策**: 独立于 fulfillments，因为一个订单可能多次发货。

```javascript
// Collection: shipments
{
  "_id": ObjectId,

  // ===== 物流标识 =====
  "tracking_number": "1Z999AA10123456784",
  "carrier": "UPS|FEDEX|DHL|EXPEDITORS|SF|OTHER",
  "carrier_ref": "EXP-2025-12345",               // 承运商内部编号
  "service_type": "EXPRESS|STANDARD|FREIGHT",

  // ===== 关联订单 =====
  "fulfillment_id": ObjectId,                    // → fulfillments
  "fulfillment_po": "PO-SPX-9988",               // 冗余，方便查询

  // ===== 状态 =====
  "current_status": "IN_TRANSIT",
  // BOOKED → PICKED_UP → IN_TRANSIT → CUSTOMS_HOLD → CUSTOMS_CLEARED → OUT_FOR_DELIVERY → DELIVERED

  "status_history": [
    {
      "status": "BOOKED",
      "timestamp": ISODate,
      "location": "Shanghai, CN",
      "trigger_email_id": ObjectId,
      "notes": "Booking confirmed"
    },
    {
      "status": "CUSTOMS_HOLD",
      "timestamp": ISODate,
      "location": "Los Angeles, US",
      "trigger_email_id": ObjectId,
      "notes": "Missing HS code documentation",
      "is_exception": true                       // 异常标记
    }
  ],

  // ===== 路线信息 =====
  "route": {
    "origin": {
      "city": "Shanghai",
      "country": "CN",
      "address": "..."
    },
    "destination": {
      "city": "Hawthorne",
      "country": "US",
      "address": "1 Rocket Rd, Hawthorne, CA"
    },
    "via": ["Hong Kong", "Los Angeles"]          // 中转站
  },

  // ===== 时间 =====
  "dates": {
    "booked_date": ISODate,
    "pickup_date": ISODate,
    "etd": ISODate,                              // 预计离港
    "eta": ISODate,                              // 预计到达
    "actual_departure": ISODate,
    "actual_arrival": ISODate
  },

  // ===== 货物信息 =====
  "cargo": {
    "packages": 5,
    "gross_weight_kg": 250,
    "volume_cbm": 1.5,
    "declared_value": 62750.00,
    "currency": "USD",
    "hs_codes": ["8108.90"],
    "dangerous_goods": false
  },

  // ===== 费用 =====
  "costs": {
    "freight": 1200.00,
    "insurance": 150.00,
    "customs_duty": 0,
    "other": 150.00,
    "total": 1500.00,
    "currency": "USD",
    "paid_by": "SHIPPER|CONSIGNEE"
  },

  // ===== 异常处理 =====
  "exceptions": [
    {
      "type": "CUSTOMS_HOLD|DELAY|DAMAGE|LOST",
      "reported_at": ISODate,
      "resolved_at": ISODate,
      "description": "Customs hold due to missing documentation",
      "resolution": "Provided additional COO",
      "email_ids": [ObjectId, ObjectId]
    }
  ],

  // ===== 数据血缘 =====
  "provenance": {
    "source": "EMAIL_EXTRACTION|CARRIER_API|MANUAL",
    "source_email_ids": [ObjectId],
    "ai_confidence": 0.88
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.shipments.createIndex({ "tracking_number": 1 })
db.shipments.createIndex({ "fulfillment_id": 1 })
db.shipments.createIndex({ "current_status": 1 })
db.shipments.createIndex({ "dates.eta": 1 })
db.shipments.createIndex({ "carrier": 1 })
db.shipments.createIndex({ "exceptions.type": 1 })
```

---

### 3.5 `finance_docs` - 财务单据

**设计决策**: 发票、付款单、Credit Note 统一存储。

```javascript
// Collection: finance_docs
{
  "_id": ObjectId,

  // ===== 单据标识 =====
  "doc_type": "INVOICE|PAYMENT|CREDIT_NOTE|DEBIT_NOTE",
  "doc_number": "INV-2025-001234",
  "external_ref": "SPX-PAY-9988",                // 对方单据号

  // ===== 关联 =====
  "fulfillment_id": ObjectId,
  "fulfillment_po": "PO-SPX-9988",               // 冗余
  "party_id": ObjectId,                          // 付款方/收款方

  // ===== 金额 =====
  "amount": {
    "subtotal": 62750.00,
    "tax": 0,
    "total": 62750.00,
    "currency": "USD"
  },

  // ===== 状态 =====
  "status": "DRAFT|SENT|RECEIVED|PARTIAL|PAID|OVERDUE|CANCELLED",
  "payment_status": {
    "paid_amount": 30000.00,
    "outstanding": 32750.00,
    "payments": [
      {
        "date": ISODate,
        "amount": 30000.00,
        "method": "WIRE|CHECK|CREDIT_CARD",
        "reference": "WT-12345",
        "source_email_id": ObjectId
      }
    ]
  },

  // ===== 日期 =====
  "dates": {
    "issue_date": ISODate,
    "due_date": ISODate,
    "received_date": ISODate,                    // 收到对方单据的日期
    "paid_date": ISODate
  },

  // ===== 明细 (可选) =====
  "line_items": [
    {
      "description": "B70 Titanium Sheet",
      "quantity": 500,
      "unit_price": 125.50,
      "amount": 62750.00
    }
  ],

  // ===== 附件 =====
  "attachments": [
    {
      "filename": "INV-2025-001234.pdf",
      "storage_path": "s3://vulcan-docs/invoices/...",
      "uploaded_at": ISODate
    }
  ],

  // ===== 数据血缘 =====
  "provenance": {
    "source": "EMAIL_EXTRACTION|ERP_SYNC|MANUAL",
    "source_email_ids": [ObjectId],
    "ai_confidence": 0.95
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.finance_docs.createIndex({ "doc_type": 1, "doc_number": 1 }, { unique: true })
db.finance_docs.createIndex({ "fulfillment_id": 1 })
db.finance_docs.createIndex({ "party_id": 1 })
db.finance_docs.createIndex({ "status": 1 })
db.finance_docs.createIndex({ "dates.due_date": 1 })
db.finance_docs.createIndex({ "payment_status.outstanding": -1 })
```

---

### 3.6 `compliance_docs` - 合规文档

**设计决策**: 独立管理，支持到期提醒。

```javascript
// Collection: compliance_docs
{
  "_id": ObjectId,

  // ===== 文档标识 =====
  "doc_type": "W9|W8|COO|COA|EXPORT_LICENSE|ITAR_LICENSE|ISO_CERT|NADCAP|OTHER",
  "doc_name": "W-9 Form 2025",
  "doc_number": "W9-SPX-2025",

  // ===== 关联方 =====
  "party_id": ObjectId,                          // 文档所属公司
  "party_name": "SpaceX",                        // 冗余

  // ===== 有效期 =====
  "validity": {
    "issue_date": ISODate,
    "expiry_date": ISODate("2026-12-31"),
    "is_valid": true,
    "days_until_expiry": 385,                    // 计算字段，定时更新
    "status": "VALID|EXPIRING_SOON|EXPIRED|REVOKED"
  },

  // ===== 文件存储 =====
  "file": {
    "filename": "SpaceX_W9_2025.pdf",
    "storage_path": "s3://vulcan-compliance/w9/...",
    "file_size": 102400,
    "mime_type": "application/pdf",
    "uploaded_at": ISODate
  },

  // ===== 使用记录 =====
  "usage": {
    "fulfillment_ids": [ObjectId, ObjectId],     // 使用此文档的订单
    "last_used": ISODate,
    "usage_count": 15
  },

  // ===== 提醒设置 =====
  "alerts": {
    "alert_days_before": [90, 60, 30, 7],        // 提前多少天提醒
    "alert_recipients": ["alice@company.com"],
    "last_alert_sent": ISODate
  },

  // ===== 数据血缘 =====
  "provenance": {
    "source": "EMAIL_EXTRACTION|MANUAL_UPLOAD",
    "source_email_id": ObjectId,
    "ai_confidence": 0.85,
    "verified_by": "Alice",
    "verified_at": ISODate
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.compliance_docs.createIndex({ "party_id": 1, "doc_type": 1 })
db.compliance_docs.createIndex({ "validity.expiry_date": 1 })
db.compliance_docs.createIndex({ "validity.status": 1 })
db.compliance_docs.createIndex({ "validity.days_until_expiry": 1 })
```

---

### 3.7 `email_events` - 邮件→业务对象映射

**设计决策**: 轻量级中间表，解耦邮件和业务对象。
**作用**: 一封邮件可能同时更新多个业务对象，此表记录映射关系。

```javascript
// Collection: email_events
{
  "_id": ObjectId,

  // ===== 来源邮件 =====
  "email_id": ObjectId,                          // → emails
  "email_subject": "Re: PO-SPX-9988 Shipping Update",
  "email_date": ISODate,
  "email_from": "logistics@expeditors.com",

  // ===== AI 分析结果 =====
  "classification": {
    "intent": "SHIPPING_UPDATE|ORDER_CONFIRM|QUOTE_REQUEST|COMPLIANCE|INVOICE|OTHER",
    "sub_intent": "tracking_update",
    "confidence": 0.92,
    "model": "qwen3:30b-a3b"
  },

  // ===== 影响的业务对象 =====
  "affects": [
    {
      "collection": "fulfillments",
      "object_id": ObjectId,
      "object_ref": "PO-SPX-9988",
      "action": "STATUS_UPDATE|CREATE|UPDATE_FIELD",
      "changes": {
        "field": "current_status",
        "old_value": "PRODUCING",
        "new_value": "SHIPPING"
      }
    },
    {
      "collection": "shipments",
      "object_id": ObjectId,
      "object_ref": "1Z999AA10123456784",
      "action": "CREATE",
      "changes": null
    }
  ],

  // ===== 提取的实体 (快照) =====
  "extracted_entities": [
    {"type": "PO_NUMBER", "value": "PO-SPX-9988", "confidence": 0.98},
    {"type": "TRACKING_NUMBER", "value": "1Z999AA10123456784", "confidence": 0.95},
    {"type": "COMPANY", "value": "SpaceX", "matched_party_id": ObjectId},
    {"type": "DATE", "value": "2025-12-15", "context": "ETA"}
  ],

  // ===== 提取的 Action Items =====
  "extracted_actions": [
    {
      "action": "更新系统中的发货状态",
      "assignee_hint": "operations",
      "urgency": "LOW",
      "created_action_item_id": ObjectId         // → action_items
    }
  ],

  // ===== 处理状态 =====
  "processing": {
    "status": "PENDING|PROCESSING|COMPLETED|FAILED|SKIPPED",
    "processed_at": ISODate,
    "error_message": null,
    "retry_count": 0
  },

  "created_at": ISODate
}
```

**索引设计**:
```javascript
db.email_events.createIndex({ "email_id": 1 }, { unique: true })
db.email_events.createIndex({ "email_date": -1 })
db.email_events.createIndex({ "classification.intent": 1 })
db.email_events.createIndex({ "affects.collection": 1, "affects.object_id": 1 })
db.email_events.createIndex({ "processing.status": 1 })
```

---

### 3.8 `action_items` - AI 生成的待办事项

**设计决策**: AI 提议，人工确认/执行。
**模式**: `OPEN → IN_PROGRESS → COMPLETED` 或 `OPEN → DISMISSED`

```javascript
// Collection: action_items
{
  "_id": ObjectId,

  // ===== 待办类型 =====
  "type": "COMPLIANCE_ALERT|PAYMENT_OVERDUE|SHIPMENT_DELAY|REPLY_NEEDED|APPROVAL_NEEDED|FOLLOW_UP|RISK_WARNING",
  "priority": "CRITICAL|HIGH|MEDIUM|LOW",
  "status": "OPEN|IN_PROGRESS|COMPLETED|DISMISSED|AUTO_RESOLVED",

  // ===== 内容 =====
  "title": "SpaceX W-9 文档将于 30 天后过期",
  "description": "W-9 文档有效期至 2026-01-15，需要在到期前获取新版本。",

  // ===== 来源上下文 =====
  "context": {
    "trigger_type": "COMPLIANCE_EXPIRY|EMAIL_RECEIVED|SCHEDULE|MANUAL",
    "source_email_id": ObjectId,
    "source_email_event_id": ObjectId,
    "related_objects": [
      {"collection": "compliance_docs", "object_id": ObjectId},
      {"collection": "parties", "object_id": ObjectId}
    ]
  },

  // ===== AI 建议的操作 =====
  "suggested_action": {
    "action_type": "SEND_EMAIL|UPDATE_RECORD|CREATE_TASK|ESCALATE|NONE",
    "draft_email": {
      "to": "tax@spacex.com",
      "subject": "Request for Updated W-9 Form",
      "body": "Dear SpaceX Team,\n\nOur records indicate that..."
    },
    "ai_confidence": 0.85
  },

  // ===== 分配 =====
  "assignment": {
    "assignee": "alice@company.com",
    "assigned_at": ISODate,
    "due_date": ISODate("2025-12-20")
  },

  // ===== 处理记录 =====
  "resolution": {
    "resolved_at": ISODate,
    "resolved_by": "Alice",
    "resolution_type": "ACTIONED|DISMISSED|AUTO_RESOLVED",
    "notes": "已发送邮件请求更新",
    "follow_up_action_id": ObjectId              // 如果产生新的待办
  },

  // ===== 评分因子 (用于排序) =====
  "scoring": {
    "base_score": 50,
    "urgency_bonus": 30,                         // 紧急度加分
    "financial_bonus": 10,                       // 涉及金额
    "compliance_bonus": 20,                      // 合规相关
    "customer_tier_bonus": 15,                   // 客户等级
    "total_score": 125                           // 最终优先级分数
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.action_items.createIndex({ "status": 1, "scoring.total_score": -1 })
db.action_items.createIndex({ "type": 1, "status": 1 })
db.action_items.createIndex({ "assignment.assignee": 1, "status": 1 })
db.action_items.createIndex({ "assignment.due_date": 1 })
db.action_items.createIndex({ "context.source_email_id": 1 })
```

---

### 3.9 `entity_merge_queue` - 实体合并队列

**设计决策**: 独立集合存储待人工确认的实体合并建议。
**作用**: Entity Resolution 过程中，置信度不足的匹配会进入此队列，等待人工审核。

```javascript
// Collection: entity_merge_queue
{
  "_id": ObjectId,

  // ===== 状态 =====
  "status": "PENDING|APPROVED|REJECTED|AUTO_MERGED",

  // ===== 合并建议 =====
  "merge_suggestion": {
    "source_party_id": ObjectId,         // 待合并的记录 (将变成别名)
    "source_name": "Space X Corp",
    "source_aliases": ["Space X Corp"],

    "target_party_id": ObjectId,         // 合并目标 (主记录)
    "target_name": "SpaceX",
    "target_aliases": ["SpaceX", "spacex.com"]
  },

  // ===== 匹配证据 =====
  "match_evidence": {
    "match_type": "DOMAIN_EXACT|NAME_FUZZY|TOKEN_OVERLAP|AI_SUGGEST",
    "confidence": 0.72,                  // 低于阈值(0.80)才进入队列
    "details": {
      "domain_match": false,
      "name_similarity": 0.85,           // Levenshtein 相似度
      "token_overlap": 0.67,             // 词元重叠率
      "ai_reasoning": "Both refer to Elon Musk's space company"
    },
    "common_emails": [                   // 共同出现在哪些邮件中
      {"email_id": ObjectId, "subject": "Re: SpaceX Order"},
      {"email_id": ObjectId, "subject": "Space X Corp PO#123"}
    ]
  },

  // ===== 风险评估 =====
  "risk_assessment": {
    "impact_level": "HIGH|MEDIUM|LOW",
    "affected_fulfillments": 5,          // 会影响多少订单
    "affected_shipments": 3,
    "affected_finance_docs": 8,
    "warning": "合并后将影响 SpaceX 的健康度评分计算"
  },

  // ===== 审核 =====
  "review": {
    "reviewed_by": "alice@company.com",
    "reviewed_at": ISODate,
    "decision": "APPROVE|REJECT",
    "rejection_reason": "这是两个不同的实体：SpaceX 和 Space X Corp (子公司)",
    "notes": "..."
  },

  // ===== 自动处理 =====
  "auto_processing": {
    "eligible_for_auto_merge": false,    // 是否满足自动合并条件
    "auto_merge_blocked_reason": "置信度低于 0.80",
    "scheduled_auto_reject_at": ISODate  // 30天未处理自动拒绝
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**索引设计**:
```javascript
db.entity_merge_queue.createIndex({ "status": 1, "created_at": -1 })
db.entity_merge_queue.createIndex({ "merge_suggestion.source_party_id": 1 })
db.entity_merge_queue.createIndex({ "merge_suggestion.target_party_id": 1 })
db.entity_merge_queue.createIndex({ "match_evidence.confidence": -1 })
db.entity_merge_queue.createIndex({ "auto_processing.scheduled_auto_reject_at": 1 })
```

---

### 3.10 `emails` 集合增强 (现有集合)

**设计决策**: 在现有 `emails` 集合上增加 `ai_extracted` 字段。

```javascript
// 在现有 emails 文档中新增字段
{
  // ... 现有字段保持不变 ...

  // ===== V2.0 新增：AI 提取结果 =====
  "ai_extracted": {
    "version": "2.0",
    "model": "qwen3:30b-a3b",
    "extracted_at": ISODate,

    // 意图分类
    "intent": {
      "primary": "SHIPPING_UPDATE",
      "secondary": ["status_notification"],
      "confidence": 0.94
    },

    // 紧急度和情感
    "urgency": "MEDIUM",
    "sentiment": "NEUTRAL",

    // 提取的业务实体
    "entities": [
      {
        "type": "PO_NUMBER",
        "value": "PO-SPX-9988",
        "normalized": "PO-SPX-9988",
        "confidence": 0.98,
        "matched_object": {
          "collection": "fulfillments",
          "object_id": ObjectId
        }
      },
      {
        "type": "TRACKING_NUMBER",
        "value": "1Z999AA10123456784",
        "confidence": 0.95
      },
      {
        "type": "COMPANY",
        "value": "SpaceX",
        "normalized": "SpaceX",
        "confidence": 0.99,
        "matched_object": {
          "collection": "parties",
          "object_id": ObjectId
        }
      },
      {
        "type": "DATE",
        "value": "December 15, 2025",
        "normalized": "2025-12-15",
        "context": "ETA",
        "confidence": 0.92
      },
      {
        "type": "AMOUNT",
        "value": "$62,750.00",
        "normalized": 62750.00,
        "currency": "USD",
        "confidence": 0.90
      }
    ],

    // 提取的待办事项
    "action_items": [
      {
        "action": "确认收货后通知财务开票",
        "assignee_hint": "finance",
        "deadline_hint": "收货后3天内",
        "urgency": "MEDIUM"
      }
    ],

    // 主题标签
    "topics": ["shipping", "tracking", "logistics"],

    // 合规标记
    "compliance_flags": [],

    // 财务信息
    "financial": {
      "has_amount": true,
      "amounts": [62750.00],
      "currency": "USD",
      "payment_terms": null
    },

    // 摘要
    "summary": "Expeditors 通知 PO-SPX-9988 已发货，追踪号 1Z999AA10123456784，预计 12月15日 到达。",

    // 关键句子
    "key_sentences": [
      "Your shipment has been dispatched",
      "Tracking number: 1Z999AA10123456784",
      "Estimated arrival: December 15, 2025"
    ]
  },

  // ===== V2.0 新增：处理状态 =====
  "processing_status": {
    "v2_extracted": true,
    "v2_extracted_at": ISODate,
    "v2_event_created": true,
    "v2_event_id": ObjectId,                     // → email_events
    "v2_objects_updated": ["fulfillments:xxx", "shipments:yyy"]
  }
}
```

**新增索引**:
```javascript
db.emails.createIndex({ "ai_extracted.intent.primary": 1 })
db.emails.createIndex({ "ai_extracted.urgency": 1 })
db.emails.createIndex({ "ai_extracted.entities.type": 1, "ai_extracted.entities.value": 1 })
db.emails.createIndex({ "processing_status.v2_extracted": 1 })
```

---

## 四、数据流设计

### 4.1 邮件处理 Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Email Processing Pipeline                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐                                                    │
│  │   emails    │  (现有 57,860 封)                                  │
│  │  collection │                                                    │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Stage 1: AI EXTRACTION                          │   │
│  │                                                              │   │
│  │  Input:  email.subject + email.body_clean                   │   │
│  │  Model:  qwen3:30b-a3b (Ollama)                             │   │
│  │  Output: ai_extracted JSON                                   │   │
│  │                                                              │   │
│  │  速度: ~30秒/封 (不追求效率，追求质量)                        │   │
│  │  批次: 每批 10 封，串行处理                                   │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│                             ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Stage 2: ENTITY RESOLUTION                      │   │
│  │                                                              │   │
│  │  For each extracted COMPANY/PERSON entity:                  │   │
│  │                                                              │   │
│  │  Step 2.1: Normalize (清洗)                                 │   │
│  │    - 移除日语敬语: 様, 御中, 株式会社                        │   │
│  │    - 统一大小写: SPACEX → SpaceX                            │   │
│  │    - 移除标点: "SpaceX, Inc." → "SpaceX Inc"                │   │
│  │                                                              │   │
│  │  Step 2.2: Match (三级匹配策略)                             │   │
│  │    ┌─────────────────────────────────────────────────┐      │   │
│  │    │ Level 1: Domain 精确匹配 (置信度 1.0)           │      │   │
│  │    │   spacex.com == spacex.com → 直接匹配           │      │   │
│  │    │   → 自动关联，不需要人工确认                     │      │   │
│  │    ├─────────────────────────────────────────────────┤      │   │
│  │    │ Level 2: Alias 精确匹配 (置信度 0.95)           │      │   │
│  │    │   "SpaceX" in party.aliases → 匹配              │      │   │
│  │    │   → 自动关联，更新 aliases 数组                  │      │   │
│  │    ├─────────────────────────────────────────────────┤      │   │
│  │    │ Level 3: Fuzzy 模糊匹配 (置信度 0.60-0.90)      │      │   │
│  │    │   Levenshtein("Space X", "SpaceX") = 0.85       │      │   │
│  │    │   Token overlap("SpaceX Corp", "SpaceX") = 0.67 │      │   │
│  │    │                                                 │      │   │
│  │    │   if confidence >= 0.80:                        │      │   │
│  │    │     → 自动合并，记录 merge_history              │      │   │
│  │    │   else:                                         │      │   │
│  │    │     → 进入 entity_merge_queue 等待人工审核      │      │   │
│  │    └─────────────────────────────────────────────────┘      │   │
│  │                                                              │   │
│  │  Step 2.3: Create or Queue (创建或排队)                     │   │
│  │    - 匹配成功: 填充 entity.matched_object                   │   │
│  │    - 匹配失败 + 置信度高: 创建新 party 记录                 │   │
│  │    - 匹配失败 + 置信度低: 创建 entity_merge_queue 记录      │   │
│  │                                                              │   │
│  │  输出: entity.matched_object 填充完成                        │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│                             ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Stage 3: BUSINESS OBJECT UPDATE                 │   │
│  │                                                              │   │
│  │  根据 intent 分发到不同处理器:                               │   │
│  │                                                              │   │
│  │  ORDER_CONFIRM  → FulfillmentProcessor                      │   │
│  │  SHIPPING_UPDATE → ShipmentProcessor                        │   │
│  │  INVOICE        → FinanceDocProcessor                       │   │
│  │  COMPLIANCE     → ComplianceDocProcessor                    │   │
│  │  QUOTE_REQUEST  → FulfillmentProcessor (创建 NEW 状态)      │   │
│  │                                                              │   │
│  │  每个 Processor:                                            │   │
│  │    1. 查找/创建业务对象                                      │   │
│  │    2. 更新状态 (追加 status_history)                        │   │
│  │    3. 记录 provenance                                       │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│                             ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Stage 4: EVENT & ACTION CREATION                │   │
│  │                                                              │   │
│  │  1. 创建 email_events 记录                                  │   │
│  │     - 记录这封邮件影响了哪些业务对象                         │   │
│  │                                                              │   │
│  │  2. 创建 action_items (如果有)                              │   │
│  │     - 从 ai_extracted.action_items 生成                     │   │
│  │     - 计算优先级分数                                         │   │
│  │                                                              │   │
│  │  3. 更新 email.processing_status                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 处理优先级

```
处理顺序 (宁慢勿错):

Phase 0: 基础数据准备
├── 0.1 从现有 companies → parties (COMPANY) 迁移
├── 0.2 从现有 contacts → parties (PERSON) 迁移
├── 0.3 建立别名映射表 (alias_mapping)
└── 0.4 清理日语噪音 (様, 御中, 株式会社)

Phase 1: 核心客户邮件 (约 5,000 封)
├── 1.1 SpaceX 相关邮件 (spacex.com)
├── 1.2 其他 STRATEGIC 客户邮件
└── 输出: fulfillments, compliance_docs 初步填充

Phase 2: 物流邮件 (约 15,000 封)
├── 2.1 Expeditors
├── 2.2 DHL
├── 2.3 UPS/FedEx
└── 输出: shipments 填充完成

Phase 3: 供应商邮件 (约 20,000 封)
├── 3.1 日本供应商
├── 3.2 国内供应商
└── 输出: parties (SUPPLIER), products 补充

Phase 4: 财务邮件 (约 10,000 封)
├── 4.1 发票相关
├── 4.2 付款相关
└── 输出: finance_docs 填充完成

Phase 5: 其他邮件 (约 10,000 封)
└── 杂项处理，补充遗漏

估计总耗时: 57,860 封 × 30秒 ≈ 480 小时 ≈ 20 天
实际执行: 可以分批跑，每天处理 3,000 封，20天完成
```

---

## 五、产品功能支撑验证

### 5.1 功能→Schema 映射

| 产品功能 | 需要查询的集合 | 关键字段 | 可行性 |
|----------|---------------|----------|--------|
| **客户健康度看板** | `parties` + `fulfillments` | `health.score`, `current_status`, `is_blocked` | ✅ |
| **供应商绩效评估** | `shipments` + `parties` | `dates.eta`, `dates.actual_arrival`, 计算 OTD | ✅ |
| **合规文档到期提醒** | `compliance_docs` | `validity.expiry_date`, `validity.days_until_expiry` | ✅ |
| **财务三单匹配** | `fulfillments` + `finance_docs` | `linked_docs.invoice_ids`, `financials.total` | ✅ |
| **订单全生命周期** | `fulfillments` | `status_history`, `current_status`, `current_stage` | ✅ |
| **物流异常预警** | `shipments` | `exceptions`, `current_status`, `dates.eta` | ✅ |
| **待办事项中心** | `action_items` | `status`, `priority`, `scoring.total_score` | ✅ |
| **邮件→业务追溯** | `email_events` | `affects`, `email_id` | ✅ |

### 5.2 查询示例

**1. 客户健康度看板**
```javascript
// 获取所有 STRATEGIC 客户的健康度和订单状态分布
db.parties.aggregate([
  { $match: { party_type: "COMPANY", "company_info.tier": "STRATEGIC" } },
  { $lookup: {
      from: "fulfillments",
      localField: "_id",
      foreignField: "refs.customer_id",
      as: "orders"
  }},
  { $project: {
      canonical_name: 1,
      health_score: "$health.score",
      total_orders: { $size: "$orders" },
      blocked_orders: {
        $size: {
          $filter: { input: "$orders", cond: { $eq: ["$$this.is_blocked", true] } }
        }
      }
  }}
])
```

**2. 供应商准时交付率 (OTD)**
```javascript
// 计算各物流商的准时交付率
db.shipments.aggregate([
  { $match: { "dates.actual_arrival": { $exists: true } } },
  { $addFields: {
      is_on_time: { $lte: ["$dates.actual_arrival", "$dates.eta"] }
  }},
  { $group: {
      _id: "$carrier",
      total: { $sum: 1 },
      on_time: { $sum: { $cond: ["$is_on_time", 1, 0] } }
  }},
  { $addFields: {
      otd_rate: { $multiply: [{ $divide: ["$on_time", "$total"] }, 100] }
  }}
])
```

**3. 合规文档到期提醒**
```javascript
// 获取 30 天内即将过期的文档
db.compliance_docs.find({
  "validity.status": { $in: ["VALID", "EXPIRING_SOON"] },
  "validity.days_until_expiry": { $lte: 30 }
}).sort({ "validity.days_until_expiry": 1 })
```

**4. 财务对账**
```javascript
// 找出金额不匹配的订单-发票
db.fulfillments.aggregate([
  { $lookup: {
      from: "finance_docs",
      localField: "linked_docs.invoice_ids",
      foreignField: "_id",
      as: "invoices"
  }},
  { $addFields: {
      invoice_total: { $sum: "$invoices.amount.total" }
  }},
  { $match: {
      $expr: { $ne: ["$financials.total", "$invoice_total"] }
  }}
])
```

---

## 六、目录结构 (更新)

```
~/vulcan-brain/
├── EMAIL_INTELLIGENCE_V2_PLAN.md           # 本文档
│
├── services/
│   ├── email_intelligence_v2/              # V2.0 模块
│   │   ├── __init__.py
│   │   ├── README.md
│   │   │
│   │   ├── models/                         # Pydantic 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── party.py                    # Party (Company/Person)
│   │   │   ├── product.py                  # Product
│   │   │   ├── fulfillment.py              # Fulfillment (核心)
│   │   │   ├── shipment.py                 # Shipment
│   │   │   ├── finance_doc.py              # FinanceDoc
│   │   │   ├── compliance_doc.py           # ComplianceDoc
│   │   │   ├── email_event.py              # EmailEvent
│   │   │   └── action_item.py              # ActionItem
│   │   │
│   │   ├── extractors/                     # AI 提取器
│   │   │   ├── __init__.py
│   │   │   ├── master_extractor.py         # 主提取器 (LLM)
│   │   │   ├── entity_resolver.py          # 实体匹配
│   │   │   └── prompts/
│   │   │       ├── extraction_prompt.py
│   │   │       └── entity_normalization.py
│   │   │
│   │   ├── processors/                     # 业务对象处理器
│   │   │   ├── __init__.py
│   │   │   ├── base_processor.py
│   │   │   ├── fulfillment_processor.py
│   │   │   ├── shipment_processor.py
│   │   │   ├── finance_processor.py
│   │   │   └── compliance_processor.py
│   │   │
│   │   ├── migration/                      # 数据迁移
│   │   │   ├── __init__.py
│   │   │   ├── schema_init.py              # 创建集合和索引
│   │   │   ├── legacy_migrator.py          # V1 → V2 迁移
│   │   │   └── alias_mapping.json          # 别名映射
│   │   │
│   │   ├── services/                       # 业务服务
│   │   │   ├── __init__.py
│   │   │   ├── pipeline_service.py         # 处理流水线
│   │   │   ├── health_service.py           # 健康度计算
│   │   │   └── alert_service.py            # 提醒服务
│   │   │
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_extractors.py
│   │       ├── test_processors.py
│   │       └── fixtures/
│   │
│   └── email_intelligence_service.py       # 保留旧版本 (兼容)
│
├── api/
│   └── email_intel_v2.py                   # V2.0 API
│
└── scripts/
    ├── init_v2_schema.py                   # 初始化脚本
    ├── migrate_legacy_data.py              # 迁移脚本
    └── batch_process.py                    # 批量处理脚本
```

---

## 七、实施计划

### Phase 0: 基础设施 (1-2 天)

```
任务 0.1: 创建 Pydantic Models
├── 定义 8 个业务对象的完整 Model
├── 包含验证规则和默认值
└── 产出: models/*.py

任务 0.2: Schema 初始化脚本
├── 创建 8 个集合
├── 创建所有索引
└── 产出: migration/schema_init.py

任务 0.3: 数据迁移脚本
├── companies → parties (COMPANY)
├── contacts → parties (PERSON)
├── 建立 belongs_to_company 关联
└── 产出: migration/legacy_migrator.py
```

### Phase 1: AI 提取器 (3-4 天)

```
任务 1.1: Master Extractor
├── 设计 Prompt (针对 B2B 供应链)
├── 实现 JSON Schema 验证
├── 错误处理和重试
└── 产出: extractors/master_extractor.py

任务 1.2: Entity Resolver (核心风险点!)
├── 三级匹配策略实现:
│   ├── Level 1: Domain 精确匹配 (confidence=1.0)
│   ├── Level 2: Alias 精确匹配 (confidence=0.95)
│   └── Level 3: Fuzzy 模糊匹配 (Levenshtein + Token overlap)
├── 日语敬语清洗: 様, 御中, 株式会社, お客様
├── 公司名标准化: Inc, Corp, LLC, Ltd 处理
├── entity_merge_queue 集成:
│   ├── confidence < 0.80 进入待审核队列
│   ├── 自动计算 risk_assessment
│   └── 30天未处理自动拒绝
├── merge_history 审计记录
└── 产出: extractors/entity_resolver.py, entity_merge_service.py

任务 1.3: 小批量测试
├── 抽样 100 封邮件测试
├── 验证提取质量
├── 调优 Prompt
└── 产出: 测试报告
```

### Phase 2: 业务处理器 (3-4 天)

```
任务 2.1: FulfillmentProcessor
├── 订单创建/更新逻辑
├── 状态机流转
├── status_history 追加
└── 产出: processors/fulfillment_processor.py

任务 2.2: ShipmentProcessor
├── 物流记录创建/更新
├── 追踪号解析
├── 异常检测
└── 产出: processors/shipment_processor.py

任务 2.3: FinanceProcessor & ComplianceProcessor
├── 发票/付款处理
├── 合规文档处理
├── 有效期计算
└── 产出: processors/finance_processor.py, compliance_processor.py
```

### Phase 3: Pipeline 集成 (2-3 天)

```
任务 3.1: Pipeline Service
├── 串联 Extractor → Resolver → Processors
├── 批量处理控制
├── 进度追踪和断点续传
└── 产出: services/pipeline_service.py

任务 3.2: Email Events & Action Items
├── 创建 email_events 记录
├── 生成 action_items
├── 优先级计算
└── 产出: 相关代码

任务 3.3: 全量处理
├── 分 Phase 处理 57,860 封邮件
├── 每天 3,000 封
├── 监控和质量抽查
└── 产出: 填充完成的数据库
```

### Phase 4: API & 前端 (2-3 天)

```
任务 4.1: V2 API
├── /v2/stats - 统计
├── /v2/fulfillments - 订单查询
├── /v2/actions - 待办事项
├── /v2/health - 健康度
└── 产出: api/email_intel_v2.py

任务 4.2: 前端集成
├── 更新现有页面调用新 API
├── 新增待办事项页面
└── 产出: 前端代码更新
```

---

## 八、风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| LLM 提取质量不稳定 | 高 | 高 | 小批量测试，迭代优化 Prompt；关键字段人工抽查 |
| **实体消歧失败 (核心风险)** | **高** | **高** | **三级匹配策略；entity_merge_queue 人工审核；保守阈值 0.80** |
| 实体碎片化 (SpaceX 分裂成多个记录) | 高 | 高 | Domain 精确匹配优先；离线批量合并脚本；定期健康度检查 |
| 处理耗时过长 | 中 | 低 | 分批处理，优先处理核心客户；接受20天处理周期 |
| 状态机流转错误 | 低 | 高 | 严格的状态机定义；每次变更记录 provenance |
| 数据迁移丢失 | 低 | 中 | 迁移前备份；迁移后验证计数 |
| 日语实体误识别 | 中 | 中 | 敬语白名单过滤；日语公司名特殊处理 |

---

## 九、成功指标

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| 意图分类准确率 | > 85% | 人工抽样 200 封验证 |
| 实体提取准确率 | > 80% | 人工抽样验证 |
| **实体消歧准确率** | **> 95%** | **抽样检查 canonical_id 指向正确** |
| **实体碎片化率** | **< 5%** | **同一公司存在多个 is_canonical=true 记录的比例** |
| **entity_merge_queue 消化率** | **> 80%/周** | **每周审核完成的比例** |
| 实体匹配准确率 | > 90% | 检查 matched_object 正确性 |
| Fulfillment 覆盖率 | > 70% PO 有对应记录 | 统计 |
| Action Item 召回率 | > 60% | 对比人工标注 |
| 数据血缘完整性 | 100% 有 provenance | 统计 |

---

## 附录 A: 意图分类定义

| Intent | 说明 | 示例主题 |
|--------|------|---------|
| `ORDER_CONFIRM` | 订单确认 | "PO Confirmation", "Order Acknowledgement" |
| `QUOTE_REQUEST` | 询价/报价请求 | "RFQ", "Request for Quote", "询价" |
| `QUOTE_RESPONSE` | 报价回复 | "Quotation", "Price Offer" |
| `SHIPPING_UPDATE` | 物流更新 | "Shipment Notification", "Tracking Update" |
| `DELIVERY_CONFIRM` | 交货确认 | "Delivery Confirmation", "POD" |
| `INVOICE` | 发票相关 | "Invoice", "Payment Request" |
| `PAYMENT` | 付款相关 | "Payment Confirmation", "Remittance" |
| `COMPLIANCE` | 合规文档 | "W-9", "Export License", "COO" |
| `ISSUE_REPORT` | 问题报告 | "Quality Issue", "Delay Notice" |
| `GENERAL` | 一般沟通 | 其他 |

---

## 附录 B: 状态机完整定义

### Fulfillment 状态机

| 状态 | 阶段 | 允许的下一状态 | 触发条件 |
|------|------|---------------|---------|
| `NEW` | SALES | `CONFIRMED`, `CANCELLED` | 收到询价 |
| `CONFIRMED` | SALES | `PRODUCING`, `CANCELLED` | 收到 PO 确认 |
| `PRODUCING` | PRODUCTION | `READY_TO_SHIP`, `BLOCKED`, `CANCELLED` | 开始生产 |
| `READY_TO_SHIP` | LOGISTICS | `SHIPPING`, `BLOCKED` | 生产完成 |
| `SHIPPING` | LOGISTICS | `DELIVERED`, `BLOCKED` | 发货 |
| `DELIVERED` | LOGISTICS | `INVOICED` | 收到 POD |
| `INVOICED` | FINANCE | `PAID`, `PARTIAL_PAID` | 开票 |
| `PARTIAL_PAID` | FINANCE | `PAID` | 部分付款 |
| `PAID` | FINANCE | `CLOSED` | 全额付款 |
| `CLOSED` | - | - | 归档 |
| `BLOCKED` | 任意 | 返回上一状态 | 异常阻塞 |
| `CANCELLED` | - | - | 取消 |

### Shipment 状态机

| 状态 | 允许的下一状态 |
|------|---------------|
| `BOOKED` | `PICKED_UP`, `CANCELLED` |
| `PICKED_UP` | `IN_TRANSIT` |
| `IN_TRANSIT` | `CUSTOMS_HOLD`, `OUT_FOR_DELIVERY` |
| `CUSTOMS_HOLD` | `CUSTOMS_CLEARED` |
| `CUSTOMS_CLEARED` | `OUT_FOR_DELIVERY` |
| `OUT_FOR_DELIVERY` | `DELIVERED` |
| `DELIVERED` | - |

---

## 附录 C: 变更日志

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2025-12-11 | 1.0 | 初始版本，基于语义调研 | Claude Agent |
| 2025-12-11 | 2.0 | 重写为领域驱动设计，采纳架构师建议 | Claude Agent |

---

*本文档将随开发进度持续更新。下一步：实现 Phase 0 基础设施。*
