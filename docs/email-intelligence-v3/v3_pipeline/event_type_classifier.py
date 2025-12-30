#!/usr/bin/env python3
"""
事件类型重分类 v2 - 修复解析逻辑
"""
import kuzu
import requests
import json
import time
import re

VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"

SYSTEM_PROMPT = """你是商业事件分类器。根据描述判断类型，只输出一个单词。

Payment = 付款/转账/发票/账单
Shipment = 发货/物流/运输/快递/提单/shipping/delivery
Order = 订单/采购/PO
Quotation = 报价/询价
Inquiry = 咨询/申请/请求/介绍/会议/visa/application
Contract = 合同/协议/审计/认证/engagement
General = 无法归类

只输出类型名，不要解释。"""

VALID_TYPES = ["Payment", "Shipment", "Order", "Quotation", "Inquiry", "Contract", "General"]

def classify_event(summary: str) -> str:
    """用LLM分类单个事件"""
    try:
        resp = requests.post(VLLM_URL, json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": summary[:200]}  # 限制长度
            ],
            "temperature": 0,
            "max_tokens": 500  # 给足够空间完成思考
        }, timeout=60)

        result = resp.json()["choices"][0]["message"]["content"].strip()

        # 关键：只在</think>之后的内容中查找类型
        if "</think>" in result:
            result = result.split("</think>")[-1].strip()

        # 取第一个词
        first_word = result.split()[0] if result.split() else ""

        # 精确匹配
        for t in VALID_TYPES:
            if first_word.lower() == t.lower():
                return t

        # 模糊匹配（如果第一个词不是精确类型）
        for t in VALID_TYPES:
            if t.lower() in result.lower()[:50]:  # 只看前50字符
                return t

        return "General"
    except Exception as e:
        return None

def main():
    print("🏷️ 事件类型重分类 v2")
    print("=" * 50)

    db = kuzu.Database(KUZU_PATH)
    conn = kuzu.Connection(db)

    # 先恢复数据：把之前错误分类的Payment改回General
    print("🔄 恢复错误分类...")
    conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type = 'Payment'
        SET be.event_type = 'General'
    """)

    # 重新获取General事件
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_type = 'General' AND be.summary IS NOT NULL
        RETURN be.id, be.summary
    """)

    events = []
    while result.has_next():
        row = result.get_next()
        events.append({"id": row[0], "summary": row[1]})

    print(f"📊 待分类事件: {len(events)}")

    # 先测试5个
    print("\n🧪 测试前5个:")
    for e in events[:5]:
        new_type = classify_event(e["summary"])
        print(f"  [{new_type}] {e['summary'][:60]}...")

    print("\n继续完整分类? (y/n)")
    # 自动继续
    print("自动继续...")

    print("\n🔄 开始分类...")
    stats = {t: 0 for t in VALID_TYPES}
    stats["Failed"] = 0

    for i, e in enumerate(events):
        if i % 100 == 0:
            print(f"进度: {i}/{len(events)}")

        new_type = classify_event(e["summary"])

        if new_type:
            try:
                conn.execute(f'MATCH (be:BusinessEvent {{id: "{e["id"]}"}}) SET be.event_type = "{new_type}"')
                stats[new_type] += 1
            except:
                stats["Failed"] += 1
        else:
            stats["Failed"] += 1

        time.sleep(0.05)

    print("\n" + "=" * 50)
    print("📊 分类结果:")
    for t, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        if cnt > 0:
            print(f"  {t}: {cnt}")

    # 最终验证
    print("\n🔍 最终分布:")
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        RETURN be.event_type, count(*) as cnt
        ORDER BY cnt DESC
    """)
    while result.has_next():
        row = result.get_next()
        print(f"  {row[0]}: {row[1]}")

if __name__ == "__main__":
    main()
