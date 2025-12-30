"""
from __future__ import annotations
企业微信邮件采集服务 v3
通过IMAP协议采集邮件备份到MongoDB
支持附件元数据提取 + 文件存储

支持多公司配置：上海(rongrongnm.com)、广西(rongrongxc.com)
"""

import imaplib
import email
import re
import hashlib
import os
from pathlib import Path
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger


class Company(str, Enum):
    SHANGHAI = "shanghai"
    GUANGXI = "guangxi"


@dataclass
class IMAPConfig:
    """IMAP连接配置"""
    company: Company
    email: str
    password: str
    folder: str
    server: str = "imap.exmail.qq.com"
    port: int = 993


# 附件存储根目录
ATTACHMENT_ROOT = Path("/home/xinyue/vulcan-brain/data/attachments")


# ==================== 过滤规则 ====================

HARD_BLACKLIST_SENDERS = {
    "noreply@", "no-reply@", "mailer-daemon@",
    "postmaster@", "newsletter@", "marketing@",
    "notification@", "alert@",
}

HARD_BLACKLIST_SUBJECTS = [
    "退订", "unsubscribe", "Unsubscribe",
    "自动回复", "Auto Reply", "Out of Office",
    "邮件投递失败", "Delivery Status", "Undeliverable",
    "验证码", "verification code",
]

SOFT_FILTER_DOMAINS = {
    "exmail.weixin.qq.com",
    "workday.com", "myworkday.com",
}

SOFT_FILTER_SUBJECTS = [
    "系统通知", "System Notification",
    "密码即将", "Password",
]


def decode_mime_str(s: Optional[str]) -> str:
    """解码MIME编码的字符串"""
    if s is None:
        return ""
    decoded = decode_header(s)
    result = []
    for part, charset in decoded:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='ignore'))
            except:
                result.append(part.decode('gb18030', errors='ignore'))
        else:
            result.append(part)
    return ''.join(result)


def extract_email_address(from_header: str) -> str:
    """从From头提取邮箱地址"""
    if '<' in from_header and '>' in from_header:
        return from_header.split('<')[1].split('>')[0].lower()
    return from_header.lower()


def check_hard_filter(sender: str, subject: str) -> Optional[str]:
    sender_lower = sender.lower()
    subject_lower = subject.lower()
    
    for blacklist in HARD_BLACKLIST_SENDERS:
        if blacklist in sender_lower:
            return f"hard_sender:{blacklist}"
    
    for keyword in HARD_BLACKLIST_SUBJECTS:
        if keyword.lower() in subject_lower:
            return f"hard_subject:{keyword}"
    
    return None


def check_soft_filter(sender: str, subject: str) -> Optional[str]:
    email_addr = extract_email_address(sender)
    subject_lower = subject.lower()
    
    for domain in SOFT_FILTER_DOMAINS:
        if domain in email_addr:
            return f"soft_domain:{domain}"
    
    for keyword in SOFT_FILTER_SUBJECTS:
        if keyword.lower() in subject_lower:
            return f"soft_subject:{keyword}"
    
    return None


