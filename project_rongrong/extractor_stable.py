#!/usr/bin/env python3
"""
Extractor 稳定版 - 带 KV cache 冷却
- 每封邮件后 3s 冷却
- 每 20 封后 30s 深度冷却
"""
import asyncio
import json
import re
import os
import base64
from datetime import datetime, timezone
from typing import Dict, List, Optional
import pymongo
import httpx

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
PROCESSED_ASSETS_ROOT = "/home/xinyue/vulcan-brain/data/processed_assets"
MAX_IMAGES = 5

# 冷却参数
SLEEP_PER_EMAIL = 3
BATCH_SIZE = 20
SLEEP_PER_BATCH = 30

# Qwen3 参数
VLLM_PARAMS = {
    "temperature": 0.6,
    "top_p": 0.95,
    "max_tokens": 30000
}

PROMPT_TEMPLATE = """# Context
你是榕融新材料的业务分析 AI。
- 公司主营：氧化铝纤维、导热材料
- 核心客户：比亚迪、宁德时代、航空航天

# Task
分析邮件（含附件图片），返回 JSON。

主题: {subject}
发件人: {sender}
正文: {body}

附件: {attachments}

# Format
仅返回一个 JSON 对象:
{{"category": "CUSTOMER|SUPPLY_CHAIN|LOGISTICS|MANAGEMENT|ADMIN|FILE", "tag": "4字业务动作", "style": "GAIN|RISK|INSIGHT|LOG|null", "summary": "一句话总结"}}

分类定义:
- CUSTOMER: 客户相关（询价、报价、样件、订单、审厂）
- SUPPLY_CHAIN: 供应链（采购、生产、质量）
- LOGISTICS: 物流（发货、报关、订舱、货运）
- MANAGEMENT: 管理（会议、考核、安全、财务决策）
- ADMIN: 行政（打卡、请假、报销、审批通知）
- FILE: 纯文件传输（扫描件、无业务语义）

ADMIN/FILE 的 style 设为 null。
"""


def extract_first_json(text: str) -> Optional[Dict]:
    """提取第一个完整 JSON（括号计数法）"""
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i, c in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def load_image_base64(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except:
        return None


def build_content_parts(email: Dict, prompt: str) -> List[Dict]:
    parts = []
    img_count = 0
    for asset in email.get("processed_assets", []):
        if img_count >= MAX_IMAGES:
            break
        if asset.get("asset_type") == "image":
            path = os.path.join(PROCESSED_ASSETS_ROOT, asset.get("asset_path", ""))
            img_b64 = load_image_base64(path)
            if img_b64:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
                img_count += 1
    parts.append({"type": "text", "text": prompt})
    return parts


async def call_vllm(content_parts: List[Dict]) -> str:
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": content_parts}],
            **VLLM_PARAMS
        })
        data = r.json()
        if "choices" not in data:
            raise Exception(f"vLLM error: {data}")
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content.strip()


async def process_email(email: Dict) -> Optional[Dict]:
    email_id = email.get("email_id", "")
    subject = email.get("subject", "") or "(无主题)"
    sender = email.get("from", "")
    if isinstance(sender, dict):
        sender = sender.get("name") or sender.get("address", "")
    body = (email.get("body", "") or "")[:2000]
    att_names = [a.get("filename", "") for a in email.get("attachments", [])]
    attachments = ", ".join(att_names[:5]) if att_names else "无"

    prompt = PROMPT_TEMPLATE.format(
        subject=subject, sender=sender, body=body, attachments=attachments
    )
    content_parts = build_content_parts(email, prompt)
    result = await call_vllm(content_parts)
    parsed = extract_first_json(result)
    if parsed:
        parsed["source_id"] = email_id
        # 修复 style: "null" → null
        if parsed.get("style") == "null":
            parsed["style"] = None
        return parsed
    return None


async def run(company: str, date_str: str):
    db = pymongo.MongoClient(MONGO_URI).vulcan_brain

    run_doc = db.rongrong_filter_runs.find_one({"company": company, "date": date_str})
    if not run_doc or "binary_filter_result" not in run_doc:
        print("未找到 filter 结果")
        return

    keep_ids = run_doc["binary_filter_result"]["KEEP"]
    print(f"[Extractor 稳定版] {len(keep_ids)} 封邮件")
    print(f"[配置] 每封 {SLEEP_PER_EMAIL}s, 每 {BATCH_SIZE} 封冷却 {SLEEP_PER_BATCH}s")

    emails = list(db.wecom_emails.find({"email_id": {"$in": keep_ids}}))

    results = {"CUSTOMER": [], "SUPPLY_CHAIN": [], "LOGISTICS": [], "MANAGEMENT": [], "ADMIN": [], "FILE": []}
    failed = []

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
            else:
                failed.append(email.get("email_id"))
                print("→ 解析失败")
        except Exception as e:
            failed.append(email.get("email_id"))
            print(f"→ 错误: {str(e)[:50]}")

        # 冷却
        await asyncio.sleep(SLEEP_PER_EMAIL)

        # 每 10 封保存
        if (i + 1) % 10 == 0:
            stats = {k: len(v) for k, v in results.items()}
            total = sum(stats.values())
            db.rongrong_filter_runs.update_one(
                {"company": company, "date": date_str},
                {"$set": {
                    "extraction_at": datetime.now(timezone.utc),
                    "extraction_results": results,
                    "extraction_stats": {"total": total, "by_category": stats, "failed": len(failed)},
                    "extraction_failed_ids": failed
                }}
            )
            print(f"  [已保存 - 成功: {total}]")

        # 深度冷却
        if (i + 1) % BATCH_SIZE == 0:
            print(f"  [深度冷却 {SLEEP_PER_BATCH}s...]")
            await asyncio.sleep(SLEEP_PER_BATCH)

    # 最终保存
    stats = {k: len(v) for k, v in results.items()}
    total = sum(stats.values())

    print(f"\n=== 完成 ===")
    print(f"成功: {total}/{len(emails)}")
    for k, v in stats.items():
        if v > 0:
            print(f"  {k}: {v}")
    if failed:
        print(f"失败: {len(failed)}")

    db.rongrong_filter_runs.update_one(
        {"company": company, "date": date_str},
        {"$set": {
            "extraction_at": datetime.now(timezone.utc),
            "extraction_results": results,
            "extraction_stats": {"total": total, "by_category": stats, "failed": len(failed)},
            "extraction_failed_ids": failed
        }}
    )
    print("已保存")


if __name__ == "__main__":
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"
    asyncio.run(run(company, date_str))
