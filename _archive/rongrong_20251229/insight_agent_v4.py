#!/usr/bin/env python3
"""
Insight Agent v4 - 混沌友好版
核心理念：企业管理是混沌系统，不是数学求解

设计哲学：
- State → Situation（张力场）
- 不强行收敛，允许 2-4 个局势点并存
- 承认不确定性，展示张力
- 让老板感觉"这像我自己想的"

结构：
- Company Situation: 2-4 个并行局势点（不统一、不归因、不给最终结论）
- Attention Focus: 这些局势中，哪一个最值得 Owner 此刻注意
- Functional Snapshots: 职能切面快照
- Financial Pulse: 财务态势
- Owner Watchlist: 要盯的事
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
    "max_tokens": 8000
}

# ========== 混沌友好版 Prompt ==========
CHAOS_FRIENDLY_PROMPT = """# 角色设定

你不是秘书、不是汇总机器人、不是分析师。
你是 **CEO 的战略过滤器**——帮老板看清"现在有哪些力量在拉扯公司"，并过滤掉不值得他关注的噪音。

# 今天的日期
**今天是 {today_date}**

# CEO 思维操作系统（这是你的核心认知框架）

## 1. 榕融的 North Star 与战略优先级

**North Star**: 成为航空航天/新能源领域高端氧化铝纤维的首选供应商

**当前战略优先级**（按重要性排序）:
1. 客户认证通过率（审厂、样件验证）—— 决定能否进入核心供应链
2. 产能与质量稳定 —— 决定能否接住大单
3. 现金流健康 —— 决定能否持续运营

## 2. 三个 CEO 级思维框架

**Second-Order Thinking（二阶思考）**
- 不只看"发生了什么"，要问"然后呢？如果失控，3个月后会怎样？"
- 示例：审厂资料延误 → 客户认证失败 → 失去进入供应链的机会 → 这是真风险
- 示例：顺丰月结账单 → 财务正常处理 → 没有后续影响 → 这是噪音

**Inversion Thinking（逆向思考）**
- 问自己：什么样的事情被老板忽略了，会让公司陷入麻烦？
- 如果答案是"不会"，那这件事就不值得放进张力点

**Materiality Filter（物质性过滤）**
- ¥690 顺丰账单 vs ¥294,800 客户回款 —— 量级差 400 倍，关注度应该差 400 倍
- 例行操作（月结、常规订舱）vs 战略节点（审厂、新客户首单）—— 只有后者值得 CEO 关注

## 3. Signal vs Noise 的判断标准

| 问自己 | 如果答案是"否" → 这是噪音 |
|--------|---------------------------|
| 这需要 CEO 亲自决策吗？ | 团队自行处理的事不算信号 |
| 忽略它会影响战略优先级吗？ | 不影响北极星的事是噪音 |
| 3个月后回看，这件事重要吗？ | 短期波动不算信号 |
| 这是系统性风险还是操作琐事？ | 琐事不算信号 |

**关键原则：宁可少报，不可滥报。老板的注意力是稀缺资源。**

# 核心原则（非常重要）

1. **企业管理是混沌系统，不是数学求解**
2. **不要强行把多重张力压成一个结论**
3. **允许多个局势点并行存在，甚至互相矛盾**
4. **老板信任的不是"答案"，而是"认知方式是否对齐"**
5. **如果今天真的没有值得关注的张力，可以只输出 1-2 个，不要凑数**

# 数据来源说明

每条事件数据包含：
- **邮件发送日期**（元数据）：系统自动记录，绝对可信
- **正文提取的日期**：从邮件内容提取，可能是笔误

正文里的日期可能指过去的事（正常），也可能是笔误。请结合上下文自行判断。

# 公司背景
榕融新材料：氧化铝连续纤维生产商。产品用于航空航天、新能源汽车等耐高温场景。
核心客户：比亚迪、宁德时代、航空航天研究院等。

# 今日业务数据
{data_summary}

# 输出结构（严格JSON）

```json
{{
  "company_situation": {{
    "description": "公司当下局势（多点并存，不强行收敛）",
    "tension_points": [
      {{
        "point": "局势点描述（一句话，描述趋势/张力/阶段性变化）",
        "signals": ["来自不同领域的信号1", "信号2"],
        "implication": "这意味着什么（不是结论，是含义）"
      }}
    ]
  }},

  "attention_focus": {{
    "which_point": "在上述局势点中，哪一个最值得 Owner 此刻注意",
    "why_now": "为什么是现在",
    "suggested_action": "Owner 可以做什么（问一句/看一眼/定边界）"
  }},

  "functional_snapshots": {{
    "production": {{
      "one_liner": "生产/现场一句话（有异常说异常，无异常说正常运转）",
      "key_people": ["关键人物"],
      "signal_level": "HIGH/MEDIUM/LOW/NONE"
    }},
    "supply_chain": {{
      "one_liner": "供应链/物流一句话",
      "key_people": ["关键人物"],
      "signal_level": "HIGH/MEDIUM/LOW/NONE"
    }},
    "management": {{
      "one_liner": "公司管理/行政一句话",
      "key_people": ["关键人物"],
      "signal_level": "HIGH/MEDIUM/LOW/NONE"
    }},
    "sales_customer": {{
      "one_liner": "销售/客户一句话",
      "key_people": ["关键人物"],
      "signal_level": "HIGH/MEDIUM/LOW/NONE"
    }}
  }},

  "financial_pulse": {{
    "inflows": [
      {{"amount": "金额", "source": "来源", "status": "confirmed/pending/expected"}}
    ],
    "outflows": [
      {{"amount": "金额", "destination": "去向", "status": "approved/pending/reminder"}}
    ],
    "rhythm": "一句话描述现金节奏感",
    "pressure": "HIGH/MEDIUM/LOW"
  }},

  "owner_watchlist": [
    {{
      "item": "要盯什么",
      "why": "为什么",
      "timeframe": "3天/7天/本月"
    }}
  ]
}}
```

