# soul_api.py - Vulcan Brain Soul System API
"""
Soul 灵魂系统 API

三大板块:
1. 数字孪生 (Digital Twin) - 展示 AI 对用户的理解程度
2. 决策推演 (Decision Sim) - 每日虚拟商业情境题
3. 实时资讯 (Real-time Info) - 热点推送 + 观点采集

数据来源:
- Genesis 20问 (冷启动/先天基因)
- 日常交互 (热更新/后天修正)
"""

import os
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from pymongo import MongoClient

# MongoDB 连接
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["vulcan_brain"]

# Collections
soul_stats_col = db["soul_user_stats"]
sandbox_questions_col = db["sandbox_questions"]
soul_interactions_col = db["soul_interactions"]
user_genesis_col = db["user_genesis"]
vision_items_col = db["vision_items"]

router = APIRouter()


# ==================== Pydantic Models ====================

class SoulStatsResponse(BaseModel):
    """数字孪生 - 用户状态响应"""
    user_id: str
    streak_days: int = 0
    last_active_date: Optional[str] = None
    understanding_score: float = 0.5  # 0.0 - 1.0
    score_history: List[Dict] = []
    dimensions: Dict[str, float] = {}  # 雷达图数据
    data_points_collected: int = 0
    insights: List[str] = []  # Vulcan 学到了什么


class SandboxQuestion(BaseModel):
    """沙盘题目"""
    question_id: str
    category: str
    scenario: str
    options: List[Dict]
    prediction: Optional[Dict] = None  # Vulcan 的预测


class SandboxSubmitRequest(BaseModel):
    """提交沙盘答案"""
    question_id: str
    selected_option_id: str


class SandboxSubmitResponse(BaseModel):
    """沙盘答案响应"""
    is_match: bool
    score_delta: float
    new_score: float
    feedback_text: str


class VisionItem(BaseModel):
    """视野 - 资讯条目"""
    item_id: str
    source_type: str
    title: str
    summary: str
    question: str
    options: List[Dict]
    peer_stats: Dict[str, int]
    published_at: str


class VisionReactRequest(BaseModel):
    """视野 - 提交观点"""
    item_id: str
    selected_option_id: str


# ==================== 辅助函数 ====================

def _get_or_create_user_stats(user_id: str) -> dict:
    """获取或创建用户状态"""
    stats = soul_stats_col.find_one({"user_id": user_id})

    if not stats:
        # 尝试从 Genesis 初始化
        genesis = user_genesis_col.find_one({"user_id": user_id})

        initial_score = 0.6 if genesis else 0.3  # 有 Genesis 数据则初始60%
        initial_dimensions = {
            "decision_style": 0.5,
            "risk_appetite": 0.5,
            "market_sense": 0.5,
            "empathy": 0.5,
            "strategy": 0.5,
            "execution": 0.5
        }

        # 如果有 Genesis 数据，用它初始化维度
        if genesis and "dimensions" in genesis:
            initial_dimensions.update(genesis["dimensions"])
            initial_score = sum(initial_dimensions.values()) / len(initial_dimensions)

        stats = {
            "user_id": user_id,
            "streak_days": 0,
            "last_active_date": None,
            "understanding_score": initial_score,
            "score_history": [
                {"date": datetime.now().strftime("%Y-%m-%d"), "score": initial_score}
            ],
            "dimensions": initial_dimensions,
            "data_points_collected": genesis.get("answer_count", 0) if genesis else 0,
            "created_at": datetime.now()
        }
        soul_stats_col.insert_one(stats)

    return stats


def _update_streak(user_id: str) -> int:
    """更新连续天数"""
    stats = soul_stats_col.find_one({"user_id": user_id})
    if not stats:
        return 0

    today = date.today().isoformat()
    last_active = stats.get("last_active_date")

    if last_active == today:
        # 今天已经活跃过
        return stats.get("streak_days", 0)

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if last_active == yesterday:
        # 连续
        new_streak = stats.get("streak_days", 0) + 1
    elif last_active is None:
        # 首次
        new_streak = 1
    else:
        # 断签
        new_streak = 1

    soul_stats_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "streak_days": new_streak,
            "last_active_date": today
        }}
    )

    return new_streak


