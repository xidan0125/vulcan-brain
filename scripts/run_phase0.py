"""
Phase 0 数据准备批处理脚本

按顺序执行:
1. 补充 conversation_id
2. 构建邮件线程
3. 清洗邮件正文
"""
import asyncio
import sys
sys.path.insert(0, "/home/xinyue/vulcan-brain")
import os
os.chdir("/home/xinyue/vulcan-brain")
from dotenv import load_dotenv
load_dotenv("/home/xinyue/vulcan-brain/.env")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain
    
    # 统计初始状态
    total_emails = await db.emails.count_documents({})
    logger.info(f"="*50)
    logger.info(f"Phase 0 数据准备开始")
    logger.info(f"总邮件数: {total_emails}")
    logger.info(f"="*50)
    
    # Step 1: 补充 conversation_id
    logger.info("\n[Step 1/3] 补充 conversation_id...")
    missing_conv = await db.emails.count_documents({"conversation_id": {"$exists": False}})
    
    if missing_conv > 0:
        logger.info(f"需要补充 {missing_conv} 封邮件的 conversation_id")
        # 这个步骤比较慢，需要调用 API
        from scripts.backfill_conversation_id import backfill_conversation_ids
        result = await backfill_conversation_ids(batch_size=500)
        logger.info(f"conversation_id 补充完成: {result}")
    else:
        logger.info("所有邮件已有 conversation_id，跳过")
    
    # Step 2: 构建线程
    logger.info("\n[Step 2/3] 构建邮件线程...")
    from services.email_thread_service import get_email_thread_service
    thread_service = get_email_thread_service()
    await thread_service.init_indexes()
    result = await thread_service.build_threads()
    logger.info(f"线程构建完成: {result}")
    
    # Step 3: 清洗正文
    logger.info("\n[Step 3/3] 清洗邮件正文...")
    from services.email_cleaner import get_email_cleaner
    cleaner = get_email_cleaner()
    result = await cleaner.process_emails()
    logger.info(f"正文清洗完成: {result}")
    
    # 最终统计
    stats = await cleaner.get_clean_stats()
    thread_stats = await thread_service.get_thread_stats()
    
    logger.info("\n" + "="*50)
    logger.info("Phase 0 完成!")
    logger.info(f"邮件统计: {stats}")
    logger.info(f"线程统计: {thread_stats}")
    logger.info("="*50)


if __name__ == "__main__":
    asyncio.run(main())
