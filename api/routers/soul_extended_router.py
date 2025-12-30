# soul_api.py - Vulcan Brain Soul System API V2 (异步版)
"""
Soul 灵魂系统 API V2 - 全异步重构

核心升级：
1. 使用 VulcanStore 统一数据访问层
2. 全异步操作，提升并发性能
3. AI驱动的情景题生成（基于实时新闻）
4. 3选项设计，每个选项带6维权重
"""

import json
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from api.routers.auth_router import get_current_user
from pydantic import BaseModel
from bson import ObjectId
import httpx

VLLM_BASE_URL = "http://localhost:8000"

def _get_vllm_model():
    try:
        resp = httpx.get(f"{VLLM_BASE_URL}/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return "default-model"

# 使用统一的异步数据存储
from vulcan_libs.store import store

router = APIRouter()

# LLM实例（懒加载）
_llm_instance = None

class VLLMClient:
    """简单的 vLLM 客户端"""
    def __init__(self):
        self.base_url = VLLM_BASE_URL
        self.model = _get_vllm_model()
    
    async def acomplete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

def get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = VLLMClient()
    return _llm_instance


# ==================== AI问题生成 ====================

QUESTION_GEN_PROMPT = """你是商学院案例设计专家。基于以下新闻/话题生成一道CEO决策情景题。

话题/新闻：{news_content}

要求：
1. 商学院案例水平，有具体数字（ARR、runway、市场份额等）
2. 3个选项，代表不同决策风格，没有标准答案
3. 每个选项对6个维度的影响权重（-30到+30之间，合理即可）

六维度说明：
- risk_appetite: 风险阈值（正=激进，负=保守）
- time_horizon: 时间视界（正=长期主义，负=短期收益）
- strategic_drive: 战略驱动（正=深度谋划，负=直觉行动）
- people_philosophy: 人际哲学（正=协作共生，负=独狼领袖）
- control_style: 控制风格（正=秩序建立，负=混沌适应）
- ethical_boundary: 伦理边界（正=原则坚守，负=灰度决策）

只输出JSON，格式如下：
{{
  "scenario": "情境描述（含具体数字，100-200字）",
  "category": "分类（FUNDING/HR/STRATEGY/MARKET/CRISIS）",
  "options": [
    {{"id": "A", "text": "选项描述（20-40字）", "weights": {{"risk_appetite": 0.1, "time_horizon": -0.1, "strategic_drive": 0.2, "people_philosophy": 0.0, "control_style": 0.1, "ethical_boundary": -0.1}}}},
    {{"id": "B", "text": "...", "weights": {{...}}}},
    {{"id": "C", "text": "...", "weights": {{...}}}}
  ]
}}
"""


async def generate_question_from_news(news_content: str) -> Optional[Dict]:
    """基于新闻生成情景题"""
    llm = get_llm()
    prompt = QUESTION_GEN_PROMPT.format(news_content=news_content)

    try:
        response = await llm.acomplete(prompt)
        text = response.text.strip()

        # 提取JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)

        # 验证结构
        assert "scenario" in data
        assert "options" in data
        assert len(data["options"]) == 3
        for opt in data["options"]:
            assert "id" in opt and "text" in opt and "weights" in opt
            assert len(opt["weights"]) == 6

        return data
    except Exception as e:
        print(f"[SoulAPI] Question generation failed: {e}")
        return None


# ==================== Pydantic Models ====================

class SoulStatsResponse(BaseModel):
    user_id: str
    streak_days: int = 0
    last_active_date: Optional[str] = None
    sync_progress: float = 50
    dimensions: Dict[str, float] = {}
    data_points_collected: int = 0
    insights: List[str] = []
    recent_topics: List[str] = []


class SandboxSubmitRequest(BaseModel):
    question_id: str
    selected_option_id: str


class SandboxSubmitResponse(BaseModel):
    is_match: bool
    ai_predicted: str
    user_selected: str
    ai_reasoning: str
    dimension_changes: Dict[str, float]


class GenerateQuestionRequest(BaseModel):
    news_content: str
    topic_tags: List[str] = []


# ==================== 异步辅助函数 ====================

async def _get_or_create_user_stats(user_id: str) -> dict:
    """获取或创建用户状态 - 从Genesis校准数据初始化"""
    stats = await store.get_soul_stats(user_id)
    genesis = await store.get_user_genesis(user_id)

    # 默认维度 (0-1 scale, 50=中间)
    default_dimensions = {
        "risk_appetite": 50.0,
        "time_horizon": 50.0,
        "strategic_drive": 50.0,
        "people_philosophy": 50.0,
        "control_style": 50.0,
        "ethical_boundary": 50.0
    }

    # 从Genesis current_genome读取校准数据 (0-100 scale -> 0-1 scale)
    if genesis and "current_genome" in genesis:
        genome = genesis["current_genome"]
        for key in default_dimensions.keys():
            if key in genome:
                default_dimensions[key] = genome[key]

    if not stats:
        # 创建新记录
        stats = {
            "user_id": user_id,
            "streak_days": 0,
            "last_active_date": None,
            "sync_progress": 30 if not genesis else 50,
            "dimensions": default_dimensions,
            "data_points_collected": genesis.get("questions_answered", 0) if genesis else 0,
            "recent_topics": [],
            "created_at": datetime.now()
        }
        await store.create_soul_stats(stats)
    else:
        # 检查是否需要从Genesis同步 (如果dimensions全是50且Genesis有数据)
        current_dims = stats.get("dimensions", {})
        all_default = all(abs(current_dims.get(k, 50) - 50) < 0.01 for k in default_dimensions.keys())

        if all_default and genesis and "current_genome" in genesis:
            # 从Genesis重新同步
            await store.update_soul_stats(user_id, {
                "$set": {"dimensions": default_dimensions, "sync_progress": 50}
            })
            stats["dimensions"] = default_dimensions
            stats["sync_progress"] = 50
            print(f"[Soul] Synced dimensions from Genesis for user {user_id}")

    return stats


async def _update_streak(user_id: str) -> int:
    """更新连续天数"""
    stats = await store.get_soul_stats(user_id)
    if not stats:
        return 0

    today = date.today().isoformat()
    last_active = stats.get("last_active_date")

    if last_active == today:
        return stats.get("streak_days", 0)

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if last_active == yesterday:
        new_streak = stats.get("streak_days", 0) + 1
    else:
        new_streak = 1

    await store.update_soul_stats(user_id, {
        "$set": {"streak_days": new_streak, "last_active_date": today}
    })

    return new_streak


async def _generate_insights(user_id: str) -> List[str]:
    """生成AI洞察"""
    stats = await store.get_soul_stats(user_id)
    if not stats:
        return ["开始答题，让Vulcan了解你的决策风格"]

    dims = stats.get("dimensions", {})
    insights = []

    if dims.get("risk_appetite", 50) > 65:
        insights.append("你倾向于激进策略，愿意承担较高风险")
    elif dims.get("risk_appetite", 50) < 35:
        insights.append("你更看重稳健，对风险持谨慎态度")

    if dims.get("time_horizon", 50) > 65:
        insights.append("你具有长期主义思维，愿意延迟满足")
    elif dims.get("time_horizon", 50) < 35:
        insights.append("你注重短期收益，追求快速回报")

    if dims.get("people_philosophy", 50) > 65:
        insights.append("你善于团队协作，重视人际关系")
    elif dims.get("people_philosophy", 50) < 35:
        insights.append("你偏好独立决策，效率优先")

    if not insights:
        insights.append("正在学习你的决策模式...")

    return insights[:3]


def _generate_ai_reasoning(option: Dict, category: str) -> str:
    """生成简单的AI推理说明"""
    weights = option.get("weights", {})

    max_dim = max(weights.items(), key=lambda x: abs(x[1]))
    min_dim = min(weights.items(), key=lambda x: x[1])

    dim_names = {
        "risk_appetite": "风险偏好",
        "time_horizon": "时间视界",
        "strategic_drive": "战略思维",
        "people_philosophy": "人际哲学",
        "control_style": "控制风格",
        "ethical_boundary": "伦理边界"
    }

    if max_dim[1] > 0.15:
        return f"这个选择体现了较强的{dim_names.get(max_dim[0], max_dim[0])}倾向"
    elif min_dim[1] < -0.15:
        return f"这个选择反映了你在{dim_names.get(min_dim[0], min_dim[0])}上的独特视角"
    else:
        return "已记录你的决策偏好"


# ==================== API 端点 ====================

@router.get("/soul/stats", response_model=SoulStatsResponse)
async def get_soul_stats(current_user: dict = Depends(get_current_user)):
    """获取数字孪生数据"""
    user_id = current_user["user_id"]
    stats = await _get_or_create_user_stats(user_id)
    insights = await _generate_insights(user_id)

    return SoulStatsResponse(
        user_id=user_id,
        streak_days=stats.get("streak_days", 0),
        last_active_date=stats.get("last_active_date"),
        sync_progress=stats.get("sync_progress", 50),
        dimensions=stats.get("dimensions", {}),
        data_points_collected=stats.get("data_points_collected", 0),
        insights=insights,
        recent_topics=stats.get("recent_topics", [])[:5]
    )


@router.get("/soul/sandbox/daily")
async def get_daily_sandbox(current_user: dict = Depends(get_current_user)):
    """获取今日情景题（3道）"""
    user_id = current_user["user_id"]
    today = date.today().isoformat()

    # 获取今天已做的题目ID
    done_interactions = await store.get_soul_interactions_since(
        user_id,
        datetime.fromisoformat(today),
        interaction_type="sandbox"
    )
    done_ids = [str(d.get("question_id")) for d in done_interactions]

    # 构建查询
    query = {"is_active": True}
    if done_ids:
        query["_id"] = {"$nin": [ObjectId(id) for id in done_ids if ObjectId.is_valid(id)]}

    # 获取未做的题目
    questions = await store.get_sandbox_questions(query, limit=3)

    result = []
    for q in questions:
        safe_options = [{"id": opt["id"], "text": opt["text"]} for opt in q.get("options", [])]
        result.append({
            "question_id": q.get("_id"),
            "category": q.get("category", ""),
            "scenario": q.get("scenario", ""),
            "options": safe_options,
            "source_topic": q.get("source_topic", "")
        })

    return {
        "questions": result,
        "completed_today": len(done_ids),
        "total_daily": 3
    }


@router.post("/soul/sandbox/submit", response_model=SandboxSubmitResponse)
async def submit_sandbox_answer(request: SandboxSubmitRequest, current_user: dict = Depends(get_current_user)):
    """提交答案，基于weights更新维度"""
    user_id = current_user["user_id"]

    # 获取完整题目（含weights）
    question = await store.get_sandbox_question(request.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 找到用户选择的选项
    selected_option = None
    for opt in question.get("options", []):
        if opt["id"] == request.selected_option_id:
            selected_option = opt
            break

    if not selected_option:
        raise HTTPException(status_code=400, detail="无效的选项")

    # 获取用户当前维度
    stats = await _get_or_create_user_stats(user_id)
    current_dims = stats.get("dimensions", {})

    # 应用权重更新维度
    weights = selected_option.get("weights", {})
    new_dims = {}
    dim_changes = {}

    for dim_key in ["risk_appetite", "time_horizon", "strategic_drive",
                    "people_philosophy", "control_style", "ethical_boundary"]:
        weight = weights.get(dim_key, 0)
        old_val = current_dims.get(dim_key, 50)
        new_val = max(0, min(100, old_val + weight * 25))
        new_dims[dim_key] = new_val
        dim_changes[dim_key] = round(new_val - old_val, 3)

    # 更新同步进度
    new_sync = min(95, stats.get("sync_progress", 30) + 0.50)

    # 更新数据库
    await _update_streak(user_id)
    await store.update_soul_stats(user_id, {
        "$set": {"dimensions": new_dims, "sync_progress": new_sync},
        "$inc": {"data_points_collected": 1}
    })

    # 记录交互
    await store.insert_soul_interaction({
        "user_id": user_id,
        "type": "sandbox",
        "question_id": request.question_id,
        "selected_option": request.selected_option_id,
        "weights_applied": weights,
        "dimension_changes": dim_changes,
        "created_at": datetime.now()
    })

    reasoning = _generate_ai_reasoning(selected_option, question.get("category", ""))

    return SandboxSubmitResponse(
        is_match=True,
        ai_predicted=request.selected_option_id,
        user_selected=request.selected_option_id,
        ai_reasoning=reasoning,
        dimension_changes=dim_changes
    )


# ==================== 问题生成端点 ====================

@router.post("/soul/admin/generate_question")
async def generate_question(request: GenerateQuestionRequest):
    """基于新闻/话题生成情景题"""
    data = await generate_question_from_news(request.news_content)

    if not data:
        raise HTTPException(status_code=500, detail="问题生成失败")

    doc = {
        "scenario": data["scenario"],
        "category": data.get("category", "GENERAL"),
        "options": data["options"],
        "source_topic": request.news_content[:100],
        "topic_tags": request.topic_tags,
        "is_active": True,
        "source": "ai_generated",
        "created_at": datetime.now()
    }

    question_id = await store.insert_sandbox_question(doc)

    return {
        "success": True,
        "question_id": question_id,
        "preview": {
            "scenario": data["scenario"],
            "options": [{"id": o["id"], "text": o["text"]} for o in data["options"]]
        }
    }


@router.post("/soul/admin/batch_generate")
async def batch_generate_questions(topics: List[str], background_tasks: BackgroundTasks):
    """批量生成问题（后台任务）"""
    async def _generate_batch():
        for topic in topics:
            await generate_question_from_news(topic)
            await asyncio.sleep(2)

    background_tasks.add_task(lambda: asyncio.run(_generate_batch()))
    return {"success": True, "message": f"开始生成 {len(topics)} 道题目"}


# ==================== 种子数据 ====================

@router.post("/soul/admin/seed_v2_questions")
async def seed_v2_questions():
    """初始化V2格式的种子题库（带weights）"""
    questions = [
        {
            "category": "FUNDING",
            "scenario": "你的SaaS公司ARR $5M，增速30%，账上有18个月runway。一家战略投资人提出以2x ARR估值收购60%股权，条件是2年内实现盈利。",
            "options": [
                {"id": "A", "text": "接受投资，聚焦盈利，稳健发展",
                 "weights": {"risk_appetite": -0.2, "time_horizon": 0.15, "strategic_drive": 0.1, "people_philosophy": 0.05, "control_style": 0.2, "ethical_boundary": 0.1}},
                {"id": "B", "text": "拒绝，继续烧钱抢市场份额",
                 "weights": {"risk_appetite": 0.25, "time_horizon": -0.15, "strategic_drive": -0.1, "people_philosophy": -0.05, "control_style": -0.1, "ethical_boundary": -0.05}},
                {"id": "C", "text": "反向谈判，只出让30%，保留控制权",
                 "weights": {"risk_appetite": 0.1, "time_horizon": 0.05, "strategic_drive": 0.2, "people_philosophy": -0.1, "control_style": 0.1, "ethical_boundary": -0.1}}
            ],
            "source_topic": "创业融资决策",
            "is_active": True,
            "source": "seed_v2"
        },
        {
            "category": "HR",
            "scenario": "核心技术VP提出离职创业，带走了关键算法。他提议：如果你投资$500K占20%股份，他承诺3年内不挖人，否则可能带走2-3个核心工程师。",
            "options": [
                {"id": "A", "text": "投资，把潜在对手变成生态伙伴",
                 "weights": {"risk_appetite": 0.15, "time_horizon": 0.2, "strategic_drive": 0.15, "people_philosophy": 0.2, "control_style": -0.15, "ethical_boundary": -0.1}},
                {"id": "B", "text": "拒绝并启动竞业协议诉讼",
                 "weights": {"risk_appetite": -0.1, "time_horizon": -0.1, "strategic_drive": 0.05, "people_philosophy": -0.25, "control_style": 0.2, "ethical_boundary": 0.15}},
                {"id": "C", "text": "不投资，但友好分手，保持行业关系",
                 "weights": {"risk_appetite": -0.05, "time_horizon": 0.1, "strategic_drive": 0.1, "people_philosophy": 0.15, "control_style": 0.0, "ethical_boundary": 0.2}}
            ],
            "source_topic": "核心人才离职",
            "is_active": True,
            "source": "seed_v2"
        },
        {
            "category": "STRATEGY",
            "scenario": "你的电商平台GMV $100M，毛利15%。拼多多推出同品类补贴战，价格比你低20%。你的现金流只够支撑6个月价格战。",
            "options": [
                {"id": "A", "text": "跟进降价，用VC的钱打消耗战",
                 "weights": {"risk_appetite": 0.25, "time_horizon": -0.2, "strategic_drive": -0.15, "people_philosophy": -0.05, "control_style": -0.1, "ethical_boundary": -0.1}},
                {"id": "B", "text": "差异化，聚焦高端用户体验",
                 "weights": {"risk_appetite": -0.1, "time_horizon": 0.2, "strategic_drive": 0.2, "people_philosophy": 0.1, "control_style": 0.15, "ethical_boundary": 0.1}},
                {"id": "C", "text": "转型供应链服务商，给拼多多供货",
                 "weights": {"risk_appetite": 0.1, "time_horizon": 0.15, "strategic_drive": 0.25, "people_philosophy": 0.05, "control_style": -0.05, "ethical_boundary": -0.15}}
            ],
            "source_topic": "价格战应对",
            "is_active": True,
            "source": "seed_v2"
        },
        {
            "category": "CRISIS",
            "scenario": "产品出现安全漏洞，用户数据泄露。媒体还没报道，你有24小时窗口期。修复需要3天，期间服务会中断。",
            "options": [
                {"id": "A", "text": "立即公告，主动下线修复",
                 "weights": {"risk_appetite": -0.15, "time_horizon": 0.2, "strategic_drive": 0.1, "people_philosophy": 0.15, "control_style": 0.1, "ethical_boundary": 30}},
                {"id": "B", "text": "静默修复，不对外公开",
                 "weights": {"risk_appetite": 0.2, "time_horizon": -0.15, "strategic_drive": 0.05, "people_philosophy": -0.2, "control_style": 0.15, "ethical_boundary": -30}},
                {"id": "C", "text": "只通知受影响用户，控制舆论范围",
                 "weights": {"risk_appetite": 0.05, "time_horizon": 0.0, "strategic_drive": 0.15, "people_philosophy": 0.0, "control_style": 0.1, "ethical_boundary": -0.1}}
            ],
            "source_topic": "数据安全危机",
            "is_active": True,
            "source": "seed_v2"
        },
        {
            "category": "MARKET",
            "scenario": "AI大模型浪潮来袭，你的传统软件产品面临被替代风险。转型需要投入年利润的200%，成功率50%。不转型，3年内市场份额预计下降60%。",
            "options": [
                {"id": "A", "text": "All in AI，押注未来",
                 "weights": {"risk_appetite": 30, "time_horizon": 0.1, "strategic_drive": 0.15, "people_philosophy": -0.1, "control_style": -0.2, "ethical_boundary": -0.05}},
                {"id": "B", "text": "渐进转型，用30%资源试水",
                 "weights": {"risk_appetite": -0.05, "time_horizon": 0.15, "strategic_drive": 0.2, "people_philosophy": 0.1, "control_style": 0.15, "ethical_boundary": 0.1}},
                {"id": "C", "text": "卖掉公司，高位套现",
                 "weights": {"risk_appetite": -0.2, "time_horizon": -0.25, "strategic_drive": 0.1, "people_philosophy": -0.15, "control_style": 0.1, "ethical_boundary": -0.1}}
            ],
            "source_topic": "技术变革应对",
            "is_active": True,
            "source": "seed_v2"
        }
    ]

    # 清空旧数据
    deleted = await store.delete_all_sandbox_questions()
    print(f"[SoulAPI] 删除了 {deleted} 道旧题目")

    # 插入新数据
    count = await store.insert_sandbox_questions_batch(questions)

    return {"success": True, "count": count}


# ==================== 新闻抓取端点 ====================

@router.get("/soul/news/sources")
async def get_news_sources():
    """获取支持的新闻源列表"""
    from news_fetcher import NEWS_SOURCES
    return {
        "sources": [
            {"id": k, "name": v["name"], "tags": v["tags"]}
            for k, v in NEWS_SOURCES.items()
        ]
    }


@router.post("/soul/news/generate_daily")
async def trigger_daily_generation(count: int = 3, background_tasks: BackgroundTasks = None):
    """触发每日题目生成（基于新闻）"""
    return {"success": False, "message": "题目生成功能待实现"}


@router.get("/soul/news/recent")
async def get_recent_news(limit: int = 10):
    """获取最近抓取的新闻"""
    news = await store.get_news_cache(limit)
    return {
        "news": [
            {
                "title": n.get("title", ""),
                "source": n.get("source_name", ""),
                "tags": n.get("tags", []),
                "fetched_at": n.get("fetched_at", datetime.now()).isoformat() if isinstance(n.get("fetched_at"), datetime) else str(n.get("fetched_at", ""))
            }
            for n in news
        ]
    }


# ==================== 智能题库补充 ====================

async def _check_and_refill_questions(user_id: str, min_available: int = 5):
    """检查并自动补充题库"""
    today = date.today().isoformat()
    done_interactions = await store.get_soul_interactions_since(
        user_id,
        datetime.fromisoformat(today),
        interaction_type="sandbox"
    )
    done_ids = set(str(d.get("question_id")) for d in done_interactions)

    # 构建查询
    query = {"is_active": True}
    if done_ids:
        query["_id"] = {"$nin": [ObjectId(id) for id in done_ids if ObjectId.is_valid(id)]}

    available = await store.count_sandbox_questions(query)
    print(f"[SoulAPI] 用户 {user_id} 可用题目: {available}, 阈值: {min_available}")

    if available < min_available:
        print(f"[SoulAPI] 题库不足，需补充 {min_available - available} 道新题...")
        return True
    return False


@router.get("/soul/sandbox/daily_v2")
async def get_daily_sandbox_v2(current_user: dict = Depends(get_current_user)):
    """获取今日情景题（自动补充版）"""
    user_id = current_user["user_id"]

    await _check_and_refill_questions(user_id, min_available=5)

    today = date.today().isoformat()
    done_interactions = await store.get_soul_interactions_since(
        user_id,
        datetime.fromisoformat(today),
        interaction_type="sandbox"
    )
    done_ids = [str(d.get("question_id")) for d in done_interactions]

    query = {"is_active": True}
    if done_ids:
        query["_id"] = {"$nin": [ObjectId(id) for id in done_ids if ObjectId.is_valid(id)]}

    questions = await store.get_sandbox_questions(query, limit=3)

    result = []
    for q in questions:
        safe_options = [{"id": opt["id"], "text": opt["text"]} for opt in q.get("options", [])]
        result.append({
            "question_id": q.get("_id"),
            "category": q.get("category", ""),
            "scenario": q.get("scenario", ""),
            "options": safe_options,
            "source_topic": q.get("source_topic", "")
        })

    total_available = await store.count_sandbox_questions({"is_active": True})

    return {
        "questions": result,
        "completed_today": len(done_ids),
        "total_available": total_available
    }


# ==================== 热门话题/资讯 ====================

@router.get("/soul/hot_topics")
async def get_hot_topics(current_user: dict = Depends(get_current_user)):
    """获取热门商业话题（实时36氪+虎嗅RSS）"""
    try:
        from news_fetcher import fetch_news
        hot_topics = fetch_news(limit=8)
    except Exception as e:
        print(f"[Soul] Error fetching news: {e}")
        hot_topics = []
    return {"topics": hot_topics, "updated_at": datetime.now().isoformat()}


# ==================== Calibration Status API ====================

@router.get("/soul/calibration")
async def get_calibration(user_id: str):
    """获取用户校准状态"""
    from prediction_engine import get_calibration_status
    return await get_calibration_status(user_id)


# ==================== Dimensions 同步辅助函数 ====================

async def _sync_dimensions_to_user_souls(user_id: str, dimensions: Dict[str, float]):
    """
    同步 soul_user_stats.dimensions 到 user_souls.dimensions
    确保两处数据一致性
    """
    try:
        await store.update_soul(user_id, {"dimensions": dimensions})
        print(f"[Soul] Synced dimensions for {user_id} to user_souls")
    except Exception as e:
        print(f"[Soul] Failed to sync dimensions: {e}")
