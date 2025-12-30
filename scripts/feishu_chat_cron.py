#!/usr/bin/env python3
"""
飞书群聊消息定时采集
每小时运行一次，自动采集机器人所在的所有群聊消息
"""
import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta
import httpx

sys.path.insert(0, "/home/xinyue/vulcan-brain")
os.chdir("/home/xinyue/vulcan-brain")

from dotenv import load_dotenv
load_dotenv("/home/xinyue/vulcan-brain/.env")

from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/home/xinyue/vulcan-brain/logs/feishu_chat_cron.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]


async def get_feishu_token() -> str:
    async with httpx.AsyncClient(timeout=30) as http_client:
        resp = await http_client.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
        )
        data = resp.json()
        return data.get("tenant_access_token")


async def get_all_bot_chats(token: str) -> list:
    chats = []
    page_token = None
    
    async with httpx.AsyncClient(timeout=60) as http_client:
        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            
            resp = await http_client.get(
                "https://open.larksuite.com/open-apis/im/v1/chats",
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            data = resp.json()
            
            if data.get("code") != 0:
                logger.error(f"获取群列表失败: {data}")
                break
            
            items = data.get("data", {}).get("items", [])
            for item in items:
                chats.append({
                    "chat_id": item.get("chat_id"),
                    "name": item.get("name", ""),
                    "owner_id": item.get("owner_id", ""),
                    "chat_mode": item.get("chat_mode", "")
                })
            
            page_token = data.get("data", {}).get("page_token")
            if not page_token or not data.get("data", {}).get("has_more"):
                break
    
    return chats


async def main():
    from services.feishu_collector import get_message_collector
    
    logger.info("="*50)
    logger.info(f"开始飞书群聊采集 @ {datetime.now()}")
    logger.info("="*50)
    
    token = await get_feishu_token()
    if not token:
        logger.error("获取飞书 token 失败，退出")
        return
    
    all_chats = await get_all_bot_chats(token)
    logger.info(f"机器人所在群聊数: {len(all_chats)}")
    
    if not all_chats:
        logger.warning("没有找到任何群聊，退出")
        return
    
    for chat in all_chats:
        db.chat_metadata.update_one(
            {"chat_id": chat["chat_id"]},
            {
                "$set": {
                    "chat_name": chat["name"],
                    "owner_id": chat["owner_id"],
                    "chat_mode": chat["chat_mode"],
                    "updated_at": datetime.now()
                },
                "$setOnInsert": {"created_at": datetime.now()}
            },
            upsert=True
        )
    
    since = datetime.now() - timedelta(hours=2)
    collector = get_message_collector()
    
    total_collected = 0
    total_inserted = 0
    
    for chat in all_chats:
        chat_id = chat["chat_id"]
        chat_name = chat["name"] or chat_id[-8:]
        try:
            result = await collector.collect_chat_messages(chat_id, since=since)
            collected = result.get("collected", 0)
            inserted = result.get("inserted", 0)
            total_collected += collected
            total_inserted += inserted
            if collected > 0:
                logger.info(f"  [{chat_name}]: 采集 {collected}, 新增 {inserted}")
        except Exception as e:
            logger.error(f"  [{chat_name}]: 采集失败 - {e}")
    
    logger.info(f"采集完成: 扫描 {len(all_chats)} 个群, 消息 {total_collected} 条, 新增 {total_inserted} 条")
    
    db.pipeline_runs.insert_one({
        "pipeline": "feishu_chat",
        "start_time": datetime.now(),
        "chats_scanned": len(all_chats),
        "total_collected": total_collected,
        "total_inserted": total_inserted,
        "status": "success"
    })

if __name__ == "__main__":
    asyncio.run(main())
