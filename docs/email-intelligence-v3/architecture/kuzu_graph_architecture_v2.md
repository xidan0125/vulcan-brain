# KùzuDB 图数据库架构设计 v2.0

> **融合方案**: 结合 Gemini 邮件智能专家 + 资深架构师的双重建议
> **创建日期**: 2025-01-14
> **版本**: v2.0

---

## 一、核心设计理念

### 1.1 从 Document-Centric 到 Event-Centric

**旧思维 (Document-Centric)**
```
Email → extracts → Facts
```

**新思维 (Event-Centric)**
```
BusinessEvent (核心) ← evidenced_by ← Email(s)
      ↓
  aggregates multiple emails via Identifier
```

**关键转变**:
- Email 只是**证据载体**，不是核心
- BusinessEvent 是**业务真相**的载体
- 一个 BusinessEvent 可关联多封 Email（通过 Identifier 聚合）

### 1.2 Thread 节点：保留对话流

B2B 邮件往往是**往来对话**（Re: Re: Re:...），Thread 节点捕获这种时序关系：

```
Thread: "HN125040209 德国Alpha报价"
  ├─ Email[1]: 初始询价 (2024-01-10)
  ├─ Email[2]: 报价回复 (2024-01-11)
  └─ Email[3]: 确认订单 (2024-01-15)
```

### 1.3 Identifier 作为聚合锚点

Invoice No、PO No、Tracking No 是**跨邮件关联**的天然锚点：

```
Identifier[INV-2024-001]
  ├─ Email: 发票邮件
  ├─ Email: 付款确认邮件
  └─ BusinessEvent: Payment (USD 5,000)
```

---

## 二、KùzuDB Schema (DDL)

```cypher
-- ============================================
-- 核心节点 (Core Nodes)
-- ============================================

-- 业务事件：系统核心
CREATE NODE TABLE BusinessEvent (
    id STRING PRIMARY KEY,
    event_type STRING,  -- 'Shipment', 'Quotation', 'Payment', 'Order'
    date DATE,
    summary STRING,
    confidence DOUBLE,
    -- 使用 STRUCT 避免节点爆炸
    financials STRUCT(amount DOUBLE, currency STRING),
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- 邮件线程
CREATE NODE TABLE Thread (
    id STRING PRIMARY KEY,
    topic STRING,
    email_count INT32,
    first_date DATE,
    last_date DATE
);

-- 邮件（证据载体）
CREATE NODE TABLE Email (
    id STRING PRIMARY KEY,  -- MongoDB ObjectId
    subject STRING,
    sent_at TIMESTAMP,
    sender STRING,
    -- 同步追踪
    kuzu_synced_at TIMESTAMP DEFAULT current_timestamp()
);

-- 公司实体
CREATE NODE TABLE Company (
    id STRING PRIMARY KEY,  -- 规范化后的名称
    original_name STRING,
    normalized_name STRING,
    aliases STRING[],
    v2_entity_id STRING,    -- V2 实体库关联
    entity_type STRING      -- 'customer', 'supplier', 'logistics'
);

-- 标识符
CREATE NODE TABLE Identifier (
    val STRING PRIMARY KEY,
    type STRING  -- 'invoice', 'po', 'tracking', 'container', 'hs_code'
);

-- 产品
CREATE NODE TABLE Product (
    id STRING PRIMARY KEY,
    name STRING,
    hs_code STRING
);

-- 人员
CREATE NODE TABLE Person (
    id STRING PRIMARY KEY,
    name STRING,
    company_id STRING,
    role STRING
);

-- ============================================
-- 关系 (Relationships)
-- ============================================

-- Email → Thread
CREATE REL TABLE BELONGS_TO (
    FROM Email TO Thread,
    position INT32  -- 在线程中的顺序
);

-- Email → BusinessEvent (证据关系)
CREATE REL TABLE EVIDENCES (
    FROM Email TO BusinessEvent,
    confidence DOUBLE,
    extracted_at TIMESTAMP
);

-- BusinessEvent → Company (参与关系)
CREATE REL TABLE INVOLVES (
    FROM BusinessEvent TO Company,
    role STRING,  -- 'buyer', 'seller', 'shipper'
    date DATE     -- 时态属性
);

-- BusinessEvent → Identifier
CREATE REL TABLE HAS_ID (
    FROM BusinessEvent TO Identifier,
    date DATE
);

-- BusinessEvent → Product
CREATE REL TABLE CONCERNS (
    FROM BusinessEvent TO Product,
    quantity INT32,
    unit STRING,
    date DATE
);

-- Company → Person
CREATE REL TABLE EMPLOYS (
    FROM Company TO Person
);

-- Thread 回复链
CREATE REL TABLE REPLIES_TO (
    FROM Email TO Email
);
```

