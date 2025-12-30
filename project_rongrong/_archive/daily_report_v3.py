"""
邮件智能日报 v3.0 - 多Agent管道架构

Pipeline:
  Stage 0: Filter (LLM智能过滤)
  Stage 1: VLM提取 (所有附件)
  Stage 2: LLM分类 (4个维度)
  Stage 3: 4 Agent并行 (客户/物流/供应商/内部)
  Stage 4: 摘要Agent (跨维度洞察)
"""
import asyncio
import sys
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, AsyncGenerator
from dataclasses import dataclass, field, asdict
from motor.motor_asyncio import AsyncIOMotorClient
import os

# 添加项目根目录
sys.path.insert(0, "/home/xinyue/vulcan-brain")
from vulcan_libs.llm_client import UnifiedLLMClient, ModelType, ChatMessage, StreamChunk, get_llm_client

# ============ 配置 ============
MAX_TOKENS = 30000  # 统一token限制
TEMPERATURE = 0.3   # 低温度，更稳定

# ============ LLM 工具类 ============

class LLMHelper:
    """统一的LLM调用助手，处理thinking过滤和token限制"""

    def __init__(self, model: ModelType = ModelType.QWEN3):
        self.client = get_llm_client()
        self.model = model

    async def generate(self, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        """
        生成文本，自动过滤thinking内容
        """
        messages = [ChatMessage(role="user", content=prompt)]

        # 使用流式API收集内容，自动分离thinking
        content_parts = []
        async for chunk in await self.client.chat(
            messages=messages,
            model=self.model,
            stream=True,
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
            enable_thinking=True
        ):
            if isinstance(chunk, StreamChunk):
                # 只收集content，忽略thinking
                if chunk.type == "content":
                    content_parts.append(chunk.text)
            else:
                # 向后兼容：如果是字符串，可能包含<think>标签
                content_parts.append(chunk)

        result = "".join(content_parts)

        # 额外保险：过滤任何残留的<think>标签
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
        if '<think>' in result:
            result = result.split('</think>')[-1] if '</think>' in result else result.split('<think>')[0]

        return result.strip()

    async def generate_json(self, prompt: str, max_tokens: int = MAX_TOKENS) -> Dict:
        """生成JSON，自动解析"""
        text = await self.generate(prompt, max_tokens)

        # 尝试提取JSON
        try:
            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取```json块
            match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
            if match:
                return json.loads(match.group(1))
            # 尝试提取{}或[]
            match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"无法解析JSON: {text[:200]}...")

# ============ Stage 0: Filter (LLM智能过滤) ============

FILTER_PROMPT = """你是邮件过滤助手。判断以下邮件是否与业务相关，需要保留。

【过滤规则】
过滤掉这些邮件（返回false）：
- OA系统通知：补打卡、考勤、系统提醒
- 营销推广：展会邀请、广告、newsletter
- 自动回复：Out of Office、Delivery Status
- 重复邮件：转发的相同内容

保留这些邮件（返回true）：
- 客户沟通：订单、询价、需求确认
- 物流进度：订舱、发货、报关
- 供应商：审厂、采购、合同
- 财务：付款、发票（非自动推送）
- 人事：入职、离职、考评（非日常考勤）
- 生产：排期、质量问题

【邮件列表】
{email_list}

【输出格式】
返回JSON数组，每个元素：{{"id": "邮件ID", "keep": true/false, "reason": "简短原因"}}

只返回JSON，不要其他内容。
"""

class EmailFilter:
    """LLM智能过滤器"""

    def __init__(self):
        self.llm = LLMHelper()

    async def filter_emails(self, emails: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤邮件（分批处理，每批30封）
        返回: (保留邮件列表, 过滤决策记录)
        """
        if not emails:
            return [], []

        BATCH_SIZE = 30
        all_decisions = []

        # 分批处理
        for batch_start in range(0, len(emails), BATCH_SIZE):
            batch = emails[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1

            # 构建邮件列表文本 - 只用标题
            email_list = []
            for i, email in enumerate(batch):
                eid = email.get('email_id', '')[:20]
                subj = email.get('subject', '')[:60]
                email_list.append(f"邮件{i+1}: ID={eid}, 主题={subj}")

            prompt = FILTER_PROMPT.format(email_list="\n".join(email_list))

            try:
                decisions = await self.llm.generate_json(prompt)
                all_decisions.extend(decisions)
                print(f"  批次{batch_num}: {len(batch)}封 -> {sum(1 for d in decisions if d.get('keep'))}封保留")
            except Exception as e:
                print(f"⚠️ 批次{batch_num}失败: {e}，保留该批邮件")
                all_decisions.extend([{"id": email.get('email_id'), "keep": True, "reason": "LLM失败"} for email in batch])

        # 构建保留邮件列表
        keep_ids = set(d['id'] for d in all_decisions if d.get('keep', True))
        kept = [e for e in emails if e.get('email_id') in keep_ids]

        return kept, all_decisions

# ============ Stage 1: VLM提取 (TODO) ============
# 复用现有的VLM提取逻辑

# ============ Stage 2: LLM分类 ============

CLASSIFY_PROMPT = """你是邮件分类助手。将以下邮件分类到4个维度。

【分类维度】
1. CUSTOMER - 客户业务：订单、询价、需求确认、客户沟通
2. LOGISTICS - 物流进度：订舱、发货、报关、运输跟踪
3. SUPPLIER - 供应商/生产：审厂、采购、生产排期、质量
4. INTERNAL - 内部综合：财务、人事、行政、会议

【邮件列表】
{email_list}

【输出格式】
返回JSON数组：[{{"id": "邮件ID", "category": "CUSTOMER/LOGISTICS/SUPPLIER/INTERNAL", "priority": 1-5}}]
priority: 1=紧急 2=重要 3=一般 4=次要 5=低

只返回JSON。
"""

async def classify_emails(emails: List[Dict]) -> Dict[str, List[Dict]]:
    """LLM分类邮件到4个桶"""
    llm = LLMHelper()

    email_list = []
    for i, email in enumerate(emails):
        eid = email.get('email_id', '')[:20]
        subj = email.get('subject', '')
        email_list.append(f"邮件{i+1}: ID={eid}, 主题={subj}")

    prompt = CLASSIFY_PROMPT.format(email_list="\n".join(email_list))

    try:
        classifications = await llm.generate_json(prompt)
    except Exception as e:
        print(f"⚠️ 分类失败: {e}")
        # 降级：全部归入INTERNAL
        return {"INTERNAL": emails}

    # 按分类分桶
    buckets = {"CUSTOMER": [], "LOGISTICS": [], "SUPPLIER": [], "INTERNAL": []}
    id_to_email = {e.get('email_id'): e for e in emails}

    for c in classifications:
        email_id = c.get('id')
        category = c.get('category', 'INTERNAL')
        if email_id in id_to_email and category in buckets:
            email = id_to_email[email_id].copy()
            email['priority'] = c.get('priority', 3)
            buckets[category].append(email)

    return buckets

# ============ 测试入口 ============

async def test_filter(company: str = 'shanghai', date_str: str = None):
    """测试Filter效果"""
    client = AsyncIOMotorClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
    db = client.vulcan_brain

    # 获取日期范围
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        date = datetime.now()

    start = datetime(date.year, date.month, date.day, 16, 0, 0) - timedelta(days=1)
    end = start + timedelta(days=1)
    print(f"查询范围: {start} ~ {end} (UTC)")

    # 查询邮件
    query = {'company': company, 'received_at': {'$gte': start, '$lt': end}}
    emails = await db.wecom_emails.find(query).to_list(length=500)
    print(f"\n📧 共 {len(emails)} 封邮件 ({company} {date.strftime('%Y-%m-%d')})")

    # 执行LLM Filter
    email_filter = EmailFilter()
    kept, decisions = await email_filter.filter_emails(emails)

    # 统计
    filtered = [d for d in decisions if not d.get('keep', True)]
    print(f"\n✅ 保留: {len(kept)} 封")
    print(f"❌ 过滤: {len(filtered)} 封")

    if filtered:
        print(f"\n--- 被过滤的邮件 ---")
        for d in filtered[:20]:
            subject = next((e['subject'] for e in emails if e.get('email_id') == d['id']), d['id'])
            print(f"  ❌ {subject[:50]}...")
            print(f"     原因: {d.get('reason', '未知')}")

    print(f"\n--- 保留的邮件 (前15封) ---")
    for e in kept[:15]:
        print(f"  ✅ {e['subject'][:60]}")

    client.close()
    return kept, decisions

async def test_classify(company: str = 'shanghai', date_str: str = None):
    """测试分类效果"""
    client = AsyncIOMotorClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
    db = client.vulcan_brain

    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        date = datetime.now()

    start = datetime(date.year, date.month, date.day, 16, 0, 0) - timedelta(days=1)
    end = start + timedelta(days=1)

    emails = await db.wecom_emails.find({
        'company': company,
        'received_at': {'$gte': start, '$lt': end}
    }).to_list(length=500)

    print(f"\n📧 共 {len(emails)} 封邮件")

    # 先Filter
    email_filter = EmailFilter()
    kept, _ = await email_filter.filter_emails(emails)
    print(f"✅ Filter后: {len(kept)} 封")

    # 再分类
    buckets = await classify_emails(kept)

    print(f"\n--- 分类结果 ---")
    for cat, items in buckets.items():
        print(f"\n【{cat}】({len(items)}封)")
        for e in items[:5]:
            print(f"  P{e.get('priority', '?')}: {e['subject'][:50]}")

    client.close()

# ============ CLI ============

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--company', default='shanghai')
    parser.add_argument('--date', default=None)
    parser.add_argument('--test-filter', action='store_true')
    parser.add_argument('--test-classify', action='store_true')
    args = parser.parse_args()

    if args.test_filter:
        asyncio.run(test_filter(args.company, args.date))
    elif args.test_classify:
        asyncio.run(test_classify(args.company, args.date))
    else:
        print("Usage:")
        print("  python daily_report_v3.py --test-filter --company shanghai --date 2025-12-25")
        print("  python daily_report_v3.py --test-classify --company shanghai --date 2025-12-25")
