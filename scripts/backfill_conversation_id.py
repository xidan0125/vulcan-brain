"""
补充已有邮件的 conversation_id 字段

使用 MS Graph API 批量获取邮件的 conversationId
"""
import asyncio
import sys
sys.path.insert(0, "/home/xinyue/vulcan-brain")
import os
os.chdir("/home/xinyue/vulcan-brain")
from dotenv import load_dotenv
load_dotenv("/home/xinyue/vulcan-brain/.env")

import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import httpx
from services.ms365_service import get_ms365_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_conversation_ids(batch_size: int = 100):
    """补充 conversation_id 字段"""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain
    emails = db.emails
    ms365 = get_ms365_service()
    
    # 查找缺少 conversation_id 的邮件
    total = await emails.count_documents({"conversation_id": {"$exists": False}})
    logger.info(f"需要补充 conversation_id 的邮件: {total}")
    
    if total == 0:
        logger.info("所有邮件已有 conversation_id")
        return {"total": 0, "updated": 0}
    
    token = await ms365.get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    updated = 0
    failed = 0
    
    async with httpx.AsyncClient(timeout=30) as http_client:
        # 按用户分组处理
        users = await emails.distinct("user_id", {"conversation_id": {"$exists": False}})
        logger.info(f"涉及 {len(users)} 个用户")
        
        for user_email in users:
            # 获取该用户所有缺少 conversation_id 的邮件
            cursor = emails.find(
                {"user_id": user_email, "conversation_id": {"$exists": False}},
                {"email_id": 1}
            ).limit(batch_size)
            
            email_ids = [doc["email_id"] async for doc in cursor]
            
            for email_id in email_ids:
                try:
                    # 获取单封邮件的 conversationId
                    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{email_id}?$select=conversationId"
                    response = await http_client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        conv_id = data.get("conversationId")
                        
                        if conv_id:
                            await emails.update_one(
                                {"email_id": email_id},
                                {"$set": {"conversation_id": conv_id}}
                            )
                            updated += 1
                    else:
                        failed += 1
                        
                    # 避免请求过快
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"处理邮件 {email_id} 失败: {e}")
                    failed += 1
            
            logger.info(f"用户 {user_email}: 已更新 {updated}, 失败 {failed}")
    
    logger.info(f"补充完成: 总计 {total}, 更新 {updated}, 失败 {failed}")
    return {"total": total, "updated": updated, "failed": failed}


if __name__ == "__main__":
    result = asyncio.run(backfill_conversation_ids(batch_size=500))
    print(f"结果: {result}")
