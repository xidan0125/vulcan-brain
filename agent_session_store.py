"""
Agent Session 用户绑定模块 (异步版)
NOW POWERED BY ACONTEXT
"""

from typing import Dict, List, Optional
from acontext_integration import get_acontext_manager

# Note: The new implementation uses Acontext as the single source of truth
# for conversation history, replacing the old VulcanStore (MongoDB) implementation.

async def get_agent_session(user_id: str, session_id: str) -> List[Dict]:
    """获取用户的Agent会话历史 from Acontext."""
    manager = get_acontext_manager()
    # Acontext already binds history to user_id implicitly via its own auth.
    return await manager.get_conversation_history(user_id=user_id, session_id=session_id)


async def save_agent_session(user_id: str, session_id: str, messages: List[Dict], agent_type: str):
    """
    保存用户的Agent会话到 Acontext.
    
    NOTE: Acontext saves one message at a time. We will save the *last* message
    from the list, assuming previous ones are already saved.
    """
    if not messages:
        return

    manager = get_acontext_manager()
    last_message = messages[-1]
    
    await manager.save_message(
        user_id=user_id,
        role=last_message.get('role', 'unknown'),
        content=last_message.get('content', ''),
        session_id=session_id
    )


async def delete_agent_session(user_id: str, session_id: str) -> bool:
    """
    删除用户的Agent会话.
    
    NOTE: The backing Acontext service does not support session deletion.
    This function is now a no-op and will always return True for compatibility.
    """
    # Log that a deletion was attempted
    from vulcan_libs.logger import api_logger
    api_logger.warning(f"Attempted to delete session {session_id} for user {user_id}, which is a no-op in Acontext.")
    return True


async def list_user_sessions(user_id: str, agent_type: Optional[str] = None) -> List[Dict]:
    """
    列出用户的所有Agent会话 from Acontext.
    
    NOTE: The 'agent_type' filter is no longer supported as Acontext sessions
    are generic.
    """
    manager = get_acontext_manager()
    # The provider parameter in list_sessions might correspond to agent_type.
    # Assuming 'gemini' as a default if no agent_type is provided.
    provider = agent_type if agent_type else "gemini"
    return await manager.client.list_sessions(user_id=user_id, provider=provider)
