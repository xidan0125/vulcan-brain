"""
邮件智能日报 v2.3 - 精简版
Stage 1: 邮件链聚合 (纯算法)
Stage 2: VLM 附件提取 (只有附件的才调用)
Stage 3: 日报生成 (1次LLM)
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import requests
import sys
sys.path.insert(0, "/home/xinyue/vulcan-brain")
from vulcan_libs.llm_client import UnifiedLLMClient, ModelType, ChatMessage

from motor.motor_asyncio import AsyncIOMotorClient

from email_threading import aggregate_emails, EmailThread
from attachment_processor import process_thread_attachments

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
VLLM_BASE = "http://localhost:8000/v1"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"


class DailyReportV2:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.collection = self.client[DB_NAME]["wecom_emails"]
    
    async def fetch_emails(self, company: str, date: str) -> List[Dict]:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_utc = datetime(date_obj.year, date_obj.month, date_obj.day) - timedelta(hours=8)
        end_utc = start_utc + timedelta(days=1)
        
        print(f"  查询: {start_utc} ~ {end_utc} (UTC)")
        
        cursor = self.collection.find({
            "company": company,
            "received_at": {"$gte": start_utc, "$lt": end_utc},
            "is_filtered": False
        }).sort("received_at", -1)
        
        return await cursor.to_list(length=200)
    
    def call_llm(self, prompt: str, max_tokens: int = 30000) -> str:
        """使用本地 Qwen3 生成日报"""
        import asyncio
        import re as regex
        from vulcan_libs.llm_client import StreamChunk
        
        async def _call():
            client = UnifiedLLMClient()
            messages = [ChatMessage(role="user", content=prompt)]
            content_parts = []
            
            async for chunk in await client.chat(
                messages=messages,
                model=ModelType.QWEN3,
                stream=True,
                temperature=0.3,
                max_tokens=max_tokens,
                enable_thinking=True
            ):
                if isinstance(chunk, StreamChunk):
                    if chunk.type == "content":
                        content_parts.append(chunk.text)
                elif isinstance(chunk, str):
                    content_parts.append(chunk)
            
            return "".join(content_parts)
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            text = loop.run_until_complete(_call())
            loop.close()
            
            # 过滤残留 <think> 标签
            text = regex.sub(r'<think>.*?</think>', '', text, flags=regex.DOTALL)
            if '<think>' in text:
                text = text.split('</think>')[-1] if '</think>' in text else text.split('<think>')[0]
            
            return text.strip()
        except Exception as e:
            return f"LLM错误: {e}"
    
    def simple_priority(self, thread: EmailThread, has_attachment_data: bool) -> int:
        """简单优先级规则"""
        score = 0
        # 分类权重
        cat_scores = {'CUSTOMER': 30, 'LOGISTICS': 25, 'FINANCE': 20, 'OTHER': 10}
        score += cat_scores.get(thread.category, 5)
        # 邮件链长度
        score += min(thread.count * 5, 20)
        # 有附件提取结果
        if has_attachment_data:
            score += 15
        return score
    
    async def run(self, company: str, date: str) -> Dict:
        print(f"[Stage 0] 获取 {company} {date} 邮件...")
        emails = await self.fetch_emails(company, date)
        print(f"  共 {len(emails)} 封\n")
        
        if not emails:
            return {"date": date, "stats": {"total": 0}, "report": "当日无邮件"}
        
        # Stage 1: 聚合
        print("[Stage 1] 邮件链聚合...")
        threads, approval_summary = aggregate_emails(emails)
        print(f"  {len(threads)} 个线程, {approval_summary['count']} 条审批\n")
        
        # Stage 2: 附件提取 (只处理有附件的)
        print("[Stage 2] VLM 附件提取...")
        thread_data = []
        for thread in threads:
            att_insights = []
            if thread.all_attachments:
                print(f"  📎 {thread.subject[:30]}...", end=" ")
                att_insights = process_thread_attachments(thread.all_attachments, company)
                extracted_count = sum(1 for a in att_insights if a.get('extracted'))
                print(f"提取{extracted_count}/{len(att_insights)}个")
            
            priority = self.simple_priority(thread, bool(att_insights))
            thread_data.append({
                'thread': thread,
                'attachments': att_insights,
                'priority': priority
            })
        
        # 按优先级排序
        thread_data.sort(key=lambda x: x['priority'], reverse=True)
        
        # Stage 3: 生成日报
        print(f"\n[Stage 3] 生成日报...")
        
        # 构建完整上下文
        context_parts = []
        for i, item in enumerate(thread_data[:12], 1):
            t = item['thread']
            latest = t.latest
            body = (latest.get('body') or '')[:800]
            
            part = f"""
