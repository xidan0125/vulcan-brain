#\!/usr/bin/env python3
"""
Insight Agent v6 - JSON文件输出版
- 读取 02_extraction.json
- 输出到 03_insights.json（覆盖式）
- 保留 MongoDB 兼容
"""
import asyncio
import json
import re
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import pymongo
import httpx

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
DATA_DIR = Path.home() / "vulcan-brain" / "data" / "rongrong"

VLLM_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 8000
}

# ========== Prompt ==========
CEO_INSIGHT_PROMPT = """# 角色设定

你是 **CEO 的战略过滤器**——帮老板看清"现在有哪些力量在拉扯公司"，并过滤掉不值得他关注的噪音。

# 今天的日期
**今天是 {today_date}**

# CEO 思维核心

**North Star**: 成为航空航天/新能源领域高端氧化铝纤维的首选供应商

**战略优先级**:
1. 客户认证通过率（审厂、样件验证）
2. 产能与质量稳定
3. 现金流健康

# Signal vs Noise 判断

| 问自己 | 如果"否" → 噪音 |
|--------|-----------------|
| 这需要 CEO 亲自决策吗？ | 团队自行处理的事不算信号 |
| 忽略它会影响战略优先级吗？ | 不影响北极星的事是噪音 |
| 3个月后回看，这件事重要吗？ | 短期波动不算信号 |

**关键原则：宁可少报，不可滥报。老板的注意力是稀缺资源。**

# 公司背景
榕融新材料：氧化铝连续纤维生产商。产品用于航空航天、新能源汽车等耐高温场景。

# 今日业务数据
{data_summary}

# 输出结构（严格JSON）

```json
{{
  "executive_summary": "一段话概述今日局势",
  
  "tension_points": [
    {{
      "point": "局势点描述",
      "signals": ["信号1", "信号2"],
      "implication": "这意味着什么"
    }}
  ],
  
  "attention_focus": {{
    "which_point": "最值得注意的局势点",
    "why_now": "为什么是现在",
    "suggested_action": "建议动作"
  }},
  
  "financial_summary": {{
    "inflows": [{{"amount": "金额", "source": "来源", "event": "事件"}}],
    "outflows": [{{"amount": "金额", "destination": "去向", "event": "事件"}}],
    "comment": "财务态势一句话"
  }},
  
  "key_people": [
    {{"name": "人名", "count": 3, "activities": ["活动1", "活动2"]}}
  ],
  
  "watchlist": [
    {{"item": "要盯什么", "timeframe": "3天/7天/本月", "why": "为什么"}}
  ]
}}
```

# tension_points 要求

1. 只输出真正值得 CEO 关注的局势点（1-3个）
2. 如果今天平淡无奇，诚实说"今日无显著张力"
3. 描述趋势/张力/阶段性变化，不是事实罗列
4. 用老板能理解的语言

仅返回 JSON，无其他内容。
"""


