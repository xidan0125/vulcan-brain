#!/usr/bin/env python3
"""
V3 PoC测试 - 单封邮件端到端处理
演示完整流程: 邮件 → 附件下载 → VLM提取 → 存储
"""
import pymongo
import json
from datetime import datetime
from pathlib import Path

# 导入V3组件
from downloader import AttachmentDownloader, GraphAPIClient
from vlm_extractor import VLMExtractor


def find_test_email(db) -> dict:
    """找一封有PDF附件的测试邮件"""
    # 优先找有PDF附件的
    email = db.emails.find_one({
        "processing_status.v2_extracted": True,
        "has_attachments": True,
        "attachments": {
            "$elemMatch": {
                "name": {"$regex": r"\.pdf$", "$options": "i"},
                "id": {"$exists": True, "$ne": ""}
            }
        }
    })

    if email:
        return email

    # 退而求其次，找有图片附件的
    email = db.emails.find_one({
        "processing_status.v2_extracted": True,
        "has_attachments": True,
        "attachments": {
            "$elemMatch": {
                "name": {"$regex": r"\.(png|jpg|jpeg)$", "$options": "i"},
                "id": {"$exists": True, "$ne": ""}
            }
        }
    })

    return email


def process_email(email: dict, downloader: AttachmentDownloader,
                  extractor: VLMExtractor, db) -> dict:
    """处理单封邮件，返回V3 Event"""

    email_id = str(email["_id"])
    print(f"\n{'='*60}")
    print(f"📧 处理邮件: {email.get('subject', 'N/A')[:50]}")
    print(f"   ID: {email_id}")
    print(f"   发件人: {email.get('from', {}).get('emailAddress', {}).get('address', 'N/A')}")
    print(f"   附件数: {len(email.get('attachments', []))}")

    # 1. 下载附件
    print(f"\n📥 Step 1: 下载附件...")
    attachments = downloader.download_email_attachments(email)

    downloaded = [a for a in attachments if a["status"] == "downloaded"]
    print(f"   下载成功: {len(downloaded)}/{len(attachments)}")

    for att in attachments:
        status_icon = "✅" if att["status"] == "downloaded" else "❌"
        print(f"   {status_icon} {att['filename']} - {att['status']}")

    if not downloaded:
        print("   ⚠️ 没有成功下载的附件，跳过VLM提取")
        return {
            "source": {"email_id": email_id},
            "event_type": "EMAIL_RECEIVED",
            "facts": [],
            "entities": {},
            "attachments_processed": 0,
            "error": "no_attachments_downloaded"
        }

    # 2. VLM提取
    print(f"\n🔍 Step 2: VLM提取...")

    all_facts = []
    all_entities = {"companies": [], "products": [], "amounts": [], "dates": []}

    for att in downloaded:
        local_path = Path(att["local_path"])
        if not local_path.exists():
            print(f"   ⚠️ 文件不存在: {local_path}")
            continue

        suffix = local_path.suffix.lower()
        if suffix not in [".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
            print(f"   ⏭️ 跳过非视觉文件: {att['filename']}")
            continue

        print(f"   🔎 处理: {att['filename']}...")

        try:
            result = extractor.extract_from_file(local_path)

            if result.get("type") == "pdf":
                for page_ext in result.get("extractions", []):
                    if not page_ext.get("parse_error"):
                        all_facts.extend(page_ext.get("facts", []))
                        for key in all_entities:
                            all_entities[key].extend(page_ext.get("entities", {}).get(key, []))
                        print(f"      Page {page_ext.get('page')}: {len(page_ext.get('facts', []))} facts")
            elif result.get("type") == "image":
                ext = result.get("extraction", {})
                if not ext.get("parse_error"):
                    all_facts.extend(ext.get("facts", []))
                    for key in all_entities:
                        all_entities[key].extend(ext.get("entities", {}).get(key, []))
                    print(f"      Extracted: {len(ext.get('facts', []))} facts")

            print(f"      ✅ 提取完成")

        except Exception as e:
            print(f"      ❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()

    # 3. 构建V3 Event
    print(f"\n📝 Step 3: 构建Event...")

    # 去重实体
    for key in all_entities:
        all_entities[key] = list(set(all_entities[key]))

    event = {
        "source": {
            "email_id": email_id,
            "graph_id": email.get("graph_id"),
            "subject": email.get("subject"),
            "from": email.get("from", {}).get("emailAddress", {}).get("address"),
            "received_at": email.get("receivedDateTime")
        },
        "event_type": "EMAIL_RECEIVED",
        "facts": all_facts,
        "entities": all_entities,
        "attachments_processed": len(downloaded),
        "v3_processed_at": datetime.utcnow(),
        "v3_version": "3.0.0-poc"
    }

    print(f"   Facts: {len(all_facts)}")
    print(f"   Entities: {sum(len(v) for v in all_entities.values())}")

    # 4. 保存到MongoDB
    print(f"\n💾 Step 4: 保存Event...")

    result = db.email_events.update_one(
        {"source.email_id": email_id},
        {"$set": event},
        upsert=True
    )

    if result.upserted_id:
        print(f"   ✅ 新建Event: {result.upserted_id}")
    else:
        print(f"   ✅ 更新Event")

    return event


def compare_with_v2(email: dict, v3_event: dict):
    """对比V3结果和V2结果"""
    print(f"\n{'='*60}")
    print("📊 V2 vs V3 对比")
    print("="*60)

    v2_extracted = email.get("ai_extracted", {})

    # V2结果
    print("\n🔹 V2 提取结果 (仅邮件正文):")
    v2_intent = v2_extracted.get("intent", "N/A")
    v2_entities = v2_extracted.get("entities", {})
    print(f"   Intent: {v2_intent}")
    if isinstance(v2_entities, dict):
        for k, v in v2_entities.items():
            if v:
                print(f"   {k}: {v[:3] if isinstance(v, list) else v}...")

    # V3结果
    print("\n🔸 V3 提取结果 (邮件正文+附件):")
    print(f"   Facts数量: {len(v3_event.get('facts', []))}")
    for key, values in v3_event.get('entities', {}).items():
        if values:
            print(f"   {key}: {values[:3]}...")

    # 展示部分Facts
    facts = v3_event.get('facts', [])
    if facts:
        print("\n   📋 提取的Facts示例:")
        for fact in facts[:5]:
            print(f"      - [{fact.get('type')}] {fact.get('value')} (conf: {fact.get('confidence', 'N/A')})")

    # 关键对比
    print("\n🎯 关键发现:")
    if v3_event.get("attachments_processed", 0) > 0:
        print(f"   ✅ V3处理了 {v3_event['attachments_processed']} 个附件")
        print("   📌 这是V2做不到的（V2只分析邮件正文）")

        new_facts = len(v3_event.get('facts', []))
        if new_facts > 0:
            print(f"   📌 从附件中提取了 {new_facts} 个Facts")
    else:
        print("   ⚠️ 没有成功处理附件")


def main():
    print("="*60)
    print("🚀 V3 全息数据底座 - PoC端到端测试")
    print("="*60)

    # 连接数据库
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.vulcan_brain

    # 找测试邮件
    print("\n🔍 寻找测试邮件...")
    email = find_test_email(db)

    if not email:
        print("❌ 没有找到合适的测试邮件 (需要有附件ID的邮件)")
        return

    print(f"   ✅ 找到: {email.get('subject', 'N/A')[:50]}")

    # 初始化组件
    print("\n⚙️ 初始化V3组件...")
    try:
        graph_client = GraphAPIClient()
        downloader = AttachmentDownloader(graph_client)
        extractor = VLMExtractor()
        print("   ✅ 组件就绪")
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 处理邮件
    v3_event = process_email(email, downloader, extractor, db)

    # 对比V2
    compare_with_v2(email, v3_event)

    print("\n" + "="*60)
    print("✅ PoC测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
