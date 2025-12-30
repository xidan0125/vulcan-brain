"""
Graph API - KùzuDB 数据查询接口
用于 Data Explorer (V2 - 以我为中心的视角)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import kuzu
import re

router = APIRouter(prefix="/api/graph", tags=["graph"])

KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"

# VSG 相关名称 - 我们自己，不应出现在"对手"列表中
VSG_ALIASES = [
    "vulcan shield", "vulcanshield", "vsg", "vulcan", 
    "保汉盾", "保汉", "vulcan shield group"
]

def is_vsg(name: str) -> bool:
    """判断是否为VSG相关实体"""
    if not name:
        return False
    name_lower = name.lower().strip()
    return any(alias in name_lower for alias in VSG_ALIASES)

def get_connection(read_only=True):
    db = kuzu.Database(KUZU_PATH, read_only=read_only)
    return kuzu.Connection(db)

# ============ 数据模型 ============
class QueryRequest(BaseModel):
    cypher: str
    limit: int = 100

class EventFilter(BaseModel):
    event_type: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 50

# ============ 公司分类逻辑 ============
def classify_company(name: str, event_types: List[str]) -> str:
    """根据公司名和事件类型推断公司角色"""
    name_lower = (name or "").lower()
    
    # 银行/金融
    bank_keywords = ["bank", "hsbc", "dbs", "ocbc", "uob", "citibank", "chase", "barclays", "finance", "capital"]
    if any(kw in name_lower for kw in bank_keywords):
        return "Bank"
    
    # 物流
    logistics_keywords = ["shipping", "logistics", "freight", "transport", "cargo", "dhl", "fedex", "ups", "maersk", "cosco"]
    if any(kw in name_lower for kw in logistics_keywords):
        return "Logistics"
    
    # 根据事件类型推断
    if event_types:
        payment_count = event_types.count("Payment")
        order_count = event_types.count("Order") + event_types.count("Quotation")
        shipment_count = event_types.count("Shipment")
        
        # 主要是付款事件 → 可能是客户
        if payment_count > order_count and payment_count > shipment_count:
            return "Customer"
        # 主要是订单/报价 → 可能是供应商
        if order_count > payment_count:
            return "Supplier"
        # 主要是物流
        if shipment_count > payment_count:
            return "Logistics"
    
    return "Partner"  # 默认

# ============ 端点 ============
@router.get("/stats")
async def get_stats():
    """获取图谱统计信息"""
    conn = get_connection()

    stats = {}

    # 节点统计
    for node_type in ["Email", "BusinessEvent", "Company", "Identifier", "Thread", "Person", "Product"]:
        result = conn.execute(f"MATCH (n:{node_type}) RETURN count(*)")
        stats[node_type] = result.get_next()[0]

    # 事件类型分布
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN ['Payment', 'Shipment', 'Contract', 'Order', 'Quotation']
        RETURN be.event_type, count(*) as cnt
        ORDER BY cnt DESC
    """)
    event_types = {}
    while result.has_next():
        row = result.get_next()
        event_types[row[0]] = row[1]
    stats["event_types"] = event_types

    return stats