def _generate_insights(user_id: str) -> List[str]:
    """生成 Vulcan 学到了什么"""
    stats = soul_stats_col.find_one({"user_id": user_id})
    if not stats:
        return ["暂无足够数据生成洞察"]

    dimensions = stats.get("dimensions", {})
    insights = []

    # 基于维度生成洞察
    if dimensions.get("risk_appetite", 0.5) > 0.7:
        insights.append("您在风险决策上倾向于激进策略")
    elif dimensions.get("risk_appetite", 0.5) < 0.3:
        insights.append("您更看重稳健，对风险持谨慎态度")

    if dimensions.get("empathy", 0.5) > 0.7:
        insights.append("在人事决策上，您会优先考虑团队情感")
    elif dimensions.get("empathy", 0.5) < 0.3:
        insights.append("您在人事决策上偏向结果导向，效率优先")

    if dimensions.get("strategy", 0.5) > 0.7:
        insights.append("您擅长长期战略规划，有远见")

    if dimensions.get("execution", 0.5) > 0.7:
        insights.append("您注重执行落地，务实高效")

    if not insights:
        insights.append("正在学习您的决策风格...")

    return insights[:3]  # 最多返回3条


# ==================== API 端点 ====================

@router.get("/soul/stats", response_model=SoulStatsResponse)
async def get_soul_stats(user_id: str = "default_user"):
    """
    获取数字孪生数据

    返回:
    - 连续天数
    - 理解度
    - 雷达图数据
    - 趋势历史
    - 洞察文字
    """
    stats = _get_or_create_user_stats(user_id)
    insights = _generate_insights(user_id)

    return SoulStatsResponse(
        user_id=user_id,
        streak_days=stats.get("streak_days", 0),
        last_active_date=stats.get("last_active_date", ""),
        understanding_score=stats.get("understanding_score", 0.5),
        score_history=stats.get("score_history", []),
        dimensions=stats.get("dimensions", {}),
        data_points_collected=stats.get("data_points_collected", 0),
        insights=insights
    )


@router.get("/soul/sandbox/daily")
async def get_daily_sandbox(user_id: str = "default_user"):
    """
    获取今日决策推演题目

    返回 3 道题，包含 Vulcan 的预测
    """
    from prediction_engine import predict_user_choice

    # 获取今天已做的题目
    today = date.today().isoformat()
    done_today = soul_interactions_col.find({
        "user_id": user_id,
        "type": "sandbox",
        "created_at": {"$gte": datetime.fromisoformat(today)}
    })
    done_ids = [str(d.get("target_id")) for d in done_today]

    # 获取未做的题目
    query = {"is_active": True}
    if done_ids:
        query["_id"] = {"$nin": [ObjectId(id) for id in done_ids]}

    questions = list(sandbox_questions_col.find(query).limit(3))

    result = []
    for q in questions:
        # 生成预测
        prediction = await predict_user_choice(str(q["_id"]), user_id)

        result.append({
            "question_id": str(q["_id"]),
            "category": q.get("category", ""),
            "scenario": q.get("scenario", ""),
            "options": q.get("options", []),
            "prediction": prediction
        })

    return {
        "questions": result,
        "completed_today": len(done_ids),
        "total_daily": 3
    }


