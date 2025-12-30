#!/usr/bin/env python3
"""ETL事件到KuzuDB"""
import kuzu
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# 连接KuzuDB
kdb = kuzu.Database("./kuzu_email_intel")
conn = kuzu.Connection(kdb)

# 获取所有事件
events = list(db.v2_business_events.find()) + list(db.email_events.find())
print(f"待导入事件: {len(events)} 条")

# 导入BusinessEvent节点
added = 0
for e in events:
    event_id = str(e["_id"])
    event_type = e.get("event_type", "General")
    summary = (e.get("summary", "") or "").replace('"', '').replace("'", "")[:200]
    amount = float(e.get("amount", 0) or 0)
    currency = e.get("currency", "USD") or "USD"
    counterparty = (e.get("counterparty", "") or "").replace('"', '').replace("'", "")[:100]
    event_date = e.get("event_date", "") or ""

    try:
        query = f'''
            CREATE (e:BusinessEvent {{
                event_id: "{event_id}",
                event_type: "{event_type}",
                summary: "{summary}",
                amount: {amount},
                currency: "{currency}",
                counterparty: "{counterparty}",
                event_date: "{event_date}",
                source: "v2_filtered"
            }})
        '''
        conn.execute(query)
        added += 1
    except Exception as ex:
        if "already exists" not in str(ex).lower() and "duplicate" not in str(ex).lower():
            print(f"Error: {ex}")

print(f"成功导入: {added} 条")

# 统计
result = conn.execute("MATCH (e:BusinessEvent) RETURN count(e) as cnt")
while result.has_next():
    print(f"KuzuDB BusinessEvent总数: {result.get_next()[0]}")
