#!/usr/bin/env python3
"""Binary Filter v7 - JSON文件输出版"""
import json, re, asyncio, os, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pymongo, httpx

MONGO_URI = "mongodb://localhost:27017"
VLLM_URL = "http://localhost:8003/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
DATA_DIR = Path.home() / "vulcan-brain" / "data" / "rongrong"

PROMPT = """# 背景
榕融新材料是一家氧化铝连续纤维生产商，客户包括航空航天、新能源汽车等行业。
你需要帮助判断哪些邮件是垃圾邮件，哪些是公司业务邮件。

# 核心原则
**宁可放过垃圾，不能漏掉业务邮件**

# 什么是垃圾邮件？（FILTER）

垃圾邮件的本质特征：
1. **发件人是外部公司**，且目的是向榕融**推销产品或服务**
2. **IT 基础设施自动通知**，与业务运营无关（如邮件备份状态、系统配置变更）

# 什么是业务邮件？（KEEP）

业务邮件的本质特征：
1. **与公司运营相关** - 客户、供应商、物流、生产、财务、人事
2. **内部沟通** - 会议、审批、通知、文件共享
3. **公司设备产生的文件** - 扫描仪发送的文件（用于存档）

# 边界判断
- 来自招聘平台的简历推送 → 外部推销，FILTER
- 来自软件公司的功能介绍 → 外部推销，FILTER
- 来自展会的招商邀请 → 外部推销，FILTER
- 来自公司扫描仪的文件 → 公司设备，KEEP
- 内部审批通知（通过/驳回）→ 内部运营，KEEP
- 业务邮件的回复 → 业务相关，KEEP

# 邮件列表
EMAIL_PLACEHOLDER

# 输出
仅返回 JSON: [{"id": "xxx", "keep": true}, ...]
"""

async def call_vllm(prompt):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(VLLM_URL, json={"model": VLLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 4096, "temperature": 0.1})
        return r.json()["choices"][0]["message"]["content"]

def save_json_atomic(filepath: Path, data: dict):
    """原子写入JSON文件（临时文件+重命名）"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=filepath.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
    except Exception:
        os.unlink(tmp_path)
        raise

def run_filter(company, date_str, days=1):
    db = pymongo.MongoClient(MONGO_URI).vulcan_brain
    
    d = datetime.strptime(date_str, "%Y-%m-%d")
    end_utc = datetime(d.year, d.month, d.day, 23, 0, 0, tzinfo=timezone.utc) - timedelta(days=1)
    start_utc = end_utc - timedelta(days=days)
    
    print(f"[Binary Filter v7] {company}")
    print(f"  范围: {(start_utc+timedelta(hours=8)).strftime('%m-%d %H:%M')} ~ {(end_utc+timedelta(hours=8)).strftime('%m-%d %H:%M')} 北京时间")
    
    emails = list(db.wecom_emails.find({"company": company, "received_at": {"$gte": start_utc, "$lt": end_utc}}))
    print(f"  邮件: {len(emails)} 封")
    
    if not emails:
        return {"keep_ids": [], "filter_ids": [], "stats": {"total": 0, "keep": 0, "filter": 0}}
    
    email_list = [{"id": e["email_id"], "subject": e.get("subject", "")[:80], 
                   "from": (e.get("from", {}).get("address") or e.get("from", {}).get("name", ""))[:40] if isinstance(e.get("from"), dict) else "",
                   "body": (e.get("body") or "")[:150]} for e in emails]
    
    all_results = []
    
    async def process():
        nonlocal all_results
        for i in range(0, len(email_list), 50):
            batch = email_list[i:i+50]
            print(f"  批次 {i//50+1}/{(len(email_list)+49)//50}...")
            prompt = PROMPT.replace("EMAIL_PLACEHOLDER", json.dumps(batch, ensure_ascii=False, indent=2))
            try:
                result = await call_vllm(prompt)
                m = re.search(r'\[.*\]', result, re.DOTALL)
                if m: all_results.extend(json.loads(m.group()))
            except Exception as e:
                print(f"  错误: {e}")
    
    asyncio.run(process())
    
    keep_ids = [i["id"] for i in all_results if i.get("keep")]
    filter_ids = [i["id"] for i in all_results if not i.get("keep")]
    
    # 构造JSON输出
    json_output = {
        "date": date_str,
        "company": company,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": "v1.0",
        "stats": {
            "total_emails": len(emails),
            "keep": len(keep_ids),
            "filter": len(filter_ids)
        },
        "keep_ids": keep_ids,
        "filter_ids": filter_ids
    }
    
    # 保存到JSON文件（覆盖式）
    json_path = DATA_DIR / company / date_str / "01_filter.json"
    save_json_atomic(json_path, json_output)
    print(f"  JSON: {json_path}")
    
    # 同时保存到MongoDB（兼容旧系统）
    db.rongrong_filter_runs.update_one(
        {"company": company, "date": date_str},
        {"$set": {
            "binary_filter_result": {"KEEP": keep_ids, "FILTER": filter_ids, "stats": json_output["stats"]},
            "binary_filter_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    print(f"\n  结果: KEEP {len(keep_ids)}, FILTER {len(filter_ids)}")
    return json_output

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--company", default="shanghai")
    p.add_argument("--date", required=True)
    p.add_argument("--days", type=int, default=1)
    args = p.parse_args()
    run_filter(args.company, args.date, args.days)