@router.get("/events")
async def get_events(
    event_type: Optional[str] = None,
    company: Optional[str] = None,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    counterparty: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50
):
    """获取事件列表，支持多种筛选"""
    conn = get_connection()

    where_clauses = []
    if event_type:
        where_clauses.append(f"be.event_type = '{event_type}'")
    if status:
        where_clauses.append(f"be.status = '{status}'")
    if direction:
        where_clauses.append(f"be.direction = '{direction}'")
    if counterparty:
        # 支持模糊匹配
        where_clauses.append(f"be.counterparty CONTAINS '{counterparty}'")
    if role:
        where_clauses.append(f"be.counterparty_role = '{role}'")

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"""
        MATCH (be:BusinessEvent)
        {where_str}
        OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
        RETURN be.id, be.event_type, be.event_date, be.summary, be.amount, be.currency,
               be.direction, be.status, be.counterparty, be.counterparty_role,
               collect(DISTINCT c.canonical_name) as companies
        ORDER BY be.event_date DESC
        LIMIT {limit}
    """

    result = conn.execute(query)

    events = []
    while result.has_next():
        row = result.get_next()
        # 过滤掉VSG相关公司名
        companies = [c for c in (row[10] or []) if c and not is_vsg(c)]
        events.append({
            "id": row[0],
            "event_type": row[1],
            "event_date": row[2],
            "summary": row[3],
            "amount": row[4],
            "currency": row[5],
            "direction": row[6] or "unknown",
            "status": row[7] or "unknown",
            "counterparty": row[8] or "",
            "counterparty_role": row[9] or "",
            "companies": companies
        })

    # 如果有公司筛选，过滤结果
    if company:
        events = [e for e in events if company.lower() in str(e.get("companies", [])).lower()]

    return {"events": events, "total": len(events)}

@router.get("/companies")
async def get_companies(limit: int = 50, include_vsg: bool = False):
    """获取公司列表及其事件统计（默认排除VSG）"""
    conn = get_connection()

    result = conn.execute(f"""
        MATCH (c:Company)<-[:INVOLVES]-(be:BusinessEvent)
        RETURN c.canonical_name as name, count(be) as event_count, collect(be.event_type) as all_types, collect(DISTINCT be.event_type) as event_types
        ORDER BY event_count DESC
        LIMIT {limit + 20}
    """)

    companies = []
    while result.has_next():
        row = result.get_next()
        name = row[0]
        
        # 排除VSG
        if not include_vsg and is_vsg(name):
            continue
            
        if len(companies) >= limit:
            break
            
        role = classify_company(name, row[2] or [])
        companies.append({
            "name": name,
            "event_count": row[1],
            "event_types": row[3],
            "role": role
        })

    return {"companies": companies}

@router.get("/company/{name}")
async def get_company_360(name: str):
    """获取公司360度视图"""
    conn = get_connection()

    # 基本信息和事件
    result = conn.execute(f"""
        MATCH (c:Company {{canonical_name: "{name}"}})<-[:INVOLVES]-(be:BusinessEvent)
        RETURN be.id, be.event_type, be.event_date, be.summary, be.amount
        ORDER BY be.event_date DESC
        LIMIT 20
    """)

    events = []
    while result.has_next():
        row = result.get_next()
        events.append({
            "id": row[0],
            "event_type": row[1],
            "event_date": row[2],
            "summary": row[3],
            "amount": row[4]
        })

    # 事件类型统计
    result = conn.execute(f"""
        MATCH (c:Company {{canonical_name: "{name}"}})<-[:INVOLVES]-(be:BusinessEvent)
        RETURN be.event_type, count(*) as cnt
        ORDER BY cnt DESC
    """)

    type_stats = {}
    all_types = []
    while result.has_next():
        row = result.get_next()
        type_stats[row[0]] = row[1]
        all_types.extend([row[0]] * row[1])

    # 关联公司（通过共同事件，排除VSG）
    result = conn.execute(f"""
        MATCH (c:Company {{canonical_name: "{name}"}})<-[:INVOLVES]-(be:BusinessEvent)-[:INVOLVES]->(other:Company)
        WHERE other.canonical_name <> "{name}"
        RETURN other.canonical_name, count(be) as shared_events
        ORDER BY shared_events DESC
        LIMIT 15
    """)

    related = []
    while result.has_next():
        row = result.get_next()
        if not is_vsg(row[0]):
            related.append({"name": row[0], "shared_events": row[1]})
            if len(related) >= 10:
                break

    role = classify_company(name, all_types)

    return {
        "name": name,
        "role": role,
        "events": events,
        "type_stats": type_stats,
        "related_companies": related
    }

