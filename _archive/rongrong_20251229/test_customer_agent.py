#!/usr/bin/env python3
"""
测试 CUSTOMER Agent - 单独运行看 JSON 产出效果
支持多模态：邮件正文 + 附件图片 → VL 模型
"""
import asyncio
import json
import re
import base64
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import httpx

# ========== 配置 ==========

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
# VL Thinking 模型 - 支持图片识别
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
ATTACHMENT_BASE_PATH = "/home/xinyue/vulcan-brain/data/attachments"

# ========== CUSTOMER Agent Prompt (架构师原版) ==========

CUSTOMER_AGENT_PROMPT = """# Role
You are the **AI Revenue Operations Expert** for a manufacturing enterprise.
Your goal is to extract **high-signal sales intelligence** from emails, minimizing noise and focusing on business outcomes.

# Core Task
Analyze the email to generate a structured JSON List.
Focus on: **The core interaction (Who did what with Whom) and the business signal.**

---

# Input Format

You will receive a batch of emails. Each email contains:
- email_id: Unique identifier
- subject: Email subject
- sender: Sender address
- received_at: Received timestamp
- body: Email body content
- attachments: List of attachments (may be empty)
  - filename: Attachment filename
  - content: Parsed text content (from OCR or text extraction)

---

# 1. Classification & Labeling

### A. Tag (业务动作标签)
生成 **4字中文标签**，描述本邮件的业务动作类型。

**关键规则**:
- Tag 必须是业务动作，**绝对不能**是客户名称或公司名
- 格式: 动作词 + 对象，如"样件申请"、"报价确认"

**正确示例**: 样件申请、订单确认、价格谈判、需求咨询、合同签订、发货催促
**错误示例**: 北京石墨烯、Fenner、青岛康复 ← 这些是实体名，不是动作，绝对禁止

### B. Signal Style (Business Nature)
Determine the nature of the event for downstream rendering. Output ONE enum:
* **`RISK`**: Negative blockage or threat. (Complaints, delays, refusal to pay, competitor threats).
* **`GAIN`**: Positive growth or breakthrough. (**Sample requests**, new orders, money received, successful audits).
* **`INSIGHT`**: Neutral but high-value intelligence. (Spec confirmations, market trends, strategic adjustments).
* **`LOG`**: Routine process flow. (Logistics updates, general scheduling, low-priority status).

---

# 2. Narrative Generation (The Summary)

**Instruction**: Summarize the event using natural, concise Chinese business language.
**Structure**: `[Active Entity] + [Action] + [Passive Entity] + [Outcome/Number]`

* *Constraint*: Focus on the **Business Consequence**, not the administrative process.
* *Bad*: "财资部批准了张三给青岛大学的流程。" (Focuses on process)
* *Good*: "**张三** 为 **青岛康复大学** 申请的 **5组** 样件已获批，准备发货。" (Focuses on result)

---

# 3. Abstract Entity Extraction (High Relevance Only)

Populate the `highlights` field. Use the following **Relevance Logic**:

- **`entities`**: Extract **PRIMARY ACTORS** only.
    - **Rule**: Include entities that are driving the event or are directly affected by it.
    - **Filter**: **Ignore** supportive/administrative roles (e.g., "Finance Dept", "HR", "System Notification") UNLESS they are the direct cause of a blocker/rejection.
    - *Example*: If "Finance approved", ignore Finance. If "Finance rejected", include Finance.
- **`numbers`**: Extract business-critical metrics (Money, Quantities, Dates, Models).

---

# 4. Output Rule

**CRITICAL**: Each email generates exactly ONE event. Do NOT aggregate emails.
- **source_id**: Must be exactly one email_id (no commas)
- **1:1 mapping**: N emails in → N events out

---

# 5. JSON Output Schema

```json
{{
  "items": [
    {{
      "source_id": "email_id_here",
      "tag": "样件申请",
      "style": "GAIN",
      "summary": "**张三** 为 **青岛康复大学** 申请 **5pcs** 导热垫样件，已获批准并发货。",
      "highlights": {{
        "entities": ["张三", "青岛康复大学"],
        "numbers": ["5pcs"]
      }}
    }}
  ]
}}
```

---

# Few-Shot Examples

**Input 1**:
Subject: 转发：你的免费样件申请（财资部）已通过 - 青岛康复大学
Content: 销售员张三申请寄送5pcs导热垫，经系统自动流转，财资部已审批通过。

**Output 1**:
```json
{{
  "source_id": "email_001",
  "tag": "样件申请",
  "style": "GAIN",
  "summary": "**张三** 为 **青岛康复大学** 申请 **5pcs** 导热垫样件，已获批准并发货。",
  "highlights": {{
    "entities": ["张三", "青岛康复大学"],
    "numbers": ["5pcs"]
  }}
}}
```

**Input 2**:
Subject: 紧急：财务驳回了给ABC公司的付款申请
Content: 财务部李四驳回了张三给ABC公司的退款申请，原因是发票抬头不对。

**Output 2**:
```json
{{
  "source_id": "email_002",
  "tag": "退款受阻",
  "style": "RISK",
  "summary": "**财务部** 驳回了 **张三** 提交的给 **ABC公司** 的退款申请，原因是发票合规问题。",
  "highlights": {{
    "entities": ["财务部", "张三", "ABC公司"],
    "numbers": []
  }}
}}
```

---

# Email Data

{email_data}

---

# Output
Return JSON only. No other content.
"""


async def call_vllm(content_parts: list) -> str:
    """
    调用 vLLM (支持多模态)

    content_parts: [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        {"type": "text", "text": "...prompt..."}
    ]
    """
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 8000,
            "temperature": 0.3
        })
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        # 去除 thinking 标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content