def extract_first_json(text: str) -> Optional[Dict]:
    """提取第一个完整 JSON"""
    text = text.replace("```json", "").replace("```", "")
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i, c in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == "'" and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def save_json_atomic(filepath: Path, data: dict):
    """原子写入JSON文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=filepath.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
    except Exception:
        os.unlink(tmp_path)
        raise


def prepare_data_summary(events: Dict) -> str:
    """将 extraction 事件转换为摘要"""
    lines = []

    category_map = {
        "SALES": "客户/销售",
        "OPERATIONS": "生产/供应链",
        "DELIVERY": "物流/交付",
        "GOVERNANCE": "公司治理"
    }

    for category in ["SALES", "OPERATIONS", "DELIVERY", "GOVERNANCE"]:
        items = events.get(category, [])
        if not items:
            continue

        display_name = category_map.get(category, category)
        lines.append(f"\n## {display_name} ({len(items)}条)")

        by_style = {"GAIN": [], "RISK": [], "INSIGHT": [], "LOG": []}
        for item in items:
            style = item.get("style") or "LOG"
            by_style.get(style, by_style["LOG"]).append(item)

        for style in ["RISK", "GAIN", "INSIGHT", "LOG"]:
            style_items = by_style[style]
            if not style_items:
                continue

            style_labels = {"RISK": "⚠️风险", "GAIN": "✅进展", "INSIGHT": "💡洞察", "LOG": "📝日常"}
            lines.append(f"  {style_labels.get(style, style)}:")

            for item in style_items[:5]:
                tag = item.get("tag", "?")
                summary = item.get("summary", "")[:60]
                highlights = item.get("highlights", {})
                entities = highlights.get("entities", [])[:3]
                numbers = highlights.get("numbers", [])[:3]

                lines.append(f"    • {tag}: {summary}")
                if entities:
                    lines.append(f"      人/公司: {", ".join(str(e) for e in entities)}")
                if numbers:
                    lines.append(f"      数字: {", ".join(str(n) for n in numbers)}")

    # ADMIN 财务相关
    admin_items = events.get("ADMIN", [])
    if admin_items:
        finance_keywords = ["报销", "付款", "财务", "费用", "结算", "回款", "收款", "开票", "审批", "预算"]
        finance_items = [i for i in admin_items if any(k in i.get("tag", "") + i.get("summary", "") for k in finance_keywords)]
        if finance_items:
            lines.append(f"\n## 财务相关 ({len(finance_items)}条)")
            for item in finance_items[:5]:
                tag = item.get("tag", "")
                summary = item.get("summary", "")[:50]
                highlights = item.get("highlights", {})
                numbers = highlights.get("numbers", [])[:2]
                lines.append(f"    • {tag}: {summary}")
                if numbers:
                    lines.append(f"      数字: {", ".join(str(n) for n in numbers)}")

    return "\n".join(lines)


async def call_vllm(prompt: str) -> str:
    """调用 vLLM"""
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            **VLLM_PARAMS
        })
        data = r.json()
        if "choices" not in data:
            raise Exception(f"vLLM error: {data}")
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        return content.strip()


class InsightAgent:
    def __init__(self, company: str, date_str: str):
        self.company = company
        self.date_str = date_str
        self.mongo = pymongo.MongoClient(MONGO_URI)
        self.db = self.mongo.vulcan_brain

    def get_extraction_events(self) -> Optional[Dict]:
        """从 02_extraction.json 读取事件"""
        json_path = DATA_DIR / self.company / self.date_str / "02_extraction.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("events", {})
        
        # 回退到 MongoDB
        run_doc = self.db.rongrong_filter_runs.find_one({
            "company": self.company,
            "date": self.date_str
        })
        if run_doc:
            return run_doc.get("extraction_results", {})
        return None

    async def generate_insights(self) -> Optional[Dict]:
        events = self.get_extraction_events()
        if not events:
            print("未找到 extraction 结果")
            return None

        # 统计
        print(f"Extraction 结果分布:")
        for cat in ["SALES", "OPERATIONS", "DELIVERY", "GOVERNANCE", "ADMIN", "FILE"]:
            items = events.get(cat, [])
            print(f"  {cat}: {len(items)}")

        data_summary = prepare_data_summary(events)
        print(f"数据摘要长度: {len(data_summary)} 字符")

        prompt = CEO_INSIGHT_PROMPT.format(data_summary=data_summary, today_date=self.date_str)

        print("调用 LLM 生成 CEO 洞察...")
        result = await call_vllm(prompt)

        insights = extract_first_json(result)
        if not insights:
            print("JSON 解析失败")
            print(f"原始输出: {result[:500]}...")
            return None

        # 添加元数据
        insights["date"] = self.date_str
        insights["company"] = self.company
        insights["created_at"] = datetime.now(timezone.utc).isoformat()
        insights["version"] = "v1.0"

        return insights

    def save_insights(self, insights: Dict):
        """保存到 JSON 文件和 MongoDB"""
        # 保存到 JSON
        json_path = DATA_DIR / self.company / self.date_str / "03_insights.json"
        save_json_atomic(json_path, insights)
        print(f"Saved to {json_path}")

        # 保存到 MongoDB（兼容旧系统）
        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {"$set": {
                "insights_v6": insights,
                "insights_v6_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )

    def print_insights(self, insights: Dict):
        print("\n" + "=" * 70)
        print(f"📊 榕融新材料 CEO 洞察 - {self.date_str}")
        print("=" * 70)

        print(f"\n📋 执行摘要")
        print(f"   {insights.get('executive_summary', '?')}") 

        print(f"\n🌊 张力点")
        for i, tp in enumerate(insights.get("tension_points", []), 1):
            print(f"   {i}. {tp.get('point', '?')}")
            print(f"      含义: {tp.get('implication', '')}")

        focus = insights.get("attention_focus", {})
        print(f"\n👁️ 此刻最值得注意")
        print(f"   → {focus.get('which_point', '?')}")
        print(f"   建议: {focus.get('suggested_action', '')}")

        fp = insights.get("financial_summary", {})
        print(f"\n💰 财务态势: {fp.get('comment', '?')}")

        watchlist = insights.get("watchlist", [])
        if watchlist:
            print(f"\n⏰ 要盯的事")
            for item in watchlist[:3]:
                print(f"   • {item.get('item', '?')} ({item.get('timeframe', '?')})")

        print("\n" + "=" * 70)

    async def run(self):
        insights = await self.generate_insights()
        if insights:
            self.save_insights(insights)
            self.print_insights(insights)
            return insights
        return None


async def main():
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"

    agent = InsightAgent(company, date_str)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
