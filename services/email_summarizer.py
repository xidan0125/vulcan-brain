"""
邮件 AI 汇总服务 - 五纬度信息收集系统 (维度3)

功能:
1. 按日期分析邮件内容（使用完整正文）
2. AI 提取关键信息: 待办事项、重要客户、紧急事项
3. 生成日报摘要 + 详情数据
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from services.email_store import get_email_store
from vulcan_libs.ai_service import get_ai_service

logger = logging.getLogger("EmailSummarizer")


# 重要客户关键词（可配置）
VIP_CLIENTS = [
    "spacex", "nasa", "boeing", "lockheed", "northrop", 
    "airbus", "raytheon", "blue origin", "virgin",
    "tesla", "google", "microsoft", "apple", "amazon"
]

# 邮件分析 Prompt 模板
EMAIL_ANALYSIS_PROMPT = """你是一位专业的企业邮件分析助手。请分析以下邮件内容，提取关键商业信息。

日期: {date}
邮件数量: {email_count}

邮件列表:
{email_list}

请以JSON格式输出分析结果，包含以下字段:
{{
    "summary": "今日邮件的整体概述（2-3句话，用中文）",
    "action_items": ["需要处理的待办事项，末尾标注来源邮件编号如（邮件3）或（邮件2、5）"],
    "vip_updates": ["重要客户相关邮件摘要，末尾标注邮件编号"],
    "urgent_matters": ["紧急事项或需要立即关注的问题，末尾标注邮件编号"],
    "key_topics": ["今日邮件涉及的主要话题（用中文）"],
    "sentiment": "positive/negative/neutral/mixed"
}}

注意:
1. 提取具体、可执行的待办事项
2. 特别关注大客户（SpaceX、NASA、Boeing等）的邮件
3. 识别任何紧急或时间敏感的事项
4. 如果是内部邮件系统测试或垃圾邮件，可以忽略
5. 所有输出使用中文
6. 【重要】每个action_item、vip_update、urgent_matter末尾必须标注来源邮件编号，格式如（邮件3）或（邮件1、5、7）
"""


class EmailSummarizer:
    """邮件 AI 汇总器"""

    def __init__(self):
        self.store = get_email_store()
        self.ai = get_ai_service()

    async def analyze_emails(
        self,
        emails: List[Dict],
        date: datetime
    ) -> Dict[str, Any]:
        """AI 分析邮件内容"""
        if not emails:
            result = self._empty_analysis()
            result["email_index_map"] = {}
            return result

        # 构建邮件摘要文本（使用完整正文，限制总长度）
        email_list, email_index_map = self._format_emails_for_analysis(emails[:30])  # 最多分析30封
        
        prompt = EMAIL_ANALYSIS_PROMPT.format(
            date=date.strftime("%Y-%m-%d"),
            email_count=len(emails),
            email_list=email_list
        )

        try:
            result = await self.ai.generate_json(prompt, temperature=0.3)
            # 添加邮件索引映射，供前端溯源使用
            result["email_index_map"] = email_index_map
            return result
        except Exception as e:
            logger.error(f"AI 分析邮件失败: {e}")
            result = self._empty_analysis(error=str(e))
            result["email_index_map"] = email_index_map
            return result

    def _format_emails_for_analysis(self, emails: List[Dict], max_body_len: int = 1000) -> tuple:
        """格式化邮件列表供 AI 分析（使用完整正文）
        
        Returns:
            tuple: (formatted_text, email_index_map)
            - formatted_text: 格式化的邮件文本
            - email_index_map: 索引到email_id的映射 {1: {...}, 2: {...}, ...}
        """
        lines = []
        email_index_map = {}  # 索引到email_id的映射
        total_len = 0
        max_total = 15000  # 总长度限制
        
        for i, email in enumerate(emails, 1):
            if total_len > max_total:
                break
            
            # 保存索引映射
            email_index_map[str(i)] = {
                "email_id": email.get("email_id"),
                "subject": email.get("subject", "无主题"),
                "from": email.get("from", {})
            }
                
            from_addr = email.get("from", {}).get("address", "未知")
            from_name = email.get("from", {}).get("name", "")
            subject = email.get("subject", "无主题")
            importance = email.get("importance", "normal")
            
            # 优先使用完整正文，否则使用预览
            body = email.get("body", "") or email.get("body_preview", "")
            body = body[:max_body_len] if len(body) > max_body_len else body
            
            # 附件信息
            attachments = email.get("attachments", [])
            attachment_info = ""
            if attachments:
                att_names = [a.get("name", "") for a in attachments[:3]]
                attachment_info = f"\n附件: {', '.join(att_names)}"
            
            entry = f"""
