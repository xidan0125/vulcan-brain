"""
Vulcan Brain - 用户认证与灵魂API (异步版)
使用统一的 VulcanStore 进行数据库访问
"""
import os
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS
import jwt
import hashlib
from passlib.context import CryptContext

# 密码加密上下文 - 使用bcrypt（行业标准）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import APIRouter, Depends, Header
from vulcan_libs.exceptions import AuthenticationError, NotFoundError
from pydantic import BaseModel

from vulcan_libs.store import store

# JWT 配置

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
    # V1 format
    answers: Optional[Dict[int, str]] = None  # {question_id: selected_value}
    # V2 format (genome-based)
    genome: Optional[Dict[str, int]] = None   # {dimension: score 0-100}
    questions_answered: Optional[int] = None
    version: Optional[str] = None
    skipped: Optional[bool] = False

class ConstitutionItem(BaseModel):
    id: str
    category: str  # redline | core | style
    content: str

class ConstitutionUpdate(BaseModel):
    items: List[ConstitutionItem]

# ==================== Helper Functions ====================

def hash_password(password: str) -> str:
    """使用bcrypt对密码进行安全hash"""
    return pwd_context.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    """
    验证密码 - 兼容旧SHA256和新bcrypt
    迁移策略：登录成功后自动升级为bcrypt
    """
    # 新格式：bcrypt hash 以 $2b$ 开头
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        return pwd_context.verify(password, stored_hash)
    
    # 旧格式：SHA256 (64位hex字符串)
    if len(stored_hash) == 64:
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    
    return False