# 关于 tension_points 的要求

1. **质量优先于数量**：只输出真正值得 CEO 关注的局势点，可以是 1-3 个
2. 每个局势点必须通过上面的 Signal vs Noise 判断标准
3. 每个局势点必须来自**不同领域的信号聚合**（不是单一事件）
4. 描述的是**趋势/张力/阶段性变化**，不是事实罗列
5. **不要求互相统一，允许并行甚至矛盾**
6. 用老板能理解的语言，不要用分析师语言
7. **如果今天真的平淡无奇，诚实说"今日无显著张力"比凑数更有价值**

# 示例局势点（风格参考，不要照抄）

- "年末治理信号明显抬头" - 预算、审计、咨询、规划类事项密集
- "客户审厂与内部安全提醒形成风险叠加" - 外部检验与内部问题同时暴露
- "业务与运营并未减速" - 供应链、样件、账款仍在高频运转

# 最终校验

输出前用 CEO 思维框架检验：

1. **Second-Order Test**: 每个局势点，如果被忽略，3个月后会怎样？
   - 如果答案是"没什么"→ 删掉它

2. **Inversion Test**: 这些局势点里，有没有"老板忽略了会后悔"的？
   - 如果都不会后悔 → 今天可能真的没什么大事

3. **Materiality Test**: 有没有把小额琐事当成风险？
   - ¥690 顺丰账单绝不应该出现在 tension_points 里

4. **老板视角 Test**:
   - 老板看完会不会点头说"对，这才是我今天应该关注的"？
   - 还是会皱眉说"这些我团队自己就能处理，为什么要告诉我"？

