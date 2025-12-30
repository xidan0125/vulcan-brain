#!/usr/bin/env python3
"""
人员数据定时同步
每天运行一次，同步 MS365 人员数据并更新活跃度
"""
import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta

sys.path.insert(0, '/home/xinyue/vulcan-brain')
os.chdir('/home/xinyue/vulcan-brain')

from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/xinyue/vulcan-brain/logs/people_sync_cron.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

client = MongoClient('mongodb://localhost:27017/')
db = client['vulcan_brain']


async def main():
    from services.people_store import get_people_store
    
    logger.info('='*50)
    logger.info(f'开始人员同步 @ {datetime.now()}')
    logger.info('='*50)
    
    store = get_people_store()
    
    # 1. 确保索引
    await store.init_indexes()
    logger.info('索引检查完成')
    
    # 2. 同步 MS365 人员
    before_count = await store.people.count_documents({})
    logger.info(f'同步前人员数: {before_count}')
    
    try:
        result = await store.sync_from_ms365()
        logger.info(f'MS365 同步结果: {result}')
    except Exception as e:
        logger.error(f'MS365 同步失败: {e}')
    
    after_count = await store.people.count_documents({})
    logger.info(f'同步后人员数: {after_count} (+{after_count - before_count})')
    
    # 3. 更新最近7天的邮件活跃度
    logger.info('更新邮件活跃度...')
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        try:
            result = await store.update_email_activity(date)
            logger.info(f'  {date.strftime("%Y-%m-%d")}: 更新 {result.get("updated", 0)} 人')
        except Exception as e:
            logger.error(f'  {date.strftime("%Y-%m-%d")}: 失败 - {e}')
    
    # 4. 获取统计
    dashboard = await store.get_dashboard()
    stats = dashboard.get('stats', {})
    logger.info(f'统计: 总人数={stats.get("total_people", 0)}, 今日活跃={stats.get("active_today", 0)}')
    
    db.pipeline_runs.insert_one({
        'pipeline': 'people_sync',
        'start_time': datetime.now(),
        'before_count': before_count,
        'after_count': after_count,
        'status': 'success'
    })
    
    logger.info('人员同步完成')

if __name__ == '__main__':
    asyncio.run(main())
