#!/usr/bin/env python3
"""重跑 vllm_crash 的邮件"""
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain/docs/email-intelligence-v3/v3_pipeline')

from batch_extractor_v312_stable import extract_email, load_attachment_images
from pathlib import Path
import pymongo
from bson import ObjectId
from datetime import datetime

RETRY_IDS_FILE = Path.home() / 'vulcan_data' / 'cache' / 'retry_vllm_crash_ids.txt'
MONGO_URI = 'mongodb://localhost:27017'
DOWNLOAD_DIR = Path.home() / 'vulcan_data' / 'attachments'

def run_retry():
    with open(RETRY_IDS_FILE) as f:
        retry_ids = [line.strip() for line in f if line.strip()]
    
    print(f'=== 重跑 vllm_crash ({len(retry_ids)} 个) ===')
    
    client = pymongo.MongoClient(MONGO_URI)
    db = client.vulcan_brain
    
    success, skipped, failed = 0, 0, 0
    
    for i, email_id in enumerate(retry_ids):
        email = db.emails.find_one({'_id': ObjectId(email_id)})
        if not email:
            print(f'[{i+1}/{len(retry_ids)}] ❌ 找不到')
            continue
        
        subject = (email.get('subject') or '')[:40]
        body = email.get('body_text', '') or email.get('body_html', '') or ''
        
        # 加载附件
        att_records = email.get('attachment_records', [])
        attachments = []
        for att in att_records:
            local_path = att.get('local_path', '')
            if local_path:
                full_path = DOWNLOAD_DIR / local_path
                if full_path.exists():
                    images = load_attachment_images(str(full_path), att.get('filename', ''))
                    if images:
                        attachments.append({'filename': att.get('filename', ''), 'images': images})
        
        if not attachments:
            print(f'[{i+1}/{len(retry_ids)}] ⏭️ 无附件: {subject}')
            skipped += 1
            continue
        
        print(f'[{i+1}/{len(retry_ids)}] {subject}...')
        
        try:
            result, duration = extract_email(email_id, body[:2000], attachments)
            if result:
                db.emails.update_one(
                    {'_id': ObjectId(email_id)},
                    {'': {"v3_extraction_v312": result}}
                )
                print(f'      ✅ {len(result.get("facts", []))} facts, {duration:.1f}s')
                success += 1
            else:
                print(f'      ⏭️ 无结果')
                skipped += 1
        except Exception as e:
            err = str(e)[:80]
            print(f'      ❌ {err}')
            failed += 1
    
    print(f'\n=== 完成 ===')
    print(f'✅ 成功: {success}/{len(retry_ids)}')
    print(f'⏭️ 跳过: {skipped}')
    print(f'❌ 失败: {failed}')

if __name__ == '__main__':
    run_retry()
