"""
邮件存储服务 - MS365 邮件同步到 MongoDB

功能:
1. 同步用户邮件到本地数据库（含完整正文和附件元数据）
2. 支持增量同步（基于时间戳）
3. 提供邮件查询接口
4. 支持补充已有邮件的正文
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
import httpx
from bs4 import BeautifulSoup
import re

logger = logging.getLogger("EmailStore")


class EmailStore:
    """邮件存储服务"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        # MongoDB
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client.vulcan_brain
        self.emails = self.db.emails
        self.sync_status = self.db.email_sync_status
        
        # MS365
        self.tenant_id = os.getenv("MS365_TENANT_ID")
        self.client_id = os.getenv("MS365_CLIENT_ID")
        self.client_secret = os.getenv("MS365_CLIENT_SECRET")
        self.token = None
        self.token_expires = None
        
        self._initialized = True
        logger.info("✅ EmailStore initialized")
    
    async def init_indexes(self):
        """初始化索引"""
        await self.emails.create_index("email_id", unique=True)
        await self.emails.create_index([("user_id", 1), ("received_at", -1)])
        await self.emails.create_index("received_at")
        await self.emails.create_index("from.address")
        await self.emails.create_index("has_full_body")  # 用于查询未补充正文的邮件
        logger.info("✅ Email indexes created")
    
    async def _get_token(self) -> str:
        """获取 MS365 access token"""
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials"
                }
            )
            data = response.json()
            
            if "access_token" not in data:
                raise Exception(f"获取 token 失败: {data}")
            
            self.token = data["access_token"]
            self.token_expires = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 60)
            return self.token
    
    async def get_all_users(self) -> List[Dict]:
        """获取所有用户列表"""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/users?$top=100&$select=id,displayName,mail",
                headers={"Authorization": f"Bearer {token}"}
            )
            return response.json().get("value", [])
    
    def _html_to_text(self, html_content: str) -> str:
        """将 HTML 正文转换为纯文本"""
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            # 移除 script 和 style 标签
            for tag in soup(["script", "style"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            # 清理多余空白
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
        except Exception:
            # 如果解析失败，简单去除 HTML 标签
            return re.sub(r'<[^>]+>', '', html_content)
    
    async def _get_email_attachments(self, user_email: str, message_id: str, client: httpx.AsyncClient, headers: dict) -> List[Dict]:
        """获取邮件附件元数据（不下载内容）"""
        try:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/attachments?$select=id,name,contentType,size",
                headers=headers,
                timeout=30
            )
            if response.status_code == 200:
                attachments = response.json().get("value", [])
                return [{
                    "id": att.get("id"),
                    "name": att.get("name", ""),
                    "content_type": att.get("contentType", ""),
                    "size": att.get("size", 0)
                } for att in attachments]
        except Exception as e:
            logger.warning(f"获取附件元数据失败: {e}")
        return []
    

    async def get_user_mail_folders(self, user_email: str) -> List[Dict]:
        """获取用户所有邮件文件夹（包含ID和displayName）"""
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        folders = []
        # 要同步的文件夹类型（用 well-known name 或遍历所有）
        target_folders = {'inbox', 'sentitems', 'archive'}
        
        async with httpx.AsyncClient(timeout=30) as client:
            # 获取顶层文件夹
            res = await client.get(
                f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders?$top=100",
                headers=headers
            )
            if res.status_code != 200:
                logger.warning(f"获取 {user_email} 文件夹失败: {res.status_code}")
                return folders
            
            data = res.json()
            for f in data.get('value', []):
                display_name = f.get('displayName', '').lower()
                folder_id = f.get('id')
                total_count = f.get('totalItemCount', 0)
                
                # 只同步收件箱、已发送、存档 (按显示名或 well-known 判断)
                is_inbox = any(x in display_name for x in ['inbox', '收件箱', 'posteingang', 'boîte de réception'])
                is_sent = any(x in display_name for x in ['sent', '已发送', 'gesendete', 'envoyés'])
                is_archive = any(x in display_name for x in ['archive', '存档', 'archiv'])
                
                if is_inbox or is_sent or is_archive:
                    folders.append({
                        'id': folder_id,
                        'displayName': f.get('displayName'),
                        'totalItemCount': total_count,
                        'type': 'inbox' if is_inbox else ('sentItems' if is_sent else 'archive')
                    })
                    logger.info(f"  发现文件夹: {f.get('displayName')} ({total_count} 封)")
        
        return folders

    async def sync_user_emails(
        self, 
        user_email: str, 
        since: datetime = None,
        folder: str = "inbox",
        max_emails: int = 500,
        fetch_full_body: bool = True
    ) -> Dict[str, int]:
        """
        同步单个用户的邮件（含完整正文和附件元数据）
        
        Returns:
            {"fetched": N, "inserted": M, "skipped": K}
        """
        if since is None:
            since = datetime.now() - timedelta(days=7)
        
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        fetched = 0
        inserted = 0
        skipped = 0
        
        # 分页获取邮件 - 请求完整 body
        select_fields = "id,conversationId,from,toRecipients,ccRecipients,subject,bodyPreview,body,hasAttachments,importance,isRead,receivedDateTime"
        next_link = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/{folder}/messages?$top=50&$orderby=receivedDateTime desc&$filter=receivedDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}&$select={select_fields}"
        
        async with httpx.AsyncClient(timeout=60) as client:
            while next_link and fetched < max_emails:
                try:
                    response = await client.get(next_link, headers=headers)
                    if response.status_code != 200:
                        logger.warning(f"获取 {user_email} 邮件失败: {response.status_code}")
                        break
                    
                    data = response.json()
                    messages = data.get("value", [])
                    
                    for msg in messages:
                        fetched += 1
                        
                        # 获取附件元数据（如果有附件）
                        attachments = []
                        if msg.get("hasAttachments"):
                            attachments = await self._get_email_attachments(
                                user_email, msg.get("id"), client, headers
                            )
                            # 避免请求过快
                            await asyncio.sleep(0.1)
                        
                        email_doc = self._parse_email(msg, user_email, folder, attachments)
                        
                        # 去重插入
                        try:
                            await self.emails.insert_one(email_doc)
                            inserted += 1
                        except Exception:
                            skipped += 1
                    
                    next_link = data.get("@odata.nextLink")
                    
                    # 避免请求过快
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    logger.error(f"同步 {user_email} 邮件出错: {e}")
                    break
        
        logger.info(f"同步 {user_email}/{folder}: 获取 {fetched}, 新增 {inserted}, 跳过 {skipped}")
        return {"fetched": fetched, "inserted": inserted, "skipped": skipped}
    
    def _parse_email(self, msg: Dict, user_id: str, folder: str, attachments: List[Dict] = None) -> Dict:
        """解析邮件数据（含完整正文和附件元数据）"""
        from_data = msg.get("from", {}).get("emailAddress", {})
        to_data = [r.get("emailAddress", {}) for r in msg.get("toRecipients", [])]
        cc_data = [r.get("emailAddress", {}) for r in msg.get("ccRecipients", [])]
        
        received_at = msg.get("receivedDateTime")
        if received_at:
            received_at = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        
        # 处理正文
        body_obj = msg.get("body", {})
        body_html = body_obj.get("content", "")
        body_type = body_obj.get("contentType", "html")
        
        # 如果是 HTML，转换为纯文本
        if body_type.lower() == "html":
            body_text = self._html_to_text(body_html)
        else:
            body_text = body_html
        
        return {
            "email_id": msg.get("id"),
            "conversation_id": msg.get("conversationId"),
            "user_id": user_id,
            "folder": folder,
            "from": {
                "address": from_data.get("address", ""),
                "name": from_data.get("name", "")
            },
            "to": [{"address": t.get("address", ""), "name": t.get("name", "")} for t in to_data],
            "cc": [{"address": c.get("address", ""), "name": c.get("name", "")} for c in cc_data],
            "subject": msg.get("subject", ""),
            "body": body_text,  # 完整正文（纯文本）
            "body_html": body_html[:50000] if len(body_html) > 50000 else body_html,  # HTML 正文（限制大小）
            "body_preview": msg.get("bodyPreview", ""),
            "has_attachments": msg.get("hasAttachments", False),
            "attachments": attachments or [],  # 附件元数据
            "importance": msg.get("importance", "normal"),
            "is_read": msg.get("isRead", False),
            "received_at": received_at,
            "synced_at": datetime.now(),
            "has_full_body": True  # 标记已获取完整正文
        }
    
    async def backfill_email_bodies(self, batch_size: int = 100) -> Dict[str, int]:
        """
        补充已有邮件的完整正文和附件元数据
        
        Returns:
            {"total": N, "updated": M, "failed": K}
        """
        # 查找没有完整正文的邮件
        cursor = self.emails.find({
            "$or": [
                {"has_full_body": {"$exists": False}},
                {"has_full_body": False}
            ]
        }).limit(batch_size)
        
        emails_to_update = await cursor.to_list(batch_size)
        total = len(emails_to_update)
        updated = 0
        failed = 0
        
        if total == 0:
            logger.info("没有需要补充正文的邮件")
            return {"total": 0, "updated": 0, "failed": 0}
        
        logger.info(f"开始补充 {total} 封邮件的正文...")
        
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(timeout=60) as client:
            for email in emails_to_update:
                try:
                    user_id = email.get("user_id")
                    email_id = email.get("email_id")
                    
                    if not user_id or not email_id:
                        failed += 1
                        continue
                    
                    # 获取完整邮件
                    response = await client.get(
                        f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{email_id}?$select=body,hasAttachments",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        msg_data = response.json()
                        body_obj = msg_data.get("body", {})
                        body_html = body_obj.get("content", "")
                        body_type = body_obj.get("contentType", "html")
                        
                        if body_type.lower() == "html":
                            body_text = self._html_to_text(body_html)
                        else:
                            body_text = body_html
                        
                        # 获取附件元数据
                        attachments = []
                        if msg_data.get("hasAttachments"):
                            attachments = await self._get_email_attachments(
                                user_id, email_id, client, headers
                            )
                        
                        # 更新数据库
                        await self.emails.update_one(
                            {"_id": email["_id"]},
                            {"$set": {
                                "body": body_text,
                                "body_html": body_html[:50000] if len(body_html) > 50000 else body_html,
                                "attachments": attachments,
                                "has_full_body": True,
                                "body_updated_at": datetime.now()
                            }}
                        )
                        updated += 1
                    else:
                        logger.warning(f"获取邮件 {email_id} 失败: {response.status_code}")
                        failed += 1
                    
                    # 避免请求过快
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"补充邮件正文失败: {e}")
                    failed += 1
        
        logger.info(f"补充正文完成: 总计 {total}, 成功 {updated}, 失败 {failed}")
        return {"total": total, "updated": updated, "failed": failed}
    
    async def get_backfill_status(self) -> Dict:
        """获取正文补充进度"""
        total = await self.emails.count_documents({})
        with_body = await self.emails.count_documents({"has_full_body": True})
        without_body = total - with_body
        
        return {
            "total_emails": total,
            "with_full_body": with_body,
            "without_full_body": without_body,
            "progress_percent": round(with_body / total * 100, 2) if total > 0 else 100
        }
    
    async def sync_all_users(self, since: datetime = None, folders: List[str] = None, max_per_folder: int = 10000) -> Dict:
        """同步所有用户的邮件（含完整正文）- 使用文件夹ID"""
        users = await self.get_all_users()
        total = {"users": 0, "fetched": 0, "inserted": 0, "skipped": 0, "folders_found": 0}
        
        for user in users:
            email = user.get("mail")
            if not email:
                continue
            
            total["users"] += 1
            logger.info(f"同步用户 {email}...")
            
            # 获取该用户的所有文件夹（自动识别多语言）
            user_folders = await self.get_user_mail_folders(email)
            total["folders_found"] += len(user_folders)
            
            for folder_info in user_folders:
                folder_id = folder_info['id']
                folder_name = folder_info['displayName']
                try:
                    result = await self.sync_user_emails(
                        email, 
                        since=since, 
                        folder=folder_info["type"],  # 使用标准类型名称(inbox/sentItems/archive)
                        max_emails=max_per_folder
                    )
                    total["fetched"] += result["fetched"]
                    total["inserted"] += result["inserted"]
                    total["skipped"] += result["skipped"]
                    logger.info(f"  {folder_name}: +{result['inserted']} 封")
                except Exception as e:
                    logger.error(f"同步 {email}/{folder_name} 失败: {e}")
        
        # 记录同步状态
        await self.sync_status.update_one(
            {"_id": "last_sync"},
            {"$set": {"timestamp": datetime.now(), "result": total}},
            upsert=True
        )
        
        logger.info(f"✅ 全量同步完成: {total}")
        return total
    
    async def get_emails_paginated(
        self, 
        folder: str = None, 
        limit: int = 50, 
        offset: int = 0,
        user_id: str = None
    ) -> Tuple[List[Dict], int]:
        """分页获取邮件列表"""
        query = {}
        if folder:
            query["folder"] = folder
        if user_id:
            query["user_id"] = user_id
        
        # 获取总数
        total = await self.emails.count_documents(query)
        
        # 分页查询
        cursor = self.emails.find(query).sort("received_at", -1).skip(offset).limit(limit)
        emails = await cursor.to_list(limit)
        
        # 格式化
        formatted = []
        for e in emails:
            formatted.append({
                "email_id": str(e.get("_id", "")),
                "ms_email_id": e.get("email_id", ""),
                "from": e.get("from", {}),
                "to": e.get("to", []),
                "subject": e.get("subject", ""),
                "body_preview": e.get("body_preview", ""),
                "body": e.get("body", "")[:500] if e.get("body") else "",  # 返回正文前500字
                "importance": e.get("importance", "normal"),
                "is_read": e.get("is_read", True),
                "has_attachments": e.get("has_attachments", False),
                "attachments": e.get("attachments", []),
                "received_at": e.get("received_at").isoformat() if e.get("received_at") else None,
                "folder": e.get("folder", "inbox"),
                "user_id": e.get("user_id", "")
            })
        
        return formatted, total
    
    async def get_emails_by_date(self, date: datetime) -> List[Dict]:
        """获取指定日期的所有邮件"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        cursor = self.emails.find({
            "received_at": {"$gte": start, "$lt": end}
        }).sort("received_at", -1)
        
        return await cursor.to_list(length=1000)
    
    async def get_email_stats(self, date: datetime) -> Dict:
        """获取指定日期的邮件统计"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        # 收件统计
        received = await self.emails.count_documents({
            "folder": "inbox",
            "received_at": {"$gte": start, "$lt": end}
        })
        
        # 发件统计
        sent = await self.emails.count_documents({
            "folder": "sentItems",
            "received_at": {"$gte": start, "$lt": end}
        })
        
        # 重要邮件
        important = await self.emails.count_documents({
            "received_at": {"$gte": start, "$lt": end},
            "importance": "high"
        })
        
        # 外部邮件统计 (发件人不是 vulcanshield.com)
        external_pipeline = [
            {"$match": {
                "folder": "inbox",
                "received_at": {"$gte": start, "$lt": end},
                "from.address": {"$not": {"$regex": "vulcanshield", "$options": "i"}}
            }},
            {"$count": "count"}
        ]
        external_result = await self.emails.aggregate(external_pipeline).to_list(1)
        external_count = external_result[0]["count"] if external_result else 0
        
        # 带附件的邮件
        with_attachments = await self.emails.count_documents({
            "received_at": {"$gte": start, "$lt": end},
            "has_attachments": True
        })
        
        return {
            "received": received,
            "sent": sent,
            "important": important,
            "external": external_count,
            "with_attachments": with_attachments
        }
    
    async def get_top_contacts(self, date: datetime, limit: int = 5) -> List[Dict]:
        """获取当日高频外部联系人"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        pipeline = [
            {"$match": {
                "folder": "inbox",
                "received_at": {"$gte": start, "$lt": end},
                "from.address": {"$not": {"$regex": "vulcanshield", "$options": "i"}}
            }},
            {"$group": {
                "_id": "$from.address",
                "name": {"$first": "$from.name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        results = await self.emails.aggregate(pipeline).to_list(limit)
        return [{"address": r["_id"], "name": r["name"], "count": r["count"]} for r in results]
    
    async def get_important_emails(self, date: datetime, limit: int = 5) -> List[Dict]:
        """获取当日重要邮件"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        cursor = self.emails.find({
            "received_at": {"$gte": start, "$lt": end},
            "importance": "high"
        }).sort("received_at", -1).limit(limit)
        
        emails = await cursor.to_list(limit)
        return [{
            "email_id": str(e["_id"]),
            "subject": e["subject"],
            "from": e["from"],
            "user_id": e["user_id"],
            "body_preview": e.get("body_preview", ""),
            "received_at": e["received_at"].isoformat() if e.get("received_at") else None
        } for e in emails]


# 单例
_email_store = None

def get_email_store() -> EmailStore:
    global _email_store
    if _email_store is None:
        _email_store = EmailStore()
    return _email_store
