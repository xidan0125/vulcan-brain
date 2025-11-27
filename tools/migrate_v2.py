#!/usr/bin/env python3
"""
Vulcan Brain 数据迁移脚本
从旧 JSON 文件迁移到 MongoDB
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加父目录到 path 以便导入 vulcan_libs
sys.path.insert(0, str(Path(__file__).parent.parent))

from vulcan_libs.store import store

async def migrate_memories():
    """迁移用户记忆 (user_memory.json -> MongoDB memories)"""
    json_path = Path(__file__).parent.parent / "data" / "user_memory.json"
    if not json_path.exists():
        print("⚠️  未找到 user_memory.json，跳过记忆迁移")
        return 0

    print(f"🔄 正在迁移 {json_path} ...")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 兼容列表和字典格式
            memories = data if isinstance(data, list) else data.get("memories", [])
            
            count = 0
            for mem in memories:
                # 兼容旧格式，给一个默认 user_id
                user_id = mem.get("user_id", "xinyue") 
                content = mem.get("content", "")
                
                # 查重：避免重复导入
                exists = await store.db.memories.find_one({"content": content, "user_id": user_id})
                if not exists and content:
                    await store.add_memory(user_id=user_id, content=content)
                    count += 1
            
            print(f"✅ 成功迁移 {count} 条记忆")
            return count
    except Exception as e:
        print(f"❌ 记忆迁移失败: {e}")
        return 0

async def migrate_alignments():
    """迁移对齐数据 (alignment_memory.json -> MongoDB alignment_feedback)"""
    json_path = Path(__file__).parent.parent / "alignment_memory.json"
    if not json_path.exists():
        # 也尝试 data 目录
        json_path = Path(__file__).parent.parent / "data" / "alignment_feedback.json"
    
    if not json_path.exists():
        print("⚠️  未找到对齐数据文件，跳过对齐迁移")
        return 0

    print(f"🔄 正在迁移 {json_path} ...")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            alignments = data if isinstance(data, list) else data.get("alignments", [])
            
            count = 0
            for item in alignments:
                user_id = item.get("user_id", "xinyue")
                situation = item.get("situation", "")
                boss_feedback = item.get("boss_feedback", "")
                lesson = item.get("lesson", "")
                
                # 查重
                exists = await store.db.alignment_feedback.find_one({
                    "situation": situation, 
                    "user_id": user_id
                })
                if not exists and (situation or boss_feedback):
                    await store.add_alignment(
                        user_id=user_id,
                        situation=situation,
                        boss_feedback=boss_feedback,
                        lesson=lesson
                    )
                    count += 1
            
            print(f"✅ 成功迁移 {count} 条对齐记录")
            return count
    except Exception as e:
        print(f"❌ 对齐迁移失败: {e}")
        return 0

async def show_stats():
    """显示迁移后的统计"""
    print("\n📊 数据库统计:")
    
    collections = await store.db.list_collection_names()
    for col in collections:
        count = await store.db[col].count_documents({})
        print(f"   {col}: {count} 条记录")

async def main():
    print("🚀 开始 Vulcan V2 -> V3 数据迁移...")
    print(f"   数据库: {store.db.name}")
    print()
    
    # 1. 确保索引存在
    print("📋 初始化索引...")
    await store.initialize_indexes()
    print()
    
    # 2. 执行迁移
    mem_count = await migrate_memories()
    align_count = await migrate_alignments()
    
    # 3. 显示统计
    await show_stats()
    
    print()
    print(f"✨ 迁移完成！共迁移 {mem_count + align_count} 条记录")

if __name__ == "__main__":
    asyncio.run(main())
