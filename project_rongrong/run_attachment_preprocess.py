#!/usr/bin/env python3
"""运行附件预处理"""
import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')

from project_rongrong.services.attachment_processor import AttachmentPreprocessor
import pymongo

async def main():
    company = sys.argv[1] if len(sys.argv) > 1 else 'shanghai'
    date_str = sys.argv[2] if len(sys.argv) > 2 else '2025-12-26'
    
    db = pymongo.MongoClient('mongodb://localhost:27017').vulcan_brain
    
    # 获取 KEEP 邮件 ID
    run = db.rongrong_filter_runs.find_one({'company': company, 'date': date_str})
    if not run or 'binary_filter_result' not in run:
        print('未找到 filter 结果')
        return
    
    keep_ids = run['binary_filter_result'].get('KEEP', [])
    print(f'[附件预处理] {company} {date_str}')
    print(f'  KEEP 邮件: {len(keep_ids)} 封')
    
    # 检查哪些还没处理
    already = db.wecom_emails.count_documents({
        'email_id': {'$in': keep_ids},
        'processed_assets.0': {'$exists': True}
    })
    print(f'  已处理: {already} 封')
    
    # 获取未处理的
    todo_emails = list(db.wecom_emails.find({
        'email_id': {'$in': keep_ids},
        '$or': [
            {'processed_assets': {'$exists': False}},
            {'processed_assets': []},
            {'processed_assets': None}
        ],
        'attachments.0': {'$exists': True}  # 只处理有附件的
    }))
    
    print(f'  待处理 (有附件): {len(todo_emails)} 封')
    
    if not todo_emails:
        print('无需处理')
        return
    
    # 处理
    processor = AttachmentPreprocessor()
    
    for i, email in enumerate(todo_emails):
        email_id = email['email_id']
        subj = (email.get('subject') or '')[:40]
        att_count = len(email.get('attachments', []))
        print(f'  [{i+1}/{len(todo_emails)}] {subj} ({att_count} 附件)...', end=' ', flush=True)
        
        try:
            paths = await processor.process_single_email(email_id)
            print(f'→ {len(paths)} 张图')
        except Exception as e:
            print(f'→ 错误: {e}')
    
    print('\n完成')

if __name__ == '__main__':
    asyncio.run(main())
