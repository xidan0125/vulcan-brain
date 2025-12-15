"""
Vulcan Brain - AContext SDK Helper
使用官方 SDK 与 AContext 交互
"""
from acontext import AcontextClient

# AContext 配置
ACONTEXT_API_URL = "http://localhost:8029/api/v1"
ACONTEXT_API_KEY = "sk-ac-your-root-api-bearer-token"

_client = None

def get_client() -> AcontextClient:
    """获取 AContext 客户端单例"""
    global _client
    if _client is None:
        _client = AcontextClient(
            base_url=ACONTEXT_API_URL,
            api_key=ACONTEXT_API_KEY
        )
    return _client

def list_sessions(limit: int = 20):
    """列出所有会话"""
    client = get_client()
    result = client.sessions.list(limit=limit)
    return result.items

def create_session():
    """创建新会话"""
    client = get_client()
    return client.sessions.create()

def send_message(session_id: str, role: str, content: str):
    """发送消息到会话"""
    client = get_client()
    return client.sessions.send_message(
        session_id=session_id,
        role=role,
        content=content
    )

def get_messages(session_id: str):
    """获取会话消息"""
    client = get_client()
    return client.sessions.get_messages(session_id=session_id)