@router.get("/event/{event_id}/trace")
async def trace_event(event_id: str):
    """追溯事件到源邮件（核心钻取功能）"""
    conn = get_connection()
    
    # 获取事件详情
    result = conn.execute(f"""
        MATCH (be:BusinessEvent {{id: "{event_id}"}})
        OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
        OPTIONAL MATCH (be)-[:HAS_ID]->(id:Identifier)
        RETURN be.event_type, be.event_date, be.summary, be.amount, be.currency,
               collect(DISTINCT c.canonical_name) as companies,
               collect(DISTINCT {{type: id.id_type, value: id.val}}) as identifiers
    """)
    
    if not result.has_next():
        raise HTTPException(status_code=404, detail="Event not found")
    
    row = result.get_next()
    event_info = {
        "id": event_id,
        "event_type": row[0],
        "event_date": row[1],
        "summary": row[2],
        "amount": row[3],
        "currency": row[4],
        "companies": [c for c in (row[5] or []) if c and not is_vsg(c)],
        "identifiers": [i for i in (row[10] or []) if i.get("value")]
    }
    
    # 获取源邮件
    result = conn.execute(f"""
        MATCH (be:BusinessEvent {{id: "{event_id}"}})<-[:EVIDENCES]-(e:Email)
        RETURN e.id, e.subject, e.sender, e.sent_at, '' as body_preview,
               '' as attachments
        ORDER BY e.sent_at DESC
    """)
    
    emails = []
    while result.has_next():
        row = result.get_next()
        emails.append({
            "message_id": row[0],
            "subject": row[1],
            "from": row[2],
            "date": row[3],
            "preview": (row[4] or "")[:200],
            "attachments": [a for a in (row[5] or []) if a]
        })
    
    return {
        "event": event_info,
        "source_emails": emails,
        "trace_depth": len(emails)
    }

@router.get("/trace/{identifier}")
async def trace_identifier(identifier: str):
    """追溯标识符（发票号、PO号等）"""
    conn = get_connection()

    result = conn.execute(f"""
        MATCH (id:Identifier)<-[:HAS_ID]-(be:BusinessEvent)
        WHERE id.val CONTAINS "{identifier}"
        OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
        OPTIONAL MATCH (be)<-[:EVIDENCES]-(e:Email)
        RETURN id.id_type, id.val, be.id, be.event_type, be.event_date, be.summary,
               collect(DISTINCT c.canonical_name) as companies, e.subject, e.message_id
        ORDER BY be.event_date
    """)

    traces = []
    while result.has_next():
        row = result.get_next()
        traces.append({
            "identifier_type": row[0],
            "identifier_value": row[1],
            "event_id": row[2],
            "event_type": row[3],
            "event_date": row[4],
            "summary": row[5],
            "companies": [c for c in (row[10] or []) if c and not is_vsg(c)],
            "email_subject": row[7],
            "email_id": row[8]
        })

    return {"identifier": identifier, "traces": traces, "count": len(traces)}

@router.post("/query")
async def execute_query(req: QueryRequest):
    """执行自定义Cypher查询"""
    conn = get_connection()

    # 安全检查：只允许读操作
    cypher_lower = req.cypher.lower()
    if any(kw in cypher_lower for kw in ["create", "delete", "set", "merge", "drop"]):
        raise HTTPException(status_code=400, detail="Only read queries allowed")

    try:
        result = conn.execute(req.cypher)

        rows = []
        columns = result.get_column_names()

        count = 0
        while result.has_next() and count < req.limit:
            rows.append(result.get_next())
            count += 1

        return {"columns": columns, "rows": rows, "count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/chart/event-types")
