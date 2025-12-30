"""
企微邮件日报生成器 - 被 cron 调用
生成后存到 MongoDB，API 只读取
"""
import asyncio
import sys
sys.path.insert(0, "/home/xinyue/vulcan-brain/services")

from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from daily_report_v2 import DailyReportV2

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"


async def generate_and_save(company: str, date: str):
    """生成日报并存 MongoDB"""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始生成 {company} {date} 日报...")
    
    pipeline = DailyReportV2()
    report = await pipeline.run(company, date)
    
    # 存到 wecom_daily_reports
    await db.wecom_daily_reports.update_one(
        {"company": company, "date": date},
        {"$set": {
            "company": company,
            "date": date,
            "report": report,
            "generated_at": datetime.now()
        }},
        upsert=True
    )
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 已保存")
    client.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="shanghai")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    await generate_and_save(args.company, args.date)


if __name__ == "__main__":
    asyncio.run(main())
