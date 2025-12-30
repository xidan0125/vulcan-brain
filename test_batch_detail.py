#!/usr/bin/env python3
"""Detailed batch test"""
import json, requests
from pymongo import MongoClient

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# Get 20 emails - same as batch
query = {"processing_status.v2_extracted": True, "has_attachments": False}
emails = list(db.emails.find(query, {"_id": 1, "subject": 1, "body_clean": 1, "body": 1}).limit(20))

print(f"Got {len(emails)} emails")
print(f"Sample subjects:")
for i, e in enumerate(emails[:3]):
    print(f"  {i}: {e.get('subject', '')[:50]}")

PROMPT = """Analyze emails and extract business events. Return JSON array with one object per email:
[{"idx": 0, "event_type": "Inquiry/Quotation/Contract/Order/Shipment/Payment/General", "summary": "brief English summary", "amount": 0, "currency": "USD", "counterparty": "company name", "direction": "inbound/outbound/internal", "status": "pending/completed"}]

Emails:
"""

texts = []
for i, e in enumerate(emails):
    subj = e.get("subject", "")
    body = (e.get("body_clean") or e.get("body", ""))[:1200]
    texts.append(f"--- Email {i} ---\nSubject: {subj}\n{body}")

payload = {
    "contents": [{"parts": [{"text": PROMPT + "\n".join(texts)}]}],
    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
}

print(f"\nSending request with {len(texts)} emails...")
resp = requests.post(GEMINI_URL, json=payload, timeout=90)
print(f"HTTP: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    # Parse JSON
    start = text.find("[")
    end = text.rfind("]")

    if start >= 0 and end > start:
        json_str = text[start:end+1]
        results = json.loads(json_str)
        print(f"\nParsed {len(results)} events")

        # Check each result
        valid = 0
        for r in results:
            idx = r.get("idx", -1)
            if isinstance(idx, int) and 0 <= idx < len(emails):
                valid += 1
            else:
                print(f"  Invalid idx: {idx} (type: {type(idx).__name__})")

        print(f"Valid idx count: {valid}/{len(results)}")
        print(f"\nFirst 3 results:")
        for r in results[:3]:
            print(f"  {r}")
    else:
        print(f"No JSON array found: start={start}, end={end}")
        print(f"Text preview: {text[:300]}")
