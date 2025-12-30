#!/usr/bin/env python3
"""
Insight Agent v7 - 多步工作流版本

工作流:
  Step 1: 数据清洗 - 过滤无意义数字，标准化格式
  Step 2: 智能去重 - LLM 语义去重，每个 event 只保留一个关键数字
  Step 3: 财务提取 - 专门扫描提取资金流入流出
  Step 4: 生成洞察 - 执行摘要、张力点、关键人物、要盯的事
  Step 5: 组装报告 - 前端可用的完整 schema
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import pymongo
import httpx

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# ========== 无意义数字过滤 ==========
def is_meaningless_number(s: str) -> bool:
    """判断是否是无意义的数字（日期、订单号等）"""
    s = str(s).strip()

    # 日期格式
    if re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', s):  # 2025-12-26
        return True
    if re.match(r'^\d{1,2}[-/]\d{1,2}$', s):  # 12/26
        return True
    if re.match(r'^\d{4}年', s):  # 2025年
        return True
    if re.match(r'^\d{1,2}月\d{1,2}日', s):  # 12月26日
        return True
    if re.match(r'^\(\d{4}[-/]\d{1,2}[-/]\d{1,2}\)$', s):  # (2025/12/25)
        return True

    # 订单号、合同号
    if re.match(r'^RRJS-', s, re.I):
        return True
    if re.match(r'^202\d{6,}', s):  # 长数字开头
        return True

    # 纯长数字（ID类）
    if re.match(r'^\d{8,}$', s):
        return True

    # 手机号
    if re.match(r'^1[3-9]\d{9}$', s):
        return True

    # 时间
    if re.match(r'^\d{1,2}:\d{2}', s):
        return True

    return False

def extract_meaningful_number(numbers: List[str]) -> Optional[str]:
    """从数字列表中提取最有意义的一个（金额/重量/数量）"""
    if not numbers:
        return None

    # 过滤无意义的
    useful = [n for n in numbers if not is_meaningless_number(str(n))]
    if not useful:
        return None

    # 优先级：带单位的 > 纯数字
    priority_units = ['元', '万', '万元', 'kg', 'KG', '吨', '千克', '公斤', '个', '件', '台', '套', '米', '%']

    for num in useful:
        num_str = str(num)
        for unit in priority_units:
            if unit in num_str:
                return num_str

    # 返回第一个有用的（如果是合理范围的数字）
    first = str(useful[0])
    # 过滤掉看起来像ID的纯数字
    if re.match(r'^\d+$', first) and len(first) > 6:
        return None
    return first


# ========== Step 2: 去重 Prompt ==========
DEDUP_PROMPT = """你是数据清洗专家。对业务事件去重并输出JSON。

## 规则
1. 同一件事只保留一条
2. 语义相同的合并
3. key_number只填金额/重量/数量，不填日期/订单号

## 数据
{raw_data}

## 输出
严格按此JSON格式，不要输出其他内容：

```json
{{
  "SALES": [{{"tag":"标签","style":"RISK/GAIN/INSIGHT/LOG","summary":"摘要","key_number":null}}],
  "GOVERNANCE": [],
  "DELIVERY": [],
  "OPERATIONS": [],
  "ADMIN": [],
  "FILE": []
}}
```

现在输出JSON："""


# ========== Step 3: 财务提取 Prompt ==========
FINANCE_PROMPT = """# 任务：提取财务信息

从下面的业务数据中，找出所有涉及资金流动的事件。

## 业务数据
{data}

## 提取要求

找出：
1. **资金流入**：回款、收款、客户付款、到账等
2. **资金流出**：付款、采购、报销、预付等

## 输出格式

```json
{{
  "inflows": [
    {{"amount": "金额（如294,800元）", "source": "来源（客户/事由）", "event": "事件类型"}}
  ],
  "outflows": [
    {{"amount": "金额", "destination": "去向", "event": "事件类型"}}
  ],
  "comment": "一句话点评今日资金状况（如无则写'今日无显著财务变动'）"
}}
```

