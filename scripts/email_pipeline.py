#!/usr/bin/env python3
"""
Vulcan Brain - 邮件数据管道自动化
每15分钟运行一次，完成：
1. 增量同步新邮件 (从最后同步时间开始)
2. 提取联系人和公司
3. 更新Intelligence计算
"""
import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta

# 设置环境
sys.path.insert(0, '/home/xinyue/vulcan-brain')
os.chdir('/home/xinyue/vulcan-brain')

from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

from pymongo import MongoClient

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/xinyue/vulcan-brain/logs/email_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB 连接
client = MongoClient('mongodb://localhost:27017/')
db = client['vulcan_brain']

async def step1_sync_emails():
    """增量同步邮件"""
    from services.email_store import get_email_store
    
    logger.info("=== Step 1: 同步邮件 ===")
    store = get_email_store()
    
    # 获取最后同步时间，默认同步最近7天
    sync_meta = db.sync_meta.find_one({'_id': 'email_sync'})
    if sync_meta and sync_meta.get('last_sync'):
        since = sync_meta['last_sync'] - timedelta(hours=1)  # 重叠1小时防漏
    else:
        since = datetime.now() - timedelta(days=7)
    
    logger.info(f"同步起始时间: {since}")
    
    result = await store.sync_all_users(since=since, max_per_folder=5000)
    
    # 更新同步时间 - 只有找到新邮件时才更新 last_sync
    update_data = {'result': result}
    if result.get('inserted', 0) > 0:
        update_data['last_sync'] = datetime.now()
        logger.info(f"已同步 {result['inserted']} 封新邮件，更新 last_sync")
    else:
        logger.info("没有新邮件，保持 last_sync 不变")
    
    db.sync_meta.update_one(
        {'_id': 'email_sync'},
        {'$set': update_data},
        upsert=True
    )
    
    logger.info(f"同步完成: {result}")
    return result

async def step2_extract_contacts():
    """从新邮件提取联系人"""
    logger.info("=== Step 2: 提取联系人 ===")
    
    # 获取最近处理时间
    proc_meta = db.sync_meta.find_one({'_id': 'contact_extract'})
    last_processed = proc_meta.get('last_processed') if proc_meta else datetime.now() - timedelta(days=7)
    
    # 查找新邮件
    new_emails = list(db.emails.find(
        {'received_at': {'$gt': last_processed}},
        {'from': 1, 'to': 1, 'cc': 1, 'received_at': 1}
    ))
    
    if not new_emails:
        logger.info("没有新邮件需要处理")
        return {'processed': 0}
    
    logger.info(f"处理 {len(new_emails)} 封新邮件")
    
    contacts_updated = 0
    for email in new_emails:
        # 处理发件人
        sender = email.get('from', {})
        if sender.get('emailAddress', {}).get('address'):
            addr = sender['emailAddress']['address'].lower()
            name = sender['emailAddress'].get('name', addr.split('@')[0])
            
            db.contacts.update_one(
                {'email': addr},
                {
                    '$set': {'name': name, 'last_seen': email.get('received_at')},
                    '$inc': {'email_count': 1},
                    '$setOnInsert': {'created_at': datetime.now()}
                },
                upsert=True
            )
            contacts_updated += 1
        
        # 处理收件人
        for recipient in email.get('to', []) + email.get('cc', []):
            addr = recipient.get('emailAddress', {}).get('address', '').lower()
            if addr:
                name = recipient.get('emailAddress', {}).get('name', addr.split('@')[0])
                db.contacts.update_one(
                    {'email': addr},
                    {
                        '$set': {'name': name},
                        '$inc': {'received_count': 1},
                        '$setOnInsert': {'created_at': datetime.now()}
                    },
                    upsert=True
                )
    
    # 更新处理时间
    db.sync_meta.update_one(
        {'_id': 'contact_extract'},
        {'$set': {'last_processed': datetime.now()}},
        upsert=True
    )
    
    logger.info(f"联系人更新: {contacts_updated}")
    return {'processed': len(new_emails), 'contacts_updated': contacts_updated}

