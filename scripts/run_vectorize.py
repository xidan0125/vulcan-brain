import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')
from services.embedding_service import get_embedding_service

async def main():
    print('初始化 Embedding 服务...', flush=True)
    svc = get_embedding_service()
    
    print('创建 Qdrant 集合...', flush=True)
    svc.init_collection()
    
    print('开始向量化邮件...', flush=True)
    result = await svc.vectorize_emails(batch_size=100)
    print(f'完成: {result}', flush=True)
    
    stats = svc.get_stats()
    print(f'统计: {stats}', flush=True)

asyncio.run(main())
