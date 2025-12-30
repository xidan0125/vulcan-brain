#!/usr/bin/env python3
"""测试筛选逻辑"""
import json, requests
from pymongo import MongoClient

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# 取10封测试
query = {"processing_status.v2_extracted": True, "has_attachments": False}
emails = list(db.emails.find(query, {"subject": 1, "body_clean": 1, "body": 1}).limit(10))

print("邮件主题:")
for i, e in enumerate(emails):
    print(f"  [{i}] {e.get('subject', '')[:60]}")

PROMPT = """Classify each email. Return JSON array with keep=true for business emails, keep=false for spam/marketing/notifications.

Business emails: inquiries, quotations, orders, shipments, payments, contracts, customer communication
Non-business: marketing, newsletters, OTP, LinkedIn, system alerts, automated notifications

Format: [{"idx":0,"keep":true},{"idx":1,"keep":false},...]

Emails:
"""

texts = []
for i, e in enumerate(emails):
    subj = e.get("subject", "")[:80]
    body = (e.get("body_clean") or e.get("body", ""))[:200]
    texts.append(f"[{i}] {subj}")

payload = {
    "contents": [{"parts": [{"text": PROMPT + "\n".join(texts)}]}],
    "generationConfig": {"temperature": 0, "maxOutputTokens": 2048}
}

resp = requests.post(GEMINI_URL, json=payload, timeout=60)
print(f"\nHTTP: {resp.status_code}")
if resp.status_code == 200:
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    print(f"响应:\n{text[:800]}")

    # 解析
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        results = json.loads(text[start:end+1])
        kept = [r["idx"] for r in results if r.get("keep") == True]
        print(f"\n保留索引: {kept}")
        print(f"保留数量: {len(kept)}/10")