---

## 三、实体规范化策略

### 3.1 公司名称规范化函数

```python
import re

def normalize_company_name(raw: str) -> str:
    """
    规则驱动的公司名称规范化
    """
    if not raw:
        return ""

    name = raw.strip().upper()

    # 移除常见后缀
    suffixes = [
        r'\s*(CO\.,?\s*LTD\.?)$',
        r'\s*(GMBH)$',
        r'\s*(INC\.?)$',
        r'\s*(LLC)$',
        r'\s*(PTE\.?\s*LTD\.?)$',
        r'\s*(LIMITED)$',
        r'\s*(CORPORATION)$',
        r'\s*(CORP\.?)$',
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    # 移除多余空白
    name = ' '.join(name.split())

    return name.strip()

# 示例
assert normalize_company_name("Alpha Tech Co., Ltd.") == "ALPHA TECH"
assert normalize_company_name("DHL Express GmbH") == "DHL EXPRESS"
```

### 3.2 三层去重漏斗

```
┌─────────────────────────────────────┐
│  Layer 1: 规则规范化                │
│  normalize_company_name()           │
│  → 快速、确定性                     │
└─────────────────────────────────────┘
              ↓ (未匹配)
┌─────────────────────────────────────┐
│  Layer 2: V2 实体库查找             │
│  查询已有 entity_id                 │
│  → 复用历史积累                     │
└─────────────────────────────────────┘
              ↓ (未匹配)
┌─────────────────────────────────────┐
│  Layer 3: 向量/LLM 模糊匹配         │
│  (可选, 用于疑难情况)               │
│  → 最后防线                         │
└─────────────────────────────────────┘
```

---

## 四、ETL Pipeline 设计

### 4.1 增量同步机制

```python
def get_unsynced_emails(mongo_db, kuzu_conn) -> List[Dict]:
    """
    获取未同步到 KùzuDB 的邮件
    使用 kuzu_synced_at 字段追踪
    """
    # 查询已同步的最新时间
    result = kuzu_conn.execute(
        "MATCH (e:Email) RETURN MAX(e.kuzu_synced_at) AS last_sync"
    )
    last_sync = result.get_next()[0] or datetime(1970, 1, 1)

    # 查询 MongoDB 中更新的邮件
    return list(mongo_db.emails.find({
        "$or": [
            {"kuzu_synced_at": {"$exists": False}},
            {"kuzu_synced_at": {"$gt": last_sync}},
            {"v3_extraction_v312": {"$exists": True}, "kuzu_synced_at": {"$exists": False}}
        ]
    }))
```

### 4.2 核心 ETL 流程