async def step3_extract_companies():
    """从联系人邮箱提取公司"""
    logger.info("=== Step 3: 提取公司 ===")
    
    # 统计每个域名的邮件
    pipeline = [
        {'$match': {'received_at': {'$exists': True}}},
        {'$addFields': {
            'sender_email': {'$toLower': '$from.emailAddress.address'}
        }},
        {'$match': {'sender_email': {'$ne': None}}},
        {'$addFields': {
            'domain': {'$arrayElemAt': [{'$split': ['$sender_email', '@']}, 1]}
        }},
        {'$match': {'domain': {'$ne': None}}},
        {'$group': {
            '_id': '$domain',
            'email_count': {'$sum': 1},
            'last_contact': {'$max': '$received_at'},
            'contacts': {'$addToSet': '$sender_email'}
        }},
        {'$match': {'email_count': {'$gte': 3}}}  # 至少3封邮件
    ]
    
    domains = list(db.emails.aggregate(pipeline))
    logger.info(f"发现 {len(domains)} 个活跃域名")
    
    companies_updated = 0
    for d in domains:
        domain = d['_id']
        # 跳过常见邮箱服务
        if any(x in domain for x in ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com', 'qq.com', '163.com', '126.com']):
            continue
        
        # 计算最近30天活跃度
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_count = db.emails.count_documents({
            'from.emailAddress.address': {'$regex': f'@{domain}$', '$options': 'i'},
            'received_at': {'$gte': thirty_days_ago}
        })
        
        # 计算沉默天数
        days_silent = (datetime.now() - d['last_contact']).days if d['last_contact'] else 999
        
        db.companies.update_one(
            {'domain': domain},
            {
                '$set': {
                    'email_count': d['email_count'],
                    'contact_count': len(d['contacts']),
                    'last_contact': d['last_contact'],
                    'days_silent': days_silent,
                    'recent_activity': recent_count,
                    'updated_at': datetime.now()
                },
                '$setOnInsert': {
                    'name': domain.split('.')[0].title(),
                    'relation_type': 'unknown',
                    'created_at': datetime.now()
                }
            },
            upsert=True
        )
        companies_updated += 1
    
    logger.info(f"公司更新: {companies_updated}")
    return {'companies_updated': companies_updated}

async def step4_compute_health_scores():
    """计算联系人健康度"""
    logger.info("=== Step 4: 计算健康度 ===")
    
    now = datetime.now()
    updated = 0
    
    # 遍历所有联系人
    for contact in db.contacts.find({'email': {'$exists': True}}):
        email = contact['email']
        
        # 统计邮件数
        sent_count = db.emails.count_documents({'from.emailAddress.address': {'$regex': f'^{email}$', '$options': 'i'}})
        received_count = db.emails.count_documents({
            '$or': [
                {'to.emailAddress.address': {'$regex': f'^{email}$', '$options': 'i'}},
                {'cc.emailAddress.address': {'$regex': f'^{email}$', '$options': 'i'}}
            ]
        })
        
        # 最近活动
        latest = db.emails.find_one(
            {'$or': [
                {'from.emailAddress.address': {'$regex': f'^{email}$', '$options': 'i'}},
                {'to.emailAddress.address': {'$regex': f'^{email}$', '$options': 'i'}}
            ]},
            sort=[('received_at', -1)]
        )
        
        days_since = (now - latest['received_at']).days if latest and latest.get('received_at') else 999
        
        # 计算健康度 (0-100)
        # 基于: 邮件频率、互动双向性、最近活跃度
        frequency_score = min(30, (sent_count + received_count) / 10 * 30)
        bidirectional = min(30, min(sent_count, received_count) / 5 * 30) if sent_count > 0 and received_count > 0 else 0
        recency_score = max(0, 40 - days_since * 0.5)
        
        health_score = int(frequency_score + bidirectional + recency_score)
        
        db.contacts.update_one(
            {'_id': contact['_id']},
            {'$set': {
                'sent_count': sent_count,
                'received_count': received_count,
                'last_contact': latest['received_at'] if latest else None,
                'days_silent': days_since,
                'health_score': health_score,
                'health_updated': now
            }}
        )
        updated += 1
        
        if updated % 100 == 0:
            logger.info(f"已处理 {updated} 个联系人...")
    
    logger.info(f"健康度更新: {updated}")
    return {'contacts_updated': updated}

async def run_pipeline():
    """运行完整管道"""
    start_time = datetime.now()
    logger.info("="*50)
    logger.info(f"开始邮件数据管道 @ {start_time}")
    logger.info("="*50)
    
    results = {}
    
    try:
        # Step 1: 同步邮件
        results['sync'] = await step1_sync_emails()
        
        # Step 2: 提取联系人
        results['contacts'] = await step2_extract_contacts()
        
        # Step 3: 提取公司
        results['companies'] = await step3_extract_companies()
        
        # Step 4: 健康度计算已废弃 - 使用 relation_type 替代
        # 健康度算法已移除，改用实体类型分类
        logger.info("健康度计算已废弃，使用实体类型(relation_type)替代")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"管道完成! 耗时: {elapsed:.1f}秒")
        logger.info(f"结果: {results}")
        
        # 记录运行历史
        db.pipeline_runs.insert_one({
            'start_time': start_time,
            'end_time': datetime.now(),
            'elapsed_seconds': elapsed,
            'results': results,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"管道错误: {e}", exc_info=True)
        db.pipeline_runs.insert_one({
            'start_time': start_time,
            'end_time': datetime.now(),
            'error': str(e),
            'status': 'failed'
        })
        raise

if __name__ == '__main__':
    asyncio.run(run_pipeline())
