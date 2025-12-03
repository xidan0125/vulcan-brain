"""
邮件线程聚合服务 - Phase 0.1

功能:
1. 使用 conversation_id 聚合邮件线程
2. 为每个线程生成摘要信息
3. 支持线程级别的搜索和检索
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os

logger = logging.getLogger("EmailThreadService")


class EmailThreadService:
    """邮件线程聚合服务"""
    
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
        self.emails = self.db.emails
        self.threads = self.db.email_threads  # 线程聚合表
        self._initialized = True
        logger.info("EmailThreadService initialized")
    
    async def init_indexes(self):
        """初始化索引"""
        # 邮件表索引
        await self.emails.create_index("conversation_id")
        
        # 线程表索引
        await self.threads.create_index("conversation_id", unique=True)
        await self.threads.create_index([("last_activity", DESCENDING)])
        await self.threads.create_index("participants")
        await self.threads.create_index([("subject", "text")])
        
        logger.info("Thread indexes created")
    
    async def build_threads(self, batch_size: int = 1000) -> Dict[str, int]:
        """
        构建邮件线程
        
        从 emails 表聚合 conversation_id，生成 threads 表
        """
        logger.info("开始构建邮件线程...")
        
        # 聚合管道：按 conversation_id 分组
        pipeline = [
            {"$match": {"conversation_id": {"$exists": True, "$ne": None}}},
            {"$group": {
                "_id": "$conversation_id",
                "email_count": {"$sum": 1},
                "first_email": {"$min": "$received_at"},
                "last_email": {"$max": "$received_at"},
                "subjects": {"$addToSet": "$subject"},
                "participants": {"$addToSet": "$from.address"},
                "all_to": {"$push": "$to"},
                "folders": {"$addToSet": "$folder"},
                "users": {"$addToSet": "$user_id"},
            }},
            {"$sort": {"last_email": -1}}
        ]
        
        created = 0
        updated = 0
        
        async for group in self.emails.aggregate(pipeline, batchSize=batch_size):
            conv_id = group["_id"]
            
            # 提取所有参与者 (from + to)
            all_participants = set(group["participants"])
            for to_list in group["all_to"]:
                for recipient in to_list:
                    if recipient.get("address"):
                        all_participants.add(recipient["address"].lower())
            
            # 选择最具代表性的主题 (去掉 Re: Fwd: 前缀)
            subjects = group["subjects"]
            clean_subjects = []
            for s in subjects:
                if s:
                    clean = s
                    for prefix in ["Re: ", "RE: ", "Fwd: ", "FW: ", "Fw: "]:
                        if clean.startswith(prefix):
                            clean = clean[len(prefix):]
                    clean_subjects.append(clean)
            
            # 选择最长的主题作为线程标题
            subject = max(clean_subjects, key=len) if clean_subjects else "无主题"
            
            thread_doc = {
                "conversation_id": conv_id,
                "subject": subject,
                "email_count": group["email_count"],
                "first_activity": group["first_email"],
                "last_activity": group["last_email"],
                "participants": list(all_participants),
                "participant_count": len(all_participants),
                "folders": group["folders"],
                "user_ids": group["users"],
                "updated_at": datetime.now(),
            }
            
            result = await self.threads.update_one(
                {"conversation_id": conv_id},
                {"$set": thread_doc},
                upsert=True
            )
            
            if result.upserted_id:
                created += 1
            elif result.modified_count:
                updated += 1
        
        # 统计无 conversation_id 的邮件
        orphan_count = await self.emails.count_documents({
            "$or": [
                {"conversation_id": {"$exists": False}},
                {"conversation_id": None}
            ]
        })
        
        total_threads = await self.threads.count_documents({})
        
        logger.info(f"线程构建完成: 创建 {created}, 更新 {updated}, 总计 {total_threads} 个线程, {orphan_count} 封孤立邮件")
        return {
            "created": created,
            "updated": updated,
            "total_threads": total_threads,
            "orphan_emails": orphan_count
        }
    
    async def get_thread(self, conversation_id: str) -> Optional[Dict]:
        """获取单个线程详情"""
        thread = await self.threads.find_one({"conversation_id": conversation_id})
        if thread:
            thread["_id"] = str(thread["_id"])
            
            # 获取线程中的所有邮件
            emails = []
            cursor = self.emails.find(
                {"conversation_id": conversation_id}
            ).sort("received_at", ASCENDING)
            
            async for email in cursor:
                email["_id"] = str(email["_id"])
                emails.append({
                    "email_id": email.get("email_id"),
                    "from": email.get("from"),
                    "to": email.get("to"),
                    "subject": email.get("subject"),
                    "body_preview": email.get("body_preview", "")[:200],
                    "received_at": email.get("received_at"),
                    "folder": email.get("folder"),
                })
            
            thread["emails"] = emails
        
        return thread
    
    async def search_threads(
        self,
        query: str = None,
        participant: str = None,
        user_id: str = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple[List[Dict], int]:
        """搜索线程"""
        filter_query = {}
        
        if query:
            filter_query["$text"] = {"$search": query}
        
        if participant:
            filter_query["participants"] = {"$regex": participant, "$options": "i"}
        
        if user_id:
            filter_query["user_ids"] = user_id
        
        total = await self.threads.count_documents(filter_query)
        
        cursor = self.threads.find(filter_query).sort(
            "last_activity", DESCENDING
        ).skip(skip).limit(limit)
        
        threads = []
        async for thread in cursor:
            thread["_id"] = str(thread["_id"])
            threads.append(thread)
        
        return threads, total
    
    async def get_thread_stats(self) -> Dict:
        """获取线程统计"""
        total_threads = await self.threads.count_documents({})
        total_emails = await self.emails.count_documents({})
        
        # 按邮件数量分布
        size_pipeline = [
            {"$bucket": {
                "groupBy": "$email_count",
                "boundaries": [1, 2, 5, 10, 20, 50, 100],
                "default": "100+",
                "output": {"count": {"$sum": 1}}
            }}
        ]
        
        size_dist = {}
        async for bucket in self.threads.aggregate(size_pipeline):
            size_dist[str(bucket["_id"])] = bucket["count"]
        
        # 最活跃的线程
        top_threads = []
        cursor = self.threads.find().sort("email_count", DESCENDING).limit(10)
        async for thread in cursor:
            top_threads.append({
                "subject": thread["subject"][:50],
                "email_count": thread["email_count"],
                "participants": thread["participant_count"],
            })
        
        return {
            "total_threads": total_threads,
            "total_emails": total_emails,
            "avg_emails_per_thread": round(total_emails / total_threads, 2) if total_threads else 0,
            "size_distribution": size_dist,
            "top_threads": top_threads,
        }


# ===== 便捷函数 =====

_service = None

def get_email_thread_service() -> EmailThreadService:
    """获取线程服务实例"""
    global _service
    if _service is None:
        _service = EmailThreadService()
    return _service


async def build_email_threads() -> Dict:
    """构建邮件线程 (便捷函数)"""
    service = get_email_thread_service()
    await service.init_indexes()
    return await service.build_threads()