async def chart_event_types():
    """事件类型分布图表数据"""
    conn = get_connection()

    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN ['Payment', 'Shipment', 'Contract', 'Order', 'Quotation']
        RETURN be.event_type, count(*) as cnt
        ORDER BY cnt DESC
    """)

    data = []
    while result.has_next():
        row = result.get_next()
        data.append({"name": row[0], "value": row[1]})

    return {
        "chart_type": "pie",
        "title": "Event Type Distribution",
        "data": data
    }

@router.get("/chart/monthly-trend")
async def chart_monthly_trend(event_type: Optional[str] = None):
    """月度趋势图表数据"""
    conn = get_connection()

    where = f"WHERE be.event_type = '{event_type}'" if event_type else ""

    result = conn.execute(f"""
        MATCH (be:BusinessEvent)
        {where}
        WHERE be.event_date IS NOT NULL AND be.event_date <> ''
        RETURN substring(be.event_date, 0, 7) as month, count(*) as cnt
        ORDER BY month
    """)

    months = []
    counts = []
    while result.has_next():
        row = result.get_next()
        if row[0]:
            months.append(row[0])
            counts.append(row[1])

    return {
        "chart_type": "line",
        "title": f"Monthly Trend" + (f" - {event_type}" if event_type else ""),
        "xAxis": months,
        "series": [{"name": "Events", "data": counts}]
    }

@router.get("/chart/top-companies")
async def chart_top_companies(limit: int = 10, include_vsg: bool = False):
    """Top公司图表数据（默认排除VSG）"""
    conn = get_connection()

    result = conn.execute(f"""
        MATCH (c:Company)<-[:INVOLVES]-(be:BusinessEvent)
        RETURN c.canonical_name, count(be) as cnt
        ORDER BY cnt DESC
        LIMIT {limit + 10}
    """)

    names = []
    counts = []
    while result.has_next():
        row = result.get_next()
        name = row[0]
        
        # 排除VSG
        if not include_vsg and is_vsg(name):
            continue
            
        if len(names) >= limit:
            break
            
        names.append(name[:20] if name else "Unknown")
        counts.append(row[1])

    return {
        "chart_type": "bar",
        "title": f"Top {limit} Companies by Events",
        "xAxis": names,
        "series": [{"name": "Events", "data": counts}]
    }

@router.get("/company-roles")
async def get_company_roles(limit: int = 30):
    """按角色分类获取公司"""
    conn = get_connection()

    result = conn.execute(f"""
        MATCH (c:Company)<-[:INVOLVES]-(be:BusinessEvent)
        RETURN c.canonical_name, count(be), collect(be.event_type)
        ORDER BY count(be) DESC
        LIMIT {limit + 20}
    """)

    roles = {"Customer": [], "Supplier": [], "Logistics": [], "Bank": [], "Partner": []}
    
    while result.has_next():
        row = result.get_next()
        name = row[0]
        
        if is_vsg(name):
            continue
            
        role = classify_company(name, row[2] or [])
        if len(roles[role]) < 10:
            roles[role].append({
                "name": name,
                "event_count": row[1]
            })

    return roles


# ============ 新增：业务看板端点 ============

@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """获取业务看板汇总"""
    conn = get_connection()
    
    summary = {}
    
    # 按 direction 统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.direction <> "unknown" AND be.direction <> ""
        RETURN be.direction, count(*) as cnt, sum(be.amount) as total_amount
        ORDER BY cnt DESC
    """)
    direction_stats = {}
    while result.has_next():
        r = result.get_next()
        direction_stats[r[0]] = {"count": r[1], "amount": r[2] or 0}
    summary["by_direction"] = direction_stats
    
    # 按 status 统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.status <> "unknown" AND be.status <> ""
        RETURN be.status, count(*) as cnt
        ORDER BY cnt DESC
    """)
    status_stats = {}
    while result.has_next():
        r = result.get_next()
        status_stats[r[0]] = r[1]
    summary["by_status"] = status_stats
    
    # 按 type + direction 金额统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.amount > 0
        RETURN be.event_type, be.direction, sum(be.amount) as total, count(*) as cnt
        ORDER BY total DESC
    """)
    type_amounts = []
    while result.has_next():
        r = result.get_next()
        type_amounts.append({
            "event_type": r[0], "direction": r[1], 
            "total_amount": r[2], "count": r[3]
        })
    summary["amounts_by_type"] = type_amounts
    
    return summary


