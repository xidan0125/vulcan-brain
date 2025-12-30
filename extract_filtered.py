#!/usr/bin/env python3
"""提取筛选后的45封邮件"""
import json, time, requests
from pymongo import MongoClient
from datetime import datetime

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# 清理旧数据
db.v2_business_events.delete_many({})

# 获取筛选保留的邮件
emails = list(db.emails.find({"v2_filter.keep": True}, {"_id": 1, "subject": 1, "body_clean": 1, "body": 1, "received_at": 1}))
print(f"待提取: {len(emails)} 封")

PROMPT = """Extract business event from each email. Return JSON array:
[{"idx":0,"type":"Inquiry/Quote/Order/Ship/Pay/Contract","summary":"brief description","cp":"company name","amount":0}]

Emails:
"""

BATCH = 10
total = 0

for i in range(0, len(emails), BATCH):
    batch = emails[i:i+BATCH]
    texts = []
    for j, e in enumerate(batch):
        subj = e.get("subject", "")[:100]
        body = (e.get("body_clean") or e.get("body", ""))[:600]
        texts.append(f"[{j}] Subject: {subj}\n{body}")

    payload = {
        "contents": [{"parts": [{"text": PROMPT + "\n---\n".join(texts)}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
    }

    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=90)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            start, end = text.find("["), text.rfind("]")
            if start >= 0 and end > start:
                results = json.loads(text[start:end+1])
                for r in results:
                    idx = r.get("idx", -1)
                    if isinstance(idx, int) and 0 <= idx < len(batch):
                        doc = batch[idx]
                        recv = doc.get("received_at")
                        date = recv.strftime("%Y-%m-%d") if isinstance(recv, datetime) else str(recv)[:10] if recv else ""

                        db.v2_business_events.insert_one({
                            "email_id": str(doc["_id"]),
                            "event_type": r.get("type", "General"),
                            "event_date": date,
                            "summary": r.get("summary", ""),
                            "amount": float(r.get("amount", 0) or 0),
                            "currency": r.get("currency", "USD"),
                            "counterparty": r.get("cp", "") or "",
                            "source": "v2_filtered",
                            "extracted_at": datetime.now()
                        })
                        total += 1
                print(f"批次{i//BATCH + 1}: 提取{len(results)}条")
    except Exception as e:
        print(f"Error: {e}")

    time.sleep(3)

print(f"\n完成! 共提取 {total} 条事件")
print(f"数据库记录: {db.v2_business_events.count_documents({})}")

# 显示样本
print("\n样本:")
for doc in db.v2_business_events.find().limit(5):
    print(f"  [{doc['event_type']}] {doc['summary'][:50]} | {doc['counterparty']}")
