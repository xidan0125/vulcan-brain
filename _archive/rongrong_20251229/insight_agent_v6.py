#!/usr/bin/env python3
"""
Insight Agent v6 - LLM 承包日报后端数据
- 智能去重 extraction_results
- 生成 CEO 洞察（含财务摘要）
- 思维链输出
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
import pymongo
import httpx

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

VLLM_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 12000
}

# ========== 去重 Prompt ==========
DEDUP_PROMPT = """# 任务：智能去重业务事件

你是一个数据清洗专家。下面是从企业邮件中提取的业务事件列表，但有很多重复或高度相似的条目。

## 去重规则

1. **完全重复**：同一件事被提取了多次 → 只保留信息最完整的那条
2. **语义重复**：不同表述但描述同一件事 → 合并为一条，保留最详细的描述
3. **关联事件**：同一件事的不同阶段（如"申请→通过"）→ 保留最新状态

## 判断是否重复的线索
- 相同的人名、公司名、项目名
- 相同的金额、日期、订单号
- 相同的动作（审批、发送、确认等）

## 原始数据

{raw_data}

## 输出要求

对每个分类（SALES, GOVERNANCE, DELIVERY, OPERATIONS），输出去重后的事件列表。

```json
{{
  "thinking": "你的思考过程：哪些是重复的，为什么",
  "deduped": {{
    "SALES": [
      {{"tag": "标签", "style": "RISK/GAIN/INSIGHT/LOG", "summary": "去重后的摘要", "numbers": ["相关数字"]}}
    ],
    "GOVERNANCE": [...],
    "DELIVERY": [...],
    "OPERATIONS": [...]
  }},
  "stats": {{
    "original_count": 原始总数,
    "deduped_count": 去重后总数,
    "removed_count": 删除了多少重复
  }}
}}
```

仅返回 JSON。
"""

# ========== CEO 洞察 Prompt ==========
CEO_INSIGHT_PROMPT = """# 角色设定

你是 **CEO 的战略过滤器**——帮老板看清"现在有哪些力量在拉扯公司"，并过滤掉不值得他关注的噪音。

# 今天的日期
**{today_date}**

# 公司背景
榕融新材料：氧化铝连续纤维生产商。产品用于航空航天、新能源汽车等耐高温场景。
核心客户：比亚迪、宁德时代、航空航天研究院等。

# 战略优先级
1. 客户认证通过率（审厂、样件验证）
2. 产能与质量稳定
3. 现金流健康

# 今日业务数据（已去重）
{data_summary}

# 输出要求

请先思考，然后输出 JSON。

## 思考过程（放在 thinking 字段）
1. 今天有什么值得 CEO 关注的？
2. 财务方面有什么大额流入流出？
3. 哪些人今天比较活跃？
4. 有什么需要老板盯着的事？

## JSON 结构

```json
{{
  "thinking": "你的思考过程...",

  "executive_summary": "一句话总结今天的局势（20-50字）",

  "tension_points": [
    {{
      "point": "张力点描述",
      "implication": "这意味着什么"
    }}
  ],

  "financial_summary": {{
    "inflows": [
      {{"amount": "金额（如294,800元）", "source": "来源客户/事由", "event": "回款/收款/确认"}}
    ],
    "outflows": [
      {{"amount": "金额", "destination": "去向", "event": "付款/报销/采购"}}
    ],
    "comment": "一句话点评现金流状态"
  }},

  "key_people": [
    {{"name": "姓名", "activities": ["今日做了什么"], "count": 出现次数}}
  ],

  "watchlist": [
    {{"item": "要盯什么", "timeframe": "3天/7天/本月", "why": "为什么要盯"}}
  ]
}}
```

## 重要提醒

1. **financial_summary 必须输出**：即使没有大额流动，也要写 "今日无显著财务变动"
2. **金额要带单位**：如 "294,800元"、"147.06KG"
3. **key_people 至少3人**：从数据中提取活跃人物
4. **tension_points 可以为空**：如果今天真的平淡，诚实说"无显著张力"

