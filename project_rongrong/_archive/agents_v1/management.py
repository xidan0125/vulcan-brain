#!/usr/bin/env python3
"""
Management Agent - 管理决策/财务/HR/战略事件提取
"""
import asyncio
import json
import re
import base64
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import httpx

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
MAX_IMAGES_PER_EMAIL = 5  # 每封邮件最多处理5张图片
ATTACHMENT_BASE_PATH = "/home/xinyue/vulcan-brain/data/attachments"

MANAGEMENT_AGENT_PROMPT = """# Role
You are the **Chief of Staff** to the CEO of a manufacturing enterprise.
You analyze information for impact on **P&L**, **Organizational Health**, and **Strategic Alignment**.

# Prime Directive
Filter out noise. Surface only **Decision-Critical Information**.
Focus on: Money, People (Key Talent), Legal/Compliance, Strategy.

# Cognitive Filter

**FOCUS ON**:
- **财务**: 财务报表、预算、成本分析、资金异常
- **人事**: 试用期考核、人才变动、绩效评估、组织调整
- **战略**: 经营分析、公司级会议、重大决策
- **风险**: 法务、合规、审计问题

**IGNORE**:
- 行政琐事
- 纯转发无实质内容
- 外部营销/新闻（除非战略相关）

---

# Input Format

Each email contains:
- email_id, subject, sender, received_at, body, attachments

---

# 1. Tag (业务动作标签)

生成 **4字中文标签**，描述管理动作。

**规则**:
- 必须是业务动作，禁止用部门名、人名作为 tag
- 示例: 财务报表、预算编制、试用考核、人事变动、经营分析、战略会议、成本分析、绩效评估

---

# 2. Style

* **RISK**: 亏损、合规问题、关键人才离职、法务风险
* **GAIN**: 盈利增长、考核通过、战略突破
* **INSIGHT**: 市场分析、行业趋势、竞争情报
* **LOG**: 例行报表、常规考核、预算提交

---

# 3. Summary

用简洁中文总结：`[主体] + [动作] + [对象] + [关键数字/结论]`

---

# 4. Output Rule

**1:1 映射**: N 封邮件 → N 条事件

---

# JSON Schema

```json
[
  {{
    "source_id": "email_id",
    "tag": "试用考核",
    "style": "LOG",
    "summary": "**杨力**（投融资总监）提交试用期考核自评表。",
    "highlights": {{
      "entities": ["杨力", "投融资部"],
      "numbers": ["2025.12"]
    }}
  }}
]
```

---

# Few-Shot Examples

**Input 1**:
Subject: 回复：试用期员工考评（自评）通知-杨力
Body: 陈经理好，试用期考核表请查阅附件。杨力 投融资总监

**Output 1**:
```json
{{
  "source_id": "email_001",
  "tag": "试用考核",
  "style": "LOG",
  "summary": "**杨力**（投融资总监）提交试用期考核自评表。",
  "highlights": {{
    "entities": ["杨力", "投融资部"],
    "numbers": []
  }}
}}
```

**Input 2**:
Subject: 上海榕融新材料技术有限公司_财务三大报表_2025-11
Body: 附件为11月财务三大报表，请查阅。

**Output 2**:
```json
{{
  "source_id": "email_002",
  "tag": "财务报表",
  "style": "LOG",
  "summary": "**财务部** 提交 **2025年11月** 财务三大报表。",
  "highlights": {{
    "entities": ["财务部"],
    "numbers": ["2025-11"]
  }}
}}
```

**Input 3**:
Subject: 2026年1月部门预算表（总裁办办公、行政管理部）
Body: 请查阅附件2026年1月预算。

**Output 3**:
```json
{{
  "source_id": "email_003",
  "tag": "预算编制",
  "style": "LOG",
  "summary": "**总裁办/行政部** 提交 **2026年1月** 部门预算表。",
  "highlights": {{
    "entities": ["总裁办", "行政管理部"],
    "numbers": ["2026年1月"]
  }}
}}
```

---

# Email Data

{email_data}

---

# Output
Return JSON array only. No other content.
"""


