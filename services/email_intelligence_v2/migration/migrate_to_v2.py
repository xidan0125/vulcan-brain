"""
Email Intelligence V2.0 - Data Migration Script
将旧版 companies/contacts 迁移到新版 parties 集合

架构师注解 2025-12-11:
- 此脚本不使用 LLM，纯规则转换
- Entity Resolution (去重) 在迁移后单独执行
- 支持断点续传 (记录迁移进度)

Usage:
    python -m services.email_intelligence_v2.migration.migrate_to_v2 [--dry-run] [--batch-size 100]
"""
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# 导入名称标准化器
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.name_normalizer import get_normalizer, normalize_company_name

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MigrationStats:
    """迁移统计"""
    def __init__(self):
        self.companies_found = 0
        self.companies_migrated = 0
        self.companies_skipped = 0
        self.contacts_found = 0
        self.contacts_migrated = 0
        self.contacts_skipped = 0
        self.errors = []
        self.start_time = datetime.utcnow()

    def summary(self) -> str:
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return f"""
=== Migration Summary ===
Duration: {elapsed:.1f} seconds

Companies:
  - Found: {self.companies_found}
  - Migrated: {self.companies_migrated}
  - Skipped: {self.companies_skipped}

Contacts:
  - Found: {self.contacts_found}
  - Migrated: {self.contacts_migrated}
  - Skipped: {self.contacts_skipped}

Errors: {len(self.errors)}
"""


