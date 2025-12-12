"""
Email Intelligence V2.0 - Entity Resolution Runner
迁移后执行实体去重 (三级匹配策略)

架构师注解 2025-12-11:
- L1 强规则: 域名/税号精确匹配 → 自动合并
- L2 模糊匹配: Levenshtein + Token 重叠 → 人工审核队列
- L3 语义匹配: Embedding (可选) → 人工审核队列
- 阈值: >= 0.98 自动合并, 0.75-0.98 人工审核, < 0.75 视为新实体

Usage:
    python -m services.email_intelligence_v2.migration.run_entity_resolution [--dry-run] [--party-type COMPANY]
"""
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# 导入依赖
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.name_normalizer import get_normalizer
from extractors.entity_resolver import EntityResolver, MatchLevel

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ResolutionStats:
    """解析统计"""
    def __init__(self):
        self.total_parties = 0
        self.already_alias = 0      # 已经是 alias 的跳过
        self.auto_merged = 0        # 自动合并 (>= 0.98)
        self.queued_for_review = 0  # 进入人工审核队列 (0.75-0.98)
        self.no_match = 0           # 无匹配，保持为新实体 (< 0.75)
        self.errors = []
        self.start_time = datetime.utcnow()

    def summary(self) -> str:
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return f"""
=== Entity Resolution Summary ===
Duration: {elapsed:.1f} seconds

Total Parties: {self.total_parties}
  - Already Alias (skipped): {self.already_alias}
  - Auto-Merged (>= 0.98): {self.auto_merged}
  - Queued for Review (0.75-0.98): {self.queued_for_review}
  - No Match (< 0.75): {self.no_match}

Errors: {len(self.errors)}
"""