@router.post("/soul/sandbox/submit", response_model=SandboxSubmitResponse)
async def submit_sandbox_answer(request: SandboxSubmitRequest, user_id: str = "default_user"):
    """
    提交决策推演答案

    - 比对预测
    - 更新理解度
    - 返回反馈
    """
    # 获取题目
    question = sandbox_questions_col.find_one({"_id": ObjectId(request.question_id)})
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 获取之前的预测
    from prediction_engine import predict_user_choice
    prediction = await predict_user_choice(request.question_id, user_id)

    is_match = prediction.get("option_id") == request.selected_option_id

    # 计算分数变化
    score_delta = 0.002 if is_match else -0.001

    # 更新用户状态
    stats = _get_or_create_user_stats(user_id)
    new_score = min(1.0, max(0.0, stats["understanding_score"] + score_delta))

    # 更新维度 (基于题目类别)
    category = question.get("category", "")
    dimension_map = {
        "HR_DECISION": "empathy",
        "RISK_DECISION": "risk_appetite",
        "STRATEGY_DECISION": "strategy",
        "EXECUTION_DECISION": "execution",
        "MARKET_DECISION": "market_sense"
    }

    dimension_key = dimension_map.get(category, "decision_style")
    new_dimensions = stats.get("dimensions", {})
    if dimension_key in new_dimensions:
        new_dimensions[dimension_key] = min(1.0, new_dimensions[dimension_key] + (0.01 if is_match else 0.005))

    # 更新连续天数
    _update_streak(user_id)

    # 写入数据库
    soul_stats_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "understanding_score": new_score,
            "dimensions": new_dimensions,
            "data_points_collected": stats.get("data_points_collected", 0) + 1
        },
        "$push": {
            "score_history": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "score": new_score
            }
        }}
    )

    # 记录交互
    soul_interactions_col.insert_one({
        "user_id": user_id,
        "type": "sandbox",
        "target_id": ObjectId(request.question_id),
        "prediction": prediction,
        "user_choice": request.selected_option_id,
        "is_match": is_match,
        "sync_delta": score_delta,
        "created_at": datetime.now()
    })

    # 生成反馈文案
    if is_match:
        feedback = f"✓ Vulcan 猜对了！理解度 +{abs(score_delta)*100:.1f}%"
    else:
        feedback = "好的，Vulcan 记住了，正在学习您的思维方式..."

    return SandboxSubmitResponse(
        is_match=is_match,
        score_delta=score_delta,
        new_score=new_score,
        feedback_text=feedback
    )


@router.get("/soul/vision/feed")
async def get_vision_feed(user_id: str = "default_user", limit: int = 10, offset: int = 0):
    """
    获取实时资讯信息流

    返回热点 + 观点问题
    """
    items = list(vision_items_col.find({"is_active": True})
                 .sort("published_at", -1)
                 .skip(offset)
                 .limit(limit))

    result = []
    for item in items:
        result.append({
            "item_id": str(item["_id"]),
            "source_type": item.get("source_type", ""),
            "title": item.get("original_title", ""),
            "summary": item.get("summary", ""),
            "question": item.get("question", "您怎么看？"),
            "options": item.get("options", []),
            "peer_stats": item.get("peer_stats", {}),
            "published_at": item.get("published_at", datetime.now()).isoformat()
        })

    return {"items": result, "total": vision_items_col.count_documents({"is_active": True})}


@router.post("/soul/vision/react")
async def submit_vision_reaction(request: VisionReactRequest, user_id: str = "default_user"):
    """
    提交资讯观点

    记录用户对热点的态度
    """
    item = vision_items_col.find_one({"_id": ObjectId(request.item_id)})
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")

    # 记录交互
    soul_interactions_col.insert_one({
        "user_id": user_id,
        "type": "vision",
        "target_id": ObjectId(request.item_id),
        "user_choice": request.selected_option_id,
        "created_at": datetime.now()
    })

    # 更新统计
    peer_stats = item.get("peer_stats", {})
    peer_stats[request.selected_option_id] = peer_stats.get(request.selected_option_id, 0) + 1

    vision_items_col.update_one(
        {"_id": ObjectId(request.item_id)},
        {"$set": {"peer_stats": peer_stats}}
    )

    # 更新用户状态
    _update_streak(user_id)
    soul_stats_col.update_one(
        {"user_id": user_id},
        {"$inc": {"data_points_collected": 1}}
    )

    return {
        "success": True,
        "peer_stats": peer_stats,
        "feedback": "已记录您的观点"
    }


# ==================== 管理端点 ====================

@router.post("/soul/admin/add_question")
async def add_sandbox_question(
    category: str,
    scenario: str,
    options: List[Dict],
    difficulty: int = 1
):
    """添加沙盘题目"""
    doc = {
        "category": category,
        "difficulty": difficulty,
        "scenario": scenario,
        "options": options,
        "source": "admin",
        "is_active": True,
        "created_at": datetime.now()
    }
    result = sandbox_questions_col.insert_one(doc)
    return {"success": True, "question_id": str(result.inserted_id)}


