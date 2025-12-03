"""
群聊汇总存储服务 - 五纬度信息系统 (维度1增强)

功能:
1. 存储每个群聊每天的AI分析结果
2. 支持增量分析（采集时实时触发）
3. 提供结构化查询接口
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os
import asyncio

logger = logging.getLogger("ChatSummaryStore")


class ChatSummaryStore:
    """群聊汇总存储管理器"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, mongo_uri: str = None):
        if hasattr(self, "_initialized"):
            return
        
        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.vulcan_brain
        
        # 集合
        self.summaries = self.db.chat_summaries      # 群聊分析汇总
        self.metadata = self.db.chat_metadata        # 群聊元数据
        self.analysis_queue = self.db.analysis_queue # 分析队列
        
        self._initialized = True
        logger.info("✅ ChatSummaryStore initialized")
    
    async def init_indexes(self):
        """初始化索引"""
        # chat_summaries: chat_id + date 联合唯一索引
        await self.summaries.create_index(
            [("chat_id", ASCENDING), ("date", ASCENDING)],
            unique=True
        )
        await self.summaries.create_index("updated_at")
        
        # chat_metadata: chat_id 唯一索引
        await self.metadata.create_index("chat_id", unique=True)
        
        # analysis_queue: 处理状态索引
        await self.analysis_queue.create_index([
            ("status", ASCENDING),
            ("created_at", ASCENDING)
        ])
        
        logger.info("✅ ChatSummaryStore indexes created")
    
    # ===== 群聊元数据管理 =====
    
    async def upsert_chat_metadata(self, chat_id: str, data: Dict) -> bool:
        """更新或插入群聊元数据"""
        data["chat_id"] = chat_id
        data["updated_at"] = datetime.now()
        data.setdefault("created_at", datetime.now())
        
        await self.metadata.update_one(
            {"chat_id": chat_id},
            {"$set": data},
            upsert=True
        )
        return True
    
    async def get_chat_metadata(self, chat_id: str) -> Optional[Dict]:
        """获取群聊元数据"""
        doc = await self.metadata.find_one({"chat_id": chat_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    
    async def get_all_chats(self) -> List[Dict]:
        """获取所有群聊列表"""
        cursor = self.metadata.find().sort("updated_at", DESCENDING)
        chats = await cursor.to_list(length=100)
        for c in chats:
            c["_id"] = str(c["_id"])
        return chats
    
    # ===== 群聊汇总管理 =====
    
    async def save_summary(
        self,
        chat_id: str,
        date: str,
        analysis: Dict,
        messages_analyzed: int
    ) -> bool:
        """
        保存群聊分析汇总
        
        Args:
            chat_id: 群聊ID
            date: 日期 (YYYY-MM-DD)
            analysis: AI分析结果
            messages_analyzed: 已分析消息数
        """
        doc = {
            "chat_id": chat_id,
            "date": date,
            "analysis": analysis,
            "messages_analyzed": messages_analyzed,
            "updated_at": datetime.now()
        }
        
        await self.summaries.update_one(
            {"chat_id": chat_id, "date": date},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"[ChatSummaryStore] Saved summary for {chat_id} on {date}")
        return True
    
    async def get_summary(self, chat_id: str, date: str) -> Optional[Dict]:
        """获取指定群聊指定日期的汇总"""
        doc = await self.summaries.find_one({"chat_id": chat_id, "date": date})
        if doc:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("updated_at"), datetime):
                doc["updated_at"] = doc["updated_at"].isoformat()
        return doc
    
    async def get_chat_history_summaries(
        self,
        chat_id: str,
        days: int = 7
    ) -> List[Dict]:
        """获取群聊最近N天的汇总列表"""
        cursor = self.summaries.find(
            {"chat_id": chat_id}
        ).sort("date", DESCENDING).limit(days)
        
        docs = await cursor.to_list(length=days)
        for d in docs:
            d["_id"] = str(d["_id"])
            if isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d["updated_at"].isoformat()
        return docs
    
    async def get_date_summaries(self, date: str) -> List[Dict]:
        """获取指定日期所有群聊的汇总"""
        cursor = self.summaries.find({"date": date})
        docs = await cursor.to_list(length=100)
        for d in docs:
            d["_id"] = str(d["_id"])
            if isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d["updated_at"].isoformat()
        return docs
    
    # ===== 分析队列管理（用于实时触发）=====
    
    async def queue_analysis(self, chat_id: str, date: str = None) -> str:
        """
        将群聊加入分析队列
        
        Returns:
            queue_id: 队列任务ID
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        doc = {
            "chat_id": chat_id,
            "date": date,
            "status": "pending",  # pending / processing / completed / failed
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "error": None
        }
        
        result = await self.analysis_queue.insert_one(doc)
        return str(result.inserted_id)
    
    async def get_pending_analysis(self, limit: int = 10) -> List[Dict]:
        """获取待处理的分析任务"""
        cursor = self.analysis_queue.find(
            {"status": "pending"}
        ).sort("created_at", ASCENDING).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs
    
    async def update_analysis_status(
        self,
        queue_id: str,
        status: str,
        error: str = None
    ):
        """更新分析任务状态"""
        from bson import ObjectId
        await self.analysis_queue.update_one(
            {"_id": ObjectId(queue_id)},
            {"$set": {
                "status": status,
                "error": error,
                "updated_at": datetime.now()
            }}
        )
    
    # ===== 统计接口 =====
    
    async def get_chat_stats(self, chat_id: str) -> Dict:
        """获取群聊统计数据"""
        # 获取最近30天的汇总
        summaries = await self.get_chat_history_summaries(chat_id, days=30)
        
        total_messages = sum(s.get("messages_analyzed", 0) for s in summaries)
        total_decisions = sum(
            len(s.get("analysis", {}).get("decisions", [])) 
            for s in summaries
        )
        total_action_items = sum(
            len(s.get("analysis", {}).get("action_items", []))
            for s in summaries
        )
        total_risks = sum(
            len(s.get("analysis", {}).get("risks", []))
            for s in summaries
        )
        
        return {
            "chat_id": chat_id,
            "days_with_data": len(summaries),
            "total_messages": total_messages,
            "total_decisions": total_decisions,
            "total_action_items": total_action_items,
            "total_risks": total_risks,
            "latest_date": summaries[0]["date"] if summaries else None
        }


# ===== 便捷函数 =====

_store = None

def get_chat_summary_store() -> ChatSummaryStore:
    """获取存储实例"""
    global _store
    if _store is None:
        _store = ChatSummaryStore()
    return _store