---
邮件 {i}:
发件人: {from_name} <{from_addr}>
主题: {subject}
重要性: {importance}{attachment_info}
正文: {body}
"""
            lines.append(entry)
            total_len += len(entry)
        
        return "\n".join(lines), email_index_map

    def _empty_analysis(self, error: str = None) -> Dict:
        """返回空的分析结果"""
        return {
            "summary": "今日无邮件" if not error else f"分析失败: {error}",
            "action_items": [],
            "vip_updates": [],
            "urgent_matters": [],
            "key_topics": [],
            "sentiment": "neutral"
        }

    def _identify_vip_emails(self, emails: List[Dict]) -> List[Dict]:
        """识别重要客户邮件"""
        vip_emails = []
        for email in emails:
            from_addr = (email.get("from") or {}).get("address", "") or ""; from_addr = from_addr.lower()
            from_name = ((email.get("from") or {}).get("name", "") or "").lower()
            subject = (email.get("subject", "") or "").lower()
            
            for client in VIP_CLIENTS:
                if client in from_addr or client in from_name or client in subject:
                    vip_emails.append({
                        "email_id": email.get("email_id"),
                        "subject": email.get("subject"),
                        "from": email.get("from"),
                        "client": client.upper(),
                        "received_at": email.get("received_at").isoformat() if email.get("received_at") else None,
                        "preview": (email.get("body", "") or email.get("body_preview", ""))[:200]
                    })
                    break
        
        return vip_emails

    async def generate_summary(self, date: datetime = None) -> Dict[str, Any]:
        """生成指定日期的完整邮件摘要"""
        if date is None:
            date = datetime.now() - timedelta(days=1)

        # 获取统计数据
        stats = await self.store.get_email_stats(date)
        
        # 获取高频外部联系人
        top_contacts = await self.store.get_top_contacts(date, limit=5)
        
        # 获取当日邮件
        emails = await self.store.get_emails_by_date(date)
        
        # 识别 VIP 客户邮件
        vip_emails = self._identify_vip_emails(emails)
        
        # AI 分析
        ai_analysis = await self.analyze_emails(emails, date)
        
        summary = {
            # 基础统计
            "total": stats["received"] + stats["sent"],
            "received": stats["received"],
            "sent": stats["sent"],
            "important": stats["important"],
            "external_count": stats["external"],
            "with_attachments": stats.get("with_attachments", 0),
            
            # 联系人
            "top_contacts": top_contacts,
            
            # VIP 客户
            "vip_emails": vip_emails,
            "vip_count": len(vip_emails),
            
            # AI 分析结果
            "ai_analysis": ai_analysis,
            
            # 元数据
            "date": date.strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat()
        }
        
        logger.info(f"✅ 邮件摘要生成完成: 收{stats['received']}/发{stats['sent']}, VIP邮件{len(vip_emails)}封")
        return summary


# ===== 便捷函数 =====

_summarizer = None

def get_email_summarizer() -> EmailSummarizer:
    """获取邮件汇总器实例"""
    global _summarizer
    if _summarizer is None:
        _summarizer = EmailSummarizer()
    return _summarizer


async def generate_email_summary(date: datetime = None) -> Dict:
    """生成邮件摘要 (便捷函数)"""
    summarizer = get_email_summarizer()
    return await summarizer.generate_summary(date)