@router.post("/soul/admin/seed_questions")
async def seed_initial_questions():
    """初始化种子题库"""
    questions = [
        {
            "category": "HR_DECISION",
            "difficulty": 2,
            "scenario": "一个核心技术骨干要求涨薪 50%，否则跳槽。他确实有不可替代性，但开了口子可能引发连锁反应。你会怎么处理？",
            "options": [
                {"id": "A", "text": "同意涨薪，保住人再说", "value_tags": ["compromise", "talent_retention"]},
                {"id": "B", "text": "谈判到 30%，双方各退一步", "value_tags": ["negotiation", "balance"]},
                {"id": "C", "text": "不涨，但给股权等长期激励", "value_tags": ["long_term", "cash_flow_saving"]},
                {"id": "D", "text": "让他走，没有不可替代的人", "value_tags": ["principle", "tough"]}
            ]
        },
        {
            "category": "HR_DECISION",
            "difficulty": 2,
            "scenario": "一个部门负责人连续三个月没完成业绩，但他的团队凝聚力很强，员工都很认可他。你倾向于？",
            "options": [
                {"id": "A", "text": "再给一个季度机会", "value_tags": ["patience", "trust"]},
                {"id": "B", "text": "调岗到非业绩导向部门", "value_tags": ["balance", "talent_utilization"]},
                {"id": "C", "text": "直接换人", "value_tags": ["results_oriented", "tough"]},
                {"id": "D", "text": "拆分团队重新分配", "value_tags": ["restructure", "pragmatic"]}
            ]
        },
        {
            "category": "RISK_DECISION",
            "difficulty": 3,
            "scenario": "有一个高风险高回报的投资机会，可能让公司规模翻倍，但也有 30% 概率血本无归。你会？",
            "options": [
                {"id": "A", "text": "全力投入，搏一把", "value_tags": ["aggressive", "risk_taker"]},
                {"id": "B", "text": "投入 30% 资金试水", "value_tags": ["cautious", "hedging"]},
                {"id": "C", "text": "观望，等更多信息", "value_tags": ["conservative", "patience"]},
                {"id": "D", "text": "放弃，专注主业", "value_tags": ["focus", "risk_averse"]}
            ]
        },
        {
            "category": "STRATEGY_DECISION",
            "difficulty": 3,
            "scenario": "竞争对手开始打价格战，你的利润空间被压缩。你会？",
            "options": [
                {"id": "A", "text": "跟进降价，守住市场份额", "value_tags": ["competitive", "market_share"]},
                {"id": "B", "text": "提升品质，差异化竞争", "value_tags": ["quality", "differentiation"]},
                {"id": "C", "text": "寻找新市场，避开正面冲突", "value_tags": ["strategic", "expansion"]},
                {"id": "D", "text": "收缩战线，保住利润", "value_tags": ["conservative", "profit_first"]}
            ]
        },
        {
            "category": "EXECUTION_DECISION",
            "difficulty": 2,
            "scenario": "一个重要项目进度严重滞后，团队士气低落。你会优先？",
            "options": [
                {"id": "A", "text": "加人加资源，死守工期", "value_tags": ["results", "resource_intensive"]},
                {"id": "B", "text": "与客户沟通延期", "value_tags": ["communication", "realistic"]},
                {"id": "C", "text": "砍掉非核心功能，保证交付", "value_tags": ["pragmatic", "scope_control"]},
                {"id": "D", "text": "换项目经理", "value_tags": ["accountability", "leadership_change"]}
            ]
        },
        {
            "category": "MARKET_DECISION",
            "difficulty": 3,
            "scenario": "行业出现颠覆性新技术，可能让现有产品过时。你会？",
            "options": [
                {"id": "A", "text": "立即投入研发新技术", "value_tags": ["innovative", "proactive"]},
                {"id": "B", "text": "收购或投资掌握新技术的公司", "value_tags": ["strategic", "acquisition"]},
                {"id": "C", "text": "观望，等技术成熟再跟进", "value_tags": ["conservative", "follower"]},
                {"id": "D", "text": "深耕现有市场，服务好存量客户", "value_tags": ["focus", "incremental"]}
            ]
        }
    ]

    # 清空旧数据
    sandbox_questions_col.delete_many({})

    # 插入新数据
    for q in questions:
        q["source"] = "system_preset"
        q["is_active"] = True
        q["created_at"] = datetime.now()

    sandbox_questions_col.insert_many(questions)

    return {"success": True, "count": len(questions)}