注意：
- 金额必须带单位（元/万/万元）
- 如果数据中没有财务信息，inflows/outflows 返回空数组
- comment 必填

仅返回 JSON。"""


# ========== Step 4: 洞察生成 Prompt ==========
INSIGHT_PROMPT = """# 角色：CEO 战略参谋

为老板生成今日简报。

# 公司背景
榕融新材料：氧化铝纤维制造商，服务航空航天、新能源汽车客户。
战略重点：客户认证、产能稳定、现金流健康。

# 今日：{today_date}

# 业务数据
{data_summary}

# 财务摘要（已提取）
{finance_summary}

# 输出要求

```json
{{
  "executive_summary": "一句话概括今日态势（20-40字）",

  "tension_points": [
    {{"point": "张力点", "implication": "影响"}}
  ],

  "key_people": [
    {{"name": "姓名", "count": 出现次数, "activities": ["活动"]}}
  ],

  "watchlist": [
    {{"item": "要盯的事", "timeframe": "3天/7天/本月", "why": "原因"}}
  ]
}}
```

要求：
1. executive_summary：必填，概括最重要的1-2件事
2. tension_points：有风险就写，没有则为空数组
3. key_people：至少3人
4. watchlist：至少2项

仅返回 JSON。"""


def extract_json(text: str) -> Optional[Dict]:
    """提取 JSON"""
    text = text.replace("```json", "").replace("```", "")
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
        if c == '"':
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
                except:
                    return None
    return None


async def call_llm(prompt: str) -> str:
    """调用 LLM"""
    async with httpx.AsyncClient(timeout=600) as client:
        # 使用 system message 禁用 thinking
        messages = [
            {"role": "system", "content": "You are a data processing assistant. Output JSON only, no thinking or explanations."},
            {"role": "user", "content": prompt}
        ]

        r = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 16000,
            "chat_template_kwargs": {"enable_thinking": False}
        })
        data = r.json()
        if "choices" not in data:
            print(f"  LLM Error: {data.get('error', data)}")
            raise Exception(f"LLM error: {data}")
        return data["choices"][0]["message"]["content"].strip()


class InsightAgentV7:
    def __init__(self, company: str, date_str: str):
        self.company = company
        self.date_str = date_str
        self.mongo = pymongo.MongoClient(MONGO_URI)
        self.db = self.mongo.vulcan_brain

    def load_data(self) -> Optional[Dict]:
        """加载原始数据"""
        doc = self.db.rongrong_filter_runs.find_one({
            "company": self.company,
            "date": self.date_str
        })
        return doc

    def step1_clean(self, extraction: Dict) -> str:
        """Step 1: 清洗数据，格式化供后续使用"""
        print("\n[Step 1] 数据清洗...")

        lines = []
        total = 0

        for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"]:
            items = extraction.get(cat, [])
            if not items:
                continue

            lines.append(f"\n## {cat}")

            for item in items:
                total += 1
                tag = item.get("tag", "")
                style = item.get("style", "LOG")
                summary = item.get("summary", "")

                # 提取有意义的数字
                numbers = item.get("highlights", {}).get("numbers", [])
                key_num = extract_meaningful_number(numbers)
                num_str = f" [{key_num}]" if key_num else ""

                lines.append(f"- [{style}] {tag}{num_str}: {summary}")

        print(f"  原始事件: {total} 条")
        return "\n".join(lines)

    async def step2_dedup(self, raw_data: str) -> Dict:
        """Step 2: LLM 去重"""
        print("\n[Step 2] 智能去重...")

        prompt = DEDUP_PROMPT.format(raw_data=raw_data)
        result = await call_llm(prompt)
        deduped = extract_json(result)

        if not deduped:
            print("  去重失败")
            return {}

        total = sum(len(deduped.get(cat, [])) for cat in
                   ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"])
        print(f"  去重后: {total} 条")

        return deduped

    async def step3_finance(self, deduped: Dict) -> Dict:
        """Step 3: 专门提取财务信息"""
        print("\n[Step 3] 财务信息提取...")

        # 格式化数据
        lines = []
        for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
            items = deduped.get(cat, [])
            for item in items:
                tag = item.get("tag", "")
                summary = item.get("summary", "")
                key_num = item.get("key_number", "")
                if key_num:
                    lines.append(f"- {tag} [{key_num}]: {summary}")
                else:
                    lines.append(f"- {tag}: {summary}")

        if not lines:
            print("  无数据，跳过")
            return {"inflows": [], "outflows": [], "comment": "今日无显著财务变动"}

        prompt = FINANCE_PROMPT.format(data="\n".join(lines))
        result = await call_llm(prompt)
        finance = extract_json(result)

        if not finance:
            print("  提取失败")
            return {"inflows": [], "outflows": [], "comment": "今日无显著财务变动"}

        # 确保结构完整
        finance.setdefault("inflows", [])
        finance.setdefault("outflows", [])
        finance.setdefault("comment", "今日无显著财务变动")

        print(f"  流入: {len(finance['inflows'])} 笔")
        print(f"  流出: {len(finance['outflows'])} 笔")

        return finance

    async def step4_insight(self, deduped: Dict, finance: Dict) -> Dict:
        """Step 4: 生成 CEO 洞察"""
        print("\n[Step 4] 生成 CEO 洞察...")

        # 格式化数据
        lines = []
        for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
            items = deduped.get(cat, [])
            if not items:
                continue

            cat_names = {"SALES": "销售", "GOVERNANCE": "治理", "DELIVERY": "交付", "OPERATIONS": "运营"}
            lines.append(f"\n### {cat_names.get(cat, cat)}")

            by_style = {"RISK": [], "GAIN": [], "INSIGHT": [], "LOG": []}
            for item in items:
                style = item.get("style", "LOG")
                by_style.get(style, by_style["LOG"]).append(item)

            for style in ["RISK", "GAIN", "INSIGHT", "LOG"]:
                if by_style[style]:
                    labels = {"RISK": "⚠️风险", "GAIN": "✅进展", "INSIGHT": "💡洞察", "LOG": "📝日常"}
                    lines.append(f"  {labels[style]}:")
                    for item in by_style[style]:
                        lines.append(f"    • {item.get('tag', '')}: {item.get('summary', '')}")

        # 财务摘要
        finance_lines = []
        if finance.get("inflows"):
            finance_lines.append("流入:")
            for f in finance["inflows"]:
                finance_lines.append(f"  + {f.get('amount', '?')} ({f.get('source', '')})")
        if finance.get("outflows"):
            finance_lines.append("流出:")
            for f in finance["outflows"]:
                finance_lines.append(f"  - {f.get('amount', '?')} ({f.get('destination', '')})")
        if not finance_lines:
            finance_lines.append(finance.get("comment", "今日无显著财务变动"))

        prompt = INSIGHT_PROMPT.format(
            today_date=self.date_str,
            data_summary="\n".join(lines),
            finance_summary="\n".join(finance_lines)
        )

        result = await call_llm(prompt)
        insights = extract_json(result)

        if not insights:
            print("  生成失败")
            return {
                "executive_summary": "数据处理中",
                "tension_points": [],
                "key_people": [],
                "watchlist": []
            }

        print(f"  执行摘要: {insights.get('executive_summary', '')[:30]}...")
        print(f"  张力点: {len(insights.get('tension_points', []))} 个")
        print(f"  关键人物: {len(insights.get('key_people', []))} 人")
        print(f"  待跟进: {len(insights.get('watchlist', []))} 项")

        return insights

    def step5_assemble(self, doc: Dict, deduped: Dict, finance: Dict, insights: Dict) -> Dict:
        """Step 5: 组装完整报告"""
        print("\n[Step 5] 组装报告...")

        # 按 style 组织 extraction
        extraction = {}
        for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"]:
            extraction[cat] = {"RISK": [], "GAIN": [], "INSIGHT": [], "LOG": []}

            for item in deduped.get(cat, []):
                style = item.get("style", "LOG")
                if style not in extraction[cat]:
                    style = "LOG"

                extraction[cat][style].append({
                    "tag": item.get("tag", ""),
                    "summary": item.get("summary", ""),
                    "key_number": item.get("key_number")
                })

        # 统计
        total_items = sum(len(deduped.get(cat, [])) for cat in
                        ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"])
        total_emails = len(doc.get("binary_filter_result", {}).get("KEEP", []))

        # 合并 insights 和 finance
        full_insights = {
            "executive_summary": insights.get("executive_summary", "暂无摘要"),
            "tension_points": insights.get("tension_points", []),
            "financial_summary": finance,
            "key_people": insights.get("key_people", []),
            "watchlist": insights.get("watchlist", [])
        }

        report = {
            "date": self.date_str,
            "company": self.company,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent_version": "v7",
            "stats": {
                "total_emails": total_emails,
                "tension_count": len(insights.get("tension_points", [])),
                "watchlist_count": len(insights.get("watchlist", [])),
                "total_items": total_items
            },
            "insights": full_insights,
            "extraction": extraction
        }

        print(f"  报告组装完成")
        return report

    def save(self, report: Dict):
        """保存到数据库"""
        self.db.rongrong_reports.update_one(
            {"company": self.company, "date": self.date_str},
            {"$set": report},
            upsert=True
        )

        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {"$set": {"report_v7": report, "report_v7_at": datetime.now(timezone.utc)}}
        )

        print(f"\n✅ 已保存到数据库")

    async def run(self) -> Optional[Dict]:
        """执行完整工作流"""
        print(f"\n{'='*50}")
        print(f"榕融日报生成 - {self.date_str}")
        print(f"{'='*50}")

        # 加载数据
        doc = self.load_data()
        if not doc or "extraction_results" not in doc:
            print("未找到数据")
            return None

        extraction = doc["extraction_results"]

        # Step 1: 清洗
        raw_data = self.step1_clean(extraction)

        # Step 2: 去重
        deduped = await self.step2_dedup(raw_data)

        # Step 3: 财务
        finance = await self.step3_finance(deduped)

        # Step 4: 洞察
        insights = await self.step4_insight(deduped, finance)

        # Step 5: 组装
        report = self.step5_assemble(doc, deduped, finance, insights)

        # 保存
        self.save(report)

        return report

    def print_report(self, report: Dict):
        """打印报告"""
        print(f"\n{'='*50}")
        print(f"📊 {report['date']} 日报")
        print(f"{'='*50}")

        ins = report["insights"]

        print(f"\n📋 {ins['executive_summary']}")

        print(f"\n⚡ 张力点 ({len(ins['tension_points'])})")
        for tp in ins["tension_points"]:
            print(f"   • {tp['point']}")

        print(f"\n💰 财务")
        fin = ins["financial_summary"]
        for f in fin.get("inflows", []):
            print(f"   + {f['amount']} | {f['source']}")
        for f in fin.get("outflows", []):
            print(f"   - {f['amount']} | {f['destination']}")
        print(f"   {fin.get('comment', '')}")

        print(f"\n👥 关键人物")
        for p in ins["key_people"][:5]:
            print(f"   • {p['name']} ({p['count']}次)")

        print(f"\n⏰ 待跟进")
        for w in ins["watchlist"]:
            print(f"   • {w['item']} [{w['timeframe']}]")


async def main():
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"

    agent = InsightAgentV7(company, date_str)
    report = await agent.run()

    if report:
        agent.print_report(report)

        with open(f"/tmp/report_{date_str}.json", "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到 /tmp/report_{date_str}.json")


if __name__ == "__main__":
    asyncio.run(main())
