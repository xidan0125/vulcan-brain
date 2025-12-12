"""
Email Intelligence V2.0 - Pipeline Service
邮件处理流水线服务

Pipeline 阶段:
1. AI 提取 (Master Extractor)
2. 实体解析 (Entity Resolver)
3. 业务对象更新 (TODO: 各业务处理器)
4. 事件/行动项创建

设计原则:
- 宁慢勿错
- 断点续传
- 完整审计
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ..models import (
    EmailEvent,
    EmailEventType,
    Classification,
    ExtractedEntity,
    ExtractedEntityType,
    ActionType,
    AffectedObject,
)
from ..extractors.master_extractor import MasterExtractor, ExtractionResult, BatchExtractor
from ..extractors.entity_resolver import EntityResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Pipeline 运行统计"""
    total_emails: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    entities_extracted: int = 0
    entities_resolved: int = 0
    action_items_created: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    @property
    def emails_per_minute(self) -> float:
        if self.duration_seconds > 0:
            return (self.processed / self.duration_seconds) * 60
        return 0

    def to_dict(self) -> Dict:
        return {
            "total_emails": self.total_emails,
            "processed": self.processed,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "entities_extracted": self.entities_extracted,
            "entities_resolved": self.entities_resolved,
            "action_items_created": self.action_items_created,
            "duration_seconds": self.duration_seconds,
            "emails_per_minute": round(self.emails_per_minute, 2),
        }


@dataclass
class PipelineConfig:
    """Pipeline 配置"""
    # vLLM 配置
    vllm_host: str = "http://localhost:30000"
    vllm_model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

    # 批处理配置
    batch_size: int = 10
    concurrency: int = 1  # 串行处理保证质量
    delay_between: float = 0.5

    # 处理策略
    skip_already_processed: bool = True
    save_raw_response: bool = True  # 保存原始响应供调试

    # Entity Resolution 配置
    auto_merge_threshold: float = 0.80
    queue_for_review_threshold: float = 0.60


