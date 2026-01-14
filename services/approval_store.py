"""
审批数据存储层 - MongoDB版 (Motor Async)
五纬度信息收集系统 - 维度4: 飞书审批

v2.0 - 2026-01-13: 从 PyMongo (sync) 迁移到 Motor (async)

Collections:
- feishu_approvals: 审批实例（原始数据）
- approval_summaries: 审批日报汇总（AI分析结果）
- approval_definitions: 审批定义缓存（审批类型）
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, UpdateOne
from bson import ObjectId
import logging

logger = logging.getLogger("ApprovalStore")


class ApprovalStore:
    """审批数据存储 - MongoDB (Async Motor)"""

    _instance = None
    _indexes_created = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client["vulcan_brain"]

        # Collections
        self.approvals_col = self.db["feishu_approvals"]
        self.summaries_col = self.db["approval_summaries"]
        self.definitions_col = self.db["approval_definitions"]

        self._initialized = True
        logger.info("[ApprovalStore Motor] 异步客户端初始化完成")

    async def ensure_indexes(self):
        """创建索引（首次查询时调用）"""
        if ApprovalStore._indexes_created:
            return

        # 审批实例索引
        await self.approvals_col.create_index("instance_code", unique=True)
        await self.approvals_col.create_index("approval_code")
        await self.approvals_col.create_index("status")
        await self.approvals_col.create_index("user_id")
        await self.approvals_col.create_index("start_time")
        await self.approvals_col.create_index("end_time")
        await self.approvals_col.create_index([("start_time", DESCENDING)])

        # 日报汇总索引
        await self.summaries_col.create_index([("date", DESCENDING)])
        await self.summaries_col.create_index("date", unique=True)

        # 审批定义索引
        await self.definitions_col.create_index("approval_code", unique=True)

        ApprovalStore._indexes_created = True
        count = await self.approvals_col.count_documents({})
        logger.info(f"[ApprovalStore Motor] 索引创建完成: {count}条审批记录")

    # ===== 审批实例 CRUD =====

    async def save_approval(self, approval_data: Dict) -> Optional[Dict]:
        """保存审批实例（幂等）"""
        await self.ensure_indexes()
        
        instance_code = approval_data.get("instance_code")
        if not instance_code:
            logger.warning("[ApprovalStore] 审批缺少instance_code")
            return None

        # 幂等检查
        existing = await self.approvals_col.find_one({"instance_code": instance_code})
        if existing:
            if existing.get("status") != approval_data.get("status"):
                await self.approvals_col.update_one(
                    {"instance_code": instance_code},
                    {"$set": {
                        "status": approval_data.get("status"),
                        "end_time": approval_data.get("end_time"),
                        "updated_at": datetime.now().isoformat()
                    }}
                )
                logger.debug(f"[ApprovalStore] 更新审批状态: {instance_code}")
            return None

        # 新增
        approval_data["created_at"] = datetime.now().isoformat()
        approval_data["updated_at"] = datetime.now().isoformat()
        await self.approvals_col.insert_one(approval_data)
        approval_data.pop("_id", None)

        logger.debug(f"[ApprovalStore] 保存审批: {instance_code}")
        return approval_data

    async def save_approvals_batch(self, approvals: List[Dict]) -> Dict:
        """批量保存审批 (bulk_write 优化)"""
        await self.ensure_indexes()
        
        if not approvals:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        operations = []
        for approval in approvals:
            instance_code = approval.get("instance_code")
            if not instance_code:
                continue
            approval["updated_at"] = datetime.now().isoformat()
            operations.append(
                UpdateOne(
                    {"instance_code": instance_code},
                    {"$set": approval, "$setOnInsert": {"created_at": datetime.now().isoformat()}},
                    upsert=True
                )
            )

        if not operations:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        result = await self.approvals_col.bulk_write(operations, ordered=False)
        stats = {
            "inserted": result.upserted_count,
            "updated": result.modified_count,
            "skipped": result.matched_count - result.modified_count
        }

        logger.info(f"[ApprovalStore] 批量保存: {stats}")
        return stats

    async def get_approval(self, instance_code: str) -> Optional[Dict]:
        """获取单个审批实例"""
        await self.ensure_indexes()
        return await self.approvals_col.find_one({"instance_code": instance_code}, {"_id": 0})

    async def list_approvals(
        self,
        approval_code: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """查询审批列表"""
        await self.ensure_indexes()
        
        query = {}
        if approval_code:
            query["approval_code"] = approval_code
        if status:
            query["status"] = status
        if user_id:
            query["user_id"] = user_id
        if since:
            query["start_time"] = {"$gte": since.isoformat() if isinstance(since, datetime) else since}
        if until:
            if "start_time" in query:
                query["start_time"]["$lte"] = until.isoformat() if isinstance(until, datetime) else until
            else:
                query["start_time"] = {"$lte": until.isoformat() if isinstance(until, datetime) else until}

        cursor = self.approvals_col.find(query, {"_id": 0}).sort("start_time", DESCENDING).limit(limit)
        return await cursor.to_list(length=None)

    async def get_today_approvals(self) -> List[Dict]:
        """获取今日审批"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return await self.list_approvals(since=today, until=tomorrow, limit=500)

    async def get_pending_approvals(self, user_id: Optional[str] = None) -> List[Dict]:
        """获取待处理审批"""
        return await self.list_approvals(status="PENDING", user_id=user_id)

    # ===== 审批统计 =====

    async def get_stats(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> Dict:
        """获取审批统计"""
        await self.ensure_indexes()
        
        match_stage = {}
        if since:
            match_stage["start_time"] = {"$gte": since.isoformat()}
        if until:
            if "start_time" in match_stage:
                match_stage["start_time"]["$lte"] = until.isoformat()
            else:
                match_stage["start_time"] = {"$lte": until.isoformat()}

        # 按状态分组
        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.append({"$group": {"_id": "$status", "count": {"$sum": 1}}})

        cursor = self.approvals_col.aggregate(pipeline)
        status_results = await cursor.to_list(length=None)
        by_status = {r["_id"]: r["count"] for r in status_results if r["_id"]}

        # 按类型分组
        pipeline2 = []
        if match_stage:
            pipeline2.append({"$match": match_stage})
        pipeline2.append({"$group": {"_id": "$approval_name", "count": {"$sum": 1}}})

        cursor2 = self.approvals_col.aggregate(pipeline2)
        type_results = await cursor2.to_list(length=None)
        by_type = {r["_id"]: r["count"] for r in type_results if r["_id"]}

        total = sum(by_status.values())
        pending_count = by_status.get("PENDING", 0)

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "pending_count": pending_count
        }

    # ===== 日报汇总 =====

    async def save_summary(self, date: str, summary_data: Dict) -> Dict:
        """保存审批日报汇总"""
        await self.ensure_indexes()
        
        summary_data["date"] = date
        summary_data["updated_at"] = datetime.now().isoformat()

        await self.summaries_col.update_one(
            {"date": date},
            {"$set": summary_data},
            upsert=True
        )

        logger.info(f"[ApprovalStore] 保存日报汇总: {date}")
        return summary_data

    async def get_summary(self, date: str) -> Optional[Dict]:
        """获取指定日期的汇总"""
        await self.ensure_indexes()
        return await self.summaries_col.find_one({"date": date}, {"_id": 0})

    async def list_summaries(self, days: int = 7) -> List[Dict]:
        """获取最近N天的汇总"""
        await self.ensure_indexes()
        cursor = self.summaries_col.find({}, {"_id": 0}).sort("date", DESCENDING).limit(days)
        return await cursor.to_list(length=None)

    # ===== 审批定义缓存 =====

    async def save_definition(self, definition: Dict) -> Dict:
        """缓存审批定义"""
        await self.ensure_indexes()
        
        approval_code = definition.get("approval_code")
        if not approval_code:
            return definition

        definition["cached_at"] = datetime.now().isoformat()

        await self.definitions_col.update_one(
            {"approval_code": approval_code},
            {"$set": definition},
            upsert=True
        )
        return definition

    async def get_definition(self, approval_code: str) -> Optional[Dict]:
        """获取审批定义"""
        await self.ensure_indexes()
        return await self.definitions_col.find_one({"approval_code": approval_code}, {"_id": 0})

    async def list_definitions(self) -> List[Dict]:
        """列出所有审批定义"""
        await self.ensure_indexes()
        cursor = self.definitions_col.find({}, {"_id": 0})
        return await cursor.to_list(length=None)


# ===== 单例 =====

_store = None

def get_approval_store() -> ApprovalStore:
    """获取审批存储单例"""
    global _store
    if _store is None:
        _store = ApprovalStore()
    return _store
