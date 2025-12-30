#!/usr/bin/env python3
"""
Supply Chain Agent - 供应链/采购/生产/质量事件提取
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
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
MAX_IMAGES_PER_EMAIL = 5  # 每封邮件最多处理5张图片
ATTACHMENT_BASE_PATH = "/home/xinyue/vulcan-brain/data/attachments"

# ========== SUPPLY_CHAIN Agent Prompt ==========

SUPPLY_CHAIN_AGENT_PROMPT = """# Role
You are a **Senior Supply Chain Planner & Production Operations Specialist** for a manufacturing enterprise.
Your thinking is governed by **MRP (Material Requirements Planning)**, **Just-in-Time**, and **Quality Management** principles.

# Prime Directive
Protect **Production Continuity**, **Quality Compliance**, and **Cost Efficiency**.
View every email through: 
- "Will this impact the production line?"
- "Is this a quality/compliance risk?"  
- "Does this affect delivery or cost?"

# Cognitive Filter

**FOCUS ON**:
- **审厂/验厂**: Supplier audits, customer audits, compliance reviews, certification
- **生产运营**: Production meetings, manufacturing issues, equipment maintenance, capacity
- **质量管理**: Quality tests, defect reports, yield rates, NG analysis
- **仓储物流**: Inventory, waste disposal, material handling
- **采购交期**: Lead time, ETD/ETA, delays, order status (if present)

**IGNORE**:
- Marketing content
- Polite greetings
- Irrelevant office matters

---

# Input Format

You will receive a batch of emails. Each email contains:
- email_id: Unique identifier
- subject: Email subject
- sender: Sender address
- received_at: Received timestamp
- body: Email body content
- attachments: List of attachments (may be empty)

---

# 1. Classification & Labeling

### A. Tag (业务动作标签)
生成 **4字中文标签**，描述本邮件的业务动作类型。

**关键规则**:
- Tag 必须是业务动作，**绝对不能**是供应商名称、客户名、人名
- 格式: 动作词 + 对象

**正确示例**: 审厂准备、审厂通知、生产例会、设备维修、品质检测、固废清理、来料检验、交期确认
**错误示例**: 广州国机、董雪瑞、制造部 ← 这些是实体名，不是动作，绝对禁止

### B. Signal Style (Business Nature)
Determine the nature of the event. Output ONE enum:

* **`RISK`**: 风险/阻塞
  - 审厂发现问题、整改要求
  - 品质异常、不良率上升
  - 设备故障、产线停机
  - 交期延误、供应商异常
  
* **`GAIN`**: 积极/突破
  - 审厂通过、认证获得
  - 良率提升、问题解决
  - 产能扩充、效率提升
  
* **`INSIGHT`**: 情报/洞察
  - 市场动态、价格变动
  - 技术方案讨论
  - 战略性信息
  
* **`LOG`**: 常规记录
  - 例行会议通知
  - 常规检验结果
  - 日常工作协调

---

# 2. Narrative Generation (Summary)

**Instruction**: 用简洁中文总结事件核心。
**Structure**: `[主体] + [动作] + [对象] + [结果/数字]`

* 重点放在**业务结果**，而非流程细节
* 如果邮件包含多个action items，提炼最重要的1-2个

---

# 3. Entity Extraction

Populate the `highlights` field:

- **`entities`**: 关键主体（部门、供应商、客户、责任人）
- **`numbers`**: 业务数字（数量、日期、百分比、型号）

---

# 4. Output Rule

**CRITICAL**: Each email generates exactly ONE event.
- **source_id**: Must be exactly one email_id
- **1:1 mapping**: N emails in → N events out

---

# 5. JSON Output Schema

```json
{{
  "items": [
    {{
      "source_id": "email_id_here",
      "tag": "审厂准备",
      "style": "LOG",
      "summary": "**科技项目组** 通知各部门准备 **广州国机** 审厂资料，**11月25日下午2点前** 提交。",
      "highlights": {{
        "entities": ["科技项目组", "广州国机", "吕静"],
        "numbers": ["11月25日下午2点"]
      }}
    }}
  ]
}}
```

---

# Few-Shot Examples

**Input 1**:
Subject: 广州国机审厂事宜
Body: 根据以往审厂经验，科技项目组于今日下午梳理出本次广州国机审厂还需要准备的资料（详见现场审核清单表），对于该附件表各负责人需认真核对好自己所负责的部分...明天下午4点半-5点半二期会议厅开一个审厂资料的沟通会议

**Output 1**:
```json
{{
  "source_id": "email_001",
  "tag": "审厂准备",
  "style": "LOG",
  "summary": "**科技项目组** 组织 **广州国机** 审厂资料准备，要求各部门 **11月25日14:00前** 提交佐证资料。",
  "highlights": {{
    "entities": ["科技项目组", "广州国机"],
    "numbers": ["11月25日14:00", "16:30-17:30"]
  }}
}}
```

**Input 2**:
Subject: 12.19 制造部例会
Body: 本次会议主题是12.19制造部例会...EHS瞿烨：牵头生产部开展噪音防护工作，将防护用品佩戴纳入考核...供应链-仓储赵东亮：外租场地已清理完成...质量部张秀丽：继续测试G22/G28胶体

