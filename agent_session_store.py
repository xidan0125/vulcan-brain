"""
Agent Session 用户绑定模块 (异步版)
NOW POWERED BY VULCANSTORE (MongoDB)
"""

from typing import Dict, List, Optional
from vulcan_libs.store import store


async def get_agent_session(user_id: str, session_id: str) -> List[Dict]:
    """获取用户的Agent会话历史 from VulcanStore."""
    return await store.get_agent_session(user_id=user_id, session_id=session_id)


async def save_agent_session(user_id: str, session_id: str, messages: List[Dict], agent_type: str):
    """保存用户的Agent会话到 VulcanStore."""
    await store.save_agent_session(
        user_id=user_id,
        session_id=session_id,
        messages=messages,
        agent_type=agent_type
    )


async def delete_agent_session(user_id: str, session_id: str) -> bool:
    """删除用户的Agent会话."""
    return await store.delete_agent_session(user_id=user_id, session_id=session_id)


async def list_user_sessions(user_id: str, agent_type: Optional[str] = None) -> List[Dict]:
    """列出用户的所有Agent会话."""
    return await store.list_user_agent_sessions(user_id=user_id, agent_type=agent_type)