class EntityResolutionRunner:
    """
    实体解析执行器

    处理流程:
    1. 遍历所有 canonical parties
    2. 对每个 party 执行三级匹配
    3. 高置信度 (>= 0.98) → 自动合并
    4. 中置信度 (0.75-0.98) → 进入审核队列
    5. 低置信度 (< 0.75) → 保持为新实体
    """

    THRESHOLD_AUTO_MERGE = 0.98
    THRESHOLD_MANUAL_REVIEW = 0.75

    def __init__(self, db: AsyncIOMotorDatabase, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.normalizer = get_normalizer()
        self.stats = ResolutionStats()

    async def run(self, party_type: Optional[str] = None, batch_size: int = 50):
        """执行 Entity Resolution"""
        logger.info(f"Starting Entity Resolution (dry_run={self.dry_run})")

        # 构建查询条件
        query = {
            "entity_resolution.is_canonical": True,  # 只处理 canonical 记录
            "entity_resolution.resolution_status": "CANONICAL",
        }
        if party_type:
            query["party_type"] = party_type.upper()

        # 获取总数
        total = await self.db.parties.count_documents(query)
        self.stats.total_parties = total
        logger.info(f"Found {total} canonical parties to process")

        if total == 0:
            return self.stats

        # 分批处理
        processed = 0
        cursor = self.db.parties.find(query).sort("created_at", 1)

        batch = []
        async for party in cursor:
            batch.append(party)
            if len(batch) >= batch_size:
                await self._process_batch(batch)
                processed += len(batch)
                logger.info(f"Progress: {processed}/{total} ({100*processed/total:.1f}%)")
                batch = []

        # 处理剩余
        if batch:
            await self._process_batch(batch)
            processed += len(batch)
            logger.info(f"Progress: {processed}/{total} (100%)")

        logger.info(self.stats.summary())
        return self.stats

    async def _process_batch(self, batch: List[Dict]):
        """处理一批 parties"""
        for party in batch:
            try:
                await self._resolve_party(party)
            except Exception as e:
                self.stats.errors.append(f"Party {party.get('_id')}: {e}")
                logger.error(f"Error resolving party {party.get('_id')}: {e}")

    async def _resolve_party(self, party: Dict):
        """解析单个 party"""
        party_id = str(party["_id"])
        party_type = party["party_type"]
        name = party["display_name"]
        domain = party.get("identifiers", {}).get("domain")
        email = party.get("person_info", {}).get("email") if party_type == "PERSON" else None

        # 跳过已经是 alias 的记录
        if not party.get("entity_resolution", {}).get("is_canonical", True):
            self.stats.already_alias += 1
            return

        # 查找潜在匹配 (排除自己)
        candidates = await self._find_candidates(party)

        if not candidates:
            self.stats.no_match += 1
            return

        # 对每个候选执行匹配
        best_match = None
        best_confidence = 0.0

        for candidate in candidates:
            confidence, match_details = await self._calculate_match_confidence(party, candidate)

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = (candidate, confidence, match_details)

        if not best_match:
            self.stats.no_match += 1
            return

        candidate, confidence, match_details = best_match

        # 根据置信度决定操作
        if confidence >= self.THRESHOLD_AUTO_MERGE:
            # 自动合并
            await self._auto_merge(party, candidate, confidence, match_details)
            self.stats.auto_merged += 1

        elif confidence >= self.THRESHOLD_MANUAL_REVIEW:
            # 进入人工审核队列
            await self._queue_for_review(party, candidate, confidence, match_details)
            self.stats.queued_for_review += 1

        else:
            # 置信度太低，视为新实体
            self.stats.no_match += 1

    async def _find_candidates(self, party: Dict) -> List[Dict]:
        """查找潜在匹配的候选"""
        party_id = party["_id"]
        party_type = party["party_type"]
        name = party.get("canonical_name", "")
        domain = party.get("identifiers", {}).get("domain")

        # 构建查询条件
        # 1. 同类型
        # 2. 是 canonical
        # 3. 不是自己
        # 4. 名称或域名有重叠
        query = {
            "_id": {"$ne": party_id},
            "party_type": party_type,
            "entity_resolution.is_canonical": True,
        }

        # 添加候选过滤条件 (OR)
        or_conditions = []

        # 条件1: 域名匹配
        if domain:
            or_conditions.append({"identifiers.domain": domain})

        # 条件2: 名称在 aliases 中
        if name:
            or_conditions.append({"aliases": {"$regex": name[:4], "$options": "i"}})

        # 条件3: canonical_name 相似
        if name:
            # 取名称前缀匹配 (简单优化，避免全表扫描)
            name_prefix = name[:3].lower() if len(name) >= 3 else name.lower()
            or_conditions.append({"canonical_name": {"$regex": f"^{name_prefix}", "$options": "i"}})

        if not or_conditions:
            return []

        query["$or"] = or_conditions

        # 限制候选数量
        cursor = self.db.parties.find(query).limit(20)
        return await cursor.to_list(length=20)

    async def _calculate_match_confidence(
        self, party: Dict, candidate: Dict
    ) -> Tuple[float, Dict]:
        """计算两个 party 的匹配置信度"""
        details = {
            "domain_match": False,
            "name_similarity": 0.0,
            "token_overlap": 0.0,
            "match_level": None,
        }

        confidence = 0.0

        # L1: 域名精确匹配
        party_domain = party.get("identifiers", {}).get("domain")
        candidate_domain = candidate.get("identifiers", {}).get("domain")

        if party_domain and candidate_domain and party_domain.lower() == candidate_domain.lower():
            details["domain_match"] = True
            confidence = max(confidence, 0.95)  # 域名匹配给 0.95 基础分
            details["match_level"] = "L1_DOMAIN"

        # L1: 税号精确匹配
        party_tax = party.get("identifiers", {}).get("tax_id")
        candidate_tax = candidate.get("identifiers", {}).get("tax_id")

        if party_tax and candidate_tax and party_tax == candidate_tax:
            confidence = 1.0  # 税号匹配直接 1.0
            details["match_level"] = "L1_TAX_ID"
            return confidence, details

        # L2: 模糊文本匹配
        party_name = party.get("canonical_name", "").lower()
        candidate_name = candidate.get("canonical_name", "").lower()

        if party_name and candidate_name:
            # Levenshtein 相似度
            from difflib import SequenceMatcher
            name_sim = SequenceMatcher(None, party_name, candidate_name).ratio()
            details["name_similarity"] = name_sim

            # Token 重叠率
            party_tokens = set(party_name.split())
            candidate_tokens = set(candidate_name.split())
            if party_tokens and candidate_tokens:
                overlap = len(party_tokens & candidate_tokens)
                total = len(party_tokens | candidate_tokens)
                token_overlap = overlap / total if total > 0 else 0
                details["token_overlap"] = token_overlap
            else:
                token_overlap = 0

            # L2 置信度 = 加权平均
            l2_confidence = 0.6 * name_sim + 0.4 * token_overlap

            # 如果域名也匹配，提升置信度
            if details["domain_match"]:
                l2_confidence = min(1.0, l2_confidence + 0.15)

            if l2_confidence > confidence:
                confidence = l2_confidence
                details["match_level"] = "L2_FUZZY"

        return confidence, details

    async def _auto_merge(
        self, source: Dict, target: Dict, confidence: float, details: Dict
    ):
        """自动合并 (source 变成 target 的 alias)"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would merge {source['display_name']} → {target['display_name']} (confidence={confidence:.2f})")
            return

        now = datetime.utcnow()
        source_id = source["_id"]
        target_id = target["_id"]

        # 1. 更新 source 为 alias
        await self.db.parties.update_one(
            {"_id": source_id},
            {
                "$set": {
                    "entity_resolution.canonical_id": target_id,
                    "entity_resolution.is_canonical": False,
                    "entity_resolution.resolution_status": "ALIAS",
                    "updated_at": now,
                },
                "$push": {
                    "entity_resolution.merge_history": {
                        "action": "AUTO_MERGED_TO",
                        "target_id": str(target_id),
                        "confidence": confidence,
                        "details": details,
                        "timestamp": now,
                    }
                }
            }
        )

        # 2. 更新 target 的别名列表
        source_aliases = source.get("aliases", [])
        await self.db.parties.update_one(
            {"_id": target_id},
            {
                "$addToSet": {"aliases": {"$each": source_aliases}},
                "$set": {"updated_at": now},
                "$push": {
                    "entity_resolution.merge_history": {
                        "action": "AUTO_MERGED_FROM",
                        "source_id": str(source_id),
                        "confidence": confidence,
                        "details": details,
                        "timestamp": now,
                    }
                }
            }
        )

        logger.info(f"Auto-merged: {source['display_name']} → {target['display_name']} (confidence={confidence:.2f})")

    async def _queue_for_review(
        self, source: Dict, target: Dict, confidence: float, details: Dict
    ):
        """进入人工审核队列"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would queue for review: {source['display_name']} ↔ {target['display_name']} (confidence={confidence:.2f})")
            return

        now = datetime.utcnow()

        # 检查是否已在队列中
        existing = await self.db.entity_merge_queue.find_one({
            "merge_suggestion.source_party_id": str(source["_id"]),
            "merge_suggestion.target_party_id": str(target["_id"]),
            "status": "PENDING",
        })
        if existing:
            logger.debug(f"Already in queue: {source['display_name']} ↔ {target['display_name']}")
            return

        # 创建审核队列记录
        queue_item = {
            "_id": ObjectId(),
            "status": "PENDING",

            "merge_suggestion": {
                "source_party_id": str(source["_id"]),
                "source_name": source["display_name"],
                "source_aliases": source.get("aliases", []),
                "source_domain": source.get("identifiers", {}).get("domain"),
                "target_party_id": str(target["_id"]),
                "target_name": target["display_name"],
                "target_aliases": target.get("aliases", []),
                "target_domain": target.get("identifiers", {}).get("domain"),
            },

            "match_evidence": {
                "match_type": details.get("match_level", "FUZZY"),
                "confidence": confidence,
                "details": {
                    "domain_match": details.get("domain_match", False),
                    "name_similarity": details.get("name_similarity", 0),
                    "token_overlap": details.get("token_overlap", 0),
                    "ai_reasoning": None,
                },
                "common_emails": [],
            },

            "risk_assessment": {
                "impact_level": "LOW",  # 默认低影响，可后续计算
                "affected_fulfillments": 0,
                "affected_shipments": 0,
                "affected_finance_docs": 0,
                "affected_compliance_docs": 0,
                "warning": None,
            },

            "review": {
                "reviewed_by": None,
                "reviewed_at": None,
                "decision": None,
                "rejection_reason": None,
                "notes": None,
            },

            "auto_processing": {
                "eligible_for_auto_merge": False,
                "auto_merge_blocked_reason": f"置信度 {confidence:.2f} 在 0.75-0.98 区间，需人工审核",
                "scheduled_auto_reject_at": datetime(now.year, now.month + 1, now.day) if now.month < 12 else datetime(now.year + 1, 1, now.day),
            },

            "created_at": now,
            "updated_at": now,
        }

        await self.db.entity_merge_queue.insert_one(queue_item)

        # 更新 source 状态为 PENDING_REVIEW
        await self.db.parties.update_one(
            {"_id": source["_id"]},
            {
                "$set": {
                    "entity_resolution.resolution_status": "PENDING_REVIEW",
                    "updated_at": now,
                }
            }
        )

        logger.info(f"Queued for review: {source['display_name']} ↔ {target['display_name']} (confidence={confidence:.2f})")


