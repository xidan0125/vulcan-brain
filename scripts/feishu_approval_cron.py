#!/usr/bin/env python3
"""
飞书审批定时采集
每小时运行一次，采集所有审批类型的实例
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
        logging.FileHandler("/home/xinyue/vulcan-brain/logs/feishu_approval_cron.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 使用 BRAIN APP (与群聊采集一致)
FEISHU_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]


async def get_feishu_token() -> str:
    async with httpx.AsyncClient(timeout=30) as http_client:
        resp = await http_client.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error(f"获取 token 失败: {data}")
            return None
        return data.get("tenant_access_token")


async def get_approval_definitions(token: str) -> list:
    definitions = []
    page_token = None
    
    async with httpx.AsyncClient(timeout=60) as http_client:
        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            
            resp = await http_client.get(
                "https://open.larksuite.com/open-apis/approval/v4/approvals",
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            data = resp.json()
            
            if data.get("code") != 0:
                logger.error(f"获取审批定义失败: {data}")
                break
            
            items = data.get("data", {}).get("approval_list", [])
            definitions.extend(items)
            
            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break
    
    return definitions


async def collect_approval_instances(token: str, approval_code: str, since: datetime) -> dict:
    instances = []
    page_token = ""
    
    async with httpx.AsyncClient(timeout=60) as http_client:
        while True:
            params = {
                "approval_code": approval_code,
                "start_time": str(int(since.timestamp() * 1000)),
                "end_time": str(int(datetime.now().timestamp() * 1000)),
                "page_size": 100
            }
            if page_token:
                params["page_token"] = page_token
            
            resp = await http_client.get(
                "https://open.larksuite.com/open-apis/approval/v4/instances",
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            data = resp.json()
            
            if data.get("code") != 0:
                logger.error(f"获取审批实例失败 [{approval_code}]: {data}")
                break
            
            items = data.get("data", {}).get("instance_code_list", [])
            instances.extend(items)
            
            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break
    
    inserted = 0
    for instance_code in instances:
        result = db.bot_approvals.update_one(
            {"instance_code": instance_code},
            {
                "$set": {
                    "approval_code": approval_code,
                    "updated_at": datetime.now()
                },
                "$setOnInsert": {
                    "created_at": datetime.now(),
                    "status": "PENDING"
                }
            },
            upsert=True
        )
        if result.upserted_id:
            inserted += 1
    
    return {"collected": len(instances), "inserted": inserted}


async def main():
    logger.info("="*50)
    logger.info(f"开始飞书审批采集 @ {datetime.now()}")
    logger.info("="*50)
    
    token = await get_feishu_token()
    if not token:
        logger.error("获取飞书 token 失败")
        return
    
    definitions = await get_approval_definitions(token)
    logger.info(f"发现 {len(definitions)} 个审批类型")
    
    for d in definitions:
        db.approval_definitions.update_one(
            {"approval_code": d.get("approval_code")},
            {
                "$set": {
                    "approval_name": d.get("approval_name"),
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )
    
    since = datetime.now() - timedelta(hours=48)
    
    total_collected = 0
    total_inserted = 0
    
    for d in definitions:
        approval_code = d.get("approval_code")
        approval_name = d.get("approval_name", approval_code)
        try:
            result = await collect_approval_instances(token, approval_code, since)
            total_collected += result["collected"]
            total_inserted += result["inserted"]
            if result["collected"] > 0:
                logger.info(f"  [{approval_name}]: 采集 {result[collected]}, 新增 {result[inserted]}")
        except Exception as e:
            logger.error(f"  [{approval_name}]: 采集失败 - {e}")
    
    logger.info(f"采集完成: {len(definitions)} 个类型, 实例 {total_collected} 条, 新增 {total_inserted} 条")
    
    db.pipeline_runs.insert_one({
        "pipeline": "feishu_approval",
        "start_time": datetime.now(),
        "definitions_count": len(definitions),
        "total_collected": total_collected,
        "total_inserted": total_inserted,
        "status": "success"
    })

if __name__ == "__main__":
    asyncio.run(main())
