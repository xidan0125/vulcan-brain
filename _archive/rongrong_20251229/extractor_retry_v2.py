#!/usr/bin/env python3
"""
Extractor Retry v2 - 带 KV cache 冷却
- 每封邮件后 sleep 1s 让 cache 释放
- 每 30 封后 sleep 10s 深度冷却
"""
import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')

from project_rongrong.extractor import process_email, MONGO_URI
from datetime import datetime, timezone
import pymongo

# KV cache 管理参数
SLEEP_PER_EMAIL = 1      # 每封邮件后等待秒数
BATCH_SIZE = 30          # 每批邮件数
SLEEP_PER_BATCH = 10     # 每批后深度冷却秒数

async def run_retry(company: str, date_str: str):
    db = pymongo.MongoClient(MONGO_URI).vulcan_brain

    # 获取失败的邮件 ID
    run_doc = db.rongrong_filter_runs.find_one({"company": company, "date": date_str})
    if not run_doc:
        print("未找到记录")
        return

    failed_ids = run_doc.get("extraction_failed_ids", [])
    print(f"[Retry v2] {len(failed_ids)} 封失败邮件")
    print(f"[配置] 每封等待 {SLEEP_PER_EMAIL}s, 每 {BATCH_SIZE} 封深度冷却 {SLEEP_PER_BATCH}s")

    if not failed_ids:
        print("无失败邮件")
        return

    # 获取邮件
    emails = list(db.wecom_emails.find({"email_id": {"$in": failed_ids}}))

    # 获取现有结果
    results = run_doc.get("extraction_results", {
        "CUSTOMER": [], "SUPPLY_CHAIN": [], "LOGISTICS": [],
        "MANAGEMENT": [], "ADMIN": [], "FILE": []
    })

    still_failed = []
    new_success = 0

    for i, email in enumerate(emails):
        subj = (email.get("subject") or "")[:35]
        img_count = len([a for a in email.get("processed_assets", []) if a.get("asset_type") == "image"])
        print(f"[{i+1}/{len(emails)}] {subj}... ({img_count}图)", end=" ", flush=True)

        try:
            extracted = await process_email(email)
            if extracted:
                cat = extracted.get("category", "FILE")
                if cat not in results:
                    cat = "FILE"
                results[cat].append(extracted)
                style = extracted.get("style") or "-"
                print(f"→ {cat} | {extracted.get('tag', '?')} | {style}")
                new_success += 1
            else:
                still_failed.append(email.get("email_id"))
                print("→ 解析失败")
        except Exception as e:
            still_failed.append(email.get("email_id"))
            err_msg = str(e)[:50]
            print(f"→ 错误: {err_msg}")

        # 每封邮件后等待，让 KV cache 释放
        await asyncio.sleep(SLEEP_PER_EMAIL)

        # 每处理 10 封保存一次
        if (i + 1) % 10 == 0:
            stats = {k: len(v) for k, v in results.items()}
            total = sum(stats.values())
            db.rongrong_filter_runs.update_one(
                {"company": company, "date": date_str},
                {"$set": {
                    "extraction_at": datetime.now(timezone.utc),
                    "extraction_results": results,
                    "extraction_stats": {"total": total, "by_category": stats, "failed": len(still_failed)},
                    "extraction_failed_ids": still_failed
                }}
            )
            print(f"  [已保存 - 成功: {total}]")

        # 每 BATCH_SIZE 封后深度冷却
        if (i + 1) % BATCH_SIZE == 0:
            print(f"  [深度冷却 {SLEEP_PER_BATCH}s...]")
            await asyncio.sleep(SLEEP_PER_BATCH)

    # 最终统计
    stats = {k: len(v) for k, v in results.items()}
    total = sum(stats.values())

    print(f"\n=== Retry 完成 ===")
    print(f"新成功: {new_success}")
    print(f"总成功: {total}/{len(run_doc['binary_filter_result']['KEEP'])}")
    for k, v in stats.items():
        if v > 0:
            print(f"  {k}: {v}")
    if still_failed:
        print(f"仍失败: {len(still_failed)}")

    # 保存
    db.rongrong_filter_runs.update_one(
        {"company": company, "date": date_str},
        {"$set": {
            "extraction_at": datetime.now(timezone.utc),
            "extraction_results": results,
            "extraction_stats": {"total": total, "by_category": stats, "failed": len(still_failed)},
            "extraction_failed_ids": still_failed
        }}
    )
    print("已保存")


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"
    asyncio.run(run_retry(company, date_str))