@router.get("/dashboard/finance")
async def get_finance_dashboard(limit: int = 50):
    """财务看板 - Payment 事件"""
    conn = get_connection()
    
    # 汇总
    result = conn.execute("""
        MATCH (be:BusinessEvent) WHERE be.event_type = "Payment"
        RETURN be.direction, sum(be.amount) as total, count(*) as cnt
        ORDER BY total DESC
    """)
    totals = {}
    while result.has_next():
        r = result.get_next()
        totals[r[0] or "unknown"] = {"amount": r[1] or 0, "count": r[2]}
    
    # 最近记录
    result = conn.execute(f"""
        MATCH (be:BusinessEvent) WHERE be.event_type = "Payment"
        RETURN be.id, be.event_date, be.summary, be.amount, be.currency,
               be.direction, be.status, be.counterparty, be.counterparty_role
        ORDER BY be.event_date DESC
        LIMIT {limit}
    """)
    
    records = []
    while result.has_next():
        r = result.get_next()
        records.append({
            "id": r[0], "date": r[1], "summary": r[2], 
            "amount": r[3], "currency": r[4],
            "direction": r[5], "status": r[6],
            "counterparty": r[7], "counterparty_role": r[8]
        })
    
    return {
        "totals": totals,
        "records": records,
        "inbound_total": totals.get("inbound", {}).get("amount", 0),
        "outbound_total": totals.get("outbound", {}).get("amount", 0)
    }


@router.get("/dashboard/logistics")
async def get_logistics_dashboard(limit: int = 50):
    """物流看板 - Shipment 事件"""
    conn = get_connection()
    
    # 按状态统计
    result = conn.execute("""
        MATCH (be:BusinessEvent) WHERE be.event_type = "Shipment"
        RETURN be.status, be.direction, count(*) as cnt
        ORDER BY cnt DESC
    """)
    status_stats = []
    while result.has_next():
        r = result.get_next()
        status_stats.append({"status": r[0], "direction": r[1], "count": r[2]})
    
    # 最近记录
    result = conn.execute(f"""
        MATCH (be:BusinessEvent) WHERE be.event_type = "Shipment"
        RETURN be.id, be.event_date, be.summary, be.amount, be.currency,
               be.direction, be.status, be.counterparty, be.counterparty_role
        ORDER BY be.event_date DESC
        LIMIT {limit}
    """)
    
    records = []
    while result.has_next():
        r = result.get_next()
        records.append({
            "id": r[0], "date": r[1], "summary": r[2],
            "amount": r[3], "currency": r[4],
            "direction": r[5], "status": r[6],
            "counterparty": r[7], "counterparty_role": r[8]
        })
    
    return {"stats": status_stats, "records": records}


