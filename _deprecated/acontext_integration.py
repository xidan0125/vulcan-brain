"""
Vulcan Brain - Acontext Integration
整合 Acontext 的 Session、Task Agent、Experience 能力
"""
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx

# Acontext API 配置 - 从 settings.py 读取
try:
    from settings import get_settings
    _settings = get_settings()
    ACONTEXT_API_URL = _settings.acontext_api_url
    ACONTEXT_CORE_URL = _settings.acontext_core_url
    ACONTEXT_BEARER_TOKEN = _settings.acontext_bearer_token or "sk-ac-your-root-api-bearer-token"
except Exception:
    # 回退到默认值
    ACONTEXT_API_URL = "http://localhost:8029"
    ACONTEXT_CORE_URL = "http://localhost:8019"
    ACONTEXT_BEARER_TOKEN = "sk-ac-your-root-api-bearer-token"


class AcontextClient:
    """Acontext REST API 客户端"""

    def __init__(self, api_url: str = ACONTEXT_API_URL, core_url: str = ACONTEXT_CORE_URL):
        self.api_url = api_url
        self.core_url = core_url
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {ACONTEXT_BEARER_TOKEN}"}
        )

    async def close(self):
        await self._client.aclose()

    # ==================== Session APIs ====================

    async def create_session(
        self,
        user_id: str,
        provider: str = "gemini",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """创建新会话"""
        payload = {
            "user_id": user_id,
            "provider": provider,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat()
        }
        response = await self._client.post(
            f"{self.api_url}/api/v1/session",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_session(self, session_id: str) -> Dict:
        """获取会话详情"""
        response = await self._client.get(
            f"{self.api_url}/api/v1/session/{session_id}"
        )
        response.raise_for_status()
        return response.json()

    async def list_sessions(
        self,
        user_id: str,
        provider: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """列出用户会话"""
        params = {"user_id": user_id, "limit": limit}
        if provider:
            params["provider"] = provider

        response = await self._client.get(
            f"{self.api_url}/api/v1/session",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """添加消息到会话"""
        payload = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        response = await self._client.post(
            f"{self.api_url}/api/v1/session/{session_id}/messages",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict]:
        """获取会话消息"""
        response = await self._client.get(
            f"{self.api_url}/api/v1/session/{session_id}/messages",
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

    # ==================== Experience Agent APIs ====================

    async def record_experience(
        self,
        user_id: str,
        session_id: str,
        experience_type: str,
        content: str,
        outcome: str = "neutral",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """记录用户经验（用于学习）"""
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "type": experience_type,  # e.g., "task_completed", "preference_learned", "feedback"
            "content": content,
            "outcome": outcome,  # "positive", "negative", "neutral"
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        response = await self._client.post(
            f"{self.api_url}/api/v1/experiences",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_user_experiences(
        self,
        user_id: str,
        experience_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """获取用户经验历史"""
        params = {"user_id": user_id, "limit": limit}
        if experience_type:
            params["type"] = experience_type

        response = await self._client.get(
            f"{self.api_url}/api/v1/experiences",
            params=params
        )
        response.raise_for_status()
        return response.json()

    # ==================== Space (Knowledge Base) APIs ====================

    async def create_space(
        self,
        name: str,
        description: str = "",
        user_id: Optional[str] = None
    ) -> Dict:
        """创建知识空间"""
        payload = {
            "name": name,
            "description": description,
            "user_id": user_id,
            "created_at": datetime.now().isoformat()
        }
        response = await self._client.post(
            f"{self.api_url}/api/v1/spaces",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def add_document(
        self,
        space_id: str,
        content: str,
        title: str = "",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """添加文档到知识空间"""
        payload = {
            "content": content,
            "title": title,
            "metadata": metadata or {}
        }
        response = await self._client.post(
            f"{self.api_url}/api/v1/spaces/{space_id}/documents",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def search_space(
        self,
        space_id: str,
        query: str,
        limit: int = 10
    ) -> List[Dict]:
        """搜索知识空间"""
        response = await self._client.get(
            f"{self.api_url}/api/v1/spaces/{space_id}/search",
            params={"query": query, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """检查 Acontext 服务状态"""
        try:
            response = await self._client.get(f"{self.api_url}/health")
            return response.status_code == 200
        except Exception:
            return False


# ==================== Vulcan Brain Integration ====================

class VulcanAcontextManager:
    """Vulcan Brain 与 Acontext 的集成管理器"""

    def __init__(self):
        self.client = AcontextClient()
        self._user_sessions: Dict[str, str] = {}  # user_id -> current_session_id

    async def start_session(
        self,
        user_id: str,
        provider: str = "gemini",
        title: Optional[str] = None
    ) -> str:
        """为用户启动新对话会话"""
        result = await self.client.create_session(
            user_id=user_id,
            provider=provider,
            metadata={"title": title or f"{provider.capitalize()} 对话"}
        )
        session_id = result.get("data", {}).get("id") or result.get("session_id") or result.get("id")
        self._user_sessions[user_id] = session_id
        return session_id

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        session_id: Optional[str] = None
    ):
        """保存对话消息"""
        sid = session_id or self._user_sessions.get(user_id)
        if not sid:
            # 自动创建会话
            sid = await self.start_session(user_id)

        await self.client.add_message(
            session_id=sid,
            role=role,
            content=content
        )

        # 如果是用户反馈，记录为经验
        if role == "user" and any(kw in content.lower() for kw in ["好", "不错", "有帮助", "谢谢", "感谢"]):
            await self.client.record_experience(
                user_id=user_id,
                session_id=sid,
                experience_type="positive_feedback",
                content=content,
                outcome="positive"
            )

    async def get_conversation_history(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """获取对话历史"""
        sid = session_id or self._user_sessions.get(user_id)
        if not sid:
            return []

        return await self.client.get_messages(session_id=sid, limit=limit)

    async def learn_from_interaction(
        self,
        user_id: str,
        interaction_type: str,
        content: str,
        outcome: str = "neutral",
        session_id: Optional[str] = None
    ):
        """从用户交互中学习"""
        sid = session_id or self._user_sessions.get(user_id)
        await self.client.record_experience(
            user_id=user_id,
            session_id=sid or "global",
            experience_type=interaction_type,
            content=content,
            outcome=outcome
        )

    async def get_user_insights(self, user_id: str) -> Dict:
        """获取用户洞察（基于历史经验）"""
        experiences = await self.client.get_user_experiences(user_id)

        # 简单统计
        positive = sum(1 for e in experiences if e.get("outcome") == "positive")
        negative = sum(1 for e in experiences if e.get("outcome") == "negative")
        total = len(experiences)

        return {
            "total_interactions": total,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "satisfaction_rate": positive / total if total > 0 else 0,
            "recent_experiences": experiences[:10]
        }

    async def close(self):
        await self.client.close()


# 全局实例
_manager: Optional[VulcanAcontextManager] = None


def get_acontext_manager() -> VulcanAcontextManager:
    """获取 Acontext 管理器实例"""
    global _manager
    if _manager is None:
        _manager = VulcanAcontextManager()
    return _manager


# ==================== FastAPI Router ====================

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/acontext", tags=["Acontext"])


class StartSessionRequest(BaseModel):
    provider: str = "gemini"
    title: Optional[str] = None


class SaveMessageRequest(BaseModel):
    session_id: Optional[str] = None
    role: str
    content: str


class LearnRequest(BaseModel):
    interaction_type: str
    content: str
    outcome: str = "neutral"
    session_id: Optional[str] = None


# 导入认证依赖
from auth_api import get_current_user


@router.get("/health")
async def acontext_health():
    """检查 Acontext 服务状态"""
    manager = get_acontext_manager()
    healthy = await manager.client.health_check()
    return {
        "acontext_available": healthy,
        "api_url": ACONTEXT_API_URL,
        "core_url": ACONTEXT_CORE_URL
    }


@router.post("/sessions/start")
async def start_session(
    req: StartSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """启动新对话会话"""
    manager = get_acontext_manager()
    try:
        session_id = await manager.start_session(
            user_id=current_user["user_id"],
            provider=req.provider,
            title=req.title
        )
        return {"session_id": session_id, "message": "会话已创建"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acontext error: {str(e)}")


@router.get("/sessions")
async def list_sessions(
    provider: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """列出用户会话"""
    manager = get_acontext_manager()
    try:
        sessions = await manager.client.list_sessions(
            user_id=current_user["user_id"],
            provider=provider,
            limit=limit
        )
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acontext error: {str(e)}")


@router.post("/messages")
async def save_message(
    req: SaveMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """保存对话消息"""
    manager = get_acontext_manager()
    try:
        await manager.save_message(
            user_id=current_user["user_id"],
            role=req.role,
            content=req.content,
            session_id=req.session_id
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acontext error: {str(e)}")


@router.get("/history")
async def get_history(
    session_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """获取对话历史"""
    manager = get_acontext_manager()
    try:
        messages = await manager.get_conversation_history(
            user_id=current_user["user_id"],
            session_id=session_id,
            limit=limit
        )
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acontext error: {str(e)}")


@router.post("/learn")
async def learn_interaction(
    req: LearnRequest,
    current_user: dict = Depends(get_current_user)
):
    """记录学习经验"""
    manager = get_acontext_manager()
    try:
        await manager.learn_from_interaction(
            user_id=current_user["user_id"],
            interaction_type=req.interaction_type,
            content=req.content,
            outcome=req.outcome,
            session_id=req.session_id
        )
        return {"success": True, "message": "经验已记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acontext error: {str(e)}")


@router.get("/insights")
async def get_insights(current_user: dict = Depends(get_current_user)):
    """获取用户洞察"""
    manager = get_acontext_manager()
    try:
        insights = await manager.get_user_insights(current_user["user_id"])
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acontext error: {str(e)}")
