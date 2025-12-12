import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')
from datetime import datetime, timedelta
from services.email_store import get_email_store

async def sync():
    store = get_email_store()
    since = datetime.now() - timedelta(days=730)
    
    users = await store.get_all_users()
    valid_users = [u for u in users if u.get('mail')]
    print(f'开始同步 {len(valid_users)} 个用户, 起始: {since.date()}', flush=True)
    
    total = {'users': 0, 'fetched': 0, 'inserted': 0, 'skipped': 0}
    
    for i, user in enumerate(valid_users):
        email = user['mail']
        folders = await store.get_user_mail_folders(email)
        
        user_total = 0
        for f in folders:
            try:
                result = await store.sync_user_emails(email, since=since, folder=f['id'], max_emails=20000)
                user_total += result['inserted']
                total['fetched'] += result['fetched']
                total['inserted'] += result['inserted']
                total['skipped'] += result['skipped']
            except Exception as e:
                print(f'  错误 {email}/{f["displayName"]}: {e}', flush=True)
        
        total['users'] += 1
        print(f'[{i+1}/{len(valid_users)}] {email}: +{user_total} (累计: {total["inserted"]})', flush=True)
    
    print(f'\n完成! {total}', flush=True)

asyncio.run(sync())
