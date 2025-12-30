#!/usr/bin/env python3
"""V2 邮件筛选+提取 - 两阶段方案 v2"""
import json, time, requests
from pymongo import MongoClient
from datetime import datetime

GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

FILTER_BATCH_SIZE = 30
EXTRACT_BATCH_SIZE = 10
DELAY = 4.5

client = MongoClient("mongodb://localhost:27017/")
db = client["vulcan_brain"]

# ============ 阶段1: 筛选 ============
FILTER_PROMPT = """Classify each email. Return JSON array with keep=true for business emails, keep=false for spam/marketing/notifications.

Business: inquiries, quotations, orders, shipments, payments, contracts, customer/supplier communication
Non-business: marketing, newsletters, OTP, LinkedIn, system alerts, automated notifications, promotions

Format: [{"idx":0,"keep":true},{"idx":1,"keep":false},...]

Emails:
"""

def parse_json(text):
    """从响应中提取JSON数组"""
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
    return []

def filter_batch(emails):
    """快速筛选，返回值得提取的邮件索引"""
    texts = []
    for i, e in enumerate(emails):
        subj = e.get("subject", "")[:80]
        texts.append(f"[{i}] {subj}")

    payload = {
        "contents": [{"parts": [{"text": FILTER_PROMPT + "\n".join(texts)}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2048}
    }

    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            results = parse_json(text)
            # 兼容 keep=True 和 keep=true
            return [r["idx"] for r in results if r.get("keep") in [True, "true", 1]]
    except Exception as e:
        print(f"F-Err:{str(e)[:15]}", end=" ")
    return []

# ============ 阶段2: 提取 ============
EXTRACT_PROMPT = """Extract business event from each email. Return JSON array:
[{"idx":0,"type":"Inquiry/Quote/Order/Ship/Pay/Contract","summary":"brief description","cp":"company name","amount":0}]

Emails:
"""

def extract_batch(emails):
    """详细提取业务事件"""
    texts = []
    for i, e in enumerate(emails):
        subj = e.get("subject", "")[:100]
        body = (e.get("body_clean") or e.get("body", ""))[:600]
        texts.append(f"[{i}] Subject: {subj}\n{body}")

    payload = {
        "contents": [{"parts": [{"text": EXTRACT_PROMPT + "\n---\n".join(texts)}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
    }

    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=90)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return parse_json(text)
    except Exception as e:
        print(f"E-Err:{str(e)[:15]}", end=" ")
    return []

# ============ 主流程 ============
def main():
    print("=" * 60)
    print("V2 邮件筛选+提取 (两阶段)")
    print("=" * 60)

    # 清理之前的数据
    deleted = db.v2_business_events.delete_many({}).deleted_count
    print(f"已清理旧数据: {deleted} 条")

    query = {"processing_status.v2_extracted": True, "has_attachments": False}
    total = db.emails.count_documents(query)
    print(f"待处理邮件: {total}")
    print(f"筛选批量: {FILTER_BATCH_SIZE}, 提取批量: {EXTRACT_BATCH_SIZE}")
    print()

    total_scanned = 0
    total_kept = 0
    total_extracted = 0
    start_time = time.time()

    cursor = db.emails.find(query, {"_id": 1, "subject": 1, "body_clean": 1, "body": 1, "received_at": 1})
    filter_batch_emails = []
    batch_num = 0

    for email in cursor:
        filter_batch_emails.append(email)

        if len(filter_batch_emails) >= FILTER_BATCH_SIZE:
            batch_num += 1
            total_scanned += len(filter_batch_emails)

            if batch_num % 20 == 1:
                elapsed = (time.time() - start_time) / 60
                keep_rate = (total_kept / total_scanned * 100) if total_scanned > 0 else 0
                print(f"\n[{batch_num}] 扫描:{total_scanned} 保留:{total_kept}({keep_rate:.0f}%) 提取:{total_extracted} {elapsed:.1f}分钟")

            print(f"{batch_num}.", end="", flush=True)

            # 阶段1: 筛选
            keep_indices = filter_batch(filter_batch_emails)
            kept_emails = [filter_batch_emails[i] for i in keep_indices if i < len(filter_batch_emails)]
            total_kept += len(kept_emails)

            if kept_emails:
                print(f"[{len(kept_emails)}]", end="", flush=True)

                # 阶段2: 提取
                for i in range(0, len(kept_emails), EXTRACT_BATCH_SIZE):
                    sub_batch = kept_emails[i:i+EXTRACT_BATCH_SIZE]
                    results = extract_batch(sub_batch)

                    for r in results:
                        idx = r.get("idx", -1)
                        if isinstance(idx, int) and 0 <= idx < len(sub_batch):
                            doc = sub_batch[idx]
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
                            total_extracted += 1

                    time.sleep(DELAY)
            else:
                print("[0]", end="", flush=True)

            filter_batch_emails = []
            time.sleep(DELAY)

    # 处理剩余
    if filter_batch_emails:
        batch_num += 1
        total_scanned += len(filter_batch_emails)
        keep_indices = filter_batch(filter_batch_emails)
        kept_emails = [filter_batch_emails[i] for i in keep_indices if i < len(filter_batch_emails)]
        total_kept += len(kept_emails)

        if kept_emails:
            results = extract_batch(kept_emails)
            for r in results:
                idx = r.get("idx", -1)
                if isinstance(idx, int) and 0 <= idx < len(kept_emails):
                    doc = kept_emails[idx]
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
                    total_extracted += 1

    duration = (time.time() - start_time) / 60
    keep_rate = (total_kept / total_scanned * 100) if total_scanned > 0 else 0

    print()
    print("=" * 60)
    print(f"完成!")
    print(f"  扫描: {total_scanned} 封邮件")
    print(f"  保留: {total_kept} 封 ({keep_rate:.1f}%)")
    print(f"  提取: {total_extracted} 条事件")
    print(f"  耗时: {duration:.1f} 分钟")
    print("=" * 60)

if __name__ == "__main__":
    main()