def load_image_as_base64(file_path: str) -> str | None:
    """加载图片并转为 base64"""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"  读取图片失败: {file_path} - {e}")
        return None


def get_mime_type(filename: str) -> str:
    """根据文件扩展名返回 MIME 类型"""
    ext = filename.lower().split(".")[-1]
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    return mime_map.get(ext, "image/png")


async def get_customer_emails(db, company: str, date_str: str) -> list:
    """从 pipeline_runs 获取 CUSTOMER 类邮件的完整数据"""

    # 1. 获取 rongrong_filter_runs 中的 email_ids
    pipeline = await db.rongrong_filter_runs.find_one({
        "date": date_str,
        "company": company
    })

    if not pipeline or "filter_result" not in pipeline:
        print(f"未找到 {company} {date_str} 的 pipeline 记录")
        return []

    email_ids = pipeline["filter_result"].get("CUSTOMER", [])
    print(f"CUSTOMER 分类: {len(email_ids)} 封邮件")

    if not email_ids:
        return []

    # 2. 获取完整邮件数据
    cursor = db.wecom_emails.find({"email_id": {"$in": email_ids}})
    emails = await cursor.to_list(length=100)

    return emails


def build_email_data(emails: list) -> tuple[str, list]:
    """
    构建邮件输入数据

    Returns:
        (email_json_str, image_parts)
        - email_json_str: 邮件文本数据 JSON
        - image_parts: [{"type": "image_url", ...}, ...] 用于多模态
    """
    email_data = []
    image_parts = []
    image_count = 0

    for email in emails:
        item = {
            "email_id": email["email_id"],
            "subject": email.get("subject", "(无主题)"),
            "sender": email.get("sender", ""),
            "received_at": email.get("received_at", datetime.now()).isoformat() if isinstance(email.get("received_at"), datetime) else str(email.get("received_at", "")),
            "body": email.get("body", "")[:2000],  # 截断正文
            "attachments": []  # 非图片附件的文本内容
        }

        # 处理附件
        for att in email.get("attachments", []):
            filename = att.get("filename", "unknown")
            file_path = att.get("file_path", "")

            # 检查是否是图片
            ext = filename.lower().split(".")[-1]
            if ext in ("png", "jpg", "jpeg", "gif", "webp"):
                # 图片附件 → 加载为 base64
                full_path = os.path.join(ATTACHMENT_BASE_PATH, file_path)
                img_b64 = load_image_as_base64(full_path)
                if img_b64:
                    mime_type = get_mime_type(filename)
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                    })
                    item["attachments"].append({
                        "filename": filename,
                        "note": f"[图片附件 #{image_count + 1}，见上方图片]"
                    })
                    image_count += 1
            else:
                # 非图片附件：如果有 parsed_content 就用
                if att.get("parsed_content"):
                    item["attachments"].append({
                        "filename": filename,
                        "content": att["parsed_content"][:1000]
                    })

        email_data.append(item)

    return json.dumps(email_data, ensure_ascii=False, indent=2), image_parts


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="测试 CUSTOMER Agent")
    parser.add_argument("--company", default="shanghai", help="公司: shanghai/guangxi")
    parser.add_argument("--date", default=None, help="日期: YYYY-MM-DD，默认今天")
    parser.add_argument("--limit", type=int, default=10, help="最多处理几封邮件")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"[CUSTOMER Agent Test] {args.company} {date_str}")
    print("=" * 60)

    # 1. 获取邮件
    emails = await get_customer_emails(db, args.company, date_str)

    if not emails:
        print("没有 CUSTOMER 类邮件")
        client.close()
        return

    # 限制数量
    if len(emails) > args.limit:
        print(f"限制为前 {args.limit} 封")
        emails = emails[:args.limit]

    # 2. 显示输入邮件
    print(f"\n=== 输入邮件 ({len(emails)} 封) ===")
    for i, email in enumerate(emails):
        subj = email.get("subject", "(无主题)")[:50]
        att_count = len(email.get("attachments", []))
        att_str = f" [附件:{att_count}]" if att_count else ""
        print(f"  {i+1}. {subj}{att_str}")

    # 3. 构建 prompt (多模态)
    email_json, image_parts = build_email_data(emails)
    prompt_text = CUSTOMER_AGENT_PROMPT.format(email_data=email_json)

    print(f"\n=== 调用 vLLM (多模态) ===")
    print(f"Prompt 长度: {len(prompt_text)} 字符")
    print(f"图片数量: {len(image_parts)}")

    # 构建多模态消息内容
    content_parts = []
    # 先放图片
    content_parts.extend(image_parts)
    # 再放文字 prompt
    content_parts.append({"type": "text", "text": prompt_text})

    # 4. 调用 LLM (多模态)
    try:
        result = await call_vllm(content_parts)
        print(f"\n=== 原始输出 ===")
        print(result[:500] + "..." if len(result) > 500 else result)

        # 5. 解析 JSON
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            print(f"\n=== 解析后的 JSON ===")
            print(json.dumps(parsed, ensure_ascii=False, indent=2))

            # 统计
            items = parsed.get("items", [])
            print(f"\n=== 统计 ===")
            print(f"  事件数: {len(items)}")

            styles = {}
            tags = {}
            for item in items:
                style = item.get("style", "UNKNOWN")
                tag = item.get("tag", "UNKNOWN")
                styles[style] = styles.get(style, 0) + 1
                tags[tag] = tags.get(tag, 0) + 1

            print(f"  风格分布: {styles}")
            print(f"  标签分布: {tags}")
        else:
            print("无法解析 JSON")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
