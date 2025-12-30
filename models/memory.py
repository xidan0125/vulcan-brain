"""
Vulcan Brain - 记忆系统数据模型 v3.0
统一的 Pydantic 模型定义

集合:
- user_memories: 用户长期记忆 (key-value 格式)
- pending_memories: 待确认记忆
- conversation_digests: 对话摘要
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from bson import ObjectId


# ==================== 类型定义 ====================

MemoryCategory = Literal["identity", "preference", "fact"]
MemorySource = Literal["user_confirmed", "ai_extracted", "manual", "migrated"]
PendingStatus = Literal["pending", "confirmed", "rejected", "expired"]


# ==================== 用户记忆 (L2层) ====================

class UserMemoryBase(BaseModel):
    """用户记忆基础模型"""
    key: str = Field(..., description="记忆键名, 如 name, role, pref_style")
    value: str = Field(..., description="记忆值")
    category: MemoryCategory = Field(default="fact", description="分类: identity/preference/fact")
    
class UserMemoryCreate(UserMemoryBase):
    """创建用户记忆"""
    source: MemorySource = Field(default="user_confirmed", description="来源")
    
class UserMemoryUpdate(BaseModel):
    """更新用户记忆"""
    value: Optional[str] = None
    category: Optional[MemoryCategory] = None

class UserMemoryDocument(UserMemoryBase):
    """
    用户记忆文档 (MongoDB Schema)
    
    集合: user_memories
    索引:
    - { user_id: 1, key: 1 } unique
    - { user_id: 1, category: 1 }
    - { user_id: 1, updated_at: -1 }
    """
    id: str = Field(alias="_id")
    user_id: str = Field(..., description="用户ID (绑定)")
    source: MemorySource = Field(default="user_confirmed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ==================== 待确认记忆 ====================

class PendingMemoryCreate(BaseModel):
    """创建待确认记忆 (从 AI 提取)"""
    session_id: str = Field(..., description="对话会话ID")
    key: str = Field(..., description="记忆键名")
    value: str = Field(..., description="记忆值")
    category: MemoryCategory = Field(default="fact")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度")
    context: str = Field(..., description="原始用户消息 (溯源)")

class PendingMemoryDocument(BaseModel):
    """
    待确认记忆文档 (MongoDB Schema)
    
    集合: pending_memories
    索引:
    - { user_id: 1, status: 1 }
    - { expires_at: 1 } TTL (自动过期)
    """
    id: str = Field(alias="_id")
    user_id: str = Field(..., description="用户ID")
    session_id: str
    key: str
    value: str
    category: MemoryCategory
    confidence: float
    context: str
    status: PendingStatus = Field(default="pending")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7),
        description="7天后自动过期"
    )
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ==================== 对话摘要 ====================

class ConversationDigestCreate(BaseModel):
    """创建对话摘要"""
    session_id: str = Field(..., description="对话会话ID")
    title: str = Field(..., max_length=50, description="摘要标题 (10字以内)")
    key_points: List[str] = Field(default_factory=list, max_length=5, description="要点 (最多5条)")
    message_count: int = Field(default=0, description="对话轮数")

class ConversationDigestDocument(BaseModel):
    """
    对话摘要文档 (MongoDB Schema)
    
    集合: conversation_digests
    索引:
    - { user_id: 1, created_at: -1 }
    - { user_id: 1, session_id: 1 } unique
    """
    id: str = Field(alias="_id")
    user_id: str
    session_id: str
    title: str
    key_points: List[str]
    message_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ==================== API 响应模型 ====================

class MemoryResponse(BaseModel):
    """记忆 API 响应"""
    id: str
    key: str
    value: str
    category: MemoryCategory
    source: MemorySource
    created_at: datetime
    updated_at: datetime

class PendingMemoryResponse(BaseModel):
    """待确认记忆 API 响应"""
    id: str
    key: str
    value: str
    category: MemoryCategory
    confidence: float
    context: str
    status: PendingStatus
    created_at: datetime
    expires_at: datetime

class MemoryExtractionResult(BaseModel):
    """记忆提取结果"""
    should_remember: bool = False
    extractions: List[dict] = Field(default_factory=list)

class CognitiveContext(BaseModel):
    """认知上下文 (注入 System Prompt)"""
    user_id: str
    memories: List[MemoryResponse] = Field(default_factory=list)
    recent_digests: List[ConversationDigestDocument] = Field(default_factory=list)
    formatted_prompt: str = ""


# ==================== 迁移相关 ====================

class LegacyMemory(BaseModel):
    """旧版记忆格式 (用于迁移)"""
    user_id: str
    content: str
    category: str
    created_at: datetime
    access_count: int = 0