def get_email_body(msg) -> str:
    """提取邮件正文"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(charset, errors='ignore')
                        break
                except:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(charset, errors='ignore')
                except:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors='ignore')
        except:
            pass
    
    return body[:10000] if body else ""


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    # 替换非法字符
    illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename


def categorize_file(ext: str, content_type: str) -> str:
    """文件类型分类"""
    if ext in ('pdf', 'ofd'):
        return 'document'
    elif ext in ('doc', 'docx'):
        return 'word'
    elif ext in ('xls', 'xlsx', 'csv'):
        return 'spreadsheet'
    elif ext in ('ppt', 'pptx'):
        return 'presentation'
    elif ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'):
        return 'image'
    elif ext in ('xml', 'json'):
        return 'data'
    elif ext in ('zip', 'rar', '7z', 'tar', 'gz'):
        return 'archive'
    elif 'image' in content_type:
        return 'image'
    else:
        return 'other'


def save_attachment(
    payload: bytes, 
    filename: str, 
    company: str, 
    email_id: str,
    received_at: datetime
) -> Optional[str]:
    """
    保存附件到文件系统
    返回相对路径
    """
    try:
        # 构建目录: attachments/{company}/{YYYY-MM}/{email_id}/
        date_folder = received_at.strftime("%Y-%m")
        dir_path = ATTACHMENT_ROOT / company / date_folder / email_id
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # 清理文件名
        safe_filename = sanitize_filename(filename)
        file_path = dir_path / safe_filename
        
        # 如果文件已存在，添加序号
        if file_path.exists():
            name, ext = os.path.splitext(safe_filename)
            counter = 1
            while file_path.exists():
                safe_filename = f"{name}_{counter}{ext}"
                file_path = dir_path / safe_filename
                counter += 1
        
        # 写入文件
        with open(file_path, 'wb') as f:
            f.write(payload)
        
        # 返回相对路径
        return str(file_path.relative_to(ATTACHMENT_ROOT))
        
    except Exception as e:
        logger.error(f"保存附件失败 {filename}: {e}")
        return None


def extract_and_save_attachments(
    msg,
    company: str,
    email_id: str,
    received_at: datetime,
    save_files: bool = True
) -> List[Dict[str, Any]]:
    """提取附件元数据并保存文件"""
    attachments = []
    
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        
        filename = part.get_filename()
        if filename:
            filename = decode_mime_str(filename)
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0
            
            ext = filename.split('.')[-1].lower() if '.' in filename else ''
            file_category = categorize_file(ext, content_type)
            
            # 保存文件
            file_path = None
            if save_files and payload and size > 0:
                file_path = save_attachment(
                    payload, filename, company, email_id, received_at
                )
            
            attachments.append({
                "filename": filename,
                "content_type": content_type,
                "size": size,
                "extension": ext,
                "category": file_category,
                "file_path": file_path,  # 相对路径
            })
    
    return attachments


def generate_email_id(company: str, message_id: str) -> str:
    """
    生成唯一邮件ID - 基于 Message-ID
    RFC 5322: 同一封邮件发给多人时 Message-ID 相同
    """
    # 清理 Message-ID 中的特殊字符
    clean_mid = re.sub(r'[<>\s]', '', message_id)
    raw = f"{company}:{clean_mid}"
    return hashlib.md5(raw.encode()).hexdigest()


class WeComEmailCollector:
    """企业微信邮件采集器"""
    
    def __init__(self, config: IMAPConfig, db: AsyncIOMotorDatabase):
        self.config = config
        self.db = db
        self.collection = db.wecom_emails
        
    async def ensure_indexes(self):
        """确保索引存在"""
        await self.collection.create_index("email_id", unique=True)
        await self.collection.create_index("company")
        await self.collection.create_index("received_at")
        await self.collection.create_index("is_filtered")
        await self.collection.create_index("has_attachments")
        await self.collection.create_index([("company", 1), ("received_at", -1)])
        
    def connect(self) -> imaplib.IMAP4_SSL:
        """连接IMAP服务器"""
        mail = imaplib.IMAP4_SSL(self.config.server, self.config.port)
        mail.login(self.config.email, self.config.password)
        return mail
    
    async def sync_emails(
        self, 
        days: int = 7, 
        limit: int = 500,
        save_attachments: bool = True
    ) -> Dict[str, int]:
        """同步邮件到MongoDB，可选保存附件"""
        stats = {
            "total": 0,
            "new": 0,
            "skipped": 0,
            "hard_filtered": 0,
            "soft_filtered": 0,
            "with_attachments": 0,
            "attachments_saved": 0,
            "errors": 0,
        }
        
        try:
            mail = self.connect()
            logger.info(f"[{self.config.company.value}] IMAP连接成功")
            
            status, _ = mail.select(self.config.folder)
            if status != 'OK':
                logger.error(f"[{self.config.company.value}] 无法选择文件夹: {self.config.folder}")
                return stats
            
            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(SINCE "{since_date}")')
            
            if not messages[0]:
                logger.info(f"[{self.config.company.value}] 没有新邮件")
                mail.logout()
                return stats
            
            mail_ids = messages[0].split()[-limit:]
            stats["total"] = len(mail_ids)
            logger.info(f"[{self.config.company.value}] 找到 {len(mail_ids)} 封邮件")
            
            for num in mail_ids:
                try:
                    status, data = mail.fetch(num, "(RFC822)")
                    if status != 'OK' or not data[0]:
                        continue
                        
                    msg = email.message_from_bytes(data[0][1])
                    
                    subject = decode_mime_str(msg["Subject"])
                    sender = decode_mime_str(msg["From"])
                    to = decode_mime_str(msg["To"])
                    date_str = msg["Date"] or ""
                    msg_id = msg["Message-ID"] or ""
                    in_reply_to = msg["In-Reply-To"] or ""
                    references = msg["References"] or ""
                    
                    try:
                        received_at = parsedate_to_datetime(date_str)
                    except:
                        received_at = datetime.now()
                    
                    email_id = generate_email_id(
                        self.config.company.value,
                        msg_id
                    )
                    
                    existing = await self.collection.find_one({"email_id": email_id})
                    if existing:
                        # 合并收件人列表（同一封邮件发给多人）
                        existing_to = existing.get('to', '')
                        if to and to not in existing_to:
                            merged_to = f"{existing_to}, {to}" if existing_to else to
                            await self.collection.update_one(
                                {"email_id": email_id},
                                {"$set": {"to": merged_to}}
                            )
                        stats["skipped"] += 1
                        continue
                    
                    hard_reason = check_hard_filter(sender, subject)
                    if hard_reason:
                        stats["hard_filtered"] += 1
                        continue
                    
                    soft_reason = check_soft_filter(sender, subject)
                    is_filtered = soft_reason is not None
                    if is_filtered:
                        stats["soft_filtered"] += 1
                    
                    body = get_email_body(msg)
                    
                    # 提取并保存附件
                    attachments = extract_and_save_attachments(
                        msg,
                        self.config.company.value,
                        email_id,
                        received_at,
                        save_files=save_attachments
                    )
                    
                    has_attachments = len(attachments) > 0
                    if has_attachments:
                        stats["with_attachments"] += 1
                        saved_count = sum(1 for a in attachments if a.get("file_path"))
                        stats["attachments_saved"] += saved_count
                    
                    doc = {
                        "email_id": email_id,
                        "company": self.config.company.value,
                        "message_id": msg_id,
                        "in_reply_to": in_reply_to,
                        "references": references,
                        "from": sender,
                        "from_email": extract_email_address(sender),
                        "to": to,
                        "subject": subject,
                        "body": body,
                        "body_preview": body[:500] if body else "",
                        "received_at": received_at,
                        "date_str": date_str,
                        "is_filtered": is_filtered,
                        "filter_reason": soft_reason,
                        "has_attachments": has_attachments,
                        "attachments": attachments,
                        "attachment_count": len(attachments),
                        "synced_at": datetime.now(),
                    }
                    
                    await self.collection.insert_one(doc)
                    stats["new"] += 1
                    
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"处理邮件失败: {e}")
                    continue
            
            mail.logout()
            logger.info(f"[{self.config.company.value}] 同步完成: {stats}")
            
        except Exception as e:
            logger.error(f"[{self.config.company.value}] 同步失败: {e}")
            stats["errors"] += 1
            
        return stats


# ==================== 公司配置 ====================

COMPANY_CONFIGS = {
    Company.SHANGHAI: IMAPConfig(
        company=Company.SHANGHAI,
        email="guanliyuan@rongrongnm.com",
        password="QD85rQi9F9LWhBTe",
        folder='"&UXZO1mWHTvZZOQ-/ai_monitoring"',
    ),
    Company.GUANGXI: IMAPConfig(
        company=Company.GUANGXI,
        email="guanliyuan@rongrongxc.com",
        password="pnJT2Kpj8KCTKFFB",
        folder='"&UXZO1mWHTvZZOQ-/ai_collector"',
    ),
}


async def create_collector(company: Company, db: AsyncIOMotorDatabase) -> WeComEmailCollector:
    config = COMPANY_CONFIGS[company]
    collector = WeComEmailCollector(config, db)
    await collector.ensure_indexes()
    return collector


async def sync_all_companies(db: AsyncIOMotorDatabase, days: int = 7) -> Dict[str, Dict]:
    results = {}
    for company in Company:
        collector = await create_collector(company, db)
        results[company.value] = await collector.sync_emails(days=days)
    return results