async def upgrade_password_hash_if_needed(username: str, password: str, stored_hash: str):
    """如果使用旧hash格式，尝试升级为bcrypt（可选）"""
    if not (stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")):
        try:
            new_hash = hash_password(password)
            await store.update_user(username, {"password_hash": new_hash})
            print(f"[SECURITY] 用户 {username} 密码已升级为bcrypt")
        except Exception as e:
            # bcrypt 在某些环境下可能有兼容性问题，继续使用旧hash
            print(f"[SECURITY] 用户 {username} 密码升级失败，保留SHA256: {e}")

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
    import traceback
    print(f"DEBUG decode_token: JWT_SECRET hash={hash(JWT_SECRET)}, len={len(JWT_SECRET)}")
    print(f"DEBUG decode_token: token={token[:20]}...")

    """解码JWT token"""
    try:
        result = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        print(f"DEBUG: decode OK, payload={result}")
        return result
    except jwt.ExpiredSignatureError as e:
        print(f"DEBUG: EXPIRED {e}")
        return None
    except jwt.InvalidTokenError as e:
        print(f"DEBUG: INVALID {e}")
        return None

async def get_current_user(authorization: str = Header(None)) -> dict:
    """从Header获取当前用户"""
    if not authorization:
        raise AuthenticationError("未提供认证token")

    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    payload = decode_token(token)
    if not payload:
        raise AuthenticationError("token无效或已过期")

    user = await store.get_user(payload["username"])
    if not user:
        raise AuthenticationError("用户不存在")

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
    user = await store.get_user(req.username)
    if not user:
        raise AuthenticationError("用户名或密码错误")

    if not verify_password(req.password, user.get("password_hash", "")):
        raise AuthenticationError("用户名或密码错误")

    # 更新最后登录时间
    await store.update_user(req.username, {"last_login": datetime.now()})
    
    # 自动升级旧密码hash为bcrypt
    await upgrade_password_hash_if_needed(req.username, req.password, user.get("password_hash", ""))

    # 获取用户灵魂配置
    soul = await store.get_soul(req.username)

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
    soul = await store.get_soul(current_user["user_id"])
    # 清理 MongoDB ObjectId
    if soul and "_id" in soul:
        soul["_id"] = str(soul["_id"])
    return {
        **current_user,
        "soul": soul
    }

# ==================== Soul APIs ====================

@router.get("/soul/status")
async def get_soul_status(current_user: dict = Depends(get_current_user)):
    """获取灵魂状态"""
    soul = await store.get_soul(current_user["user_id"])
    genesis = await store.get_user_genesis(current_user["user_id"])
    constitution_count = await store.count_user_constitution(current_user["user_id"])

    return {
        "user_id": current_user["user_id"],
        "genesis_completed": soul.get("genesis_completed", False) if soul else False,
        "sync_rate": soul.get("sync_rate", 0) if soul else 0,
        "has_constitution": constitution_count > 0
    }

@router.post("/soul/genesis")
async def submit_genesis(req: GenesisSubmit, current_user: dict = Depends(get_current_user)):
    """提交创世校准答案 - 支持 V1 和 V2 格式"""
    user_id = current_user["user_id"]

    # V2.0 格式处理 (genome-based)
    if req.genome is not None:
        # 直接使用前端计算的 genome 分数
        genome_data = req.genome

        # 保存创世记录
        genesis_data = {
            "user_id": user_id,
            "genome": genome_data,
            "version": req.version or "2.0",
            "questions_answered": req.questions_answered or 0,
            "skipped": req.skipped or False,
            "completed_at": datetime.now()
        }
        await store.update_user_genesis(user_id, genesis_data)

        # 更新 user_souls - 设置 genesis_completed = True
        soul_update = {
            "genesis_completed": True,
            "genome": genome_data,
            "sync_rate": 30.0 if req.skipped else 50.0,
            "updated_at": datetime.now()
        }
        await store.update_soul(user_id, soul_update)

        logging.info(f"Genesis v2.0 completed for user {user_id}, skipped={req.skipped}")

        return {
            "status": "success",
            "genesis_completed": True,
            "genome": genome_data,
            "version": "2.0"
        }

    # V1 格式处理 (answers-based) - 保持向后兼容
    if req.answers is None:
        raise HTTPException(status_code=400, detail="Missing answers or genome data")

    # 计算用户画像
    answers_list = []
    risk_score = 0
    management_score = 0

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
    genesis_data = {
        "user_id": user_id,
        "answers": answers_list,
        "completed_at": datetime.now(),
        "computed_profile": {
            "risk_tendency": min(risk_score / 50, 1.0),
            "management_tendency": min(management_score / 50, 1.0)
        }
    }
    await store.update_user_genesis(user_id, genesis_data)

    # 更新 user_souls
    risk_label = "激进型" if risk_score > 30 else ("中等" if risk_score > 15 else "保守型")
    mgmt_label = "铁腕型" if management_score > 30 else ("平衡型" if management_score > 15 else "人性化")

    soul_update = {
        "genesis_completed": True,
        "risk_profile": {"score": risk_score * 2, "label": risk_label},
        "management_style": {"score": management_score * 2, "label": mgmt_label},
        "sync_rate": 50.0,
        "updated_at": datetime.now()
    }
    await store.update_soul(user_id, soul_update)

    # 生成默认宪法
    default_constitution = [
        {"id": "r1", "category": "redline", "content": "绝不泄露用户隐私数据"},
        {"id": "r2", "category": "redline", "content": "不使用非法竞争手段"},
        {"id": "c1", "category": "core", "content": "追求长期价值而非短期增长"},
        {"id": "c2", "category": "core", "content": "数据驱动决策"},
        {"id": "s1", "category": "style", "content": f"风险偏好: {risk_label}"},
        {"id": "s2", "category": "style", "content": f"管理风格: {mgmt_label}"}
    ]

    await store.update_user_constitution(user_id, default_constitution)

    return {"success": True, "message": "创世对齐完成", "sync_rate": 50.0}

@router.get("/soul/constitution")
async def get_constitution(current_user: dict = Depends(get_current_user)):
    """获取宪法条目"""
    doc = await store.get_user_constitution(current_user["user_id"])
    if not doc:
        return {"user_id": current_user["user_id"], "items": []}
    return doc

@router.put("/soul/constitution")
async def update_constitution(req: ConstitutionUpdate, current_user: dict = Depends(get_current_user)):
    """更新宪法条目"""
    items = [item.dict() for item in req.items]
    
    await store.update_user_constitution(current_user["user_id"], items)

    # 同步核心条目到 user_souls
    redlines = [i["content"] for i in items if i["category"] == "redline"]
    core_values = [i["content"] for i in items if i["category"] == "core"]

    await store.update_soul(current_user["user_id"], {
        "redlines": redlines,
        "core_values": core_values,
        "updated_at": datetime.now()
    })

    return {"success": True, "message": "宪法已更新"}

@router.get("/soul/profile")
async def get_soul_profile(current_user: dict = Depends(get_current_user)):
    """获取完整灵魂档案（用于AI System Prompt）"""
    soul = await store.get_soul(current_user["user_id"])
    constitution = await store.get_user_constitution(current_user["user_id"])

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

    redlines = soul.get("redlines", [])
    if redlines:
        lines.append("\n【红线 - 绝对禁止】")
        for r in redlines:
            lines.append(f"- {r}")

    core_values = soul.get("core_values", [])
    if core_values:
        lines.append("\n【核心价值观】")
        for v in core_values:
            lines.append(f"- {v}")

    style = soul.get("communication_style", {})
    if style:
        tone_map = {"brief_and_direct": "简洁直接", "detailed": "详细全面", "technical": "技术型", "casual": "轻松随意"}
        lines.append(f"\n【沟通风格】{tone_map.get(style.get(tone, ), 默认)}")

    risk = soul.get("risk_profile", {})
    if risk.get("label"):
        lines.append(f"【风险偏好】{risk[label]}")

    return "\n".join(lines)

# ==================== Alignment APIs ====================

@router.post("/soul/alignment/submit")
async def submit_alignment(
    card_id: str,
    selected: str,
    expected: str,
    current_user: dict = Depends(get_current_user)
):
    """提交对齐测试答案"""
    is_correct = selected == expected
    delta = 2.5 if is_correct else -0.5

    # 获取当前同步率
    soul = await store.get_soul(current_user["user_id"])
    new_sync_rate = max(0, min(100, (soul.get("sync_rate", 50) if soul else 50) + delta))

    # 更新同步率
    await store.update_soul(current_user["user_id"], {
        "sync_rate": new_sync_rate, 
        "updated_at": datetime.now()
    })

    # 记录对齐历史
    alignment_response = {
        "card_id": card_id,
        "selected": selected,
        "expected": expected,
        "is_correct": is_correct,
        "timestamp": datetime.now()
    }
    await store.add_user_alignment_response(current_user["user_id"], alignment_response)

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
    await store.delete_user_genesis(user_id)
    
    # 重置 user_souls 状态
    await store.update_soul(user_id, {"genesis_completed": False, "sync_rate": 0})
    
    # 删除宪法
    await store.delete_user_constitution(user_id)
    
    return {"success": True, "message": "校准状态已重置"}


async def get_current_user_optional(authorization: str = Header(None)) -> Optional[dict]:
    """可选的用户认证 - 未登录时返回None而不是抛出异常"""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except:
        return None
