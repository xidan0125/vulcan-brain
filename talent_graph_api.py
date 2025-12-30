"""

人才图谱 API V2 - 支持时间维度筛选

所有端点都支持 time_window 参数: 30d, 90d, 180d, 365d, all
"""
import json

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Literal
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from pymongo import MongoClient

# 有效的时间窗口
VALID_TIME_WINDOWS = ["30d", "90d", "180d", "365d", "all"]

def get_db():
    client = MongoClient("mongodb://localhost:27017")
    return client.vulcan_brain


def get_collection_names(time_window: str) -> tuple:
    """根据时间窗口获取集合名"""
    if time_window == "all" or time_window not in VALID_TIME_WINDOWS:
        return "talent_nodes", "talent_edges", "risk_alerts"
    else:
        return (
            f"talent_nodes_{time_window}",
            f"talent_edges_{time_window}",
            f"risk_alerts_{time_window}"
        )


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/talent-graph", tags=["talent-graph"])


# ============ Pydantic Models ============

class OrganizationOverview(BaseModel):
    """组织全景"""
    time_window: str
    total_internal: int
    total_external: int
    total_edges: int
    health_score: float
    key_risks: List[dict]
    top_influencers: List[dict]
    function_distribution: dict
    community_count: int


class TimeWindowInfo(BaseModel):
    """时间窗口信息"""
    windows: List[dict]
    current: str


# ============ New: Time Windows Endpoint ============

@router.get("/time-windows", response_model=TimeWindowInfo)
async def get_time_windows():
    """获取可用的时间窗口及各窗口的数据量"""
    db = get_db()
    
    windows = []
    for tw in VALID_TIME_WINDOWS:
        nodes_col, edges_col, _ = get_collection_names(tw)
        node_count = db[nodes_col].count_documents({"is_internal": True})
        edge_count = db[edges_col].count_documents({})
        
        label = {
            "30d": "近30天",
            "90d": "近90天",
            "180d": "近半年",
            "365d": "近一年",
            "all": "全部数据"
        }.get(tw, tw)
        
        windows.append({
            "id": tw,
            "label": label,
            "node_count": node_count,
            "edge_count": edge_count
        })
    
    return TimeWindowInfo(
        windows=windows,
        current="all"
    )


# ============ API Endpoints (with time_window support) ============

