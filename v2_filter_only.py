#!/usr/bin/env python3
"""V2 邮件快速筛选 - 只标记，不提取"""
import json, time, requests
from pymongo import MongoClient

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

BATCH_SIZE = 50  # 大批量快速筛选
DELAY = 3  # 3秒延迟

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

FILTER_PROMPT = """Classify emails. Return JSON: [{"idx":0,"keep":true/false}]

keep=true: business emails (inquiries, quotes, orders, shipments, payments, contracts, customer/supplier)
keep=false: marketing, newsletters, OTP, LinkedIn, system alerts, notifications, promotions, spam

Emails:
"""

def filter_batch(emails):
    texts = [f"[{i}] {e.get('subject', '')[:80]}" for i, e in enumerate(emails)]

    payload = {
        "contents": [{"parts": [{"text": FILTER_PROMPT + "\n".join(texts)}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2048}
    }

    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            start, end = text.find("["), text.rfind("]")
            if start >= 0 and end > start:
                results = json.loads(text[start:end+1])
                return {r["idx"]: r.get("keep") in [True, "true", 1] for r in results}
    except Exception as e:
        print(f"Err:{str(e)[:15]}", end=" ")
    return {}

def main():
    print("=" * 50)
    print("V2 邮件快速筛选")
    print("=" * 50)

    query = {"processing_status.v2_extracted": True, "has_attachments": False}
    total = db.emails.count_documents(query)
    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    est_min = batches * DELAY / 60

    print(f"待筛选: {total} 封")
    print(f"批量: {BATCH_SIZE}, 批次: {batches}, 预计: {est_min:.0f} 分钟")
    print()

    total_scanned = 0
    total_kept = 0
    start_time = time.time()

    cursor = db.emails.find(query, {"_id": 1, "subject": 1})
    batch = []
    batch_num = 0

    for email in cursor:
        batch.append(email)

        if len(batch) >= BATCH_SIZE:
            batch_num += 1
            total_scanned += len(batch)

            if batch_num % 20 == 1:
                elapsed = (time.time() - start_time) / 60
                rate = total_scanned / elapsed if elapsed > 0 else 0
                eta = (total - total_scanned) / rate if rate > 0 else 0
                keep_pct = (total_kept / total_scanned * 100) if total_scanned > 0 else 0
                print(f"\n[{batch_num}/{batches}] 已扫描:{total_scanned} 保留:{total_kept}({keep_pct:.0f}%) ETA:{eta:.0f}分钟")

            print(f"{batch_num}.", end="", flush=True)

            results = filter_batch(batch)
            kept = 0

            for idx, keep in results.items():
                if idx < len(batch):
                    email_id = batch[idx]["_id"]
                    db.emails.update_one(
                        {"_id": email_id},
                        {"$set": {"v2_filter": {"keep": keep, "filtered_at": time.time()}}}
                    )
                    if keep:
                        kept += 1

            total_kept += kept
            print(f"[{kept}]", end=" ", flush=True)
            batch = []
            time.sleep(DELAY)

    # 剩余
    if batch:
        batch_num += 1
        total_scanned += len(batch)
        results = filter_batch(batch)
        for idx, keep in results.items():
            if idx < len(batch):
                db.emails.update_one(
                    {"_id": batch[idx]["_id"]},
                    {"$set": {"v2_filter": {"keep": keep, "filtered_at": time.time()}}}
                )
                if keep:
                    total_kept += 1

    duration = (time.time() - start_time) / 60
    keep_pct = (total_kept / total_scanned * 100) if total_scanned > 0 else 0

    print()
    print("=" * 50)
    print(f"完成!")
    print(f"  扫描: {total_scanned}")
    print(f"  保留: {total_kept} ({keep_pct:.1f}%)")
    print(f"  过滤: {total_scanned - total_kept}")
    print(f"  耗时: {duration:.1f} 分钟")
    print("=" * 50)

if __name__ == "__main__":
    main()
