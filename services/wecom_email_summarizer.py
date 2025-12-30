"""
企业微信邮件日报生成服务 v2
为管理层生成高质量的邮件摘要，支持数据溯源
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, MONGO_DB_NAME
from vulcan_libs.ai_service import get_ai_service

logger = logging.getLogger("WeComEmailSummarizer")


# 高质量日报 Prompt（经过验证）
WECOM_EMAIL_ANALYSIS_PROMPT = """分析榕融新材料公司邮件，生成管理层日报。

公司背景：
- 榕融新材料是新材料制造企业，主营氧化铝纤维相关产品
- 主要客户：广州国机、汽车零部件厂商等
- 有国际贸易业务（出口到欧洲等）
- 组织：研发部、销售部、财务部、行政部、质检部、EHS

日期: {date}
邮件数量: {email_count}

邮件列表:
{email_list}

请输出管理层日报：

【今日要事】
1-3件最重要的事，简洁有力

【紧急事项】
- 事项名称 [邮件X]
  截止时间：具体时间
  责任人/联系人：如有
  
【客户动态】
- 客户名 [邮件X]：进展描述

【业务概览】
按部门分类核心事务：
- 销售部：...
- 物流部：...
- 财务部：...
- 行政部：...

【执行建议】
今日优先处理的1-2项建议
"""


class WeComEmailSummarizer:
    """企业微信邮件日报生成器 v2"""

    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.collection = self.db.wecom_emails
        self.ai = get_ai_service()

    async def get_emails_by_date(
        self, 
        company: str, 
        date: datetime,
        include_filtered: bool = False
    ) -> List[Dict]:
        """获取指定日期的邮件"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        query = {
            "company": company,
            "received_at": {"$gte": start, "$lt": end}
        }
        
        if not include_filtered:
            query["is_filtered"] = False
        
        cursor = self.collection.find(query).sort("received_at", -1)
        return await cursor.to_list(length=500)

    def _format_emails_for_analysis(
        self, 
        emails: List[Dict], 
        max_body_len: int = 500
    ) -> tuple:
        """格式化邮件供AI分析"""
        lines = []
        email_index_map = {}
        total_len = 0
        max_total = 18000
        
        for i, email in enumerate(emails, 1):
            if total_len > max_total:
                break
            
            # 保存索引映射
            email_index_map[str(i)] = {
                "email_id": email.get("email_id"),
                "subject": email.get("subject", "无主题"),
                "from": email.get("from", ""),
                "from_email": email.get("from_email", ""),
                "received_at": email.get("received_at").isoformat() if email.get("received_at") else None,
                "attachments": email.get("attachments", [])
            }
            
            from_str = email.get("from", "未知")[:30]
            subject = email.get("subject", "无主题")[:60]
            body = email.get("body", "") or email.get("body_preview", "")
            body = body[:max_body_len] if len(body) > max_body_len else body
            
            # 附件信息
            attachments = email.get("attachments", [])
            att_info = ""
            if attachments:
                att_names = [a.get("filename", "")[:30] for a in attachments[:3]]
                att_info = f"\n   附件: {", ".join(att_names)}"
            
            entry = f"""
[邮件{i}] {from_str}
主题: {subject}{att_info}
正文: {body}
"""
            lines.append(entry)
            total_len += len(entry)
        
        return "\n".join(lines), email_index_map

    async def analyze_emails(
        self, 
        emails: List[Dict], 
        date: datetime
    ) -> Dict[str, Any]:
        """AI分析邮件内容"""
        if not emails:
            return self._empty_analysis()
        
        email_list, email_index_map = self._format_emails_for_analysis(emails[:35])
        
        prompt = WECOM_EMAIL_ANALYSIS_PROMPT.format(
            date=date.strftime("%Y-%m-%d"),
            email_count=len(emails),
            email_list=email_list
        )
        
        try:
            # 使用generate而不是generate_json，因为输出是Markdown
            raw_result = await self.ai.generate(prompt, temperature=0.3, max_tokens=16000)
            
            # 提取thinking后的实际内容
            if "</think>" in raw_result:
                raw_result = raw_result.split("</think>")[-1].strip()
            
            # 解析Markdown结构为字典
            analysis = self._parse_markdown_report(raw_result)
            analysis["raw_markdown"] = raw_result
            analysis["email_index_map"] = email_index_map
            
            return analysis
            
        except Exception as e:
            logger.error(f"AI分析邮件失败: {e}")
            result = self._empty_analysis(error=str(e))
            result["email_index_map"] = email_index_map
            return result

    def _parse_markdown_report(self, markdown: str) -> Dict:
        """从Markdown提取结构化数据"""
        result = {
            "executive_summary": "",
            "critical_alerts": [],
            "customer_updates": [],
            "business_overview": {},
            "recommendations": ""
        }
        
        # 提取【今日要事】
        match = re.search(r"【今日要事】\s*([\s\S]*?)(?=【|$)", markdown)
        if match:
            result["executive_summary"] = match.group(1).strip()[:500]
        
        # 提取【紧急事项】
        match = re.search(r"【紧急事项】\s*([\s\S]*?)(?=【|$)", markdown)
        if match:
            alerts_text = match.group(1).strip()
            # 简单按 - 分割提取
            alerts = [a.strip() for a in alerts_text.split("\n- ") if a.strip()]
            result["critical_alerts"] = alerts[:10]
        
        # 提取【客户动态】
        match = re.search(r"【客户动态】\s*([\s\S]*?)(?=【|$)", markdown)
        if match:
            customers_text = match.group(1).strip()
            customers = [c.strip() for c in customers_text.split("\n- ") if c.strip()]
            result["customer_updates"] = customers[:10]
        
        # 提取【业务概览】
        match = re.search(r"【业务概览】\s*([\s\S]*?)(?=【|$)", markdown)
        if match:
            overview_text = match.group(1).strip()
            result["business_overview"] = overview_text
        
        # 提取【执行建议】
        match = re.search(r"【执行建议】\s*([\s\S]*?)(?=【|$)", markdown)
        if match:
            result["recommendations"] = match.group(1).strip()[:500]
        
        return result

    def _empty_analysis(self, error: str = None) -> Dict:
        """返回空的分析结果"""
        return {
            "executive_summary": "今日无邮件" if not error else f"分析失败: {error}",
            "critical_alerts": [],
            "customer_updates": [],
            "business_overview": {},
            "recommendations": "",
            "raw_markdown": ""
        }

    def _enrich_with_sources(
        self, 
        analysis: Dict, 
        email_index_map: Dict
    ) -> Dict:
        """为分析结果添加数据源信息"""
        # 将email_index_map转换为可用格式
        analysis["sources"] = {}
        for idx, info in email_index_map.items():
            analysis["sources"][f"邮件{idx}"] = {
                "email_id": info["email_id"],
                "subject": info["subject"],
                "from": info["from"],
                "attachments": [
                    {
                        "filename": a.get("filename"),
                        "file_path": a.get("file_path")
                    }
                    for a in info.get("attachments", [])
                ]
            }
        return analysis

    async def get_stats(self, company: str, date: datetime) -> Dict:
        """获取邮件统计"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        query_base = {
            "company": company,
            "received_at": {"$gte": start, "$lt": end}
        }
        
        total = await self.collection.count_documents(query_base)
        filtered = await self.collection.count_documents({**query_base, "is_filtered": True})
        with_attachments = await self.collection.count_documents({**query_base, "has_attachments": True})
        
        # 附件统计
        pipeline = [
            {"$match": {**query_base, "has_attachments": True}},
            {"$unwind": "$attachments"},
            {"$group": {
                "_id": "$attachments.category",
                "count": {"$sum": 1}
            }}
        ]
        att_stats = {}
        async for doc in self.collection.aggregate(pipeline):
            att_stats[doc["_id"]] = doc["count"]
        
        return {
            "total": total,
            "filtered": filtered,
            "valid": total - filtered,
            "with_attachments": with_attachments,
            "attachment_breakdown": att_stats
        }

    async def generate_summary(
        self, 
        company: str, 
        date: datetime = None
    ) -> Dict[str, Any]:
        """生成完整的邮件日报"""
        if date is None:
            date = datetime.now()
        
        # 获取统计
        stats = await self.get_stats(company, date)
        
        # 获取邮件
        emails = await self.get_emails_by_date(company, date, include_filtered=False)
        
        # AI分析
        analysis = await self.analyze_emails(emails, date)
        
        # 添加数据源
        email_index_map = analysis.pop("email_index_map", {})
        analysis = self._enrich_with_sources(analysis, email_index_map)
        
        summary = {
            "company": company,
            "date": date.strftime("%Y-%m-%d"),
            "stats": stats,
            "analysis": analysis,
            "generated_at": datetime.now().isoformat()
        }
        
        logger.info(f"✅ [{company}] 日报生成完成: {stats['valid']}封有效邮件")
        return summary


# 便捷函数
_summarizer = None

def get_wecom_email_summarizer() -> WeComEmailSummarizer:
    global _summarizer
    if _summarizer is None:
        _summarizer = WeComEmailSummarizer()
    return _summarizer


async def generate_wecom_email_summary(company: str, date: datetime = None) -> Dict:
    summarizer = get_wecom_email_summarizer()
    return await summarizer.generate_summary(company, date)
