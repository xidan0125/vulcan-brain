#!/usr/bin/env python3
"""V2 无附件邮件事件提取 - Gemini 2.5 Flash - DEBUG"""
import json, time, re, requests
from pymongo import MongoClient
from datetime import datetime

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
BATCH_SIZE = 20
DELAY = 4.5

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

PROMPT = """Analyze emails and extract business events. Return JSON array with one object per email:
[{"idx": 0, "event_type": "Inquiry/Quotation/Contract/Order/Shipment/Payment/General", "summary": "brief English summary", "amount": 0, "currency": "USD", "counterparty": "company name", "direction": "inbound/outbound/internal", "status": "pending/completed"}]

Emails:
"""

def extract_batch(emails):
    texts = []
    for i, e in enumerate(emails):
        subj = e.get("subject", "")
        body = (e.get("body_clean") or e.get("body", ""))[:1200]
        texts.append(f"--- Email {i} ---\nSubject: {subj}\n{body}")

    payload = {
        "contents": [{"parts": [{"text": PROMPT + "\n".join(texts)}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
    }

    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=90)
        print(f"[DEBUG] HTTP status: {resp.status_code}", end=" ")
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Parse JSON
            text_clean = re.sub(r'```json\s*', '', text)
            text_clean = re.sub(r'```\s*', '', text_clean)
            start = text_clean.find('[')
            end = text_clean.rfind(']') + 1
            if start >= 0 and end > start:
                try:
                    results = json.loads(text_clean[start:end])
                    print(f"[DEBUG] Parsed {len(results)} items", end=" ")
                    return results
                except json.JSONDecodeError as je:
                    print(f"[DEBUG] JSON error: {je}", end=" ")
            else:
                print(f"[DEBUG] No JSON array found in: {text[:100]}", end=" ")
        return []
    except Exception as e:
        print(f"[DEBUG] Exception: {e}", end=" ")
        return []

def main():
    print("=" * 50)
    print("V2 无附件邮件事件提取 (DEBUG)")
    print("=" * 50)

    query = {"processing_status.v2_extracted": True, "has_attachments": False}
    total = db.emails.count_documents(query)
    print(f"待处理: {total}")

    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"批次: {batches}")
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
            print(f"\n批次 {batch_num}/{batches}...", flush=True)

            results = extract_batch(batch)
            batch_extracted = 0
            for r in results:
                idx = r.get("idx", 0)
                if isinstance(idx, int) and idx < len(batch):
                    doc = batch[idx]
                    recv = doc.get("received_at")
                    date = recv.strftime("%Y-%m-%d") if isinstance(recv, datetime) else str(recv)[:10] if recv else ""

                    db.entities_v3.insert_one({
                        "email_id": str(doc["_id"]),
                        "event_type": r.get("event_type", "General"),
                        "event_date": date,
                        "summary": r.get("summary", ""),
                        "amount": float(r.get("amount") or 0),
                        "currency": r.get("currency", "USD"),
                        "counterparty": r.get("counterparty") or "",
                        "counterparty_role": "other",
                        "direction": r.get("direction", "unknown"),
                        "status": r.get("status", "unknown"),
                        "source": "v2_body",
                        "extracted_at": datetime.now()
                    })
                    batch_extracted += 1
                    extracted += 1

            processed += len(batch)
            print(f"-> Extracted: {batch_extracted}/{len(results)}")
            batch = []

            # 只运行3批用于测试
            if batch_num >= 3:
                print("\n[DEBUG] Stopping after 3 batches for testing")
                break

            time.sleep(DELAY)

    dur = time.time() - start
    print()
    print("=" * 50)
    print(f"完成! 处理: {processed}, 提取: {extracted}, 耗时: {dur/60:.1f}分钟")

    # 验证数据库
    count = db.entities_v3.count_documents({"source": "v2_body"})
    print(f"数据库中 v2_body 记录: {count}")

if __name__ == "__main__":
    main()
