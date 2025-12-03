"""
批量补充 conversation_id - 使用 MS Graph $batch API
一次请求获取 20 封邮件的 conversationId
"""
import asyncio
import sys
sys.path.insert(0, "/home/xinyue/vulcan-brain")
import os
os.chdir("/home/xinyue/vulcan-brain")
from dotenv import load_dotenv
load_dotenv("/home/xinyue/vulcan-brain/.env")

import logging
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from services.ms365_service import get_ms365_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 20  # MS Graph 限制

async def backfill_batch():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain
    emails = db.emails
    ms365 = get_ms365_service()
    
    # 统计
    total = await emails.count_documents({"conversation_id": {"$exists": False}})
    logger.info(f"需要补充: {total} 封邮件")
    
    if total == 0:
        return {"total": 0, "updated": 0}
    
    token = await ms365._get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    updated = 0
    failed = 0
    batches = 0
    
    async with httpx.AsyncClient(timeout=60) as http:
        # 按用户分组处理
        users = await emails.distinct("user_id", {"conversation_id": {"$exists": False}})
        logger.info(f"涉及 {len(users)} 个用户")
        
        for user_email in users:
            # 获取该用户所有缺少 conversation_id 的邮件
            cursor = emails.find(
                {"user_id": user_email, "conversation_id": {"$exists": False}},
                {"email_id": 1, "_id": 1}
            )
            
            email_batch = []
            async for doc in cursor:
                email_batch.append(doc)
                
                # 满 20 个就发一次批量请求
                if len(email_batch) >= BATCH_SIZE:
                    result = await process_batch(http, headers, emails, user_email, email_batch)
                    updated += result["updated"]
                    failed += result["failed"]
                    batches += 1
                    email_batch = []
                    
                    if batches % 50 == 0:
                        logger.info(f"进度: {batches} 批次, 更新 {updated}, 失败 {failed}")
            
            # 处理剩余的
            if email_batch:
                result = await process_batch(http, headers, emails, user_email, email_batch)
                updated += result["updated"]
                failed += result["failed"]
                batches += 1
    
    logger.info(f"完成! 总批次: {batches}, 更新: {updated}, 失败: {failed}")
    return {"total": total, "updated": updated, "failed": failed, "batches": batches}


async def process_batch(http, headers, emails_coll, user_email, email_batch):
    """处理一个批次的邮件"""
    # 构建 $batch 请求体
    requests = []
    for i, doc in enumerate(email_batch):
        requests.append({
            "id": str(i),
            "method": "GET",
            "url": f"/users/{user_email}/messages/{doc[email_id]}?$select=id,conversationId"
        })
    
    batch_body = {"requests": requests}
    
    updated = 0
    failed = 0
    
    try:
        response = await http.post(
            "https://graph.microsoft.com/v1.0/$batch",
            headers=headers,
            json=batch_body
        )
        
        if response.status_code == 200:
            data = response.json()
            for resp in data.get("responses", []):
                idx = int(resp["id"])
                if resp["status"] == 200:
                    conv_id = resp["body"].get("conversationId")
                    if conv_id:
                        await emails_coll.update_one(
                            {"_id": email_batch[idx]["_id"]},
                            {"$set": {"conversation_id": conv_id}}
                        )
                        updated += 1
                else:
                    failed += 1
        else:
            logger.warning(f"Batch 请求失败: {response.status_code}")
            failed += len(email_batch)
            
        # 避免限流
        await asyncio.sleep(0.2)
        
    except Exception as e:
        logger.error(f"Batch 处理出错: {e}")
        failed += len(email_batch)
    
    return {"updated": updated, "failed": failed}


if __name__ == "__main__":
    result = asyncio.run(backfill_batch())
    print(f"\n结果: {result}")
