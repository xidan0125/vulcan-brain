#!/usr/bin/env python3
"""ETL新事件到真正的KuzuDB - 使用正确schema"""
import kuzu
from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"
kdb = kuzu.Database(KUZU_PATH)
conn = kuzu.Connection(kdb)

# 获取所有新事件
events = list(db.v2_business_events.find()) + list(db.email_events.find())
print(f"待导入事件: {len(events)} 条")

# 导入前统计
result = conn.execute("MATCH (e:BusinessEvent) RETURN count(e)")
before_count = result.get_next()[0]
print(f"导入前BusinessEvent: {before_count}")

# 导入BusinessEvent节点 - 使用正确的schema
added = 0
for i, e in enumerate(events):
    evt_id = f"v2_{i}_{str(e['_id'])[-8:]}"  # 短ID
    event_type = e.get("event_type", "General") or "General"
    summary = (e.get("summary", "") or "").replace('"', "'").replace("\n", " ")[:300]
    amount = float(e.get("amount", 0) or 0)
    currency = e.get("currency", "USD") or "USD"
    counterparty = (e.get("counterparty", "") or "").replace('"', "'")[:100]
    event_date = e.get("event_date", "") or ""
    created_at = datetime.now().isoformat()

    try:
        query = f'''
            CREATE (e:BusinessEvent {{
                id: "{evt_id}",
                event_type: "{event_type}",
                event_date: "{event_date}",
                summary: "{summary}",
                amount: {amount},
                currency: "{currency}",
                created_at: "{created_at}",
                direction: "unknown",
                status: "pending",
                counterparty: "{counterparty}",
                counterparty_role: "other"
            }})
        '''
        conn.execute(query)
        added += 1
        print(f"  + [{event_type}] {counterparty[:20]}")
    except Exception as ex:
        err = str(ex).lower()
        if "duplicate" not in err and "already exists" not in err and "unique" not in err:
            print(f"  错误: {str(ex)[:60]}")

print(f"\n成功导入: {added} 条")

# 导入后统计
result = conn.execute("MATCH (e:BusinessEvent) RETURN count(e)")
after_count = result.get_next()[0]
print(f"导入后BusinessEvent: {after_count}")
print(f"新增: {after_count - before_count} 条")