```python
def etl_email_to_graph(email: Dict, extraction: Dict, kuzu_conn, v2_entities: Dict):
    """
    单封邮件的 ETL 流程
    """
    email_id = str(email["_id"])

    # 1. 创建 Email 节点
    kuzu_conn.execute("""
        MERGE (e:Email {id: $id})
        SET e.subject = $subject,
            e.sent_at = $sent_at,
            e.sender = $sender,
            e.kuzu_synced_at = current_timestamp()
    """, {
        "id": email_id,
        "subject": email.get("subject", ""),
        "sent_at": email.get("received_time"),
        "sender": email.get("sender", "")
    })

    # 2. 处理 Thread (基于 subject 的 Re: 链)
    thread_id = extract_thread_id(email.get("subject", ""))
    if thread_id:
        kuzu_conn.execute("""
            MERGE (t:Thread {id: $tid})
            ON CREATE SET t.topic = $topic
            WITH t
            MATCH (e:Email {id: $eid})
            MERGE (e)-[:BELONGS_TO]->(t)
        """, {"tid": thread_id, "topic": thread_id, "eid": email_id})

    # 3. 提取 Identifiers 并聚合 BusinessEvent
    identifiers = [f for f in extraction.get("facts", []) if f.get("type") == "identifier"]

    for ident in identifiers:
        ident_val = ident["value"]
        ident_type = classify_identifier_type(ident["key"])

        # 创建 Identifier 节点
        kuzu_conn.execute("""
            MERGE (i:Identifier {val: $val})
            SET i.type = $type
        """, {"val": ident_val, "type": ident_type})

        # 尝试找到或创建关联的 BusinessEvent
        event_id = f"evt_{ident_val}"
        event_type = infer_event_type(extraction.get("email_type", ""))

        kuzu_conn.execute("""
            MERGE (be:BusinessEvent {id: $eid})
            ON CREATE SET be.event_type = $etype,
                          be.date = $date,
                          be.summary = $summary
            WITH be
            MATCH (i:Identifier {val: $ival})
            MERGE (be)-[:HAS_ID]->(i)
        """, {
            "eid": event_id,
            "etype": event_type,
            "date": extraction.get("document_date"),
            "summary": extraction.get("summary", ""),
            "ival": ident_val
        })

        # Email EVIDENCES BusinessEvent
        kuzu_conn.execute("""
            MATCH (e:Email {id: $email_id}), (be:BusinessEvent {id: $event_id})
            MERGE (e)-[:EVIDENCES {confidence: 0.9}]->(be)
        """, {"email_id": email_id, "event_id": event_id})

    # 4. 处理公司实体
    for company_raw in extraction.get("companies", []):
        normalized = normalize_company_name(company_raw)
        v2_id = v2_entities.get(normalized)  # 查找 V2 实体库

        kuzu_conn.execute("""
            MERGE (c:Company {id: $cid})
            ON CREATE SET c.original_name = $raw,
                          c.normalized_name = $norm,
                          c.v2_entity_id = $v2id
            ON MATCH SET c.aliases = c.aliases + [$raw]
        """, {"cid": normalized, "raw": company_raw, "norm": normalized, "v2id": v2_id})

        # 关联到 BusinessEvent
        if identifiers:
            event_id = f"evt_{identifiers[0]['value']}"
            kuzu_conn.execute("""
                MATCH (be:BusinessEvent {id: $eid}), (c:Company {id: $cid})
                MERGE (be)-[:INVOLVES {role: 'participant', date: $date}]->(c)
            """, {"eid": event_id, "cid": normalized, "date": extraction.get("document_date")})

    # 5. 处理金额 (使用 STRUCT)
    amounts = [f for f in extraction.get("facts", []) if f.get("type") == "amount"]
    if amounts and identifiers:
        amt = amounts[0]
        amount_val, currency = parse_amount(amt["value"])
        event_id = f"evt_{identifiers[0]['value']}"

        kuzu_conn.execute("""
            MATCH (be:BusinessEvent {id: $eid})
            SET be.financials = {amount: $amt, currency: $curr}
        """, {"eid": event_id, "amt": amount_val, "curr": currency})
```

### 4.3 辅助函数

