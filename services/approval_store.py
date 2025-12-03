"""
审批数据存储层 - MongoDB版
五纬度信息收集系统 - 维度4: 飞书审批

Collections:
- feishu_approvals: 审批实例（原始数据）
- approval_summaries: 审批日报汇总（AI分析结果）
- approval_definitions: 审批定义缓存（审批类型）
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
import logging

logger = logging.getLogger("ApprovalStore")


class ApprovalStore:
    """审批数据存储 - MongoDB"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["vulcan_brain"]

        # Collections
        self.approvals_col = self.db["feishu_approvals"]      # 审批实例
        self.summaries_col = self.db["approval_summaries"]    # 日报汇总
        self.definitions_col = self.db["approval_definitions"] # 审批定义缓存

        self._create_indexes()
        self._initialized = True

        count = self.approvals_col.count_documents({})
        logger.info(f"[ApprovalStore] 初始化完成: {count}条审批记录")

    def _create_indexes(self):
        """创建索引"""
        # 审批实例索引
        self.approvals_col.create_index("instance_code", unique=True)
        self.approvals_col.create_index("approval_code")  # 审批类型
        self.approvals_col.create_index("status")
        self.approvals_col.create_index("user_id")  # 发起人
        self.approvals_col.create_index("start_time")
        self.approvals_col.create_index("end_time")
        self.approvals_col.create_index([("start_time", DESCENDING)])

        # 日报汇总索引
        self.summaries_col.create_index([("date", DESCENDING)])
        self.summaries_col.create_index("date", unique=True)

        # 审批定义索引
        self.definitions_col.create_index("approval_code", unique=True)

    # ===== 审批实例 CRUD =====

    async def save_approval(self, approval_data: Dict) -> Optional[Dict]:
        """
        保存审批实例（幂等）

        Args:
            approval_data: 飞书审批实例数据

        Returns:
            保存的审批数据，如果已存在返回None
        """
        instance_code = approval_data.get("instance_code")
        if not instance_code:
            logger.warning("[ApprovalStore] 审批缺少instance_code")
            return None

        # 幂等检查
        existing = self.approvals_col.find_one({"instance_code": instance_code})
        if existing:
            # 如果状态变化，更新
            if existing.get("status") != approval_data.get("status"):
                self.approvals_col.update_one(
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
        self.approvals_col.insert_one(approval_data)
        approval_data.pop("_id", None)

        logger.debug(f"[ApprovalStore] 保存审批: {instance_code}")
        return approval_data

    async def save_approvals_batch(self, approvals: List[Dict]) -> Dict:
        """
        批量保存审批

        Returns:
            {"inserted": 数量, "updated": 数量, "skipped": 数量}
        """
        stats = {"inserted": 0, "updated": 0, "skipped": 0}

        for approval in approvals:
            result = await self.save_approval(approval)
            if result:
                stats["inserted"] += 1
            else:
                # 检查是否是更新还是跳过
                instance_code = approval.get("instance_code")
                existing = self.approvals_col.find_one({"instance_code": instance_code})
                if existing and existing.get("status") != approval.get("status"):
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1

        logger.info(f"[ApprovalStore] 批量保存: {stats}")
        return stats

    async def get_approval(self, instance_code: str) -> Optional[Dict]:
        """获取单个审批实例"""
        result = self.approvals_col.find_one({"instance_code": instance_code}, {"_id": 0})
        return result

    async def list_approvals(
        self,
        approval_code: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查询审批列表

        Args:
            approval_code: 审批定义code（审批类型）
            status: 状态 (PENDING/APPROVED/REJECTED/CANCELED/DELETED)
            user_id: 发起人ID
            since: 开始时间
            until: 结束时间
            limit: 返回数量
        """
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

        results = list(
            self.approvals_col.find(query, {"_id": 0})
            .sort("start_time", DESCENDING)
            .limit(limit)
        )
        return results

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
        """
        获取审批统计

        Returns:
            {
                "total": 总数,
                "by_status": {"PENDING": n, "APPROVED": n, ...},
                "by_type": {"请假": n, "报销": n, ...},
                "pending_count": 待处理数
            }
        """
        match_stage = {}
        if since:
            match_stage["start_time"] = {"$gte": since.isoformat()}
        if until:
            if "start_time" in match_stage:
                match_stage["start_time"]["$lte"] = until.isoformat()
            else:
                match_stage["start_time"] = {"$lte": until.isoformat()}

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})

        # 按状态分组
        pipeline.append({
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }
        })

        status_results = list(self.approvals_col.aggregate(pipeline))
        by_status = {r["_id"]: r["count"] for r in status_results if r["_id"]}

        # 按类型分组
        pipeline2 = []
        if match_stage:
            pipeline2.append({"$match": match_stage})
        pipeline2.append({
            "$group": {
                "_id": "$approval_name",
                "count": {"$sum": 1}
            }
        })

        type_results = list(self.approvals_col.aggregate(pipeline2))
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
        """
        保存审批日报汇总

        Args:
            date: 日期 (YYYY-MM-DD)
            summary_data: 汇总数据
        """
        summary_data["date"] = date
        summary_data["updated_at"] = datetime.now().isoformat()

        self.summaries_col.update_one(
            {"date": date},
            {"$set": summary_data},
            upsert=True
        )

        logger.info(f"[ApprovalStore] 保存日报汇总: {date}")
        return summary_data

    async def get_summary(self, date: str) -> Optional[Dict]:
        """获取指定日期的汇总"""
        result = self.summaries_col.find_one({"date": date}, {"_id": 0})
        return result

    async def list_summaries(self, days: int = 7) -> List[Dict]:
        """获取最近N天的汇总"""
        results = list(
            self.summaries_col.find({}, {"_id": 0})
            .sort("date", DESCENDING)
            .limit(days)
        )
        return results

    # ===== 审批定义缓存 =====

    async def save_definition(self, definition: Dict) -> Dict:
        """缓存审批定义"""
        approval_code = definition.get("approval_code")
        if not approval_code:
            return definition

        definition["cached_at"] = datetime.now().isoformat()

        self.definitions_col.update_one(
            {"approval_code": approval_code},
            {"$set": definition},
            upsert=True
        )
        return definition

    async def get_definition(self, approval_code: str) -> Optional[Dict]:
        """获取审批定义"""
        return self.definitions_col.find_one({"approval_code": approval_code}, {"_id": 0})

    async def list_definitions(self) -> List[Dict]:
        """列出所有审批定义"""
        return list(self.definitions_col.find({}, {"_id": 0}))


# ===== 单例 =====

_store = None

def get_approval_store() -> ApprovalStore:
    """获取审批存储单例"""
    global _store
    if _store is None:
        _store = ApprovalStore()
    return _store