**Output 2**:
```json
{{
  "source_id": "email_002",
  "tag": "生产例会",
  "style": "LOG",
  "summary": "**制造部** 12.19例会：EHS加强噪音防护考核，仓储完成外租场地清理，质量部持续G22/G28胶体测试。",
  "highlights": {{
    "entities": ["制造部", "EHS", "供应链-仓储", "质量部"],
    "numbers": ["12月19日"]
  }}
}}
```

**Input 3**:
Subject: 回复：车间工业固废回收清理
Body: 已安排下周一来处理...麻烦安排一位财务同事协同

**Output 3**:
```json
{{
  "source_id": "email_003",
  "tag": "固废清理",
  "style": "LOG",
  "summary": "**胡专员** 确认 **下周一** 安排工业固废清运，需财务协同。",
  "highlights": {{
    "entities": ["胡娟娟", "财务"],
    "numbers": ["下周一"]
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
    """调用 vLLM (支持多模态)"""
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 16000,
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


async def get_supply_chain_emails(db, company: str, date_str: str) -> list:
    """从 rongrong_filter_runs 获取 SUPPLY_CHAIN 类邮件的完整数据"""

    pipeline = await db.rongrong_filter_runs.find_one({
        "date": date_str,
        "company": company
    })

    if not pipeline or "filter_result" not in pipeline:
        print(f"未找到 {company} {date_str} 的 pipeline 记录")
        return []

    email_ids = pipeline["filter_result"].get("SUPPLY_CHAIN", [])
    print(f"SUPPLY_CHAIN 分类: {len(email_ids)} 封邮件")

    if not email_ids:
        return []

    cursor = db.wecom_emails.find({"email_id": {"$in": email_ids}})
    emails = await cursor.to_list(length=100)

    return emails


def build_email_data(emails: list) -> tuple[str, list]:
    """构建邮件输入数据"""
    email_data = []
    image_parts = []
    image_count = 0

    for email in emails:
        image_count_per_email = 0
        item = {
            "email_id": email["email_id"],
            "subject": email.get("subject", "(无主题)"),
            "sender": email.get("from", email.get("sender", "")),
            "received_at": email.get("received_at", datetime.now()).isoformat() if isinstance(email.get("received_at"), datetime) else str(email.get("received_at", "")),
            "body": email.get("body", "")[:3000],  # 供应链邮件可能较长
            "attachments": []
        }

        # 处理附件
        for att in email.get("attachments", []):
            filename = att.get("filename", "unknown")
            file_path = att.get("file_path", "")

            ext = filename.lower().split(".")[-1]
            if ext in ("png", "jpg", "jpeg", "gif", "webp"):
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
                if att.get("parsed_content"):
                    item["attachments"].append({
                        "filename": filename,
                        "content": att["parsed_content"][:1500]
                    })

        email_data.append(item)

    return json.dumps(email_data, ensure_ascii=False, indent=2), image_parts


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="测试 SUPPLY_CHAIN Agent")
    parser.add_argument("--company", default="shanghai", help="公司: shanghai/guangxi")
    parser.add_argument("--date", default=None, help="日期: YYYY-MM-DD，默认今天")
    parser.add_argument("--limit", type=int, default=10, help="最多处理几封邮件")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"[SUPPLY_CHAIN Agent Test] {args.company} {date_str}")
    print("=" * 60)

    # 1. 获取邮件
    emails = await get_supply_chain_emails(db, args.company, date_str)

    if not emails:
        print("没有 SUPPLY_CHAIN 类邮件")
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
    prompt_text = SUPPLY_CHAIN_AGENT_PROMPT.format(email_data=email_json)

    print(f"\n=== 调用 vLLM (多模态) ===")
    print(f"Prompt 长度: {len(prompt_text)} 字符")
    print(f"图片数量: {len(image_parts)}")

    # 构建多模态消息内容
    content_parts = []
    content_parts.extend(image_parts)
    content_parts.append({"type": "text", "text": prompt_text})

    # 4. 调用 LLM
    try:
        result = await call_vllm(content_parts)
        print(f"\n=== 原始输出 ===")
        print(result[:800] + "..." if len(result) > 800 else result)

        # 5. 解析 JSON - 优先匹配数组格式
        items = []
        try:
            # 尝试匹配 [...] 数组
            match_arr = re.search(r"\[.*\]", result, re.DOTALL)
            if match_arr:
                items = json.loads(match_arr.group())
        except json.JSONDecodeError:
            pass
        
        if not items:
            try:
                # 尝试匹配 {"items": [...]}
                match_obj = re.search(r"\{.*\}", result, re.DOTALL)
                if match_obj:
                    parsed = json.loads(match_obj.group())
                    items = parsed.get("items", [])
            except json.JSONDecodeError:
                pass
        
        if items:
            print(f"\n=== 解析后的 JSON ({len(items)} 条) ===")
            for item in items:
                print(json.dumps(item, ensure_ascii=False, indent=2))
                print("---")

            # 统计
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