@router.get("/dashboard/deals")
async def get_deals_dashboard(limit: int = 50):
    """商务看板 - Contract/Order/Quotation"""
    conn = get_connection()
    
    # 按类型金额统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN [Contract, Order, Quotation]
        RETURN be.event_type, be.status, sum(be.amount) as total, count(*) as cnt
        ORDER BY total DESC
    """)
    type_stats = []
    while result.has_next():
        r = result.get_next()
        type_stats.append({
            "event_type": r[0], "status": r[1], 
            "total_amount": r[2] or 0, "count": r[3]
        })
    
    # 最近记录
    result = conn.execute(f"""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN [Contract, Order, Quotation]
        RETURN be.id, be.event_type, be.event_date, be.summary, be.amount, be.currency,
               be.direction, be.status, be.counterparty, be.counterparty_role
        ORDER BY be.event_date DESC
        LIMIT {limit}
    """)
    
    records = []
    while result.has_next():
        r = result.get_next()
        records.append({
            "id": r[0], "event_type": r[1], "date": r[2], "summary": r[3],
            "amount": r[4], "currency": r[5],
            "direction": r[6], "status": r[7],
            "counterparty": r[8], "counterparty_role": r[9]
        })
    
    return {"stats": type_stats, "records": records}


@router.get("/dashboard/full-stats")
async def get_full_dashboard_stats():
    """获取完整的业务统计（从数据库聚合）"""
    conn = get_connection()
    stats = {}
    
    # 1. 总事件数
    result = conn.execute("MATCH (be:BusinessEvent) RETURN count(*)")
    stats["total_events"] = result.get_next()[0]
    
    # 2. 按事件类型统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN ['Payment', 'Shipment', 'Contract', 'Order', 'Quotation']
        RETURN be.event_type, count(*) as cnt, sum(be.amount) as total_amount
        ORDER BY cnt DESC
    """)
    by_type = []
    while result.has_next():
        r = result.get_next()
        by_type.append({"type": r[0], "count": r[1], "amount": r[2] or 0})
    stats["by_type"] = by_type
    
    # 3. 按状态统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN ['Payment', 'Shipment', 'Contract', 'Order', 'Quotation']
        RETURN be.status, count(*) as cnt
        ORDER BY cnt DESC
    """)
    by_status = {}
    while result.has_next():
        r = result.get_next()
        by_status[r[0]] = r[1]
    stats["by_status"] = by_status
    
    # 4. 按方向统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type IN ['Payment', 'Shipment', 'Contract', 'Order', 'Quotation']
        RETURN be.direction, count(*) as cnt, sum(be.amount) as total_amount
        ORDER BY cnt DESC
    """)
    by_direction = {}
    while result.has_next():
        r = result.get_next()
        by_direction[r[0]] = {"count": r[1], "amount": r[2] or 0}
    stats["by_direction"] = by_direction
    
    # 5. 交易对手统计（带简单归一化）
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.counterparty IS NOT NULL AND be.counterparty <> ""
        RETURN be.counterparty, be.counterparty_role, count(*) as cnt, sum(be.amount) as total_amount
        ORDER BY cnt DESC
        LIMIT 50
    """)
    counterparties_raw = []
    while result.has_next():
        r = result.get_next()
        counterparties_raw.append({
            "name": r[0], "role": r[1], "count": r[2], "amount": r[3] or 0
        })
    
    # 简单归一化：合并名称相似的公司
    def normalize_name(name):
        if not name:
            return ""
        n = name.upper().strip()
        # 移除尾部标点
        n = n.rstrip(".,;:")
        # 常见缩写统一
        n = n.replace(" CO.,", " CO").replace(" CO.", " CO")
        n = n.replace(" LTD.", " LTD").replace(" LTD,", " LTD")
        n = n.replace(" PTE.", " PTE").replace(" PTE,", " PTE")
        return n
    
    merged = {}
    for cp in counterparties_raw:
        key = normalize_name(cp["name"])
        if key in merged:
            merged[key]["count"] += cp["count"]
            merged[key]["amount"] += cp["amount"]
        else:
            merged[key] = {
                "name": cp["name"],  # 保留原始名称
                "role": cp["role"],
                "count": cp["count"],
                "amount": cp["amount"]
            }
    
    # 按 count 排序
    stats["counterparties"] = sorted(merged.values(), key=lambda x: x["count"], reverse=True)[:20]
    
    # 6. 按角色统计
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.counterparty_role IS NOT NULL AND be.counterparty_role <> "" AND be.counterparty_role <> "other"
        RETURN be.counterparty_role, count(*) as cnt
        ORDER BY cnt DESC
    """)
    by_role = {}
    while result.has_next():
        r = result.get_next()
        by_role[r[0]] = r[1]
    stats["by_role"] = by_role
    
    return stats
