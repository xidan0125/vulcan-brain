"""
每日日报服务 - 五纬度信息收集系统

功能:
1. 生成/存储每日日报
2. 支持五个维度的数据汇总
3. 提供日报摘要 + 详情两种数据格式
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os

from services.chat_summarizer import generate_chat_summary
from services.feishu_collector import get_message_collector

logger = logging.getLogger("DailyReport")


class DailyReportService:
    """每日日报服务"""
    
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
        self.collection = self.db.daily_reports
        self._initialized = True
        logger.info("✅ DailyReportService initialized")
    
    async def init_indexes(self):
        """初始化索引"""
        # date 唯一索引
        await self.collection.create_index("date", unique=True)
        # created_at 索引
        await self.collection.create_index("created_at")
        logger.info("✅ DailyReport indexes created")
    
    async def generate_report(self, date: datetime = None) -> Dict[str, Any]:
        """
        生成指定日期的日报
        
        Args:
            date: 日期 (默认昨天)
            
        Returns:
            完整日报数据
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        date_str = date.strftime("%Y-%m-%d")
        logger.info(f"开始生成 {date_str} 日报...")
        
        # 0. 先从飞书采集消息 (维度1的数据来源)
        collector = get_message_collector()
        if collector:
            try:
                # 获取已配置的群聊列表
                chat_ids = await collector.get_configured_chat_ids()
                logger.info(f"采集 {len(chat_ids)} 个群聊的消息...")
                
                # 采集消息 (内部会去重)
                for chat_id in chat_ids:
                    try:
                        result = await collector.collect_chat_messages(
                            chat_id, 
                            since=date.replace(hour=0, minute=0, second=0, microsecond=0)
                        )
                        logger.info(f"群聊 {chat_id[-8:]} 采集完成: 新增 {result.get('inserted', 0)} 条")
                    except Exception as e:
                        logger.warning(f"群聊 {chat_id[-8:]} 采集失败: {e}")
            except Exception as e:
                logger.error(f"消息采集失败: {e}")
        
        # 1. 生成聊天汇总 (维度1) - 基于已采集的消息
        chat_summary = await generate_chat_summary(date)
        
        # 2. 项目状态 (维度2) - TODO
        project_summary = await self._get_project_summary(date)
        
        # 3. 邮件摘要 (维度3) - TODO
        email_summary = await self._get_email_summary(date)
        
        # 4. 审批动态 (维度4) - TODO
        approval_summary = await self._get_approval_summary(date)
        
        # 5. 人员管理 (维度5) - TODO
        people_summary = await self._get_people_summary(date, chat_summary)
        
        # 构建完整日报
        report = {
            "date": date_str,
            "created_at": datetime.now(),
            "dimensions": {
                "chat": chat_summary,
                "project": project_summary,
                "email": email_summary,
                "approval": approval_summary,
                "people": people_summary
            },
            "overview": self._generate_overview(
                chat_summary, project_summary, email_summary,
                approval_summary, people_summary
            )
        }
        
        # 存储到 MongoDB (upsert)
        await self.collection.update_one(
            {"date": date_str},
            {"$set": report},
            upsert=True
        )
        
        logger.info(f"✅ {date_str} 日报生成完成")
        return report
    
    async def get_report(self, date: str) -> Optional[Dict]:
        """
        获取指定日期的日报
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
        """
        report = await self.collection.find_one({"date": date})
        if report:
            report["_id"] = str(report["_id"])
        return report
    
    async def get_latest_reports(self, limit: int = 7) -> List[Dict]:
        """获取最近几天的日报"""
        cursor = self.collection.find().sort("date", DESCENDING).limit(limit)
        reports = await cursor.to_list(length=limit)
        for r in reports:
            r["_id"] = str(r["_id"])
        return reports
    
    async def get_report_summary(self, date: str) -> Optional[Dict]:
        """
        获取日报摘要 (用于日报列表/概览页面)
        
        只返回精简信息，不包含详细内容
        """
        report = await self.get_report(date)
        if not report:
            return None
        
        return {
            "date": report["date"],
            "overview": report.get("overview", {}),
            "created_at": report.get("created_at")
        }
    
    async def get_chat_detail(self, date: str) -> Optional[Dict]:
        """
        获取聊天详情 (用于聊天详情页面)
        
        返回完整的聊天分析数据
        """
        report = await self.get_report(date)
        if not report:
            return None
        
        return report.get("dimensions", {}).get("chat", {})
    
    def _generate_overview(
        self,
        chat: Dict,
        project: Dict,
        email: Dict,
        approval: Dict,
        people: Dict
    ) -> Dict:
        """生成概览数据"""
        chat_totals = chat.get("totals", {})
        
        return {
            "chat": {
                "total_messages": chat_totals.get("total_messages", 0),
                "total_decisions": chat_totals.get("total_decisions", 0),
                "total_action_items": chat_totals.get("total_action_items", 0),
                "total_risks": chat_totals.get("total_risks", 0),
                "chat_count": len(chat.get("chats", []))
            },
            "project": {
                "in_progress": project.get("in_progress", 0),
                "blocked": project.get("blocked", 0),
                "completed": project.get("completed", 0)
            },
            "email": {
                "total": email.get("total", 0),
                "important": email.get("important", 0)
            },
            "approval": {
                "pending": approval.get("pending", 0),
                "approved": approval.get("approved", 0)
            },
            "people": {
                "active_count": people.get("active_count", 0),
                "total_count": people.get("total_count", 0)
            }
        }
    
    async def _get_project_summary(self, date: datetime) -> Dict:
        """获取项目状态 (TODO: 接入飞书任务)"""
        # 暂时返回模拟数据
        return {
            "in_progress": 0,
            "blocked": 0,
            "completed": 0,
            "tasks": []
        }
    
    async def _get_email_summary(self, date: datetime) -> Dict:
        """获取邮件摘要 (MS365 Outlook)"""
        try:
            from services.email_summarizer import generate_email_summary
            return await generate_email_summary(date)
        except Exception as e:
            logger.error(f"邮件摘要生成失败: {e}")
            return {
                "total": 0,
                "received": 0,
                "sent": 0,
                "important": 0,
                "external_count": 0,
                "top_contacts": [],
                "important_emails": []
            }
    
    async def _get_approval_summary(self, date: datetime) -> Dict:
        """获取审批动态 (TODO: 接入飞书审批)"""
        return {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "approvals": []
        }
    
    async def _get_people_summary(self, date: datetime, chat_data: Dict) -> Dict:
        """
        生成人员活跃度数据
        
        基于聊天记录分析每个员工的活跃情况
        """
        # 从聊天数据中提取发送者统计
        sender_stats = {}
        
        for chat in chat_data.get("chats", []):
            # TODO: 需要从原始消息中提取发送者信息
            # 目前 chat_summary 中没有保留原始发送者数据
            pass
        
        return {
            "active_count": len(sender_stats),
            "total_count": 0,  # TODO: 从通讯录获取
            "members": []
        }


# ===== 便捷函数 =====

_service = None

def get_daily_report_service() -> DailyReportService:
    """获取日报服务实例"""
    global _service
    if _service is None:
        _service = DailyReportService()
    return _service


async def generate_daily_report(date: datetime = None) -> Dict:
    """生成日报 (便捷函数)"""
    service = get_daily_report_service()
    return await service.generate_report(date)
