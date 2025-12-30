#!/usr/bin/env python3
"""
用 Gemini 分析 BusinessEvent，填充 direction, status, counterparty, counterparty_role
"""
import kuzu
import json
import time
import os
import requests
from typing import List, Dict

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM")
KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"
BATCH_SIZE = 20

# VSG 别名
VSG_ALIASES = [
    "VULCAN SHIELD GLOBAL", "VSG", "VULCANSHIELD", "VULCAN SHIELD",
    "VULCAN SHIELD GLOBAL PTE", "VULCAN SHIELD GLOBAL PTE. LTD."
]

def is_vsg(name: str) -> bool:
    if not name:
        return False
    upper = name.upper().strip()
    return any(alias in upper for alias in VSG_ALIASES)


ANALYSIS_PROMPT = """你是B2B商业分析专家。分析以下业务事件，判断：

1. direction（资金/货物流向，相对于 VSG/Vulcan Shield 公司）:
   - inbound: 收入/收货（客户付款给我们，货物发给我们）
   - outbound: 支出/发货（我们付款，我们发货给客户）
   - internal: 内部事务
   - unknown: 无法判断

2. status:
   - completed: 已完成（已付款、已签署、已发货、已到货）
   - pending: 进行中/待处理
   - unknown: 无法判断

3. counterparty: 交易对手公司名（不是VSG的那一方）

4. counterparty_role:
   - customer: 客户（买我们的东西）
   - supplier: 供应商（卖东西给我们）
   - logistics: 物流公司
   - bank: 银行
   - other: 其他

事件列表:
{events_json}

输出JSON数组，每个事件一个对象:
[
  {{"id": "evt_xxx", "direction": "...", "status": "...", "counterparty": "...", "counterparty_role": "..."}}
]

只输出JSON，不要其他内容。"""


def get_events_to_enrich(conn, limit: int = 500) -> List[Dict]:
    """获取需要分析的事件"""
    result = conn.execute(f"""
        MATCH (be:BusinessEvent)
        WHERE be.direction = unknown
        OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
        RETURN be.id, be.event_type, be.summary, be.amount, be.currency, 
               collect(DISTINCT c.canonical_name) as companies
        LIMIT {limit}
    """)
    
    events = []
    while result.has_next():
        r = result.get_next()
        companies = [c for c in (r[5] or []) if c and not is_vsg(c)]
        events.append({
            "id": r[0],
            "event_type": r[1],
            "summary": (r[2] or "")[:200],
            "amount": r[3] or 0,
            "currency": r[4] or "USD",
            "companies": companies
        })
    return events


def call_gemini(prompt: str) -> str:
    """直接调用 Gemini API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0}
    }
    
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def analyze_batch(events: List[Dict]) -> List[Dict]:
    """调用 Gemini 分析一批事件"""
    events_json = json.dumps(events, ensure_ascii=False, indent=2)
    prompt = ANALYSIS_PROMPT.format(events_json=events_json)
    
    try:
        text = call_gemini(prompt).strip()
        
        # 清理 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        text = text.strip()
        
        return json.loads(text)
    except Exception as e:
        print(f"  Gemini error: {e}")
        return []


def update_events(conn, results: List[Dict]):
    """更新数据库"""
    for r in results:
        try:
            event_id = r["id"]
            direction = r.get("direction", "unknown")
            status = r.get("status", "unknown")
            counterparty = r.get("counterparty", "")
            role = r.get("counterparty_role", "")
            
            conn.execute(f"""
                MATCH (be:BusinessEvent {{id: "{event_id}"}})
                SET be.direction = "{direction}",
                    be.status = "{status}",
                    be.counterparty = "{counterparty}",
                    be.counterparty_role = "{role}"
            """)
        except Exception as e:
            print(f"  Update error {r.get(id)}: {e}")


def main():
    print("=" * 60)
    print("Gemini 事件分析 - 填充 direction/status/counterparty")
    print("=" * 60)
    
    db = kuzu.Database(KUZU_PATH)
    conn = kuzu.Connection(db)
    
    # 获取待分析事件
    events = get_events_to_enrich(conn, limit=800)
    print(f"\n待分析事件: {len(events)}")
    
    if not events:
        print("没有需要分析的事件")
        return
    
    # 分批处理
    total_updated = 0
    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i:i+BATCH_SIZE]
        print(f"\n批次 {i//BATCH_SIZE + 1}/{(len(events)-1)//BATCH_SIZE + 1}: 分析 {len(batch)} 条...")
        
        results = analyze_batch(batch)
        if results:
            update_events(conn, results)
            total_updated += len(results)
            print(f"  更新: {len(results)} 条")
        
        time.sleep(0.5)
    
    print("\n" + "="*60)
    print(f"✅ 完成: 共更新 {total_updated} 条")
    
    # 统计结果
    print("\n" + "=" * 60)
    print("统计结果")
    print("=" * 60)
    
    for field in ["direction", "status", "counterparty_role"]:
        result = conn.execute(f"""
            MATCH (be:BusinessEvent)
            WHERE be.{field} <> unknown AND be.{field} <> 
            RETURN be.{field}, count(*) as cnt
            ORDER BY cnt DESC
        """)
        print(f"\n{field}:")
        while result.has_next():
            r = result.get_next()
            print(f"  {r[0]}: {r[1]}")


if __name__ == "__main__":
    main()