class DataMigrator:
    """
    数据迁移器

    迁移规则:
    1. companies → parties (type=COMPANY)
    2. contacts → parties (type=PERSON)
    3. 保留原始 _id 作为 migration_source.source_id
    4. 标准化名称 (name_normalizer)
    5. 跳过已迁移的记录 (幂等)
    """

    def __init__(self, db: AsyncIOMotorDatabase, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.normalizer = get_normalizer()
        self.stats = MigrationStats()

    async def migrate_all(self, batch_size: int = 100):
        """执行全部迁移"""
        logger.info(f"Starting migration (dry_run={self.dry_run}, batch_size={batch_size})")

        # 1. 迁移 companies → parties (COMPANY)
        await self.migrate_companies(batch_size)

        # 2. 迁移 contacts → parties (PERSON)
        await self.migrate_contacts(batch_size)

        # 3. 输出统计
        logger.info(self.stats.summary())

        # 4. 输出错误详情
        if self.stats.errors:
            logger.error("\n=== Errors ===")
            for err in self.stats.errors[:10]:  # 只显示前10个
                logger.error(f"  {err}")

        return self.stats

    async def migrate_companies(self, batch_size: int):
        """迁移 companies 集合"""
        logger.info("\n=== Migrating Companies → Parties (COMPANY) ===")

        # 检查源集合是否存在
        collections = await self.db.list_collection_names()
        if "companies" not in collections:
            logger.warning("Source collection 'companies' not found, skipping")
            return

        # 获取总数
        total = await self.db.companies.count_documents({})
        self.stats.companies_found = total
        logger.info(f"Found {total} companies to migrate")

        if total == 0:
            return

        # 分批处理
        processed = 0
        cursor = self.db.companies.find({})

        batch = []
        async for doc in cursor:
            batch.append(doc)
            if len(batch) >= batch_size:
                await self._process_company_batch(batch)
                processed += len(batch)
                logger.info(f"Progress: {processed}/{total} ({100*processed/total:.1f}%)")
                batch = []

        # 处理剩余
        if batch:
            await self._process_company_batch(batch)
            processed += len(batch)
            logger.info(f"Progress: {processed}/{total} (100%)")

    async def _process_company_batch(self, batch: List[Dict]):
        """处理一批 company 记录"""
        for company in batch:
            try:
                # 检查是否已迁移 (通过 source_id)
                existing_by_source = await self.db.parties.find_one({
                    "provenance.migration_source.source_id": str(company["_id"])
                })
                if existing_by_source:
                    self.stats.companies_skipped += 1
                    continue

                party = self._transform_company_to_party(company)
                if not party:
                    self.stats.companies_skipped += 1
                    continue

                # 检查是否已存在同名记录 (通过 canonical_name)
                # 如果存在，合并别名而不是创建新记录
                existing_by_name = await self.db.parties.find_one({
                    "party_type": "COMPANY",
                    "canonical_name": party["canonical_name"]
                })

                if existing_by_name:
                    # 合并到已有记录
                    if not self.dry_run:
                        await self.db.parties.update_one(
                            {"_id": existing_by_name["_id"]},
                            {
                                "$addToSet": {"aliases": {"$each": party["aliases"]}},
                                "$set": {"updated_at": datetime.utcnow()}
                            }
                        )
                    logger.debug(f"Merged duplicate: {party['display_name']} → {existing_by_name['display_name']}")
                    self.stats.companies_migrated += 1
                else:
                    # 插入新记录
                    if not self.dry_run:
                        await self.db.parties.insert_one(party)
                    self.stats.companies_migrated += 1

            except Exception as e:
                self.stats.errors.append(f"Company {company.get('_id')}: {e}")
                continue

        if self.dry_run:
            logger.info(f"[DRY RUN] Would process {len(batch)} companies")

    def _transform_company_to_party(self, company: Dict) -> Optional[Dict]:
        """将 company 转换为 party (COMPANY 类型)"""
        name = company.get("name", "").strip()
        if not name:
            return None

        # 标准化名称
        norm_result = self.normalizer.normalize(name)

        # 构建 party 文档
        now = datetime.utcnow()
        party = {
            "_id": ObjectId(),  # 新 ID
            "party_type": "COMPANY",
            "canonical_name": norm_result.normalized,
            "display_name": name,  # 保留原始显示名
            "aliases": list(set([name, norm_result.normalized])),  # 去重

            # 标识符
            "identifiers": {
                "domain": company.get("domain"),
                "tax_id": company.get("tax_id"),
                "duns": company.get("duns"),
            },

            # 公司信息
            "company_info": {
                "relationship": company.get("relationship", "UNKNOWN"),
                "tier": company.get("tier"),
                "industry": company.get("industry"),
                "country": company.get("country"),
                "employees": [],  # 稍后由 contacts 迁移填充
            },

            # 健康度 (默认值)
            "health": {
                "score": company.get("health_score", 50),
                "revenue_trend": "STABLE",
                "communication_frequency": "NORMAL",
                "last_activity": company.get("last_activity"),
                "concerns": [],
            },

            # Entity Resolution (初始状态)
            "entity_resolution": {
                "canonical_id": None,  # 指向自己
                "is_canonical": True,  # 默认是 canonical
                "merge_history": [],
                "resolution_status": "CANONICAL",  # 待 Entity Resolution 处理
            },

            # 数据血缘
            "provenance": {
                "first_seen_email_id": company.get("first_seen_email_id"),
                "last_seen_email_id": company.get("last_seen_email_id"),
                "total_interactions": company.get("email_count", 0),
                "migration_source": {
                    "collection": "companies",
                    "source_id": str(company["_id"]),
                    "migrated_at": now,
                },
            },

            # 时间戳
            "created_at": company.get("created_at", now),
            "updated_at": now,
        }

        # 清理 None 值
        party["identifiers"] = {k: v for k, v in party["identifiers"].items() if v}

        return party

    async def migrate_contacts(self, batch_size: int):
        """迁移 contacts 集合"""
        logger.info("\n=== Migrating Contacts → Parties (PERSON) ===")

        # 检查源集合是否存在
        collections = await self.db.list_collection_names()
        if "contacts" not in collections:
            logger.warning("Source collection 'contacts' not found, skipping")
            return

        # 获取总数
        total = await self.db.contacts.count_documents({})
        self.stats.contacts_found = total
        logger.info(f"Found {total} contacts to migrate")

        if total == 0:
            return

        # 分批处理
        processed = 0
        cursor = self.db.contacts.find({})

        batch = []
        async for doc in cursor:
            batch.append(doc)
            if len(batch) >= batch_size:
                await self._process_contact_batch(batch)
                processed += len(batch)
                logger.info(f"Progress: {processed}/{total} ({100*processed/total:.1f}%)")
                batch = []

        # 处理剩余
        if batch:
            await self._process_contact_batch(batch)
            processed += len(batch)
            logger.info(f"Progress: {processed}/{total} (100%)")

    async def _process_contact_batch(self, batch: List[Dict]):
        """处理一批 contact 记录"""
        for contact in batch:
            try:
                # 检查是否已迁移 (通过 source_id)
                existing_by_source = await self.db.parties.find_one({
                    "provenance.migration_source.source_id": str(contact["_id"])
                })
                if existing_by_source:
                    self.stats.contacts_skipped += 1
                    continue

                party = await self._transform_contact_to_party(contact)
                if not party:
                    self.stats.contacts_skipped += 1
                    continue

                # 检查是否已存在同名记录 (通过 canonical_name + party_type)
                existing_by_name = await self.db.parties.find_one({
                    "party_type": "PERSON",
                    "canonical_name": party["canonical_name"]
                })

                if existing_by_name:
                    # 合并到已有记录
                    if not self.dry_run:
                        await self.db.parties.update_one(
                            {"_id": existing_by_name["_id"]},
                            {
                                "$addToSet": {"aliases": {"$each": party["aliases"]}},
                                "$set": {"updated_at": datetime.utcnow()}
                            }
                        )
                    logger.debug(f"Merged duplicate contact: {party['display_name']}")
                    self.stats.contacts_migrated += 1
                else:
                    # 插入新记录
                    if not self.dry_run:
                        await self.db.parties.insert_one(party)
                    self.stats.contacts_migrated += 1

                    # 更新公司的 employees 列表
                    if party.get("person_info", {}).get("belongs_to_company") and not self.dry_run:
                        await self.db.parties.update_one(
                            {"_id": ObjectId(party["person_info"]["belongs_to_company"])},
                            {"$addToSet": {"company_info.employees": str(party["_id"])}}
                        )

            except Exception as e:
                self.stats.errors.append(f"Contact {contact.get('_id')}: {e}")
                continue

        if self.dry_run:
            logger.info(f"[DRY RUN] Would process {len(batch)} contacts")

    async def _transform_contact_to_party(self, contact: Dict) -> Optional[Dict]:
        """将 contact 转换为 party (PERSON 类型)"""
        name = contact.get("name", "").strip()
        email = contact.get("email", "").strip().lower()

        if not name and not email:
            return None

        # 标准化名称
        norm_result = self.normalizer.normalize(name) if name else None
        canonical_name = norm_result.normalized if norm_result else email.split("@")[0]

        # 查找关联的公司 (通过 company_id 或 domain)
        belongs_to_company = None
        if contact.get("company_id"):
            # 直接引用
            company = await self.db.parties.find_one({
                "provenance.migration_source.source_id": str(contact["company_id"])
            })
            if company:
                belongs_to_company = str(company["_id"])
        elif email and "@" in email:
            # 通过域名匹配
            domain = email.split("@")[1]
            company = await self.db.parties.find_one({
                "party_type": "COMPANY",
                "identifiers.domain": domain
            })
            if company:
                belongs_to_company = str(company["_id"])

        # 构建 party 文档
        now = datetime.utcnow()
        party = {
            "_id": ObjectId(),
            "party_type": "PERSON",
            "canonical_name": canonical_name,
            "display_name": name or email,
            "aliases": list(set(filter(None, [name, canonical_name, email]))),

            # 标识符
            "identifiers": {
                "domain": email.split("@")[1] if email and "@" in email else None,
            },

            # 个人信息
            "person_info": {
                "email": email,
                "phone": contact.get("phone"),
                "title": contact.get("title"),
                "department": contact.get("department"),
                "belongs_to_company": belongs_to_company,
                "is_decision_maker": contact.get("is_decision_maker", False),
                "timezone": contact.get("timezone"),
                "language_preference": contact.get("language", "en"),
            },

            # 健康度 (默认值)
            "health": {
                "score": contact.get("health_score", 50),
                "revenue_trend": "STABLE",
                "communication_frequency": "NORMAL",
                "last_activity": contact.get("last_activity"),
                "concerns": [],
            },

            # Entity Resolution (初始状态)
            "entity_resolution": {
                "canonical_id": None,
                "is_canonical": True,
                "merge_history": [],
                "resolution_status": "CANONICAL",
            },

            # 数据血缘
            "provenance": {
                "first_seen_email_id": contact.get("first_seen_email_id"),
                "last_seen_email_id": contact.get("last_seen_email_id"),
                "total_interactions": contact.get("email_count", 0),
                "migration_source": {
                    "collection": "contacts",
                    "source_id": str(contact["_id"]),
                    "migrated_at": now,
                },
            },

            # 时间戳
            "created_at": contact.get("created_at", now),
            "updated_at": now,
        }

        # 清理 None 值
        party["identifiers"] = {k: v for k, v in party["identifiers"].items() if v}
        party["person_info"] = {k: v for k, v in party["person_info"].items() if v is not None}

        return party


async def main(
    mongo_uri: str,
    db_name: str,
    dry_run: bool = False,
    batch_size: int = 100
):
    """主函数"""
    logger.info(f"Connecting to MongoDB: {mongo_uri}")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    try:
        # 测试连接
        await client.admin.command('ping')
        logger.info("MongoDB connection successful")

        # 确保目标集合存在
        collections = await db.list_collection_names()
        if "parties" not in collections:
            logger.error("Target collection 'parties' not found. Run schema_init.py first!")
            return

        # 执行迁移
        migrator = DataMigrator(db, dry_run=dry_run)
        stats = await migrator.migrate_all(batch_size)

        if dry_run:
            logger.info("\n[DRY RUN] No data was actually written.")
        else:
            logger.info("\n✓ Migration completed successfully!")

    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Email Intelligence data to V2.0")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db-name", default="vulcan_brain", help="Database name")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")

    args = parser.parse_args()

    asyncio.run(main(
        args.mongo_uri,
        args.db_name,
        args.dry_run,
        args.batch_size
    ))