async def call_vllm(content_parts: list) -> str:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 16000,
            "temperature": 0.3
        })
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content


def load_image_as_base64(file_path: str) -> str | None:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except:
        return None


def get_mime_type(filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")


async def get_emails(db, company: str, date_str: str, category: str) -> list:
    pipeline = await db.rongrong_filter_runs.find_one({"date": date_str, "company": company})
    if not pipeline or "filter_result" not in pipeline:
        return []
    email_ids = pipeline["filter_result"].get(category, [])
    print(f"{category} 分类: {len(email_ids)} 封邮件")
    if not email_ids:
        return []
    cursor = db.wecom_emails.find({"email_id": {"$in": email_ids}})
    return await cursor.to_list(length=100)


def build_email_data(emails: list) -> tuple[str, list]:
    email_data = []
    image_parts = []
    for email in emails:
        image_count_per_email = 0
        item = {
            "email_id": email["email_id"],
            "subject": email.get("subject", ""),
            "sender": email.get("from", ""),
            "received_at": str(email.get("received_at", "")),
            "body": email.get("body", "")[:3000],
            "attachments": []
        }
        for att in email.get("attachments", []):
            filename = att.get("filename", "")
            ext = filename.lower().split(".")[-1]
            if ext in ("png", "jpg", "jpeg"):
                full_path = os.path.join(ATTACHMENT_BASE_PATH, att.get("file_path", ""))
                img_b64 = load_image_as_base64(full_path)
                if img_b64 and image_count_per_email < MAX_IMAGES_PER_EMAIL:
                    image_count_per_email += 1
                    image_parts.append({"type": "image_url", "image_url": {"url": f"data:{get_mime_type(filename)};base64,{img_b64}"}})
                    item["attachments"].append({"filename": filename, "note": "[图片附件]"})
            else:
                item["attachments"].append({"filename": filename})
        email_data.append(item)
    return json.dumps(email_data, ensure_ascii=False, indent=2), image_parts


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="shanghai")
    parser.add_argument("--date", default=None)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"[MANAGEMENT Agent Test] {args.company} {date_str}")
    print("=" * 60)

    emails = await get_emails(db, args.company, date_str, "MANAGEMENT")
    if not emails:
        print("没有 MANAGEMENT 邮件")
        client.close()
        return

    if len(emails) > args.limit:
        emails = emails[:args.limit]

    print(f"\n=== 输入邮件 ({len(emails)} 封) ===")
    for i, e in enumerate(emails):
        print(f"  {i+1}. {e.get('subject', '')[:50]}")

    email_json, image_parts = build_email_data(emails)
    prompt_text = MANAGEMENT_AGENT_PROMPT.format(email_data=email_json)

    print(f"\n=== 调用 vLLM ===")
    print(f"Prompt: {len(prompt_text)} 字符, 图片: {len(image_parts)}")

    content_parts = image_parts + [{"type": "text", "text": prompt_text}]

    try:
        result = await call_vllm(content_parts)
        print(f"\n=== 原始输出 ===\n{result[:600]}...")

        items = []
        match_arr = re.search(r"\[.*\]", result, re.DOTALL)
        if match_arr:
            try:
                items = json.loads(match_arr.group())
            except:
                pass
        if not items:
            match_obj = re.search(r"\{.*\"items\".*\}", result, re.DOTALL)
            if match_obj:
                try:
                    items = json.loads(match_obj.group()).get("items", [])
                except:
                    pass

        if items:
            print(f"\n=== 解析结果 ({len(items)} 条) ===")
            for item in items:
                print(json.dumps(item, ensure_ascii=False, indent=2))
                print("---")
            tags = {}
            for i in items:
                t = i.get('tag', '?')
                tags[t] = tags.get(t, 0) + 1
            print(f"\n统计: 标签分布={tags}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    client.close()

if __name__ == "__main__":
    asyncio.run(main())