class EmailPipeline:
    """
    邮件处理流水线

    用法:
        pipeline = EmailPipeline(db)
        stats = await pipeline.run(limit=100)
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        config: Optional[PipelineConfig] = None,
    ):
        self.db = db
        self.config = config or PipelineConfig()

        # 初始化组件
        self.extractor = MasterExtractor(
            vllm_host=self.config.vllm_host,
            model=self.config.vllm_model,
        )
        self.batch_extractor = BatchExtractor(
            extractor=self.extractor,
            concurrency=self.config.concurrency,
            delay_between=self.config.delay_between,
        )
        self.resolver = EntityResolver(db)

        self.stats = PipelineStats()

    async def run(
        self,
        limit: int = 100,
        filter_query: Optional[Dict] = None,
        progress_callback: Optional[Callable] = None,
    ) -> PipelineStats:
        """
        运行 Pipeline

        Args:
            limit: 最多处理多少封邮件
            filter_query: 额外的筛选条件
            progress_callback: 进度回调 (current, total, email_id, status)

        Returns:
            PipelineStats: 运行统计
        """
        self.stats = PipelineStats(start_time=datetime.utcnow())

        try:
            # 1. 获取待处理邮件
            emails = await self._get_emails_to_process(limit, filter_query)
            self.stats.total_emails = len(emails)

            if not emails:
                logger.info("没有待处理的邮件")
                return self.stats

            logger.info(f"开始处理 {len(emails)} 封邮件...")

            # 2. 逐封处理 (不用批量，保证可控)
            for i, email in enumerate(emails):
                email_id = str(email["_id"])

                try:
                    await self._process_single_email(email)
                    self.stats.success += 1
                except Exception as e:
                    logger.error(f"处理失败 [{email_id}]: {e}")
                    self.stats.failed += 1
                    # 记录错误
                    await self._mark_email_processed(email_id, error=str(e))

                self.stats.processed += 1

                if progress_callback:
                    progress_callback(
                        i + 1, len(emails), email_id,
                        "success" if self.stats.failed == 0 else "failed"
                    )

                # 间隔
                if self.config.delay_between > 0:
                    await asyncio.sleep(self.config.delay_between)

        finally:
            self.stats.end_time = datetime.utcnow()

        logger.info(f"Pipeline 完成: {self.stats.to_dict()}")
        return self.stats

    async def _get_emails_to_process(
        self,
        limit: int,
        filter_query: Optional[Dict] = None,
    ) -> List[Dict]:
        """获取待处理邮件"""
        query = {"body_clean": {"$exists": True, "$ne": ""}}

        # 跳过已处理的
        if self.config.skip_already_processed:
            query["processing_status.v2_extracted"] = {"$ne": True}

        # 合并额外筛选条件
        if filter_query:
            query.update(filter_query)

        cursor = self.db.emails.find(query).sort("date", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def _process_single_email(self, email: Dict) -> None:
        """处理单封邮件"""
        email_id = str(email["_id"])
        logger.info(f"处理邮件: {email_id} - {email.get('subject', '')[:50]}...")

        # Stage 1: AI 提取
        extraction = await self.extractor.extract(
            email_id=email_id,
            subject=email.get("subject", ""),
            body=email.get("body_clean", "") or email.get("body", ""),
            sender=email.get("from_address", ""),
            email_date=email.get("date", datetime.utcnow()),
        )

        if not extraction.success:
            raise Exception(f"AI 提取失败: {extraction.error}")

        self.stats.entities_extracted += len(extraction.entities)

        # Stage 2: Entity Resolution (仅处理 COMPANY 类型)
        resolved_entities = []
        for entity in extraction.entities:
            if entity.entity_type == ExtractedEntityType.COMPANY:
                # 解析公司实体
                match_result = await self.resolver.resolve_company(
                    name=entity.value,
                    domain=self._extract_domain_from_email(email.get("from_address", "")),
                )
                if match_result and match_result.matched_party_id:
                    entity.matched_party_id = str(match_result.matched_party_id)
                    self.stats.entities_resolved += 1

            resolved_entities.append(entity)

        # Stage 3: 创建 EmailEvent
        event = await self._create_email_event(email, extraction, resolved_entities)

        # Stage 4: 更新邮件处理状态
        await self._update_email_with_extraction(email_id, extraction, event)

        # Stage 5: 创建 Action Items (如果有)
        if extraction.action_items:
            await self._create_action_items(email, extraction)

        logger.info(f"  ✓ 意图: {extraction.classification.intent}, 实体: {len(resolved_entities)}")

    async def _create_email_event(
        self,
        email: Dict,
        extraction: ExtractionResult,
        resolved_entities: List[ExtractedEntity],
    ) -> EmailEvent:
        """创建邮件事件记录"""
        event = EmailEvent(
            email_id=str(email["_id"]),
            email_subject=email.get("subject"),
            email_date=email.get("date"),
            email_from=email.get("from_address"),
            classification=extraction.classification,
            extracted_entities=resolved_entities,
            processed=True,
        )

        # 准备插入的文档，移除 None 的 _id
        event_dict = event.dict(by_alias=True, exclude_none=True)
        if "_id" in event_dict and event_dict["_id"] is None:
            del event_dict["_id"]

        # 插入数据库
        result = await self.db.email_events.insert_one(event_dict)
        event.id = result.inserted_id

        return event

    async def _update_email_with_extraction(
        self,
        email_id: str,
        extraction: ExtractionResult,
        event: EmailEvent,
    ) -> None:
        """更新邮件文档，添加提取结果"""
        update_data = {
            "processing_status": {
                "v2_extracted": True,
                "v2_extracted_at": datetime.utcnow(),
                "v2_event_id": str(event.id) if event.id else None,
            },
            "ai_extracted": {
                "version": "2.0",
                "model": self.config.vllm_model,
                "extracted_at": datetime.utcnow(),
                "intent": {
                    "primary": extraction.classification.intent.value if hasattr(extraction.classification.intent, 'value') else str(extraction.classification.intent),
                    "sub_intent": extraction.classification.sub_intent,
                    "confidence": extraction.classification.confidence,
                },
                "summary": extraction.summary,
                "entities": [
                    {
                        "type": e.entity_type.value if hasattr(e.entity_type, 'value') else str(e.entity_type),
                        "value": e.value,
                        "normalized": e.normalized_value,
                        "confidence": e.confidence,
                        "matched_party_id": e.matched_party_id,
                        "context": e.context,
                    }
                    for e in extraction.entities
                ],
                "action_items": extraction.action_items,
            },
        }

        # 可选保存原始响应
        if self.config.save_raw_response and extraction.raw_response:
            update_data["ai_extracted"]["raw_response"] = extraction.raw_response[:5000]  # 截断

        await self.db.emails.update_one(
            {"_id": ObjectId(email_id)},
            {"$set": update_data}
        )

    async def _mark_email_processed(self, email_id: str, error: str) -> None:
        """标记邮件处理失败"""
        await self.db.emails.update_one(
            {"_id": ObjectId(email_id)},
            {"$set": {
                "processing_status.v2_extracted": False,
                "processing_status.v2_error": error,
                "processing_status.v2_attempted_at": datetime.utcnow(),
            }}
        )

    async def _create_action_items(
        self,
        email: Dict,
        extraction: ExtractionResult,
    ) -> None:
        """创建行动项"""
        for item in extraction.action_items:
            action_doc = {
                "type": "EMAIL_FOLLOW_UP",
                "priority": item.get("urgency", "MEDIUM"),
                "status": "OPEN",
                "title": item.get("action", "")[:100],
                "description": item.get("action", ""),
                "context": {
                    "trigger_type": "EMAIL_RECEIVED",
                    "source_email_id": str(email["_id"]),
                    "source_email_subject": email.get("subject"),
                },
                "assignment": {
                    "assignee_hint": item.get("assignee_hint"),
                    "deadline_hint": item.get("deadline_hint"),
                },
                "scoring": {
                    "base_score": 50,
                    "urgency_bonus": 30 if item.get("urgency") == "HIGH" else 10,
                    "total_score": 60 if item.get("urgency") == "HIGH" else 60,
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            await self.db.action_items.insert_one(action_doc)
            self.stats.action_items_created += 1

    def _extract_domain_from_email(self, email_address: str) -> Optional[str]:
        """从邮箱地址提取域名"""
        if not email_address:
            return None
        if "@" in email_address:
            return email_address.split("@")[-1].lower()
        return None


async def run_pipeline(
    db: AsyncIOMotorDatabase,
    limit: int = 100,
    filter_query: Optional[Dict] = None,
    vllm_host: str = "http://localhost:30000",
) -> PipelineStats:
    """
    便捷函数：运行 Pipeline

    Args:
        db: MongoDB 数据库连接
        limit: 最多处理邮件数
        filter_query: 筛选条件
        vllm_host: vLLM 服务地址

    Returns:
        PipelineStats: 运行统计
    """
    config = PipelineConfig(vllm_host=vllm_host)
    pipeline = EmailPipeline(db, config)

    def progress(current, total, email_id, status):
        logger.info(f"  [{current}/{total}] {email_id} - {status}")

    return await pipeline.run(
        limit=limit,
        filter_query=filter_query,
        progress_callback=progress,
    )


# CLI 入口
async def main():
    """命令行入口"""
    import argparse
    from motor.motor_asyncio import AsyncIOMotorClient

    parser = argparse.ArgumentParser(description="Email Intelligence V2.0 Pipeline")
    parser.add_argument("--limit", type=int, default=10, help="处理邮件数量")
    parser.add_argument("--vllm", default="http://localhost:30000", help="vLLM 服务地址")
    parser.add_argument("--domain", help="只处理指定域名的邮件")
    parser.add_argument("--intent", help="只处理指定意图的邮件 (重处理)")
    args = parser.parse_args()

    # 连接数据库
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain

    # 构建筛选条件
    filter_query = {}
    if args.domain:
        filter_query["from_address"] = {"$regex": f"@{args.domain}$", "$options": "i"}

    # 运行
    stats = await run_pipeline(
        db=db,
        limit=args.limit,
        filter_query=filter_query,
        vllm_host=args.vllm,
    )

    print(f"\n=== Pipeline 完成 ===")
    print(f"处理: {stats.processed}/{stats.total_emails}")
    print(f"成功: {stats.success}")
    print(f"失败: {stats.failed}")
    print(f"提取实体: {stats.entities_extracted}")
    print(f"解析实体: {stats.entities_resolved}")
    print(f"行动项: {stats.action_items_created}")
    print(f"耗时: {stats.duration_seconds:.1f}秒")
    print(f"速度: {stats.emails_per_minute:.1f} 封/分钟")


if __name__ == "__main__":
    asyncio.run(main())
