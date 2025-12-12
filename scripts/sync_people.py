import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

from services.people_store import get_people_store

async def main():
    store = get_people_store()
    
    # 初始化索引
    await store.init_indexes()
    print("索引已创建")
    
    # 检查现有数据
    count = await store.people.count_documents({})
    print("现有人员:", count)
    
    if count == 0:
        # 同步
        print("开始同步...")
        result = await store.sync_from_ms365()
        print("同步结果:", result)
    else:
        print("人员数据已存在")
    
    # 更新活跃度 (最近3天)
    from datetime import datetime, timedelta
    for i in range(3):
        date = datetime.now() - timedelta(days=i)
        result = await store.update_email_activity(date)
        print("活跃度更新 (" + date.strftime('%Y-%m-%d') + "):", result['updated'], "人")
    
    # 获取仪表盘
    dashboard = await store.get_dashboard()
    stats = dashboard["stats"]
    print("\n=== 仪表盘 ===")
    print("总人数:", stats['total_people'])
    print("今日活跃:", stats['active_today'])
    print("部门数:", stats['department_count'])
    print("职能数:", stats['function_count'])

asyncio.run(main())
