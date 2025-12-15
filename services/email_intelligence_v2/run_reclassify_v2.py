#!/usr/bin/env python3
"""二次清洗 V2 - 更精细的规则"""
import asyncio
import re
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# 更精细的升级规则
UPGRADE_RULES = {
    "CONTRACT": [
        r"LOI", r"letter of intent", r"意向书",
        r"agreement", r"contract", r"合同", r"协议",
        r"NDA", r"non-disclosure", r"保密协议",
        r"MOU", r"memorandum"
    ],
    "COMPLIANCE": [
        r"patent", r"专利", r"trademark", r"商标",
        r"intellectual property", r"知识产权",
        r"legal", r"法务", r"律师",
        r"certificate", r"认证", r"certification",
        r"audit", r"审计", r"inspection"
    ],
    "QUALITY": [
        r"test.*result", r"测试结果", r"lab report",
        r"material.*spec", r"规格", r"specification",
        r"sample.*evaluation", r"样品评估",
        r"technical.*data", r"技术数据"
    ],
    "OTHER_BUSINESS": [
        r"development", r"研发", r"R&D",
        r"experiment", r"实验", r"试验",
        r"prototype", r"原型", r"打样",
        r"project.*update", r"项目进展",
        r"partnership", r"合作", r"collaboration"
    ],
    "MEETING": [
        r"meeting.*schedul", r"会议安排",
        r"call.*schedul", r"电话安排",
        r"appointment", r"预约",
        r"visit.*schedul", r"拜访安排"
    ]
}

# 真正应该跳过的（不再升级）
TRULY_SKIP = [
    r"请假", r"leave.*approv", r"annual.*leave", r"sick.*leave",
    r"OTP", r"verification.*code", r"验证码",
    r"out of office", r"自动回复", r"automatic.*reply",
    r"unsubscribe", r"退订",
    r"newsletter", r"简报",
    r"survey", r"问卷", r"feedback.*request",
    r"marketing", r"promotion", r"discount", r"% off",
    r"hotel.*stay", r"flight.*upgrade", r"airline.*booking"
]

async def reclassify_v2():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain
    
    stats = {"upgraded": 0, "skipped_confirm": 0, "changes": {}}
    
    print("=== 二次清洗 V2 ===\n")
    
    async for event in db.email_events.find({"classification.intent": "OTHER"}):
        email_id = event.get("email_id")
        email = None
        if email_id:
            try:
                email = await db.emails.find_one({"_id": ObjectId(email_id)})
            except:
                pass
        
        if not email:
            continue
        
        subject = email.get("subject", "")
        body = email.get("body_clean", "")[:2000]
        sub_intent = event.get("classification", {}).get("sub_intent", "")
        text = f"{subject} {body} {sub_intent}".lower()
        
        # 先检查是否真的该跳过
        truly_skip = False
        for pattern in TRULY_SKIP:
            if re.search(pattern, text, re.IGNORECASE):
                truly_skip = True
                stats["skipped_confirm"] += 1
                break
        
        if truly_skip:
            continue
        
        # 检查升级规则
        new_intent = None
        for intent, patterns in UPGRADE_RULES.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    new_intent = intent
                    break
            if new_intent:
                break
        
        if new_intent:
            await db.email_events.update_one(
                {"_id": event["_id"]},
                {"$set": {
                    "classification.intent": new_intent,
                    "classification.reclassified": True,
                    "classification.reclassified_from": "OTHER",
                    "classification.reclassified_at": datetime.now(timezone.utc),
                    "classification.reclassified_round": 2
                }}
            )
            stats["upgraded"] += 1
            stats["changes"][new_intent] = stats["changes"].get(new_intent, 0) + 1
            
            if stats["upgraded"] <= 15:
                print(f"升级: {subject[:55]} -> {new_intent}")
    
    print(f"\n总升级: {stats[upgraded]}")
    print(f"确认跳过: {stats[skipped_confirm]}")
    print(f"\n升级详情:")
    for intent, count in sorted(stats["changes"].items(), key=lambda x: -x[1]):
        print(f"  {intent}: +{count}")

asyncio.run(reclassify_v2())