async def main(
    mongo_uri: str,
    db_name: str,
    dry_run: bool = False,
    party_type: Optional[str] = None,
    batch_size: int = 50
):
    """主函数"""
    logger.info(f"Connecting to MongoDB: {mongo_uri}")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    try:
        # 测试连接
        await client.admin.command('ping')
        logger.info("MongoDB connection successful")

        # 检查集合
        collections = await db.list_collection_names()
        if "parties" not in collections:
            logger.error("Collection 'parties' not found. Run schema_init.py and migrate_to_v2.py first!")
            return
        if "entity_merge_queue" not in collections:
            logger.error("Collection 'entity_merge_queue' not found. Run schema_init.py first!")
            return

        # 执行 Entity Resolution
        runner = EntityResolutionRunner(db, dry_run=dry_run)
        stats = await runner.run(party_type=party_type, batch_size=batch_size)

        if dry_run:
            logger.info("\n[DRY RUN] No data was actually modified.")
        else:
            logger.info("\n✓ Entity Resolution completed successfully!")

    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Entity Resolution on V2.0 data")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db-name", default="vulcan_brain", help="Database name")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--party-type", choices=["COMPANY", "PERSON"], help="Only process this party type")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")

    args = parser.parse_args()

    asyncio.run(main(
        args.mongo_uri,
        args.db_name,
        args.dry_run,
        args.party_type,
        args.batch_size
    ))
