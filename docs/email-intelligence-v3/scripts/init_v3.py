#!/usr/bin/env python3
"""
V3 全息数据底座 - 初始化脚本
创建 MongoDB 集合和索引
"""

import pymongo
from datetime import datetime

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.vulcan_brain

def create_email_events_collection():
    """创建 email_events 集合"""
    
    # 如果存在则跳过
    if "email_events" in db.list_collection_names():
        print("⚠️  email_events 集合已存在，跳过创建")
        return
    
    # 创建集合
    db.create_collection("email_events")
    print("✅ 创建 email_events 集合")
    
    # 创建索引
    db.email_events.create_index("source.email_id", unique=True)
    db.email_events.create_index("event_type")
    db.email_events.create_index("timestamp")
    db.email_events.create_index("state.current")
    db.email_events.create_index("entities.id")
    db.email_events.create_index("entities.name")
    db.email_events.create_index("chain.thread_id")
    db.email_events.create_index("meta.processed_at")
    
    print("✅ 创建 email_events 索引")

def create_entities_v3_collection():
    """创建 entities_v3 集合 (去重后的实体主数据)"""
    
    if "entities_v3" in db.list_collection_names():
        print("⚠️  entities_v3 集合已存在，跳过创建")
        return
    
    db.create_collection("entities_v3")
    print("✅ 创建 entities_v3 集合")
    
    # 创建索引
    db.entities_v3.create_index("canonical_name")
    db.entities_v3.create_index("type")
    db.entities_v3.create_index("aliases")
    db.entities_v3.create_index([("canonical_name", "text"), ("aliases", "text")])
    
    print("✅ 创建 entities_v3 索引")

def create_processing_log_collection():
    """创建处理日志集合"""
    
    if "v3_processing_log" in db.list_collection_names():
        print("⚠️  v3_processing_log 集合已存在，跳过创建")
        return
    
    db.create_collection("v3_processing_log")
    print("✅ 创建 v3_processing_log 集合")
    
    db.v3_processing_log.create_index("email_id", unique=True)
    db.v3_processing_log.create_index("status")
    db.v3_processing_log.create_index("processed_at")
    
    print("✅ 创建 v3_processing_log 索引")

def create_attachment_cache_collection():
    """创建附件缓存元数据集合"""
    
    if "attachment_cache" in db.list_collection_names():
        print("⚠️  attachment_cache 集合已存在，跳过创建")
        return
    
    db.create_collection("attachment_cache")
    print("✅ 创建 attachment_cache 集合")
    
    db.attachment_cache.create_index("email_id")
    db.attachment_cache.create_index("file_hash", unique=True)
    db.attachment_cache.create_index("file_name")
    
    print("✅ 创建 attachment_cache 索引")

def show_stats():
    """显示当前状态"""
    print("\n" + "=" * 50)
    print("📊 V3 数据库状态")
    print("=" * 50)
    
    for coll_name in ["email_events", "entities_v3", "v3_processing_log", "attachment_cache"]:
        if coll_name in db.list_collection_names():
            count = db[coll_name].count_documents({})
            print(f"  {coll_name}: {count} 文档")
        else:
            print(f"  {coll_name}: 未创建")
    
    # V2 参考数据
    print("\n📌 V2 参考数据:")
    v2_total = db.emails.count_documents({"processing_status.v2_extracted": True})
    v2_with_att = db.emails.count_documents({
        "processing_status.v2_extracted": True,
        "has_attachments": True
    })
    print(f"  V2业务邮件: {v2_total}")
    print(f"  其中有附件: {v2_with_att}")

def main():
    print("=" * 50)
    print("🚀 V3 全息数据底座 - 初始化")
    print("=" * 50)
    print(f"时间: {datetime.now()}")
    print()
    
    create_email_events_collection()
    create_entities_v3_collection()
    create_processing_log_collection()
    create_attachment_cache_collection()
    
    show_stats()
    
    print("\n✨ 初始化完成")

if __name__ == "__main__":
    main()