仅返回 JSON，无其他内容。
"""


def extract_first_json(text: str) -> Optional[Dict]:
    """提取第一个完整 JSON"""
    text = text.replace("```json", "").replace("```", "")
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


def prepare_data_summary(extraction_results: Dict, email_dates: Dict[str, str] = None) -> str:
    """将 extraction 结果转换为摘要，包含邮件发送日期"""
    lines = []
    email_dates = email_dates or {}

    category_map = {
        "CUSTOMER": "客户/销售",
        "SUPPLY_CHAIN": "供应链",
        "LOGISTICS": "物流",
        "MANAGEMENT": "公司管理"
    }

    for category in ["CUSTOMER", "SUPPLY_CHAIN", "LOGISTICS", "MANAGEMENT"]:
        items = extraction_results.get(category, [])
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
                source_id = item.get("source_id", "")
                highlights = item.get("highlights", {})
                entities = highlights.get("entities", [])[:3]
                numbers = highlights.get("numbers", [])[:3]

                # 获取邮件发送日期
                email_date = email_dates.get(source_id, "")
                date_str = f" [邮件日期:{email_date}]" if email_date else ""

                lines.append(f"    • {tag}: {summary}{date_str}")
                if entities:
                    lines.append(f"      人/公司: {', '.join(entities)}")
                if numbers:
                    lines.append(f"      正文日期: {', '.join(str(n) for n in numbers)}")

    # ADMIN 和 FILE
    admin_items = extraction_results.get("ADMIN", [])
    file_items = extraction_results.get("FILE", [])

    if admin_items or file_items:
        lines.append(f"\n## 行政/文件 ({len(admin_items) + len(file_items)}条)")

        finance_keywords = ['报销', '付款', '财务', '费用', '结算', '回款', '收款', '开票', '审批', '预算', '审计']
        for item in admin_items:
            tag = item.get("tag", "")
            if any(k in tag for k in finance_keywords):
                summary = item.get("summary", "")[:50]
                entities = item.get("entities", [])[:2]
                lines.append(f"    • {tag}: {summary}")

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
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content.strip()


class ChaosFriendlyAgent:
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

    def get_email_dates(self, extraction_results: Dict) -> Dict[str, str]:
        """获取所有 source_id 对应的邮件发送日期"""
        # 收集所有 source_id
        source_ids = []
        for cat, items in extraction_results.items():
            if isinstance(items, list):
                for item in items:
                    if item.get("source_id"):
                        source_ids.append(item["source_id"])

        if not source_ids:
            return {}

        # 查询邮件发送日期
        emails = self.db.wecom_emails.find(
            {"email_id": {"$in": source_ids}},
            {"email_id": 1, "received_at": 1}
        )

        email_dates = {}
        for email in emails:
            received_at = email.get("received_at")
            if received_at:
                # 格式化为 YYYY-MM-DD
                if hasattr(received_at, 'strftime'):
                    email_dates[email["email_id"]] = received_at.strftime("%Y-%m-%d")
                else:
                    email_dates[email["email_id"]] = str(received_at)[:10]

        return email_dates

    async def generate_insights(self) -> Optional[Dict]:
        extraction_results = self.get_extraction_results()
        if not extraction_results:
            print("未找到 extraction 结果")
            return None

        # 获取邮件发送日期映射
        email_dates = self.get_email_dates(extraction_results)
        print(f"获取了 {len(email_dates)} 封邮件的发送日期")

        data_summary = prepare_data_summary(extraction_results, email_dates)
        print(f"数据摘要长度: {len(data_summary)} 字符")

        prompt = CHAOS_FRIENDLY_PROMPT.format(data_summary=data_summary, today_date=self.date_str)

        print("调用 LLM 生成混沌友好洞察...")
        result = await call_vllm(prompt)

        insights = extract_first_json(result)
        if not insights:
            print("JSON 解析失败")
            print(f"原始输出: {result[:500]}...")
            return None

        insights["meta"] = {
            "company": self.company,
            "date": self.date_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent_version": "v5-ceo-mindset"
        }

        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {"$set": {
                "insights_v4": insights,
                "insights_v4_at": datetime.now(timezone.utc)
            }}
        )

        return insights

    def print_insights(self, insights: Dict):
        print(f"\n{'='*70}")
        print(f"📊 榕融新材料 混沌友好洞察 - {self.date_str}")
        print(f"{'='*70}")

        # Company Situation
        situation = insights.get("company_situation", {})
        print(f"\n🌊 公司当下局势（多点并存，不强行收敛）")

        for i, tp in enumerate(situation.get("tension_points", []), 1):
            print(f"\n   {i}. {tp.get('point', '?')}")
            signals = tp.get('signals', [])
            if signals:
                print(f"      信号: {', '.join(signals[:3])}")
            print(f"      含义: {tp.get('implication', '')}")

        # Attention Focus
        focus = insights.get("attention_focus", {})
        print(f"\n👁️ 此刻最值得注意")
        print(f"   → {focus.get('which_point', '?')}")
        print(f"   为什么是现在: {focus.get('why_now', '')}")
        print(f"   建议动作: {focus.get('suggested_action', '')}")

        # Functional Snapshots
        snapshots = insights.get("functional_snapshots", {})
        print(f"\n📋 职能快照")

        for key, label in [("production", "生产/现场"), ("supply_chain", "供应链/物流"),
                           ("management", "公司管理"), ("sales_customer", "销售/客户")]:
            func = snapshots.get(key, {})
            signal = func.get("signal_level", "NONE")
            icon = "🔴" if signal == "HIGH" else "🟡" if signal == "MEDIUM" else "🟢" if signal == "LOW" else "⚪"
            print(f"   {icon} [{label}] {func.get('one_liner', '无显著异常')}")
            people = func.get('key_people', [])
            if people and signal in ["HIGH", "MEDIUM"]:
                print(f"      关键人: {', '.join(people)}")

        # Financial Pulse
        fp = insights.get("financial_pulse", {})
        print(f"\n💰 财务态势")

        inflows = fp.get("inflows", [])
        if inflows:
            print(f"   流入:")
            for item in inflows[:3]:
                print(f"      + {item.get('amount', '?')} | {item.get('source', '?')} | {item.get('status', '?')}")

        outflows = fp.get("outflows", [])
        if outflows:
            print(f"   流出:")
            for item in outflows[:3]:
                print(f"      - {item.get('amount', '?')} | {item.get('destination', '?')} | {item.get('status', '?')}")

        pressure = fp.get("pressure", "?")
        pressure_icon = "🔴" if pressure == "HIGH" else "🟡" if pressure == "MEDIUM" else "🟢"
        print(f"   节奏: {fp.get('rhythm', '?')}")
        print(f"   压力: {pressure_icon} {pressure}")

        # Owner Watchlist
        watchlist = insights.get("owner_watchlist", [])
        if watchlist:
            print(f"\n⏰ 要盯的事")
            for item in watchlist[:3]:
                print(f"   • {item.get('item', '?')} ({item.get('timeframe', '?')})")
                print(f"     {item.get('why', '')}")

        print(f"\n{'='*70}")


async def main():
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"

    agent = ChaosFriendlyAgent(company, date_str)
    insights = await agent.generate_insights()

    if insights:
        agent.print_insights(insights)

        with open(f"/tmp/insights_v4_{date_str}.json", "w") as f:
            json.dump(insights, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到 /tmp/insights_v4_{date_str}.json")


if __name__ == "__main__":
    asyncio.run(main())
