"""
信息中心 API - 共享模块
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import os

# MongoDB 连接
_client = None
def get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return _client.vulcan_brain


# ===== Pydantic Models =====

class GenerateReportRequest(BaseModel):
    date: Optional[str] = None

class AnalyzeChatRequest(BaseModel):
    date: Optional[str] = None

class UpdatePersonRequest(BaseModel):
    department: Optional[str] = None
    function: Optional[str] = None

class CollectApprovalsRequest(BaseModel):
    approval_codes: Optional[List[str]] = None
    since_hours: int = 24
