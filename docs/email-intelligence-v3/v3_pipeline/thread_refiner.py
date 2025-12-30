#!/usr/bin/env python3
"""
Thread Refiner - LLM驱动的数据炼油
用整个Thread上下文重新提取高质量BusinessEvent
"""
import json
import re
import kuzu
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from tqdm import tqdm
import pymongo
from bson import ObjectId

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"
MONGO_URI = "mongodb://localhost:27017"

# ============ Schema ============
REFINED_EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["Payment", "Shipment", "Order", "Quotation", "Inquiry", "Contract", "General"]
                    },
                    "event_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD format"
                    },
                    "summary": {
                        "type": "string",
                        "description": "One sentence summary of the event"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Transaction amount, null if not applicable"
                    },
                    "currency": {
                        "type": "string",
                        "description": "USD, EUR, SGD, CNY, etc."
                    },
                    "companies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Companies involved in this event"
                    },
                    "identifiers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": "string"}
                            }
                        },
                        "description": "Invoice numbers, PO numbers, tracking numbers"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"]
                    }
                },
                "required": ["event_type", "event_date", "summary", "confidence"]
            }
        }
    }
}

SYSTEM_PROMPT = """/no_think
你是一个顶级数据清洗专家。你的任务是阅读整个邮件对话（Thread），并提取准确的商业事件。

## 输入数据的问题
- 日期格式混乱（有多种格式）
- 金额可能是错误的（比如把产品编号当成金额）
- 事件类型分类太笼统

## 你的任务
1. **识别真实事件**：基于对话上下文，判断真实发生的商业行为
   - Payment: 付款、转账、收款确认
   - Shipment: 发货、到货、物流跟踪
   - Order: 下单、订单确认
   - Quotation: 报价、询价回复
   - Inquiry: 产品咨询、需求询问
   - Contract: 合同签署、协议确认
   - General: 仅当无法归类到以上类型时使用

2. **清洗金额**：
   - 只提取明确的交易金额（发票金额、付款金额、报价金额）
   - 忽略：产品编号、年份数字、电话号码、邮编等
   - 如果金额超过1亿美元，请仔细核实是否合理

3. **标准化日期**：
   - 统一输出 YYYY-MM-DD 格式
   - 优先使用邮件中明确提到的事件日期
   - 如果没有明确日期，使用邮件发送时间

4. **合并重复**：
   - 如果多封邮件讨论同一件事（如反复确认同一笔付款），只生成一个Event
   - 在summary中汇总关键信息

5. **提取标识符**：
   - Invoice Number (INV-xxx, 发票号)
   - PO Number (PO-xxx, 采购订单号)
   - Tracking Number (物流单号)
   - Contract Number (合同号)

## 输出要求
- 输出JSON格式，结构为: {"events": [...]}
- 每个Event必须有confidence评级
- 如果整个Thread没有任何商业事件，返回 {"events": []}
- 不要编造信息，只提取邮件中明确存在的内容
- 只输出JSON，不要输出其他文字"""

# ============ 工具函数 ============
def get_thread_content(conn, thread_id: str, mongo_db) -> str:
    """获取Thread下所有邮件内容，按时间排序拼接"""
    # 获取该Thread下的所有Email ID
    result = conn.execute(f"""
        MATCH (e:Email)-[:BELONGS_TO]->(t:Thread {{id: "{thread_id}"}})
        RETURN e.id
        ORDER BY e.sent_at
    """)

    email_ids = []
    while result.has_next():
        email_ids.append(result.get_next()[0])

    if not email_ids:
        return ""

    # 从MongoDB获取邮件详情
    parts = []
    for eid in email_ids:
        email = mongo_db.emails.find_one({"_id": ObjectId(eid)})
        if email:
            sender = email.get("from", {})
            if isinstance(sender, dict):
                sender_name = sender.get("emailAddress", {}).get("name", "Unknown")
            else:
                sender_name = str(sender)[:30]

            date = email.get("received_at", "")
            if isinstance(date, datetime):
                date = date.strftime("%Y-%m-%d %H:%M")

            subject = email.get("subject", "")
            body = email.get("body", "")[:2000]  # 限制长度

            parts.append(f"[{date}] {sender_name}\nSubject: {subject}\n{body}\n")

    return "\n---\n".join(parts)


