"""
图谱智能 API - Graph Intelligence API
提供智能查询、摘要和洞察功能
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.graph_intelligence_service import (
    query_graph, 
    generate_daily_summary, 
    get_entity_insights
)

router = APIRouter()

# ==================== 请求模型 ====================

class QueryRequest(BaseModel):
    question: str

class EntityRequest(BaseModel):
    entity: str

class SummaryRequest(BaseModel):
    date: Optional[str] = None

# ==================== API 端点 ====================

@router.post("/graph-intel/query")
async def api_query_graph(req: QueryRequest):
    """
    智能图谱查询
    
    输入: 自然语言问题
    输出: 基于图谱的答案
    
    示例: "谁和SpaceX有关系？"
    """
    if not req.question or len(req.question) < 2:
        raise HTTPException(400, "问题太短")
    
    result = await query_graph(req.question)
    return result


@router.post("/graph-intel/summary")
async def api_daily_summary(req: SummaryRequest = None):
    """
    生成每日/周邮件摘要
    
    输入: 可选日期 (YYYY-MM-DD)
    输出: 智能摘要
    """
    date = req.date if req else None
    result = await generate_daily_summary(date)
    return result


@router.get("/graph-intel/summary")
async def api_daily_summary_get():
    """
    获取今日邮件摘要 (GET 版本)
    """
    result = await generate_daily_summary()
    return result


@router.post("/graph-intel/insights")
async def api_entity_insights(req: EntityRequest):
    """
    实体洞察 (客户360视图)
    
    输入: 实体名称 (人名/公司名)
    输出: 完整关系网络和洞察分析
    """
    if not req.entity or len(req.entity) < 2:
        raise HTTPException(400, "实体名称太短")
    
    result = await get_entity_insights(req.entity)
    return result


@router.get("/graph-intel/insights/{entity}")
async def api_entity_insights_get(entity: str):
    """
    实体洞察 (GET 版本)
    
    路径参数: entity - 实体名称
    """
    if not entity or len(entity) < 2:
        raise HTTPException(400, "实体名称太短")
    
    result = await get_entity_insights(entity)
    return result


@router.get("/graph-intel/stats")
async def api_graph_stats():
    """
    获取图谱统计信息
    """
    from services.graph_intelligence_service import get_graph_data
    
    data = get_graph_data()
    relationships = data.get("relationships", [])
    entities = data.get("top_entities", [])
    
    # 关系类型分布
    rel_types = {}
    for r in relationships:
        t = r.get("relation_type", "unknown")
        rel_types[t] = rel_types.get(t, 0) + 1
    
    return {
        "total_entities": len(entities),
        "total_relationships": len(relationships),
        "relation_types": rel_types,
        "generated_at": data.get("generated_at"),
        "version": data.get("version")
    }
