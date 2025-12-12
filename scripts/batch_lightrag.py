import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

from services.lightrag_service import get_lightrag_service

async def main():
    print("Starting LightRAG batch indexing...", flush=True)
    svc = get_lightrag_service()
    
    total_indexed = 0
    batch_num = 0
    
    while True:
        batch_num += 1
        print(f"\n=== Batch {batch_num} ===", flush=True)
        
        result = await svc.index_emails(limit=1000, days=730)  # 2年
        indexed = result.get("indexed", 0)
        total_indexed += indexed
        
        print(f"Batch indexed: {indexed}, Total: {total_indexed}", flush=True)
        
        if indexed == 0:
            print("\nNo more emails to index!", flush=True)
            break
        
        # 获取当前统计
        stats = await svc.get_stats()
        print(f"Progress: {stats['indexed_emails']}/{stats['total_emails']} ({stats['index_ratio']}%)", flush=True)
    
    print(f"\n=== DONE! Total indexed: {total_indexed} ===", flush=True)

asyncio.run(main())
