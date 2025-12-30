#!/usr/bin/env python3
"""
Logistics Agent v2 - 物流/货代/报关事件提取 (支持线程聚合)
"""
import asyncio
import json
import re
import base64
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import httpx
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
from project_rongrong.services.email_loader import EmailLoader, ThreadedEmail

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
ATTACHMENT_BASE_PATH = "/home/xinyue/vulcan-brain/data/attachments"
MAX_IMAGES_PER_EMAIL = 5

LOGISTICS_AGENT_PROMPT = """# Role
You are a **Logistics Control Tower Operator** and **Freight Forwarding Specialist**.
You think in terms of **Nodes, Transit Times, and Incoterms** (FOB, CIF, FCA, DAP).

# Prime Directive
Ensure **Visibility** of goods in transit. Focus on **Exceptions** and key milestones.

# Cognitive Filter

**FOCUS ON**:
- **订舱/提货**: 托书、货物信息、提货安排、装箱清单
- **运输状态**: ETD/ETA、航班/船期、到港通知
- **异常**: 延误、货损、舱位取消、清关受阻
- **单证**: AWB、B/L、运单号、HS Code

**IGNORE**:
- 货代公司广告/推销
- 纯寒暄/问候

---

# Thread Handling (CRITICAL)

If `thread_emails` is present, this represents a **conversation thread**.
- `thread_emails` are sorted chronologically: **LAST item = LATEST message**
- **ALWAYS base your summary on the LAST email** - this is the current status
- Earlier emails provide context only

**Example**:
If thread_emails[2] (latest) says "等国外批复后安排", your summary should reflect "待批复" status, NOT "已安排".
If thread_emails[2] (latest) says "已安排提货", then summary reflects "提货中".

---

# Input Format

Each item may be a single email or a thread:
- email_id: ID of the latest email
- subject: Thread subject
- thread_count: Number of emails in thread
- thread_emails: Conversation history (if thread)
- attachments: All attachments from the thread

---

# 1. Tag (业务动作标签)

生成 **4字中文标签**，描述物流动作。

**规则**:
- 必须是物流动作，禁止用货代公司名、船名、人名
- 示例: 订舱确认、托书发送、提货通知、报关放行、货物到港、运输延误、单证签发

---

# 2. Style

* **RISK**: 延误、货损、舱位取消、清关问题
* **GAIN**: 提前到港、顺利清关
* **INSIGHT**: 运价变动、航线调整
* **LOG**: 常规订舱、托书、提货安排

---

# 3. Summary

用简洁中文总结：`[主体] + [动作] + [货物/目的地] + [关键数字]`

对于线程，总结**最新状态**，可引用历史上下文。

---

# 4. Output Rule

**1:1 映射**: N 个线程 → N 条事件

---

# JSON Schema

```json
[
  {{
    "source_id": "latest_email_id",
    "tag": "托书发送",
    "style": "LOG",
    "summary": "**仝占凤** 发送托书给货代，**11托/1441kg** 货物备妥待提。",
    "highlights": {{
      "entities": ["仝占凤", "广西工厂", "Expeditors"],
      "numbers": ["11托", "1441.5kg", "H#41X0122131"]
    }}
  }}
]
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
        if "error" in data:
            print(f"API Error: {data["error"]}")
            return ""
        content = data["choices"][0]["message"]["content"]
        # Remove thinking blocks (closed or unclosed)
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        content = re.sub(r"<think>.*", "", content, flags=re.DOTALL)
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


def build_threaded_email_data(threads: list[ThreadedEmail]) -> tuple[str, list]:
    """构建线程邮件数据"""
    email_data = []
    image_parts = []
    total_images = 0
    
    for thread in threads:
        item = {
            "email_id": thread.email_id,
            "subject": thread.subject,
            "thread_count": thread.thread_count,
            "latest_sender": thread.latest_sender,
            "latest_time": thread.latest_time.isoformat() if thread.latest_time else "",
            "attachments": []
        }
        
        # 如果是线程，包含对话历史
        if thread.thread_count > 1:
            item["thread_emails"] = thread.thread_emails
        else:
            # 单封邮件，直接用 body
            if thread.thread_emails:
                item["body"] = thread.thread_emails[0].get("body", "")[:2000]
        
        # 处理附件图片 (限制数量)
        images_for_thread = 0
        for att in thread.attachments:
            filename = att.get("filename", "")
            ext = filename.lower().split(".")[-1]
            
            if ext in ("png", "jpg", "jpeg") and images_for_thread < MAX_IMAGES_PER_EMAIL:
                file_path = att.get("file_path", "")
                if file_path:
                    full_path = os.path.join(ATTACHMENT_BASE_PATH, file_path)
                    img_b64 = load_image_as_base64(full_path)
                    if img_b64:
                        image_parts.append({
                            "type": "image_url", 
                            "image_url": {"url": f"data:{get_mime_type(filename)};base64,{img_b64}"}
                        })
                        images_for_thread += 1
                        total_images += 1
                        item["attachments"].append({"filename": filename, "note": f"[图片 #{total_images}]"})
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

    loader = EmailLoader()

    print(f"[LOGISTICS Agent v2 - Threaded] {args.company} {date_str}")
    print("=" * 60)

    # 获取线程聚合后的邮件
    threads = await loader.get_emails_by_category_threaded(
        args.company, date_str, "LOGISTICS", limit=args.limit
    )
    
    if not threads:
        print("没有 LOGISTICS 邮件")
        return

    print(f"\n=== 输入线程 ({len(threads)} 个) ===")
    for i, t in enumerate(threads):
        att_count = len(t.attachments)
        print(f"  {i+1}. [{t.thread_count}封] {t.subject[:45]}... (附件:{att_count})")

    # 构建 prompt
    email_json, image_parts = build_threaded_email_data(threads)
    prompt_text = LOGISTICS_AGENT_PROMPT.format(email_data=email_json)

    print(f"\n=== 调用 vLLM ===")
    print(f"Prompt: {len(prompt_text)} 字符, 图片: {len(image_parts)}")

    content_parts = image_parts + [{"type": "text", "text": prompt_text}]

    try:
        result = await call_vllm(content_parts)
        print(f"\n=== 原始输出 ===\n{result[:800]}...")

        # 解析 JSON
        items = []
        match_arr = re.search(r"\[.*\]", result, re.DOTALL)
        if match_arr:
            try:
                items = json.loads(match_arr.group())
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
            print(f"\n统计: {len(threads)} 线程 → {len(items)} 事件, 标签={tags}")
        else:
            print("无法解析 JSON")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
