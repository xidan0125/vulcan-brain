"""
记忆系统数据迁移脚本 v3.0
- 迁移旧 memories 集合到 user_memories
- 清理 anonymous 数据
- 创建索引
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "vulcan_brain"


async def migrate():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("=" * 50)
    print("记忆系统数据迁移 v3.0")
    print("=" * 50)
    
    # ==================== 1. 迁移旧 memories ====================
    print("\n[1/4] 迁移旧 memories 集合...")
    
    old_memories = db.memories
    new_memories = db.user_memories
    
    old_count = await old_memories.count_documents({})
    print(f"  旧集合记录数: {old_count}")
    
    if old_count > 0:
        migrated = 0
        async for doc in old_memories.find({}):
            # 跳过已迁移的
            if doc.get("category") == "migrated":
                continue
                
            # 转换格式: content -> key-value
            content = doc.get("content", "")
            user_id = doc.get("user_id", "unknown")
            
            # 跳过 anonymous
            if user_id in ["anonymous", "unknown", ""]:
                continue
            
            # 生成 key (从 content 提取或使用时间戳)
            key = f"legacy_{doc['_id']}"
            
            new_doc = {
                "user_id": user_id,
                "key": key,
                "value": content,
                "category": "fact",
                "source": "migrated",
                "created_at": doc.get("created_at", datetime.now(timezone.utc)),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # 使用 upsert 避免重复
            await new_memories.update_one(
                {"user_id": user_id, "key": key},
                {"$setOnInsert": new_doc},
                upsert=True
            )
            migrated += 1
        
        print(f"  迁移完成: {migrated} 条")
    
    # ==================== 2. 清理 anonymous 数据 ====================
    print("\n[2/4] 清理 anonymous 数据...")
    
    # user_memories
    result = await new_memories.delete_many({"user_id": {"$in": ["anonymous", "", None]}})
    print(f"  user_memories 清理: {result.deleted_count} 条")
    
    # pending_memories
    pending = db.pending_memories
    result = await pending.delete_many({"user_id": {"$in": ["anonymous", "", None]}})
    print(f"  pending_memories 清理: {result.deleted_count} 条")
    
    # ==================== 3. 创建索引 ====================
    print("\n[3/4] 创建索引...")
    
    # user_memories 索引
    await new_memories.create_index([("user_id", 1), ("key", 1)], unique=True, name="user_key_unique")
    await new_memories.create_index([("user_id", 1), ("category", 1)], name="user_category")
    await new_memories.create_index([("user_id", 1), ("updated_at", -1)], name="user_updated")
    print("  user_memories: 3个索引")
    
    # pending_memories 索引
    await pending.create_index([("user_id", 1), ("status", 1)], name="user_status")
    await pending.create_index("expires_at", expireAfterSeconds=0, name="auto_expire")  # TTL 索引
    print("  pending_memories: 2个索引 (含TTL自动过期)")
    
    # conversation_digests 索引
    digests = db.conversation_digests
    await digests.create_index([("user_id", 1), ("created_at", -1)], name="user_created")
    await digests.create_index([("user_id", 1), ("session_id", 1)], unique=True, name="user_session_unique")
    print("  conversation_digests: 2个索引")
    
    # ==================== 4. 验证结果 ====================
    print("\n[4/4] 验证结果...")
    
    final_user_memories = await new_memories.count_documents({})
    final_pending = await pending.count_documents({})
    final_digests = await digests.count_documents({})
    
    print(f"  user_memories: {final_user_memories} 条")
    print(f"  pending_memories: {final_pending} 条")
    print(f"  conversation_digests: {final_digests} 条")
    
    # 按用户统计
    print("\n  按用户分布:")
    pipeline = [
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    async for doc in new_memories.aggregate(pipeline):
        print(f"    {doc['_id']}: {doc['count']} 条")
    
    print("\n" + "=" * 50)
    print("迁移完成!")
    print("=" * 50)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