def extract_json_from_llm(content: str) -> Optional[Dict]:
    """从LLM输出中提取JSON，处理各种格式"""

    # 1. 处理thinking标签
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()

    # 2. 移除markdown代码块
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if json_match:
        content = json_match.group(1).strip()

    # 3. 尝试找到JSON对象 { ... }
    brace_match = re.search(r'\{[\s\S]*\}', content)
    if brace_match:
        content = brace_match.group(0)

    # 4. 清理常见问题
    content = content.strip()

    # 5. 尝试解析
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        # 尝试只取第一个完整JSON对象
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(content)
            return obj
        except:
            print(f"JSON解析失败: {str(e)[:50]}")
            return None


def call_llm(thread_text: str) -> Optional[Dict]:
    """调用vLLM进行清洗"""
    # 限制输入长度防止超时
    if len(thread_text) > 50000:
        thread_text = thread_text[:25000] + "\n...(内容过长已截断)...\n" + thread_text[-25000:]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请分析以下邮件对话并提取商业事件:\n\n{thread_text}"}
    ]

    try:
        response = requests.post(
            VLLM_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 8192
            },
            timeout=180
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        return extract_json_from_llm(content)
    except requests.exceptions.Timeout:
        print("LLM超时(180s)")
        return None
    except Exception as e:
        print(f"LLM调用错误: {e}")
        return None


def update_kuzu_events(conn, thread_id: str, events: List[Dict]):
    """更新KùzuDB中的事件"""
    # 这里先只打印，实际写入需要更复杂的逻辑
    # TODO: 实现实际的数据库更新
    pass


# ============ 主流程 ============
def refine_sample(n: int = 5):
    """测试：清洗n个Thread样本"""
    # 连接数据库
    db = kuzu.Database(KUZU_PATH, read_only=True)
    conn = kuzu.Connection(db)

    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client["vulcan_brain"]

    # 获取有多封邮件的Thread（更有价值）
    result = conn.execute("""
        MATCH (t:Thread)
        WHERE t.email_count > 1
        RETURN t.id, t.topic, t.email_count
        ORDER BY t.email_count DESC
        LIMIT 20
    """)

    threads = []
    while result.has_next():
        row = result.get_next()
        threads.append({"id": row[0], "topic": row[1], "count": row[2]})

    print(f"找到 {len(threads)} 个多邮件Thread")
    print(f"测试前 {n} 个:\n")

    for t in threads[:n]:
        print("="*60)
        print(f"Thread: {t['topic'][:50]}... ({t['count']} emails)")
        print("="*60)

        # 获取Thread内容
        content = get_thread_content(conn, t["id"], mongo_db)
        if not content:
            print("  ⚠️ 无法获取内容")
            continue

        print(f"  内容长度: {len(content)} 字符")

        # 调用LLM
        print("  🔄 调用LLM清洗...")
        result = call_llm(content)

        if result and "events" in result:
            events = result["events"]
            print(f"  ✅ 提取到 {len(events)} 个事件:")
            for e in events:
                print(f"     [{e.get('event_type')}] {e.get('event_date')} - {e.get('summary', '')[:50]}")
                if e.get("amount"):
                    print(f"        金额: {e.get('amount')} {e.get('currency', 'USD')}")
                if e.get("identifiers"):
                    print(f"        标识: {e.get('identifiers')}")
        else:
            print("  ❌ 清洗失败")

        print()


if __name__ == "__main__":
    print("🧪 Thread Refiner - 样本测试")
    print()
    refine_sample(3)
