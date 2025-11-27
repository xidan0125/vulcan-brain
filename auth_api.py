"""
Vulcan Brain - 用户认证与灵魂API
"""
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from pymongo import MongoClient

# MongoDB 连接
mongo_client = MongoClient("mongodb://localhost:27017")
db = mongo_client["vulcan_brain"]

# JWT 配置
JWT_SECRET = "vulcan_brain_secret_2024"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7天

router = APIRouter()

# ==================== Pydantic Models ====================

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str
    role_level: int
    soul: Optional[dict] = None

class GenesisSubmit(BaseModel):
    answers: Dict[int, str]  # {question_id: selected_value}

class ConstitutionItem(BaseModel):
    id: str
    category: str  # redline | core | style
    content: str

class ConstitutionUpdate(BaseModel):
    items: List[ConstitutionItem]

# ==================== Helper Functions ====================

def hash_password(password: str) -> str:
    """简单的密码hash（生产环境应用bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    """验证密码 - 支持明文和hash两种方式"""
    # 先尝试明文比较（开发阶段）
    if password == stored_hash:
        return True
    # 再尝试hash比较
    return hash_password(password) == stored_hash

def create_token(user_id: str, username: str) -> str:
    """创建JWT token"""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    """解码JWT token"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(authorization: str = Header(None)) -> dict:
    """从Header获取当前用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证token")

    # 支持 "Bearer xxx" 和 "xxx" 两种格式
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token无效或已过期")

    user = db.users.find_one({"username": payload["username"]})
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return {
        "user_id": payload["username"],
        "username": payload["username"],
        "display_name": user.get("display_name", payload["username"]),
        "role_level": user.get("role_level", 10)
    }

# ==================== Auth APIs ====================

@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """用户登录"""
    user = db.users.find_one({"username": req.username})
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 更新最后登录时间
    db.users.update_one(
        {"username": req.username},
        {"$set": {"last_login": datetime.now()}}
    )

    # 获取用户灵魂配置
    soul = db.user_souls.find_one({"user_id": req.username}, {"_id": 0})

    token = create_token(str(user["_id"]), user["username"])

    return {
        "token": token,
        "user": {
            "user_id": user["username"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
            "role_level": user.get("role_level", 10),
            "genesis_completed": soul.get("genesis_completed", False) if soul else False
        }
    }

@router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    soul = db.user_souls.find_one({"user_id": current_user["user_id"]}, {"_id": 0})
    return {
        **current_user,
        "soul": soul
    }

# ==================== Soul APIs ====================

@router.get("/soul/status")
async def get_soul_status(current_user: dict = Depends(get_current_user)):
    """获取灵魂状态"""
    soul = db.user_souls.find_one({"user_id": current_user["user_id"]}, {"_id": 0})
    genesis = db.user_genesis.find_one({"user_id": current_user["user_id"]}, {"_id": 0})

    return {
        "user_id": current_user["user_id"],
        "genesis_completed": soul.get("genesis_completed", False) if soul else False,
        "sync_rate": soul.get("sync_rate", 0) if soul else 0,
        "has_constitution": db.user_constitution.count_documents({"user_id": current_user["user_id"]}) > 0
    }

@router.post("/soul/genesis")
async def submit_genesis(req: GenesisSubmit, current_user: dict = Depends(get_current_user)):
    """提交创世20问答案"""
    user_id = current_user["user_id"]

    # 计算用户画像
    answers_list = []
    risk_score = 0
    management_score = 0

    # 简单的画像计算逻辑
    risk_keywords = ["risk_seeking", "speed_first", "aggressive_growth", "proactive_change"]
    management_keywords = ["culture_over_talent", "performance_first", "strict_rules", "wolf_culture"]

    for qid, value in req.answers.items():
        answers_list.append({
            "question_id": int(qid),
            "value": value,
            "answered_at": datetime.now()
        })
        if value in risk_keywords:
            risk_score += 5
        if value in management_keywords:
            management_score += 5

    # 保存创世问答记录
    db.user_genesis.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "answers": answers_list,
                "completed_at": datetime.now(),
                "computed_profile": {
                    "risk_tendency": min(risk_score / 50, 1.0),
                    "management_tendency": min(management_score / 50, 1.0)
                }
            }
        },
        upsert=True
    )

    # 更新 user_souls
    risk_label = "激进型" if risk_score > 30 else ("中等" if risk_score > 15 else "保守型")
    mgmt_label = "铁腕型" if management_score > 30 else ("平衡型" if management_score > 15 else "人性化")

    db.user_souls.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "genesis_completed": True,
                "risk_profile": {"score": risk_score * 2, "label": risk_label},
                "management_style": {"score": management_score * 2, "label": mgmt_label},
                "sync_rate": 50.0,  # 初始同步率
                "updated_at": datetime.now()
            }
        }
    )

    # 生成默认宪法
    default_constitution = [
        {"id": "r1", "category": "redline", "content": "绝不泄露用户隐私数据"},
        {"id": "r2", "category": "redline", "content": "不使用非法竞争手段"},
        {"id": "c1", "category": "core", "content": "追求长期价值而非短期增长"},
        {"id": "c2", "category": "core", "content": "数据驱动决策"},
        {"id": "s1", "category": "style", "content": f"风险偏好: {risk_label}"},
        {"id": "s2", "category": "style", "content": f"管理风格: {mgmt_label}"}
    ]

    db.user_constitution.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "items": default_constitution,
                "updated_at": datetime.now()
            }
        },
        upsert=True
    )

    return {"success": True, "message": "创世对齐完成", "sync_rate": 50.0}

@router.get("/soul/constitution")
async def get_constitution(current_user: dict = Depends(get_current_user)):
    """获取宪法条目"""
    doc = db.user_constitution.find_one({"user_id": current_user["user_id"]}, {"_id": 0})
    if not doc:
        return {"user_id": current_user["user_id"], "items": []}
    return doc

@router.put("/soul/constitution")
async def update_constitution(req: ConstitutionUpdate, current_user: dict = Depends(get_current_user)):
    """更新宪法条目"""
    items = [item.dict() for item in req.items]

    db.user_constitution.update_one(
        {"user_id": current_user["user_id"]},
        {
            "$set": {
                "user_id": current_user["user_id"],
                "items": items,
                "updated_at": datetime.now()
            }
        },
        upsert=True
    )

    # 同步核心条目到 user_souls
    redlines = [i["content"] for i in items if i["category"] == "redline"]
    core_values = [i["content"] for i in items if i["category"] == "core"]

    db.user_souls.update_one(
        {"user_id": current_user["user_id"]},
        {
            "$set": {
                "redlines": redlines,
                "core_values": core_values,
                "updated_at": datetime.now()
            }
        }
    )

    return {"success": True, "message": "宪法已更新"}

@router.get("/soul/profile")
async def get_soul_profile(current_user: dict = Depends(get_current_user)):
    """获取完整灵魂档案（用于AI System Prompt）"""
    soul = db.user_souls.find_one({"user_id": current_user["user_id"]}, {"_id": 0})
    constitution = db.user_constitution.find_one({"user_id": current_user["user_id"]}, {"_id": 0})

    if not soul:
        return {"error": "灵魂档案不存在"}

    return {
        "user_id": current_user["user_id"],
        "display_name": current_user["display_name"],
        "soul": soul,
        "constitution": constitution.get("items", []) if constitution else [],
        "system_prompt_snippet": build_system_prompt_snippet(soul, constitution)
    }

def build_system_prompt_snippet(soul: dict, constitution: dict) -> str:
    """构建注入System Prompt的片段"""
    lines = ["### 用户价值观对齐配置 ###"]

    # 红线
    redlines = soul.get("redlines", [])
    if redlines:
        lines.append("\n【红线 - 绝对禁止】")
        for r in redlines:
            lines.append(f"- {r}")

    # 核心价值观
    core_values = soul.get("core_values", [])
    if core_values:
        lines.append("\n【核心价值观】")
        for v in core_values:
            lines.append(f"- {v}")

    # 沟通风格
    style = soul.get("communication_style", {})
    if style:
        tone_map = {"brief_and_direct": "简洁直接", "detailed": "详细全面", "technical": "技术型", "casual": "轻松随意"}
        lines.append(f"\n【沟通风格】{tone_map.get(style.get('tone', ''), '默认')}")

    # 风险偏好
    risk = soul.get("risk_profile", {})
    if risk.get("label"):
        lines.append(f"【风险偏好】{risk['label']}")

    return "\n".join(lines)

# ==================== Alignment APIs ====================

@router.post("/soul/alignment/submit")
async def submit_alignment(
    card_id: str,
    selected: str,  # "A" or "B"
    expected: str,  # "A" or "B"
    current_user: dict = Depends(get_current_user)
):
    """提交对齐测试答案"""
    is_correct = selected == expected
    delta = 2.5 if is_correct else -0.5

    # 更新同步率
    soul = db.user_souls.find_one({"user_id": current_user["user_id"]})
    new_sync_rate = max(0, min(100, (soul.get("sync_rate", 50) if soul else 50) + delta))

    db.user_souls.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"sync_rate": new_sync_rate, "updated_at": datetime.now()}}
    )

    # 记录对齐历史
    db.user_alignments.update_one(
        {"user_id": current_user["user_id"]},
        {
            "$push": {
                "responses": {
                    "card_id": card_id,
                    "selected": selected,
                    "expected": expected,
                    "is_correct": is_correct,
                    "timestamp": datetime.now()
                }
            },
            "$set": {"updated_at": datetime.now()}
        },
        upsert=True
    )

    return {
        "is_correct": is_correct,
        "sync_delta": delta,
        "new_sync_rate": new_sync_rate
    }


@router.delete("/soul/genesis/reset")
async def reset_genesis(current_user: dict = Depends(get_current_user)):
    """重置校准状态（开发调试用）"""
    user_id = current_user["user_id"]
    
    # 删除 genesis 记录
    db.user_genesis.delete_one({"user_id": user_id})
    
    # 重置 user_souls 状态
    db.user_souls.update_one(
        {"user_id": user_id},
        {"$set": {"genesis_completed": False, "sync_rate": 0}}
    )
    
    # 删除宪法
    db.user_constitution.delete_one({"user_id": user_id})
    
    return {"success": True, "message": "校准状态已重置"}