---邮件{i}---
主题: {t.subject}
分类: {t.category} | 往来: {t.count}封 | 参与: {', '.join(t.participants[:3])}
正文摘要:
{body}
"""
            # 附件提取结果
            for att in item['attachments']:
                if att.get('extracted'):
                    part += f"\n📎附件[{att.get('filename','')}]提取内容:\n{str(att['extracted'])[:600]}\n"
            
            context_parts.append(part)
        
        prompt = f"""你是公司老板的高管情报助手。你不是总结机器，而是一个能够思考的助理。

【你的角色】
- 你刚刚看完了今天所有的邮件往来
- 老板很忙，只有2分钟时间听你汇报
- 你需要告诉他：今天最值得关注的是什么？有什么需要他知道或决策的？

【数据背景】
日期: {date}
邮件数: {len(emails)}封，聚合为{len(threads)}个主题
审批: {approval_summary['count']}条（已单独处理，不用重复）

【邮件内容】
{''.join(context_parts)}

【输出要求】
不要死板地按模板填充。用你的智能思考：
- 哪些事情真正重要？（客户订单、审厂截止日期、大额物流）
- 你发现了什么问题或风险？（比如：某客户催促回复但负责人可能不在、某个截止日快到了但进度不明）
- 有什么需要老板关注或决策的？

格式建议（可灵活调整）：
## 执行摘要
（1-2句话，今天最重要的事）

## 业务要点
（3-5条，按重要性排序，不是按邮件顺序）

## 客户动态
（有客户相关就写，没有就跳过）

## 物流跟踪
（有物流就写，没有就跳过）

## 风险提示
（你发现的任何潜在问题，没有就跳过）

## 行政备忘
（出差、报销等低优先级事项，简要列出）

记住：你的价值在于洞察，不是复读。老板看完应该觉得这个助理真有用，而不是这不就是邮件标题列表吗。
"""
        
        report = self.call_llm(prompt)
        
        return {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "stats": {
                "emails": len(emails),
                "threads": len(threads),
                "approvals": approval_summary['count'],
                "attachments_processed": sum(1 for d in thread_data if d['attachments'])
            },
            "approval_summary": approval_summary,
            "top_threads": [
                {
                    "subject": d['thread'].subject,
                    "category": d['thread'].category,
                    "count": d['thread'].count,
                    "priority": d['priority'],
                    "has_attachment_data": bool(d['attachments'])
                }
                for d in thread_data[:10]
            ],
            "report": report
        }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成企微邮件日报")
    parser.add_argument("--company", default="shanghai", help="公司: shanghai/guangxi")
    parser.add_argument("--date", default=None, help="日期: YYYY-MM-DD，默认今天")
    parser.add_argument("--save", action="store_true", help="保存到 MongoDB")
    args = parser.parse_args()
    
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    
    pipeline = DailyReportV2()
    result = await pipeline.run(args.company, date)
    
    # 保存到 MongoDB
    if args.save:
        await pipeline.client[DB_NAME].wecom_daily_reports.update_one(
            {"company": args.company, "date": date},
            {"$set": {
                "company": args.company,
                "date": date,
                "report": result,
                "generated_at": datetime.now()
            }},
            upsert=True
        )
        print(f"\n✓ 已保存到 MongoDB: wecom_daily_reports")
    
    # 打印摘要
    print(f"\n{'='*60}")
    print(f"📊 {args.company} {date} 日报")
    print(f"📊 统计: {result['stats']}")
    print(f"\n📋 Top线程:")
    for t in result.get('top_threads', [])[:5]:
        att_mark = "📎" if t['has_attachment_data'] else ""
        print(f"  P{t['priority']:2d} [{t['category']:8s}] {t['subject'][:40]} {att_mark}")
    print(f"\n{'='*60}")
    print(result.get('report', '')[:1500])


if __name__ == "__main__":
    asyncio.run(main())
