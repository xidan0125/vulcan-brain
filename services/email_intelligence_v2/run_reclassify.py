#!/usr/bin/env python3
"""
Email Intelligence V2.0 - 二次清洗脚本
对 OTHER 和 OTHER_BUSINESS 进行重新分类
"""
import asyncio
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 需要重新分类的关键词模式
RECLASSIFY_PATTERNS = {
    # OTHER -> 具体类别
    "SHIPPING_UPDATE": [
        r"shipment", r"shipping", r"delivery", r"tracking", 
        r"空运", r"海运", r"订舱", r"发货", r"到货",
        r"DHL", r"UPS", r"FedEx", r"TNT", r"货运"
    ],
    "ORDER_CONFIRM": [
        r"purchase order", r"PO\s*#", r"订单确认", r"order confirm"
    ],
    "QUOTE_REQUEST": [
        r"quote", r"quotation", r"报价", r"询价", r"RFQ"
    ],
    "INVOICE": [
        r"invoice", r"发票", r"账单", r"billing"
    ],
    "PAYMENT": [
        r"payment", r"付款", r"汇款", r"remittance", r"TT"
    ],
}

# OTHER_BUSINESS 中应该移到 OTHER 的模式
DEMOTE_TO_OTHER = [
    r"water.*bill", r"electric.*bill", r"utility",
    r"parking", r"facility.*maintenance", 
    r"office.*move", r"office.*relocation",
    r"award.*nomination", r"nomination.*confirm",
    r"survey", r"feedback.*request",
]

import re

async def reclassify_emails():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain
    
    stats = {
        "other_upgraded": 0,
        "other_business_demoted": 0,
        "total_checked": 0,
        "changes": {}
    }
    
    # 1. 检查 OTHER 中的漏网之鱼
    logger.info("=== 检查 OTHER 中的漏网之鱼 ===")
    
    async for event in db.email_events.find({"classification.intent": "OTHER"}):
        stats["total_checked"] += 1
        
        email_id = event.get("email_id")
        email = None
        if email_id:
            try:
                email = await db.emails.find_one({"_id": ObjectId(email_id)})
            except:
                pass
        
        if not email:
            continue
            
        subject = email.get("subject", "").lower()
        body = email.get("body_clean", "")[:1000].lower()
        text = f"{subject} {body}"
        
        # 检查是否匹配任何升级模式
        new_intent = None
        for intent, patterns in RECLASSIFY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    new_intent = intent
                    break
            if new_intent:
                break
        
        if new_intent:
            # 升级分类
            await db.email_events.update_one(
                {"_id": event["_id"]},
                {"$set": {
                    "classification.intent": new_intent,
                    "classification.reclassified": True,
                    "classification.reclassified_from": "OTHER",
                    "classification.reclassified_at": datetime.utcnow()
                }}
            )
            stats["other_upgraded"] += 1
            stats["changes"][new_intent] = stats["changes"].get(new_intent, 0) + 1
            
            if stats["other_upgraded"] <= 10:
                logger.info(f"  升级: {subject[:50]} -> {new_intent}")
    
    # 2. 检查 OTHER_BUSINESS 中应该降级的
    logger.info("\n=== 检查 OTHER_BUSINESS 中应该降级的 ===")
    
    async for event in db.email_events.find({"classification.intent": "OTHER_BUSINESS"}):
        stats["total_checked"] += 1
        
        email_id = event.get("email_id")
        email = None
        if email_id:
            try:
                email = await db.emails.find_one({"_id": ObjectId(email_id)})
            except:
                pass
        
        if not email:
            continue
            
        subject = email.get("subject", "").lower()
        sub_intent = event.get("classification", {}).get("sub_intent", "").lower()
        text = f"{subject} {sub_intent}"
        
        # 检查是否匹配降级模式
        should_demote = False
        for pattern in DEMOTE_TO_OTHER:
            if re.search(pattern, text, re.IGNORECASE):
                should_demote = True
                break
        
        if should_demote:
            await db.email_events.update_one(
                {"_id": event["_id"]},
                {"$set": {
                    "classification.intent": "OTHER",
                    "classification.reclassified": True,
                    "classification.reclassified_from": "OTHER_BUSINESS",
                    "classification.reclassified_at": datetime.utcnow()
                }}
            )
            stats["other_business_demoted"] += 1
            
            if stats["other_business_demoted"] <= 10:
                logger.info(f"  降级: {subject[:50]} -> OTHER")
    
    # 打印统计
    logger.info("\n" + "=" * 50)
    logger.info("二次清洗完成!")
    logger.info("=" * 50)
    logger.info(f"检查总数: {stats[total_checked]}")
    logger.info(f"OTHER 升级: {stats[other_upgraded]}")
    logger.info(f"OTHER_BUSINESS 降级: {stats[other_business_demoted]}")
    if stats["changes"]:
        logger.info("升级详情:")
        for intent, count in stats["changes"].items():
            logger.info(f"  {intent}: +{count}")

if __name__ == "__main__":
    asyncio.run(reclassify_emails())