仅返回 JSON，无其他内容。
"""


def extract_first_json(text: str) -> Optional[Dict]:
    """提取第一个完整 JSON"""
    text = text.replace("```json", "").replace("```", "")
    # 移除 thinking 标签
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i, c in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def format_extraction_for_dedup(extraction_results: Dict) -> str:
    """格式化 extraction 数据供去重"""
    lines = []
    for category in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
        items = extraction_results.get(category, [])
        if not items:
            continue

        lines.append(f"\n## {category} ({len(items)}条)")
        for i, item in enumerate(items, 1):
            tag = item.get("tag", "?")
            style = item.get("style", "LOG")
            summary = item.get("summary", "")
            highlights = item.get("highlights", {})
            numbers = highlights.get("numbers", [])
            entities = highlights.get("entities", [])

            lines.append(f"{i}. [{style}] {tag}: {summary}")
            if numbers:
                lines.append(f"   数字: {', '.join(str(n) for n in numbers)}")
            if entities:
                lines.append(f"   实体: {', '.join(str(e) for e in entities[:3])}")

    return "\n".join(lines)


def format_deduped_for_insight(deduped: Dict) -> str:
    """格式化去重后的数据供 insight 生成"""
    lines = []
    category_names = {
        "SALES": "销售/客户",
        "GOVERNANCE": "公司治理",
        "DELIVERY": "物流交付",
        "OPERATIONS": "生产运营"
    }

    for category in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
        items = deduped.get(category, [])
        if not items:
            continue

        name = category_names.get(category, category)
        lines.append(f"\n## {name} ({len(items)}条)")

        # 按 style 分组
        by_style = {"RISK": [], "GAIN": [], "INSIGHT": [], "LOG": []}
        for item in items:
            style = item.get("style", "LOG")
            by_style.get(style, by_style["LOG"]).append(item)

        for style in ["RISK", "GAIN", "INSIGHT", "LOG"]:
            style_items = by_style[style]
            if not style_items:
                continue

            labels = {"RISK": "⚠️风险", "GAIN": "✅进展", "INSIGHT": "💡洞察", "LOG": "📝日常"}
            lines.append(f"  {labels[style]}:")

            for item in style_items:
                tag = item.get("tag", "?")
                summary = item.get("summary", "")
                numbers = item.get("numbers", [])

                lines.append(f"    • {tag}: {summary}")
                if numbers:
                    lines.append(f"      金额/数量: {', '.join(str(n) for n in numbers)}")

    return "\n".join(lines)


async def call_vllm(prompt: str) -> str:
    """调用 vLLM"""
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            **VLLM_PARAMS
        })
        data = r.json()
        if "choices" not in data:
            raise Exception(f"vLLM error: {data}")
        content = data["choices"][0]["message"]["content"]
        return content.strip()


class InsightAgentV6:
    def __init__(self, company: str, date_str: str):
        self.company = company
        self.date_str = date_str
        self.mongo = pymongo.MongoClient(MONGO_URI)
        self.db = self.mongo.vulcan_brain

    def get_extraction_results(self) -> Optional[Dict]:
        run_doc = self.db.rongrong_filter_runs.find_one({
            "company": self.company,
            "date": self.date_str
        })
        if not run_doc or "extraction_results" not in run_doc:
            return None
        return run_doc["extraction_results"]

    async def step1_dedup(self, extraction_results: Dict) -> Dict:
        """Step 1: LLM 智能去重"""
        print("\n=== Step 1: 智能去重 ===")

        raw_data = format_extraction_for_dedup(extraction_results)
        prompt = DEDUP_PROMPT.format(raw_data=raw_data)

        print(f"原始数据长度: {len(raw_data)} 字符")
        print("调用 LLM 进行去重...")

        result = await call_vllm(prompt)
        dedup_result = extract_first_json(result)

        if not dedup_result:
            print("去重 JSON 解析失败，使用原始数据")
            # 返回原始数据的简化版
            return {
                "SALES": extraction_results.get("SALES", []),
                "GOVERNANCE": extraction_results.get("GOVERNANCE", []),
                "DELIVERY": extraction_results.get("DELIVERY", []),
                "OPERATIONS": extraction_results.get("OPERATIONS", [])
            }

        # 打印思考过程
        if dedup_result.get("thinking"):
            print(f"\nLLM 思考过程:\n{dedup_result['thinking'][:500]}...")

        stats = dedup_result.get("stats", {})
        print(f"\n去重统计: 原始 {stats.get('original_count', '?')} → 去重后 {stats.get('deduped_count', '?')} (删除 {stats.get('removed_count', '?')})")

        return dedup_result.get("deduped", {})

    async def step2_insight(self, deduped: Dict) -> Dict:
        """Step 2: 生成 CEO 洞察"""
        print("\n=== Step 2: 生成 CEO 洞察 ===")

        data_summary = format_deduped_for_insight(deduped)
        prompt = CEO_INSIGHT_PROMPT.format(
            data_summary=data_summary,
            today_date=self.date_str
        )

        print(f"去重后数据长度: {len(data_summary)} 字符")
        print("调用 LLM 生成洞察...")

        result = await call_vllm(prompt)
        insights = extract_first_json(result)

        if not insights:
            print("洞察 JSON 解析失败")
            print(f"原始输出: {result[:500]}...")
            return None

        # 打印思考过程
        if insights.get("thinking"):
            print(f"\nLLM 思考过程:\n{insights['thinking'][:500]}...")

        return insights

    async def generate(self) -> Optional[Dict]:
        """完整流程"""
        extraction_results = self.get_extraction_results()
        if not extraction_results:
            print("未找到 extraction 结果")
            return None

        # 统计原始数据
        print(f"\n原始 Extraction 结果分布:")
        total = 0
        for cat in ["SALES", "OPERATIONS", "DELIVERY", "GOVERNANCE", "ADMIN", "FILE"]:
            count = len(extraction_results.get(cat, []))
            total += count
            print(f"  {cat}: {count}")
        print(f"  总计: {total}")

        # Step 1: 去重
        deduped = await self.step1_dedup(extraction_results)

        # Step 2: 生成洞察
        insights = await self.step2_insight(deduped)

        if not insights:
            return None

        # 组装最终结果
        final_result = {
            "insights": insights,
            "deduped_extraction": deduped,
            "meta": {
                "company": self.company,
                "date": self.date_str,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "agent_version": "v6-llm-dedup"
            }
        }

        # 保存到数据库
        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {"$set": {
                "insights_v6": final_result["insights"],
                "deduped_extraction": final_result["deduped_extraction"],
                "insights_v6_at": datetime.now(timezone.utc)
            }}
        )

        return final_result

    def print_result(self, result: Dict):
        insights = result.get("insights", {})
        deduped = result.get("deduped_extraction", {})

        print(f"\n{'='*70}")
        print(f"📊 榕融日报 - {self.date_str}")
        print(f"{'='*70}")

        # 执行摘要
        print(f"\n📋 执行摘要")
        print(f"   {insights.get('executive_summary', '无')}")

        # 张力点
        print(f"\n⚡ 张力点")
        tension_points = insights.get("tension_points", [])
        if tension_points:
            for i, tp in enumerate(tension_points, 1):
                print(f"   {i}. {tp.get('point', '?')}")
                print(f"      → {tp.get('implication', '')}")
        else:
            print("   今日无显著张力")

        # 财务摘要
        print(f"\n💰 财务摘要")
        fin = insights.get("financial_summary", {})

        inflows = fin.get("inflows", [])
        if inflows:
            print("   流入:")
            for item in inflows[:3]:
                print(f"      + {item.get('amount', '?')} | {item.get('source', '?')} | {item.get('event', '?')}")

        outflows = fin.get("outflows", [])
        if outflows:
            print("   流出:")
            for item in outflows[:3]:
                print(f"      - {item.get('amount', '?')} | {item.get('destination', '?')} | {item.get('event', '?')}")

        comment = fin.get("comment", "")
        if comment:
            print(f"   点评: {comment}")

        # 关键人物
        print(f"\n👥 关键人物")
        for person in insights.get("key_people", [])[:5]:
            name = person.get("name", "?")
            count = person.get("count", 0)
            activities = person.get("activities", [])
            print(f"   • {name} ({count}次): {', '.join(activities[:2])}")

        # 要盯的事
        print(f"\n⏰ 要盯的事")
        for item in insights.get("watchlist", [])[:3]:
            print(f"   • {item.get('item', '?')} [{item.get('timeframe', '?')}]")
            print(f"     {item.get('why', '')}")

        # 去重统计
        print(f"\n📊 去重后数据")
        for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
            count = len(deduped.get(cat, []))
            print(f"   {cat}: {count}")

        print(f"\n{'='*70}")


async def main():
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"

    agent = InsightAgentV6(company, date_str)
    result = await agent.generate()

    if result:
        agent.print_result(result)

        with open(f"/tmp/insight_v6_{date_str}.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到 /tmp/insight_v6_{date_str}.json")


if __name__ == "__main__":
    asyncio.run(main())
