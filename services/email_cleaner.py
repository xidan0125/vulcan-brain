"""
邮件正文清洗服务 - Phase 0.2

功能:
1. 去除邮件签名
2. 去除免责声明
3. 去除引用的历史邮件
4. 提取纯净的邮件正文用于 AI 分析
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger("EmailCleaner")


class EmailCleaner:
    """邮件正文清洗器"""
    
    # 签名分隔符模式
    SIGNATURE_PATTERNS = [
        r"^--\s*$",  # 标准签名分隔符
        r"^_{10,}$",  # 下划线分隔
        r"^-{10,}$",  # 短横线分隔
        r"^={10,}$",  # 等号分隔
        r"^Best regards,?$",
        r"^Best,?$",
        r"^Thanks,?$",
        r"^Thank you,?$",
        r"^Regards,?$",
        r"^Cheers,?$",
        r"^Sincerely,?$",
        r"^Kind regards,?$",
        r"^Warm regards,?$",
        r"^BR,?$",
        r"^此致$",
        r"^祝好$",
        r"^谢谢$",
        r"^顺颂商祺$",
        r"^Mit freundlichen Grüßen,?$",
        r"^Viele Grüße,?$",
        r"^MfG,?$",
        r"^Sent from my iPhone$",
        r"^Sent from my iPad$",
        r"^发自我的 iPhone$",
        r"^发自我的 iPad$",
        r"^Get Outlook for.*$",
    ]
    
    # 免责声明关键词
    DISCLAIMER_PATTERNS = [
        r"^DISCLAIMER:",
        r"^CONFIDENTIALITY NOTICE:",
        r"^LEGAL NOTICE:",
        r"^This email and any attachments",
        r"^This message is intended only",
        r"^The information contained in this",
        r"^If you are not the intended recipient",
        r"^免责声明",
        r"^本邮件及其附件",
        r"^如果您不是本邮件的预期收件人",
        r"^Vertraulichkeit",
        r"^Diese Nachricht ist",
    ]
    
    # 引用历史邮件的分隔符
    QUOTE_PATTERNS = [
        r"^On .+ wrote:$",
        r"^-----Original Message-----",
        r"^-{5,}原始邮件-{5,}",
        r"^From:.*Sent:.*To:.*Subject:",
        r"^发件人:.*发送时间:.*收件人:.*主题:",
        r"^>",  # 引用行
        r"^\| ",  # 另一种引用格式
    ]
    
    def __init__(self, mongo_uri: str = None):
        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.vulcan_brain
        self.emails = self.db.emails
        
        # 编译正则表达式
        self._signature_re = [re.compile(p, re.MULTILINE | re.IGNORECASE) 
                             for p in self.SIGNATURE_PATTERNS]
        self._disclaimer_re = [re.compile(p, re.MULTILINE | re.IGNORECASE) 
                              for p in self.DISCLAIMER_PATTERNS]
        self._quote_re = [re.compile(p, re.MULTILINE | re.IGNORECASE) 
                         for p in self.QUOTE_PATTERNS]
        
        logger.info("EmailCleaner initialized")
    
    def clean_body(self, body: str) -> Dict[str, str]:
        """
        清洗邮件正文
        
        Returns:
            {
                "clean_body": "清洗后的正文",
                "signature": "提取的签名",
                "disclaimer": "提取的免责声明",
                "quoted": "提取的引用内容"
            }
        """
        if not body:
            return {"clean_body": "", "signature": "", "disclaimer": "", "quoted": ""}
        
        lines = body.split("\n")
        clean_lines = []
        signature_lines = []
        disclaimer_lines = []
        quoted_lines = []
        
        in_signature = False
        in_disclaimer = False
        in_quote = False
        
        for line in lines:
            stripped = line.strip()
            
            # 检查是否进入签名区
            if not in_signature:
                for pattern in self._signature_re:
                    if pattern.match(stripped):
                        in_signature = True
                        break
            
            # 检查是否进入免责声明区
            if not in_disclaimer and not in_signature:
                for pattern in self._disclaimer_re:
                    if pattern.match(stripped):
                        in_disclaimer = True
                        break
            
            # 检查是否进入引用区
            if not in_quote and not in_signature and not in_disclaimer:
                for pattern in self._quote_re:
                    if pattern.match(stripped):
                        in_quote = True
                        break
            
            # 分类存储
            if in_disclaimer:
                disclaimer_lines.append(line)
            elif in_signature:
                signature_lines.append(line)
            elif in_quote:
                quoted_lines.append(line)
            else:
                clean_lines.append(line)
        
        # 清理空行
        clean_body = "\n".join(clean_lines).strip()
        
        # 移除连续空行
        clean_body = re.sub(r"\n{3,}", "\n\n", clean_body)
        
        return {
            "clean_body": clean_body,
            "signature": "\n".join(signature_lines).strip(),
            "disclaimer": "\n".join(disclaimer_lines).strip(),
            "quoted": "\n".join(quoted_lines).strip(),
        }
    
    async def process_emails(self, batch_size: int = 500) -> Dict[str, int]:
        """
        批量清洗邮件正文
        
        为每封邮件添加 body_clean 字段
        """
        logger.info("开始清洗邮件正文...")
        
        # 查找未清洗的邮件
        query = {"body_clean": {"$exists": False}, "body": {"$exists": True, "$ne": ""}}
        total = await self.emails.count_documents(query)
        
        if total == 0:
            logger.info("所有邮件已清洗")
            return {"total": 0, "processed": 0}
        
        logger.info(f"需要清洗 {total} 封邮件")
        
        processed = 0
        cursor = self.emails.find(query, {"_id": 1, "body": 1}).batch_size(batch_size)
        
        async for email in cursor:
            body = email.get("body", "")
            result = self.clean_body(body)
            
            await self.emails.update_one(
                {"_id": email["_id"]},
                {"$set": {
                    "body_clean": result["clean_body"],
                    "body_signature": result["signature"] if result["signature"] else None,
                    "body_disclaimer": result["disclaimer"] if result["disclaimer"] else None,
                    "body_cleaned_at": datetime.now(),
                }}
            )
            
            processed += 1
            if processed % 1000 == 0:
                logger.info(f"已清洗 {processed}/{total} 封邮件")
        
        logger.info(f"清洗完成: {processed} 封邮件")
        return {"total": total, "processed": processed}
    
    async def get_clean_stats(self) -> Dict:
        """获取清洗统计"""
        total = await self.emails.count_documents({})
        cleaned = await self.emails.count_documents({"body_clean": {"$exists": True}})
        has_signature = await self.emails.count_documents({
            "body_signature": {"$exists": True, "$ne": None}
        })
        has_disclaimer = await self.emails.count_documents({
            "body_disclaimer": {"$exists": True, "$ne": None}
        })
        
        # 平均正文长度比较
        pipeline = [
            {"$match": {"body_clean": {"$exists": True}}},
            {"$project": {
                "original_len": {"$strLenCP": {"$ifNull": ["$body", ""]}},
                "clean_len": {"$strLenCP": {"$ifNull": ["$body_clean", ""]}}
            }},
            {"$group": {
                "_id": None,
                "avg_original": {"$avg": "$original_len"},
                "avg_clean": {"$avg": "$clean_len"},
            }}
        ]
        
        async for result in self.emails.aggregate(pipeline):
            avg_original = result.get("avg_original", 0)
            avg_clean = result.get("avg_clean", 0)
            reduction = ((avg_original - avg_clean) / avg_original * 100) if avg_original else 0
        
        return {
            "total_emails": total,
            "cleaned_emails": cleaned,
            "with_signature": has_signature,
            "with_disclaimer": has_disclaimer,
            "avg_original_length": round(avg_original, 0),
            "avg_clean_length": round(avg_clean, 0),
            "reduction_percent": round(reduction, 1),
        }


# ===== 便捷函数 =====

_cleaner = None

def get_email_cleaner() -> EmailCleaner:
    """获取清洗器实例"""
    global _cleaner
    if _cleaner is None:
        _cleaner = EmailCleaner()
    return _cleaner


async def clean_all_emails() -> Dict:
    """清洗所有邮件 (便捷函数)"""
    cleaner = get_email_cleaner()
    return await cleaner.process_emails()
