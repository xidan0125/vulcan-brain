#!/usr/bin/env python3
"""ETL新事件到真正的KuzuDB"""
import kuzu
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# 正确的KuzuDB路径
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

# 导入BusinessEvent节点
added = 0
for e in events:
    event_id = f"v2_{str(e['_id'])}"  # 加前缀避免冲突
    event_type = e.get("event_type", "General") or "General"
    summary = (e.get("summary", "") or "").replace('"', '').replace("'", "").replace("\n", " ")[:200]
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
        err = str(ex).lower()
        if "duplicate" not in err and "already exists" not in err and "unique" not in err:
            print(f"  错误: {str(ex)[:60]}")

print(f"成功导入: {added} 条")

# 导入后统计
result = conn.execute("MATCH (e:BusinessEvent) RETURN count(e)")
after_count = result.get_next()[0]
print(f"导入后BusinessEvent: {after_count}")
print(f"新增: {after_count - before_count} 条")
