"""
Vulcan Brain - 记忆 API v3.0
统一记忆管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import logging
import asyncio
import httpx

from api.routers.auth_router import get_current_user
from services.memory_service import MemoryService, get_memory_service
from services.memory_extractor import MemoryExtractor, get_memory_extractor

logger = logging.getLogger("MemoryAPI")

router = APIRouter(prefix="/memory", tags=["Memory v3"])


# ==================== 请求/响应模型 ====================

class RememberRequest(BaseModel):
    """存储记忆请求"""
    key: str
    value: str
    category: str = "fact"  # identity | preference | fact


class ExtractRequest(BaseModel):
    """提取记忆请求"""
    message: str
    session_id: str


class UpdatePendingRequest(BaseModel):
    """编辑待确认记忆请求"""
    new_value: str


class DigestRequest(BaseModel):
    """保存摘要请求"""
    session_id: str
    title: str
    key_points: List[str]


# ==================== 依赖注入 ====================

async def get_user_id(user: dict = Depends(get_current_user)) -> str:
    """从认证信息获取用户ID"""
    return user.get("user_id", user.get("username", "anonymous"))


# ==================== 显式记忆 CRUD ====================

@router.post("/remember")
async def remember(
    req: RememberRequest,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    主动存储记忆

    - **key**: 记忆键 (如 name, role, pref_style)
    - **value**: 记忆值
    - **category**: 分类 (identity/preference/fact)
    """
    return await svc.remember(user_id, req.key, req.value, req.category)


@router.get("/recall")
async def recall(
    key: Optional[str] = None,
    category: Optional[str] = None,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    查询记忆

    - **key**: 可选，模糊匹配键名
    - **category**: 可选，按分类筛选
    """
    return await svc.recall(user_id, key, category)


@router.get("/all")
async def get_all_memories(
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """获取所有记忆"""
    return await svc.get_all(user_id)


@router.delete("/forget/{key}")
async def forget(
    key: str,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    删除记忆

    - **key**: 要删除的记忆键
    """
    success = await svc.forget(user_id, key)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "key": key}


# ==================== 记忆提取 ====================


async def background_extract_and_store(
    message: str,
    session_id: str,
    user_id: str,
    extractor,
    svc
):
    """后台执行记忆提取，不阻塞主链路"""
    logger.info(f"Background task started for user {user_id}, message: {message[:50]}...")
    try:
        extractions = await extractor.extract(message)
        
        if not extractions:
            return
            
        for ext in extractions:
            await svc.add_pending(
                user_id=user_id,
                session_id=session_id,
                key=ext["key"],
                value=ext["value"],
                category=ext.get("category", "fact"),
                confidence=ext.get("confidence", 0.8),
                context=message
            )
        logger.info(f"Background extracted {len(extractions)} memories for user {user_id}")
    except Exception as e:
        logger.error(f"Background memory extraction failed: {e}")

@router.post("/extract")
async def extract_memories(
    req: ExtractRequest,
    user_id: str = Depends(get_user_id)
):
    """
    从消息提取记忆 (异步调用 worker)
    
    Fire-and-forget 调用独立 worker 服务
    """
    async def call_worker():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    "http://localhost:8003/extract",
                    json={
                        "message": req.message,
                        "session_id": req.session_id,
                        "user_id": user_id
                    }
                )
        except Exception as e:
            logger.warning(f"Worker call failed (non-blocking): {e}")
    
    asyncio.create_task(call_worker())
    return {"status": "queued", "message": "Memory extraction delegated to worker"}


# ==================== 待确认记忆管理 ====================

@router.get("/pending")
async def get_pending(
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """获取待确认记忆列表"""
    return await svc.get_pending(user_id)


@router.post("/confirm/{pending_id}")
async def confirm_memory(
    pending_id: str,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    确认记忆

    将待确认记忆转为正式记忆
    """
    memory = await svc.confirm_pending(pending_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Pending memory not found")

    logger.info(f"Memory confirmed: {pending_id}")
    return memory


@router.post("/reject/{pending_id}")
async def reject_memory(
    pending_id: str,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    拒绝记忆

    标记待确认记忆为已拒绝
    """
    success = await svc.reject_pending(pending_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending memory not found")

    logger.info(f"Memory rejected: {pending_id}")
    return {"status": "rejected", "id": pending_id}


@router.put("/pending/{pending_id}")
async def update_and_confirm(
    pending_id: str,
    req: UpdatePendingRequest,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    编辑并确认记忆

    修改待确认记忆的值后确认
    """
    memory = await svc.update_pending(pending_id, req.new_value)
    if not memory:
        raise HTTPException(status_code=404, detail="Pending memory not found")

    logger.info(f"Memory updated and confirmed: {pending_id}")
    return memory


# ==================== 对话摘要 ====================



class GenerateDigestRequest(BaseModel):
    """生成摘要请求"""
    session_id: str
    messages: List[dict]  # [{role, content}, ...]


@router.post("/digest/generate")
async def generate_digest(
    req: GenerateDigestRequest,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    自动生成对话摘要（LLM）
    
    - **session_id**: 会话ID
    - **messages**: 对话消息列表
    """
    result = await svc.generate_digest(
        user_id=user_id,
        session_id=req.session_id,
        messages=req.messages
    )
    
    if result:
        return {"status": "created", "digest": result}
    return {"status": "skipped", "message": "对话太短或无需摘要"}

@router.post("/digest")
async def save_digest(
    req: DigestRequest,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    保存对话摘要

    - **session_id**: 会话ID
    - **title**: 标题 (10字以内)
    - **key_points**: 关键点 (最多3条)
    """
    return await svc.save_digest(
        user_id=user_id,
        session_id=req.session_id,
        title=req.title,
        key_points=req.key_points
    )


@router.get("/digests")
async def get_digests(
    limit: int = 15,
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """获取最近对话摘要"""
    return await svc.get_recent_digests(user_id, limit)


# ==================== 上下文 ====================

@router.get("/context")
async def get_memory_context(
    user_id: str = Depends(get_user_id),
    svc: MemoryService = Depends(get_memory_service)
):
    """
    获取记忆上下文

    返回可注入 System Prompt 的文本块（调试用）
    """
    context = await svc.build_context(user_id)
    return {"user_id": user_id, "context": context}


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """记忆服务健康检查"""
    return {"status": "ok", "service": "memory_v3"}


# ==================== 完整认知上下文 ====================

@router.get("/cognitive-context")
async def get_cognitive_context(
    user_id: str = Depends(get_user_id)
):
    """
    获取完整认知上下文 (调试用)
    
    返回 L0+L1+L2 层的完整上下文
    """
    from services.cognitive_context_service import get_cognitive_context_service
    
    service = get_cognitive_context_service()
    context = await service.build_full_context(user_id)
    stats = await service.get_context_stats(user_id)
    
    return {
        "user_id": user_id,
        "context": context,
        "stats": stats
    }
