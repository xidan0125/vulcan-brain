#!/usr/bin/env python3
"""V2 无附件邮件事件提取 - Gemini 2.5 Flash - FINAL v2"""
import json, time, requests
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
BATCH_SIZE = 10  # Reduced to avoid truncation
DELAY = 4.5

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# Use a new collection to avoid index conflicts
COLLECTION = "v2_business_events"

PROMPT = """Extract business events from emails. Return compact JSON array:
[{"idx":0,"type":"General","summary":"brief","cp":"company","dir":"in"}]

type: Inquiry/Quote/Contract/Order/Ship/Pay/General
dir: in/out/internal

Emails:
"""

def extract_batch(emails):
    texts = []
    for i, e in enumerate(emails):
        subj = e.get("subject", "")[:100]
        body = (e.get("body_clean") or e.get("body", ""))[:600]
        texts.append(f"[{i}] {subj}\n{body}")

    payload = {
        "contents": [{"parts": [{"text": PROMPT + "\n---\n".join(texts)}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}
    }

    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=90)
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        else:
            print(f"HTTP{resp.status_code}", end=" ")
    except Exception as e:
        print(f"E:{str(e)[:20]}", end=" ")
    return []

def main():
    print("=" * 50)
    print("V2 无附件邮件事件提取 (Gemini 2.5 Flash)")
    print("=" * 50)

    query = {"processing_status.v2_extracted": True, "has_attachments": False}
    total = db.emails.count_documents(query)
    print(f"待处理: {total}")

    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    est_min = batches * DELAY / 60
    print(f"批次: {batches} (size={BATCH_SIZE}), 预计: {est_min:.0f} 分钟")
    print(f"目标集合: {COLLECTION}")
    print()

    processed = extracted = 0
    start = time.time()

    cursor = db.emails.find(query, {"_id": 1, "subject": 1, "body_clean": 1, "body": 1, "received_at": 1})
    batch = []
    batch_num = 0

    for email in cursor:
        batch.append(email)
        if len(batch) >= BATCH_SIZE:
            batch_num += 1
            if batch_num % 50 == 1:
                elapsed = (time.time() - start) / 60
                rate = batch_num / elapsed if elapsed > 0 else 0
                eta = (batches - batch_num) / rate if rate > 0 else 0
                print(f"\n[{batch_num}/{batches}] 已处理:{processed} 已提取:{extracted} ETA:{eta:.0f}分钟")

            print(f"{batch_num}.", end="", flush=True)

            results = extract_batch(batch)
            batch_extracted = 0
            for r in results:
                idx = r.get("idx", -1)
                if isinstance(idx, int) and 0 <= idx < len(batch):
                    doc = batch[idx]
                    recv = doc.get("received_at")
                    date = recv.strftime("%Y-%m-%d") if isinstance(recv, datetime) else str(recv)[:10] if recv else ""

                    # Map compact fields to full names
                    event_type = r.get("type", r.get("event_type", "General"))
                    direction = r.get("dir", r.get("direction", "unknown"))
                    if direction == "in": direction = "inbound"
                    elif direction == "out": direction = "outbound"

                    db[COLLECTION].insert_one({
                        "email_id": str(doc["_id"]),
                        "event_type": event_type,
                        "event_date": date,
                        "summary": r.get("summary", ""),
                        "amount": float(r.get("amount", 0) or 0),
                        "currency": r.get("currency", "USD"),
                        "counterparty": r.get("cp", r.get("counterparty", "")) or "",
                        "direction": direction,
                        "status": r.get("status", "unknown"),
                        "source": "v2_body",
                        "extracted_at": datetime.now()
                    })
                    batch_extracted += 1
                    extracted += 1

            processed += len(batch)
            if batch_extracted > 0:
                print(f"({batch_extracted})", end=" ")
            batch = []
            time.sleep(DELAY)

    # Handle remaining batch
    if batch:
        batch_num += 1
        print(f"{batch_num}.", end="", flush=True)
        results = extract_batch(batch)
        for r in results:
            idx = r.get("idx", -1)
            if isinstance(idx, int) and 0 <= idx < len(batch):
                doc = batch[idx]
                recv = doc.get("received_at")
                date = recv.strftime("%Y-%m-%d") if isinstance(recv, datetime) else str(recv)[:10] if recv else ""

                event_type = r.get("type", r.get("event_type", "General"))
                direction = r.get("dir", r.get("direction", "unknown"))
                if direction == "in": direction = "inbound"
                elif direction == "out": direction = "outbound"

                db[COLLECTION].insert_one({
                    "email_id": str(doc["_id"]),
                    "event_type": event_type,
                    "event_date": date,
                    "summary": r.get("summary", ""),
                    "amount": float(r.get("amount", 0) or 0),
                    "currency": r.get("currency", "USD"),
                    "counterparty": r.get("cp", r.get("counterparty", "")) or "",
                    "direction": direction,
                    "status": r.get("status", "unknown"),
                    "source": "v2_body",
                    "extracted_at": datetime.now()
                })
                extracted += 1
        processed += len(batch)

    dur = time.time() - start
    print()
    print("=" * 50)
    print(f"完成! 处理: {processed}, 提取: {extracted}, 耗时: {dur/60:.1f}分钟")

    count = db[COLLECTION].count_documents({})
    print(f"集合 {COLLECTION} 总记录: {count}")

if __name__ == "__main__":
    main()
