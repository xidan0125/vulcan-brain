import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

from services.entity_service import get_entity_service

async def main():
    print("Loading entity service...", flush=True)
    svc = get_entity_service()
    
    # 批量处理所有邮件 - 每次1000封
    total_processed = 0
    while True:
        result = await svc.process_batch(limit=500)
        total_processed += result["processed"]
        print("Batch:", result["processed"], "Total:", total_processed, flush=True)
        
        if result["processed"] == 0:
            break
    
    # 获取统计
    print("\n=== Final stats ===", flush=True)
    stats = await svc.get_entity_stats()
    print("Total processed:", stats["total_processed"], flush=True)
    print("Entity types:", stats["entity_types"], flush=True)
    print("Categories:", stats["categories"], flush=True)

asyncio.run(main())