@router.get("/overview", response_model=OrganizationOverview)
async def get_organization_overview(
    time_window: str = Query(default="all", description="时间窗口: 30d, 90d, 180d, 365d, all")
):
    """
    组织全景视图
    
    CEO视角：公司整体沟通健康度、关键风险、核心人物
    """
    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Invalid time_window. Valid options: {VALID_TIME_WINDOWS}")
    
    db = get_db()
    nodes_col, edges_col, risks_col = get_collection_names(time_window)
    
    # 基础统计
    total_internal = db[nodes_col].count_documents({"is_internal": True})
    total_external = db[nodes_col].count_documents({"is_internal": False})
    total_edges = db[edges_col].count_documents({})
    
    # 健康度评分
    high_risks = db[risks_col].count_documents({"severity": "high"})
    medium_risks = db[risks_col].count_documents({"severity": "medium"})
    health_score = max(0, 100 - high_risks * 5 - medium_risks * 2)
    
    # 关键风险 TOP 5
    key_risks = list(db[risks_col].find(
        {"severity": "high"},
        {"_id": 0, "type": 1, "detail": 1, "sole_maintainer": 1, "person": 1, "domain": 1}
    ).sort("severity", -1).limit(5))
    
    # TOP 影响力人物
    top_influencers = list(db[nodes_col].find(
        {"is_internal": True, "network_metrics.influence_score": {"$exists": True}},
        {"_id": 0, "email": 1, "network_metrics.influence_score": 1, 
         "function_metrics.primary_function": 1, "external_metrics.external_domain_count": 1}
    ).sort("network_metrics.influence_score", -1).limit(10))
    
    top_influencers = [{
        "email": p["email"],
        "name": p["email"].split("@")[0],
        "influence_score": round(p.get("network_metrics", {}).get("influence_score", 0), 3),
        "function": p.get("function_metrics", {}).get("primary_function", "Unknown"),
        "external_reach": p.get("external_metrics", {}).get("external_domain_count", 0)
    } for p in top_influencers]
    
    # 职能分布
    func_agg = db[nodes_col].aggregate([
        {"$match": {"is_internal": True, "function_metrics.primary_function": {"$exists": True}}},
        {"$group": {"_id": "$function_metrics.primary_function", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ])
    function_distribution = {doc["_id"]: doc["count"] for doc in func_agg}
    
    # 社区数量
    community_agg = db[nodes_col].aggregate([
        {"$match": {"is_internal": True, "network_metrics.community_id": {"$exists": True}}},
        {"$group": {"_id": "$network_metrics.community_id"}}
    ])
    community_count = len(list(community_agg))
    
    return OrganizationOverview(
        time_window=time_window,
        total_internal=total_internal,
        total_external=total_external,
        total_edges=total_edges,
        health_score=health_score,
        key_risks=key_risks,
        top_influencers=top_influencers,
        function_distribution=function_distribution,
        community_count=community_count
    )


@router.get("/functions")
async def get_functions_overview(
    time_window: str = Query(default="all", description="时间窗口: 30d, 90d, 180d, 365d, all")
):
    """职能概览"""
    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Invalid time_window")
    
    db = get_db()
    nodes_col, _, _ = get_collection_names(time_window)
    
    pipeline = [
        {"$match": {"is_internal": True, "function_metrics.primary_function": {"$exists": True}}},
        {"$group": {
            "_id": "$function_metrics.primary_function",
            "members": {"$push": {
                "email": "$email",
                "influence": "$network_metrics.influence_score",
                "external_reach": "$external_metrics.external_domain_count"
            }},
            "count": {"$sum": 1},
            "total_external_reach": {"$sum": "$external_metrics.external_domain_count"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    results = list(db[nodes_col].aggregate(pipeline))
    
    functions = []
    for r in results:
        members = sorted(r["members"], key=lambda x: x.get("influence", 0) or 0, reverse=True)
        
        functions.append({
            "function": r["_id"],
            "member_count": r["count"],
            "total_external_reach": r["total_external_reach"],
            "key_members": [{
                "email": m["email"],
                "name": m["email"].split("@")[0],
                "influence": round(m.get("influence", 0) or 0, 3),
                "external_reach": m.get("external_reach", 0) or 0
            } for m in members[:5]]
        })
    
    return {"time_window": time_window, "functions": functions}


@router.get("/function/{function_name}")
async def get_function_detail(
    function_name: str,
    time_window: str = Query(default="all", description="时间窗口")
):
    """单个职能的详细视图"""
    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Invalid time_window")
    
    db = get_db()
    nodes_col, _, risks_col = get_collection_names(time_window)
    
    members = list(db[nodes_col].find(
        {"is_internal": True, "function_metrics.primary_function": function_name},
        {"_id": 0}
    ).sort("network_metrics.influence_score", -1))
    
    if not members:
        raise HTTPException(status_code=404, detail=f"Function {function_name} not found")
    
    member_emails = [m["email"] for m in members]
    risks = list(db[risks_col].find({
        "$or": [
            {"sole_maintainer": {"$in": member_emails}},
            {"person": {"$in": member_emails}}
        ]
    }, {"_id": 0}))
    
    return {
        "time_window": time_window,
        "function": function_name,
        "member_count": len(members),
        "members": [{
            "email": m["email"],
            "name": m["email"].split("@")[0],
            "influence_score": round(m.get("network_metrics", {}).get("influence_score", 0), 3),
            "external_reach": m.get("external_metrics", {}).get("external_domain_count", 0),
            "is_function_owner": m.get("function_metrics", {}).get("is_function_owner", False),
            "primary_topic": m.get("function_metrics", {}).get("primary_topic", "")
        } for m in members],
        "risks": risks,
        "risk_count": len(risks)
    }


@router.get("/person/{email}")
async def get_person_profile(
    email: str,
    time_window: str = Query(default="all", description="时间窗口")
):
    """个人深度画像"""
    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Invalid time_window")
    
    db = get_db()
    nodes_col, edges_col, risks_col = get_collection_names(time_window)
    
    person = db[nodes_col].find_one({"email": email})
    if not person:
        person = db[nodes_col].find_one({"email": {"$regex": email, "$options": "i"}})
    
    if not person:
        raise HTTPException(status_code=404, detail=f"Person {email} not found in {time_window}")
    
    email = person["email"]
    network = person.get("network_metrics", {})
    func = person.get("function_metrics", {})
    external = person.get("external_metrics", {})
    
    influence_score = network.get("influence_score", 0)
    higher_count = db[nodes_col].count_documents({
        "is_internal": True,
        "network_metrics.influence_score": {"$gt": influence_score}
    })
    influence_rank = higher_count + 1
    
    strategic_value = {
        "information_hub": {
            "score": round(network.get("betweenness_centrality", 0), 4),
            "interpretation": _interpret_betweenness(network.get("betweenness_centrality", 0))
        },
        "external_resources": {
            "domain_count": external.get("external_domain_count", 0),
            "contact_count": external.get("external_contact_count", 0),
            "exclusive_contacts": external.get("exclusive_external_contacts", 0),
            "interpretation": _interpret_external(external)
        },
        "irreplaceability": {
            "fragmentation_impact": network.get("fragmentation_impact", 0),
            "interpretation": _interpret_irreplaceability(network.get("fragmentation_impact", 0))
        },
        "structural_position": {
            "constraint": network.get("constraint", 0),
            "is_broker": network.get("constraint", 1) < 0.5,
            "interpretation": _interpret_constraint(network.get("constraint", 0))
        }
    }
    
    # 内部关系
    internal_edges = list(db[edges_col].find({
        "$or": [{"from_email": email}, {"to_email": email}],
    }).sort("interaction_count", -1).limit(20))
    
    internal_connections = []
    for edge in internal_edges:
        other = edge["to_email"] if edge["from_email"] == email else edge["from_email"]
        other_node = db[nodes_col].find_one({"email": other})
        if other_node and other_node.get("is_internal"):
            internal_connections.append({
                "email": other,
                "name": other.split("@")[0],
                "interaction_count": edge.get("interaction_count", 0),
                "function": other_node.get("function_metrics", {}).get("primary_function", "Unknown")
            })
        if len(internal_connections) >= 10:
            break
    
    # 外部关系
    external_edges = list(db[edges_col].find({
        "$or": [{"from_email": email}, {"to_email": email}],
    }).sort("interaction_count", -1))
    
    domain_stats = {}
    for edge in external_edges:
        other = edge["to_email"] if edge["from_email"] == email else edge["from_email"]
        if "vulcanshield" not in other.lower():
            domain = other.split("@")[1] if "@" in other else other
            if domain not in domain_stats:
                domain_stats[domain] = {"count": 0, "contacts": []}
            domain_stats[domain]["count"] += edge.get("interaction_count", 0)
            domain_stats[domain]["contacts"].append(other)
    
    external_connections = sorted([
        {"domain": d, "interaction_count": s["count"], "contact_count": len(set(s["contacts"]))}
        for d, s in domain_stats.items()
    ], key=lambda x: x["interaction_count"], reverse=True)[:10]
    
    risks = list(db[risks_col].find({
        "$or": [{"sole_maintainer": email}, {"person": email}]
    }, {"_id": 0}))
    
    communication_pattern = {
        "work_pattern": network.get("work_pattern", "normal"),
        "degree_centrality": round(network.get("degree_centrality", 0), 4),
        "community_id": network.get("community_id"),
        "is_bridge": network.get("is_bridge_node", False)
    }
    
    return {
        "time_window": time_window,
        "email": email,
        "name": email.split("@")[0],
        "is_internal": person.get("is_internal", False),
        "primary_function": func.get("primary_function", "Unknown"),
        "primary_topic": func.get("primary_topic", ""),
        "influence_rank": influence_rank,
        "influence_score": round(influence_score, 4),
        "burnout_score": person.get("risk_metrics", {}).get("burnout_score"),
        "flight_score": person.get("risk_metrics", {}).get("flight_score"),
        "strategic_value": strategic_value,
        "internal_connections": internal_connections,
        "external_connections": external_connections,
        "risks": risks,
        "communication_pattern": communication_pattern
    }


@router.get("/person/{email}/evidence")
async def get_person_evidence(
    email: str,
    related_to: Optional[str] = None,
    limit: int = Query(default=20, le=100)
):
    """证据溯源 - 查看具体邮件 (邮件总是从原始集合查询)"""
    db = get_db()
    
    query = {
        "$or": [
            {"from.address": {"$regex": email, "$options": "i"}},
            {"to.address": {"$regex": email, "$options": "i"}},
            {"cc.address": {"$regex": email, "$options": "i"}}
        ]
    }
    
    if related_to:
        query = {
            "$and": [
                query,
                {"$or": [
                    {"from.address": {"$regex": related_to, "$options": "i"}},
                    {"to.address": {"$regex": related_to, "$options": "i"}},
                    {"cc.address": {"$regex": related_to, "$options": "i"}}
                ]}
            ]
        }
    
    emails = list(db.emails.find(query).sort("date", -1).limit(limit))
    
    evidence = []
    for e in emails:
        evidence.append({
            "id": str(e.get("_id", "")),
            "date": e.get("date"),
            "subject": e.get("subject", "(No Subject)"),
            "from": e.get("from", {}).get("address", ""),
            "to": [r.get("address", "") for r in e.get("to", [])],
            "snippet": (e.get("body", "") or "")[:200] + "..." if e.get("body") else ""
        })
    
    return {
        "person": email,
        "related_to": related_to,
        "total_found": len(evidence),
        "evidence": evidence
    }


@router.get("/risks")
async def get_all_risks(
    time_window: str = Query(default="all", description="时间窗口"),
    severity: Optional[str] = None,
    risk_type: Optional[str] = None
):
    """风险预警列表"""
    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Invalid time_window")
    
    db = get_db()
    _, _, risks_col = get_collection_names(time_window)
    
    query = {}
    if severity:
        query["severity"] = severity
    if risk_type:
        query["type"] = risk_type
    
    risks = list(db[risks_col].find(query, {"_id": 0}).sort("severity", -1).limit(100))
    
    stats = {
        "high": db[risks_col].count_documents({"severity": "high"}),
        "medium": db[risks_col].count_documents({"severity": "medium"}),
        "low": db[risks_col].count_documents({"severity": "low"})
    }
    
    return {
        "time_window": time_window,
        "stats": stats,
        "risks": risks
    }


@router.get("/graph-data")
async def get_graph_data(
    time_window: str = Query(default="all", description="时间窗口"),
    include_external: bool = False,
    min_interactions: int = 5
):
    """图可视化数据 (Cytoscape.js 格式)"""
    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Invalid time_window")
    
    db = get_db()
    nodes_col, edges_col, _ = get_collection_names(time_window)
    
    node_query = {"is_internal": True} if not include_external else {}
    nodes = list(db[nodes_col].find(node_query, {
        "_id": 0, "email": 1, "is_internal": 1,
        "network_metrics.influence_score": 1,
        "function_metrics.primary_function": 1
    }))
    
    node_emails = {n["email"] for n in nodes}
    
    edges = list(db[edges_col].find(
        {"interaction_count": {"$gte": min_interactions}},
        {"_id": 0, "from_email": 1, "to_email": 1, "interaction_count": 1}
    ))
    
    if not include_external:
        edges = [e for e in edges if e["from_email"] in node_emails and e["to_email"] in node_emails]
    
    cyto_nodes = [{
        "data": {
            "id": n["email"],
            "label": n["email"].split("@")[0],
            "influence": n.get("network_metrics", {}).get("influence_score", 0),
            "function": n.get("function_metrics", {}).get("primary_function", "Unknown"),
            "isInternal": n.get("is_internal", False)
        }
    } for n in nodes]
    
    cyto_edges = [{
        "data": {
            "source": e["from_email"],
            "target": e["to_email"],
            "weight": e.get("interaction_count", 0)
        }
    } for e in edges]
    
    return {
        "time_window": time_window,
        "nodes": cyto_nodes,
        "edges": cyto_edges
    }


# ============ Compare Time Windows ============

@router.get("/compare")
async def compare_time_windows(
    email: str,
    windows: str = Query(default="30d,90d,180d,365d,all", description="逗号分隔的时间窗口")
):
    """
    比较同一个人在不同时间窗口的指标变化
    
    用于发现趋势：活跃度上升/下降、影响力变化、关系网络变化
    """
    db = get_db()
    window_list = [w.strip() for w in windows.split(",") if w.strip() in VALID_TIME_WINDOWS]
    
    comparison = []
    for tw in window_list:
        nodes_col, _, _ = get_collection_names(tw)
        person = db[nodes_col].find_one({"email": {"$regex": email, "$options": "i"}})
        
        if person:
            network = person.get("network_metrics", {})
            external = person.get("external_metrics", {})
            
            comparison.append({
                "time_window": tw,
                "found": True,
                "influence_score": round(network.get("influence_score", 0), 4),
                "degree_centrality": round(network.get("degree_centrality", 0), 4),
                "betweenness_centrality": round(network.get("betweenness_centrality", 0), 4),
                "external_domain_count": external.get("external_domain_count", 0),
                "external_contact_count": external.get("external_contact_count", 0)
            })
        else:
            comparison.append({
                "time_window": tw,
                "found": False
            })
    
    return {
        "email": email,
        "comparison": comparison
    }


# ============ Helper Functions ============

def _interpret_betweenness(score: float) -> str:
    if score > 0.1:
        return "核心信息枢纽，大量跨部门沟通经过此人"
    elif score > 0.05:
        return "重要的信息桥梁，连接多个群体"
    elif score > 0.01:
        return "有一定的桥梁作用"
    else:
        return "主要在自己的圈子内沟通"


def _interpret_external(external: dict) -> str:
    domains = external.get("external_domain_count", 0)
    exclusive = external.get("exclusive_external_contacts", 0)
    
    if domains > 100:
        if exclusive > 50:
            return f"掌握大量外部资源({domains}个组织)，其中{exclusive}个是独占联系"
        return f"广泛的外部网络({domains}个组织)"
    elif domains > 30:
        return f"较好的外部关系网络({domains}个组织)"
    else:
        return "外部联系较少，主要面向内部"


def _interpret_irreplaceability(fragmentation: float) -> str:
    if fragmentation > 0.2:
        return f"极高不可替代性！移除后{fragmentation*100:.1f}%的沟通路径断裂"
    elif fragmentation > 0.1:
        return f"高不可替代性，移除后{fragmentation*100:.1f}%的沟通受影响"
    elif fragmentation > 0.05:
        return f"有一定不可替代性({fragmentation*100:.1f}%影响)"
    else:
        return "可替代性较高，离开影响可控"


def _interpret_constraint(constraint: float) -> str:
    if constraint < 0.3:
        return "结构洞位置，是不同群体之间的关键连接者"
    elif constraint < 0.5:
        return "较好的网络位置，能接触到多元信息"
    else:
        return "网络位置较封闭，主要在紧密群体内"


# ============ AI Insights ============

@router.get("/insights")
async def get_ai_insights(
    time_window: str = Query(default="all", description="时间窗口"),
    force_refresh: bool = False
):
    """使用 Gemini 生成组织洞察"""
    from vulcan_libs.llm_client import UnifiedLLMClient as LLMClient, ChatMessage
    import hashlib

    if time_window not in VALID_TIME_WINDOWS:
        raise HTTPException(status_code=400, detail="Invalid time_window")

    db = get_db()
    nodes_col, edges_col, alerts_col = get_collection_names(time_window)

    # 缓存键
    cache_key = f"ai_insights_{time_window}"

    # 检查缓存 (1小时有效)
    if not force_refresh:
        cached = db.talent_graph_cache.find_one({"key": cache_key})
        if cached:
            from datetime import timedelta
            if datetime.now() - cached.get("created_at", datetime.min) < timedelta(hours=1):
                return cached.get("insights")

    # 收集数据
    nodes = list(db[nodes_col].find({"is_internal": True}))
    alerts = list(db[alerts_col].find({"severity": {"$in": ["high", "medium"]}}))

    # 统计信息
    total_internal = len(nodes)
    total_external = db[nodes_col].count_documents({"is_internal": False})
    total_alerts = len(alerts)
    high_risk_count = sum(1 for a in alerts if a.get("severity") == "high")

    # Top 影响力人员
    top_influencers = sorted(
        nodes,
        key=lambda x: x.get("network_metrics", {}).get("influence_score", 0),
        reverse=True
    )[:5]

    # 职能分布
    function_counts = {}
    for node in nodes:
        func = node.get("function_metrics", {}).get("primary_function", "Unknown")
        function_counts[func] = function_counts.get(func, 0) + 1

    # 风险类型分布
    risk_types = {}
    for alert in alerts:
        rt = alert.get("type", "unknown")
        risk_types[rt] = risk_types.get(rt, 0) + 1

    # 构建 Prompt
    prompt = f"""你是一位组织分析专家。基于以下企业通讯网络数据，生成3-5条关键洞察。

## 组织概况 (时间窗口: {time_window})
- 内部员工: {total_internal} 人
- 外部联系人: {total_external} 人
- 风险预警: {total_alerts} 条 (高风险: {high_risk_count})

## 职能分布
{chr(10).join(f'- {k}: {v}人' for k, v in sorted(function_counts.items(), key=lambda x: -x[1])[:8])}

## TOP 5 影响力人员
{chr(10).join(f'- {p.get("email", "").split("@")[0]}: 影响力 {p.get("network_metrics", {}).get("influence_score", 0):.3f}, 职能: {p.get("function_metrics", {}).get("primary_function", "Unknown")}' for p in top_influencers)}

## 风险类型分布
{chr(10).join(f'- {k}: {v}条' for k, v in sorted(risk_types.items(), key=lambda x: -x[1]))}

请生成洞察，格式为 JSON 数组:
[
  {{"type": "insight|warning|opportunity", "title": "标题", "content": "详细说明", "priority": 1-5}}
]

要求:
1. 洞察要具体可操作，不要泛泛而谈
2. 关注单点故障风险和关键人物
3. 识别组织协作中的瓶颈
4. 提出改进建议"""

    try:
        client = LLMClient()
        response = await client.chat([ChatMessage(role="user", content=prompt)])

        # 解析 JSON
        import re
        json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if json_match:
            insights = json.loads(json_match.group())
        else:
            insights = [{"type": "insight", "title": "分析完成", "content": response.content, "priority": 3}]

        result = {
            "time_window": time_window,
            "generated_at": datetime.now().isoformat(),
            "insights": insights
        }

        # 缓存结果
        db.talent_graph_cache.update_one(
            {"key": cache_key},
            {"$set": {"key": cache_key, "insights": result, "created_at": datetime.now()}},
            upsert=True
        )

        return result

    except Exception as e:
        logger.error(f"AI insights generation failed: {e}")
        return {
            "time_window": time_window,
            "error": str(e),
            "insights": [
                {"type": "warning", "title": "AI 分析暂时不可用", "content": f"请稍后再试: {str(e)}", "priority": 1}
            ]
        }

# ============ AI 组织诊断端点 ============

@router.get("/ai-diagnosis")
async def get_ai_diagnosis(
    time_window: str = Query(default="all", description="时间窗口"),
    force_refresh: bool = Query(default=False, description="强制刷新")
):
    """
    AI 组织智能诊断 - 调用 talent_analyst Gemini Skill
    返回结构化的组织健康诊断报告
    """
    import subprocess
    import os

    db = get_db()
    nodes_col, edges_col, alerts_col = get_collection_names(time_window)

    # 检查缓存 (1小时有效)
    cache_key = f"ai_diagnosis_{time_window}"
    if not force_refresh:
        cached = db.talent_graph_cache.find_one({"key": cache_key})
        if cached:
            cache_time = cached.get("created_at", datetime.min)
            if datetime.now() - cache_time < timedelta(hours=1):
                return cached.get("diagnosis")

    # 收集数据
    nodes = list(db[nodes_col].find({"is_internal": True}))
    external_nodes = list(db[nodes_col].find({"is_internal": False}))
    alerts = list(db[alerts_col].find())

    # 从 talent_edges 计算每个人的边指标
    def compute_edge_metrics(email: str) -> dict:
        """从 talent_edges 计算外部联系人数和内部连接数，包括域名细分"""
        from collections import defaultdict

        # 域名分类
        AFFILIATE_DOMAINS = {
            "rongrongnm.com",  # 生产厂
            # 可以添加其他关联公司域名
        }
        LOGISTICS_KEYWORDS = ["logistics", "expeditors", "cargo", "freight", "shipping", "dhl", "fedex", "ups", "oocl", "maersk", "cosco", "dpex"]
        SERVICE_KEYWORDS = ["bank", "insurance", "legal", "audit", "consulting"]

        def categorize_domain(domain: str, email_addr: str) -> str:
            """分类域名"""
            domain_lower = domain.lower()
            email_lower = email_addr.lower()

            if domain_lower in AFFILIATE_DOMAINS:
                return "affiliate"
            if any(kw in domain_lower or kw in email_lower for kw in LOGISTICS_KEYWORDS):
                return "logistics"
            if any(kw in domain_lower for kw in SERVICE_KEYWORDS):
                return "service"
            return "business"  # 真正的业务联系

        internal_out = 0
        external_out = 0
        internal_in = 0
        external_in = 0

        # 域名统计 - 按类别分
        domain_stats = defaultdict(lambda: {"count": 0, "interactions": 0, "category": "business"})
        top_contacts = []
        category_stats = {"business": 0, "affiliate": 0, "logistics": 0, "service": 0}

        # 发出的边
        for edge in db[edges_col].find({"from_email": email}):
            to = edge.get("to_email", "")
            interactions = edge.get("interaction_count", 0)
            if to.endswith("vulcanshield.com"):
                internal_out += 1
            else:
                external_out += 1
                domain = to.split("@")[1] if "@" in to else "unknown"
                category = categorize_domain(domain, to)
                domain_stats[domain]["count"] += 1
                domain_stats[domain]["interactions"] += interactions
                domain_stats[domain]["category"] = category
                category_stats[category] += 1
                if interactions > 10 and category == "business":
                    top_contacts.append({
                        "email": to,
                        "interactions": interactions,
                        "direction": "out",
                        "reciprocal": edge.get("is_reciprocal", False)
                    })

        # 收到的边
        for edge in db[edges_col].find({"to_email": email}):
            frm = edge.get("from_email", "")
            interactions = edge.get("interaction_count", 0)
            if frm.endswith("vulcanshield.com"):
                internal_in += 1
            else:
                external_in += 1
                domain = frm.split("@")[1] if "@" in frm else "unknown"
                category = categorize_domain(domain, frm)
                if interactions > 10 and category == "business":
                    existing = [c for c in top_contacts if c["email"] == frm]
                    if not existing:
                        top_contacts.append({
                            "email": frm,
                            "interactions": interactions,
                            "direction": "in",
                            "reciprocal": edge.get("is_reciprocal", False)
                        })

        # 只保留业务类域名
        business_domains = [(d, s) for d, s in domain_stats.items() if s["category"] == "business"]
        sorted_domains = sorted(business_domains, key=lambda x: -x[1]["interactions"])[:10]
        top_contacts.sort(key=lambda x: -x["interactions"])

        return {
            "external_reach": external_out + external_in,
            "internal_degree": internal_out + internal_in,
            "external_out": external_out,
            "external_in": external_in,
            "domain_count": len(domain_stats),
            "business_contacts": category_stats["business"],
            "affiliate_contacts": category_stats["affiliate"],
            "logistics_contacts": category_stats["logistics"],
            "service_contacts": category_stats["service"],
            "top_domains": sorted_domains,
            "top_contacts": top_contacts[:10]
        }

    # Top 影响力人员 (详细信息)
    top_influencers = sorted(
        nodes,
        key=lambda x: x.get("network_metrics", {}).get("influence_score", 0),
        reverse=True
    )[:10]

    # 职能分布
    function_counts = {}
    for node in nodes:
        func = node.get("function_metrics", {}).get("primary_function", "Unknown")
        function_counts[func] = function_counts.get(func, 0) + 1

    # 风险统计
    risk_by_type = {}
    risk_by_severity = {"high": 0, "medium": 0, "low": 0}
    for alert in alerts:
        rt = alert.get("type", "unknown")
        risk_by_type[rt] = risk_by_type.get(rt, 0) + 1
        sev = alert.get("severity", "low")
        risk_by_severity[sev] = risk_by_severity.get(sev, 0) + 1

    # 构建详细的数据 prompt
    data_context = f"""## 组织数据概览 (时间窗口: {time_window})

### 基础统计
- 内部员工总数: {len(nodes)} 人
- 外部联系人总数: {len(external_nodes)} 人
- 风险预警总数: {len(alerts)} 条 (高: {risk_by_severity['high']}, 中: {risk_by_severity['medium']}, 低: {risk_by_severity['low']})

### 职能分布
{chr(10).join(f'- {k}: {v}人 ({round(v/len(nodes)*100, 1)}%)' for k, v in sorted(function_counts.items(), key=lambda x: -x[1]))}

### TOP 10 影响力人员详情
"""

    for i, p in enumerate(top_influencers, 1):
        email = p.get("email", "")
        name = p.get("name", email.split("@")[0])
        func = p.get("function_metrics", {}).get("primary_function", "Unknown")
        influence = p.get("network_metrics", {}).get("influence_score", 0)

        # 从 talent_edges 动态计算边指标
        edge_metrics = compute_edge_metrics(email)
        external_reach = edge_metrics["external_reach"]
        internal_degree = edge_metrics["internal_degree"]

        burnout = p.get("network_metrics", {}).get("burnout_score", 0)
        flight = p.get("network_metrics", {}).get("flight_score", 0)

        # 分类统计
        biz = edge_metrics.get("business_contacts", 0)
        aff = edge_metrics.get("affiliate_contacts", 0)
        log = edge_metrics.get("logistics_contacts", 0)
        svc = edge_metrics.get("service_contacts", 0)

        data_context += f"""
#### {i}. {name} ({email})
- 职能: {func}
- 影响力分数: {influence:.3f}
- 外部联系分类:
  - 业务客户: {biz}人
  - 关联公司(生产厂等): {aff}人
  - 物流服务商: {log}人
  - 其他服务商: {svc}人
- 内部连接: {internal_degree}人
- 燃尽风险: {burnout:.2f}, 离职风险: {flight:.2f}
"""

        # 添加外部联系人细分（仅对关键人物）- 只显示业务客户
        if edge_metrics.get("top_domains"):
            data_context += "\n**主要业务客户/公司:**\n"
            for domain, stats in edge_metrics["top_domains"][:5]:
                data_context += f"  - {domain}: {stats['count']}人, {stats['interactions']}次互动\n"

        if edge_metrics.get("top_contacts"):
            data_context += "\n**高频业务联系人:**\n"
            for contact in edge_metrics["top_contacts"][:5]:
                direction = "⇄" if contact["reciprocal"] else ("→" if contact["direction"] == "out" else "←")
                data_context += f"  - {direction} {contact['email']}: {contact['interactions']}次\n"


    # 风险预警详情
    data_context += "\n### 风险预警详情\n"
    high_alerts = [a for a in alerts if a.get("severity") == "high"]
    for alert in high_alerts[:10]:
        data_context += f"- [{alert.get('severity', 'unknown').upper()}] {alert.get('type', 'unknown')}: {alert.get('person', alert.get('sole_maintainer', alert.get('domain', 'N/A')))}\n"

    # 调用 Gemini talent_analyst skill
    task_prompt = f"""请基于以下组织数据，生成组织健康诊断报告。

{data_context}

特别关注：
1. David Kneale 和 Barry Claypool 都是销售团队的关键人物
2. 分析 David 的资源边界和能力范围 - 他掌握了哪些客户资源？团队对他的依赖度如何？
3. 分析组织的结构性风险和瓶颈
4. 给出具体可执行的改进建议

请按照系统提示词中的格式输出分析报告。"""

    try:
        # 使用 subprocess 调用 run_skill.py
        result = subprocess.run(
            ["python3", "/home/xinyue/vulcan-brain/run_skill.py", "talent", "--stdin"],
            input=task_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/home/xinyue/vulcan-brain"
        )

        if result.returncode != 0:
            raise Exception(f"Skill execution failed: {result.stderr}")

        # 解析输出 (跳过头部装饰)
        output = result.stdout
        # 找到实际内容开始的位置 (跳过 ====== 分隔线)
        lines = output.split('\n')
        content_start = 0
        for i, line in enumerate(lines):
            if line.startswith('===') and i > 0:
                content_start = i + 1
                break

        analysis_content = '\n'.join(lines[content_start:]).strip()

        diagnosis = {
            "time_window": time_window,
            "generated_at": datetime.now().isoformat(),
            "analysis": analysis_content,
            "data_summary": {
                "total_internal": len(nodes),
                "total_external": len(external_nodes),
                "total_alerts": len(alerts),
                "high_risk_count": risk_by_severity['high'],
                "top_influencer": top_influencers[0].get("name", top_influencers[0].get("email", "N/A").split("@")[0]) if top_influencers else "N/A"
            }
        }

        # 缓存结果
        db.talent_graph_cache.update_one(
            {"key": cache_key},
            {"$set": {"key": cache_key, "diagnosis": diagnosis, "created_at": datetime.now()}},
            upsert=True
        )

        return diagnosis

    except subprocess.TimeoutExpired:
        return {
            "time_window": time_window,
            "error": "AI 分析超时，请稍后再试",
            "analysis": None
        }
    except Exception as e:
        logger.error(f"AI diagnosis failed: {e}")
        return {
            "time_window": time_window,
            "error": str(e),
            "analysis": None
        }