```python
def extract_thread_id(subject: str) -> str:
    """从 subject 提取 thread ID"""
    # 移除 Re: Fwd: 等前缀
    clean = re.sub(r'^(Re:\s*|Fwd:\s*|回复:\s*|转发:\s*)+', '', subject, flags=re.IGNORECASE)
    # 提取标识符作为 thread ID
    match = re.search(r'[A-Z]{2,}\d{6,}', clean)
    if match:
        return match.group(0)
    return hashlib.md5(clean.encode()).hexdigest()[:12]

def classify_identifier_type(key: str) -> str:
    """分类标识符类型"""
    key_lower = key.lower()
    if 'invoice' in key_lower or 'inv' in key_lower:
        return 'invoice'
    if 'po' in key_lower or 'order' in key_lower:
        return 'po'
    if 'tracking' in key_lower or 'awb' in key_lower:
        return 'tracking'
    if 'container' in key_lower:
        return 'container'
    if 'hs' in key_lower:
        return 'hs_code'
    return 'other'

def infer_event_type(email_type: str) -> str:
    """从邮件类型推断事件类型"""
    mapping = {
        'shipping': 'Shipment',
        'invoice': 'Payment',
        'quotation': 'Quotation',
        'order': 'Order',
        'inquiry': 'Inquiry'
    }
    for key, val in mapping.items():
        if key in email_type.lower():
            return val
    return 'General'

def parse_amount(value: str) -> tuple:
    """解析金额和货币"""
    match = re.search(r'([A-Z]{3}|[$€¥£])\s*([\d,]+\.?\d*)', value)
    if match:
        currency = match.group(1)
        amount = float(match.group(2).replace(',', ''))
        return amount, currency
    return 0.0, 'USD'
```

---

## 五、实施计划

### Phase A: 基础设施 (Day 1)
- [ ] 安装 KùzuDB: `pip install kuzu`
- [ ] 创建 schema 初始化脚本
- [ ] 创建数据库文件

### Phase B: 实体层 (Day 2)
- [ ] 公司规范化函数
- [ ] V2 实体库对接
- [ ] Person/Product 节点

### Phase C: 事件层 (Day 3-4)
- [ ] BusinessEvent 聚合逻辑
- [ ] Identifier 关联
- [ ] Thread 构建

### Phase D: ETL 集成 (Day 5)
- [ ] 增量同步机制
- [ ] MongoDB 字段更新
- [ ] 批量处理脚本

### Phase E: 查询验证 (Day 6)
- [ ] 验证查询集
- [ ] 性能测试
- [ ] 可视化工具

---

## 六、验证查询示例

```cypher
-- 1. 查看某公司的所有业务事件
MATCH (c:Company {normalized_name: "ALPHA TECH"})<-[:INVOLVES]-(be:BusinessEvent)
RETURN be.event_type, be.date, be.financials
ORDER BY be.date DESC;

-- 2. 追踪某个 Invoice 的完整链路
MATCH (i:Identifier {val: "INV-2024-001"})<-[:HAS_ID]-(be:BusinessEvent)
MATCH (be)<-[:EVIDENCES]-(e:Email)
RETURN be.event_type, e.subject, e.sent_at;

-- 3. 查看邮件线程的时间线
MATCH (t:Thread {id: "HN125040209"})<-[:BELONGS_TO]-(e:Email)
RETURN e.subject, e.sent_at
ORDER BY e.sent_at;

-- 4. 分析某公司的交易总额
MATCH (c:Company {normalized_name: "DHL EXPRESS"})<-[:INVOLVES]-(be:BusinessEvent)
WHERE be.financials.currency = 'USD'
RETURN SUM(be.financials.amount) AS total_usd;
```

---

## 附录: 文件结构

```
~/vulcan-brain/docs/email-intelligence-v3/
├── architecture/
│   └── kuzu_graph_architecture_v2.md  (本文档)
├── v3_pipeline/
│   ├── batch_extractor_v312_refined.py
│   └── kuzu_etl/
│       ├── __init__.py
│       ├── schema.py           # Schema DDL
│       ├── normalizer.py       # 实体规范化
│       ├── etl_pipeline.py     # 主 ETL 逻辑
│       └── queries.py          # 验证查询
└── kuzu_data/                  # KùzuDB 数据目录
    └── email_graph/
```
