"""
Email Intelligence V2.0 - Schema Initialization Script
创建 9 个集合和所有索引

Usage:
    python -m services.email_intelligence_v2.migration.schema_init [--drop-existing]
"""
import asyncio
import argparse
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 集合定义
COLLECTIONS = [
    "parties",
    "products",
    "fulfillments",
    "shipments",
    "finance_docs",
    "compliance_docs",
    "email_events",
    "action_items",
    "entity_merge_queue",
]

# 索引定义 (从 models 导入)
INDEXES = {
    "parties": [
        {"keys": [("party_type", 1), ("canonical_name", 1)], "unique": True},
        {"keys": [("aliases", 1)]},
        {"keys": [("domain", 1)]},
        {"keys": [("company_info.relationship", 1)]},
        {"keys": [("company_info.tier", 1)]},
        {"keys": [("person_info.email", 1)]},
        {"keys": [("person_info.belongs_to_company", 1)]},
        {"keys": [("health.score", -1)]},
        {"keys": [("entity_resolution.canonical_id", 1)]},
        {"keys": [("entity_resolution.is_canonical", 1)]},
        {"keys": [("entity_resolution.resolution_status", 1)]},
    ],
    "products": [
        {"keys": [("sku_code", 1)], "unique": True},
        {"keys": [("canonical_name", 1)]},
        {"keys": [("aliases", 1)]},
        {"keys": [("specs.category", 1)]},
        {"keys": [("supply_chain.export_controlled", 1)]},
        {"keys": [("supply_chain.itar_controlled", 1)]},
    ],
    "fulfillments": [
        {"keys": [("client_po", 1)], "unique": True},
        {"keys": [("internal_so", 1)]},
        {"keys": [("current_status", 1)]},
        {"keys": [("current_stage", 1)]},
        {"keys": [("refs.customer_id", 1)]},
        {"keys": [("refs.customer_name", 1)]},
        {"keys": [("dates.target_delivery", 1)]},
        {"keys": [("dates.po_date", -1)]},
        {"keys": [("created_at", -1)]},
        {"keys": [("is_blocked", 1), ("current_status", 1)]},
    ],
    "shipments": [
        {"keys": [("tracking_number", 1)], "unique": True},
        {"keys": [("carrier", 1)]},
        {"keys": [("current_status", 1)]},
        {"keys": [("fulfillment_id", 1)]},
        {"keys": [("fulfillment_po", 1)]},
        {"keys": [("dates.eta", 1)]},
        {"keys": [("dates.booked_date", -1)]},
        {"keys": [("created_at", -1)]},
    ],
    "finance_docs": [
        {"keys": [("doc_type", 1), ("doc_number", 1)], "unique": True},
        {"keys": [("refs.party_id", 1)]},
        {"keys": [("refs.fulfillment_ids", 1)]},
        {"keys": [("payment_status", 1)]},
        {"keys": [("due_date", 1)]},
        {"keys": [("issue_date", -1)]},
        {"keys": [("created_at", -1)]},
        {"keys": [("payment_status", 1), ("due_date", 1)]},
    ],
    "compliance_docs": [
        {"keys": [("party_id", 1), ("doc_type", 1)]},
        {"keys": [("validity.expiry_date", 1)]},
        {"keys": [("validity.status", 1)]},
        {"keys": [("validity.days_until_expiry", 1)]},
        {"keys": [("doc_type", 1)]},
        {"keys": [("created_at", -1)]},
    ],
    "email_events": [
        {"keys": [("email_id", 1)], "unique": True},
        {"keys": [("classification.intent", 1)]},
        {"keys": [("email_date", -1)]},
        {"keys": [("affects.collection", 1), ("affects.object_id", 1)]},
        {"keys": [("processed", 1)]},
        {"keys": [("created_at", -1)]},
    ],
    "action_items": [
        {"keys": [("status", 1), ("scoring.total_score", -1)]},
        {"keys": [("item_type", 1), ("status", 1)]},
        {"keys": [("assignment.assignee", 1), ("status", 1)]},
        {"keys": [("assignment.due_date", 1)]},
        {"keys": [("context.source_email_id", 1)]},
        {"keys": [("priority", 1), ("status", 1)]},
        {"keys": [("created_at", -1)]},
    ],
    "entity_merge_queue": [
        {"keys": [("status", 1), ("created_at", -1)]},
        {"keys": [("merge_suggestion.source_party_id", 1)]},
        {"keys": [("merge_suggestion.target_party_id", 1)]},
        {"keys": [("match_evidence.confidence", -1)]},
        {"keys": [("auto_processing.scheduled_auto_reject_at", 1)]},
        {"keys": [("risk_assessment.impact_level", 1)]},
    ],
}


async def create_collections(db, drop_existing: bool = False):
    """创建集合"""
    existing = await db.list_collection_names()

    for collection_name in COLLECTIONS:
        if collection_name in existing:
            if drop_existing:
                logger.warning(f"Dropping existing collection: {collection_name}")
                await db.drop_collection(collection_name)
            else:
                logger.info(f"Collection already exists: {collection_name}")
                continue

        try:
            await db.create_collection(collection_name)
            logger.info(f"Created collection: {collection_name}")
        except CollectionInvalid:
            logger.info(f"Collection already exists: {collection_name}")


async def create_indexes(db):
    """创建索引"""
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]

        for index_def in indexes:
            keys = index_def["keys"]
            unique = index_def.get("unique", False)

            try:
                # 生成索引名称
                index_name = "_".join([f"{k}_{v}" for k, v in keys])

                await collection.create_index(
                    keys,
                    unique=unique,
                    name=index_name,
                    background=True
                )
                logger.info(f"Created index on {collection_name}: {index_name}")
            except Exception as e:
                logger.error(f"Failed to create index on {collection_name}: {e}")


async def verify_schema(db):
    """验证 Schema"""
    logger.info("\n=== Schema Verification ===")

    # 检查集合
    existing = await db.list_collection_names()
    for collection_name in COLLECTIONS:
        status = "✓" if collection_name in existing else "✗"
        logger.info(f"{status} Collection: {collection_name}")

    # 检查索引
    for collection_name in COLLECTIONS:
        collection = db[collection_name]
        indexes = await collection.index_information()
        logger.info(f"\n{collection_name} indexes ({len(indexes)}):")
        for idx_name, idx_info in indexes.items():
            logger.info(f"  - {idx_name}: {idx_info.get('key')}")


async def main(mongo_uri: str, db_name: str, drop_existing: bool = False):
    """主函数"""
    logger.info(f"Connecting to MongoDB: {mongo_uri}")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    try:
        # 测试连接
        await client.admin.command('ping')
        logger.info("MongoDB connection successful")

        # 创建集合
        logger.info("\n=== Creating Collections ===")
        await create_collections(db, drop_existing)

        # 创建索引
        logger.info("\n=== Creating Indexes ===")
        await create_indexes(db)

        # 验证
        await verify_schema(db)

        logger.info("\n=== Schema Initialization Complete ===")
        logger.info(f"Database: {db_name}")
        logger.info(f"Collections: {len(COLLECTIONS)}")
        logger.info(f"Total indexes: {sum(len(idx) for idx in INDEXES.values())}")

    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Email Intelligence V2.0 Schema")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db-name", default="vulcan_brain", help="Database name")
    parser.add_argument("--drop-existing", action="store_true", help="Drop existing collections")

    args = parser.parse_args()

    asyncio.run(main(args.mongo_uri, args.db_name, args.drop_existing))
