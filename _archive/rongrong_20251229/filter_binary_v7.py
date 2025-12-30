#!/usr/bin/env python3
"""
Binary Filter v7 - 规则层 + LLM 层
- 规则层：快速过滤考勤类通知（补打卡、请假、值班）
- LLM层：使用 Coder 模型智能判断
- 自动切换模型（sleep/wake）
"""
import json, re, asyncio
from datetime import datetime, timedelta, timezone
import pymongo, httpx

MONGO_URI = "mongodb://localhost:27017"

# Coder 模型（非 thinking，适合结构化输出）
VLLM_URL = "http://localhost:8003/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

# Sleep/Wake 端点
SLEEP_URL_8000 = "http://localhost:8000/sleep?level=1"
WAKE_URL_8003 = "http://localhost:8003/wake_up"
STATUS_URL_8003 = "http://localhost:8003/is_sleeping"

# ========== 规则层：硬过滤 ==========
HARD_FILTER_PATTERNS = [
    r"补打卡",           # 考勤
    r"请假申请",         # 考勤
    r"值班申请",         # 考勤
    r"邮箱容量已满",      # IT 通知
]

def should_hard_filter(subject: str) -> bool:
    """规则层过滤：考勤类通知"""
    for pattern in HARD_FILTER_PATTERNS:
        if re.search(pattern, subject or ""):
            return True
    return False

# ========== 模型切换 ==========
async def switch_to_coder():
    """切换到 Coder 模型：sleep 8000, wake 8003"""
    async with httpx.AsyncClient(timeout=60) as client:
        # 先让 8000 休眠
        try:
            await client.post(SLEEP_URL_8000)
            print("  8000 (VL) → sleep")
        except:
            pass

        # 等待一下让 GPU 释放
        await asyncio.sleep(5)

        # 唤醒 8003
        try:
            await client.post(WAKE_URL_8003)
            print("  8003 (Coder) → wake")
        except:
            pass

        # 等待模型加载
        await asyncio.sleep(10)

        # 检查状态
        for _ in range(30):  # 最多等 30 秒
            try:
                r = await client.get("http://localhost:8003/v1/models", timeout=5)
                if r.status_code == 200:
                    print("  8003 ready!")
                    return True
            except:
                pass
            await asyncio.sleep(1)

        print("  警告：8003 未就绪")
        return False

# ========== LLM 层 ==========
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
4. **涉及金额的通知** - 机票、报销、发票、付款（有财务价值）
5. **样件申请、客户需求** - 核心业务流程

# 边界判断
- 来自招聘平台的简历推送 → 外部推销，FILTER
- 来自软件公司的功能介绍 → 外部推销，FILTER
- 来自展会的招商邀请 → 外部推销，FILTER
- 来自公司扫描仪的文件 → 公司设备，KEEP
- 内部审批通知（通过/驳回）→ 内部运营，KEEP
- 业务邮件的回复 → 业务相关，KEEP
- 机票/报销/发票相关 → 涉及金额，KEEP

# 邮件列表
EMAIL_PLACEHOLDER

# 输出
仅返回 JSON: [{"id": "xxx", "keep": true}, ...]
"""

async def call_vllm(prompt):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.1
        })
        data = r.json()
        if "choices" not in data:
            raise Exception(f"vLLM error: {data}")
        return data["choices"][0]["message"]["content"]

async def run_filter_async(company, date_str, days=1):
    db = pymongo.MongoClient(MONGO_URI).vulcan_brain

    d = datetime.strptime(date_str, "%Y-%m-%d")
    end_utc = datetime(d.year, d.month, d.day, 23, 0, 0, tzinfo=timezone.utc) - timedelta(days=1)
    start_utc = end_utc - timedelta(days=days)

    print(f"[Binary Filter v7] {company}")
    print(f"  范围: {(start_utc+timedelta(hours=8)).strftime('%m-%d %H:%M')} ~ {(end_utc+timedelta(hours=8)).strftime('%m-%d %H:%M')} 北京时间")

    emails = list(db.wecom_emails.find({"company": company, "received_at": {"$gte": start_utc, "$lt": end_utc}}))
    print(f"  邮件: {len(emails)} 封")

    if not emails:
        return {"KEEP": [], "FILTER": []}

    # ========== 第一层：规则过滤 ==========
    rule_filtered = []
    llm_candidates = []

    for e in emails:
        subject = e.get("subject", "")
        if should_hard_filter(subject):
            rule_filtered.append(e["email_id"])
        else:
            llm_candidates.append(e)

    print(f"  规则层过滤: {len(rule_filtered)} 封 (考勤类)")
    print(f"  进入LLM层: {len(llm_candidates)} 封")

    # ========== 切换到 Coder 模型 ==========
    print("\n  [切换模型]")
    await switch_to_coder()

    # ========== 第二层：LLM 判断 ==========
    email_list = [{
        "id": e["email_id"],
        "subject": e.get("subject", "")[:80],
        "from": (e.get("from", {}).get("address") or e.get("from", {}).get("name", ""))[:40] if isinstance(e.get("from"), dict) else "",
        "body": (e.get("body") or "")[:150]
    } for e in llm_candidates]

    llm_results = []

    for i in range(0, len(email_list), 50):
        batch = email_list[i:i+50]
        print(f"  LLM批次 {i//50+1}/{(len(email_list)+49)//50}...")
        prompt = PROMPT.replace("EMAIL_PLACEHOLDER", json.dumps(batch, ensure_ascii=False, indent=2))
        try:
            result = await call_vllm(prompt)
            m = re.search(r'\[.*\]', result, re.DOTALL)
            if m:
                llm_results.extend(json.loads(m.group()))
        except Exception as e:
            print(f"  错误: {e}")

    # ========== 汇总结果 ==========
    llm_keep = [i["id"] for i in llm_results if i.get("keep")]
    llm_filter = [i["id"] for i in llm_results if not i.get("keep")]

    keep = llm_keep
    filt = rule_filtered + llm_filter

    result = {
        "KEEP": keep,
        "FILTER": filt,
        "stats": {
            "total": len(emails),
            "keep": len(keep),
            "filter": len(filt),
            "rule_filtered": len(rule_filtered),
            "llm_filtered": len(llm_filter)
        }
    }

    db.rongrong_filter_runs.update_one(
        {"company": company, "date": date_str},
        {"$set": {
            "binary_filter_result": result,
            "binary_filter_at": datetime.now(timezone.utc),
            "filter_version": "v7"
        }},
        upsert=True
    )

    print(f"\n  === 结果 ===")
    print(f"  规则层过滤: {len(rule_filtered)}")
    print(f"  LLM层过滤: {len(llm_filter)}")
    print(f"  总计 KEEP: {len(keep)}, FILTER: {len(filt)}")
    return result

def run_filter(company, date_str, days=1):
    return asyncio.run(run_filter_async(company, date_str, days))

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--company", default="shanghai")
    p.add_argument("--date", required=True)
    p.add_argument("--days", type=int, default=1)
    args = p.parse_args()
    run_filter(args.company, args.date, args.days)
