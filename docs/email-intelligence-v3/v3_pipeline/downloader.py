#!/usr/bin/env python3
"""
V3 附件下载器
从 Graph API 下载邮件附件到本地缓存
使用 client_credentials 认证方式
"""
import os
import hashlib
import pymongo
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json

# 配置
CACHE_DIR = Path.home() / "attachment_cache"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# MS365 凭据 (从环境变量或配置文件获取)
MS365_TENANT_ID = os.environ.get("MS365_TENANT_ID", "")
MS365_CLIENT_ID = os.environ.get("MS365_CLIENT_ID", "")
MS365_CLIENT_SECRET = os.environ.get("MS365_CLIENT_SECRET", "")


class GraphAPIClient:
    """Microsoft Graph API 客户端"""

    def __init__(self, tenant_id: str = None, client_id: str = None, client_secret: str = None):
        self.tenant_id = tenant_id or MS365_TENANT_ID
        self.client_id = client_id or MS365_CLIENT_ID
        self.client_secret = client_secret or MS365_CLIENT_SECRET

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            # 尝试从配置文件读取
            self._load_from_config()

        self.token = None
        self.token_expires = None

    def _load_from_config(self):
        """从配置文件加载凭据"""
        config_paths = [
            Path.home() / ".vulcan" / "ms365.json",
            Path("/etc/vulcan/ms365.json"),
            Path.home() / "vulcan-brain" / ".env.ms365"
        ]

        for path in config_paths:
            if path.exists():
                try:
                    if path.suffix == ".json":
                        with open(path) as f:
                            config = json.load(f)
                        self.tenant_id = config.get("tenant_id", self.tenant_id)
                        self.client_id = config.get("client_id", self.client_id)
                        self.client_secret = config.get("client_secret", self.client_secret)
                    break
                except Exception:
                    continue

    def get_token(self) -> str:
        """获取 access token"""
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token

        response = requests.post(
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


class AttachmentDownloader:
    """附件下载器"""

    def __init__(self, graph_client: GraphAPIClient = None):
        self.graph_client = graph_client or GraphAPIClient()
        self.client = pymongo.MongoClient("mongodb://localhost:27017/")
        self.db = self.client.vulcan_brain
        self.cache_collection = self.db.attachment_cache

    def _get_headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.graph_client.get_token()}",
            "Content-Type": "application/json"
        }

    def _get_cache_path(self, email_id: str, attachment_id: str, filename: str) -> Path:
        """生成缓存文件路径"""
        email_hash = hashlib.md5(email_id.encode()).hexdigest()[:8]
        safe_filename = "_".join(filename.split())
        return CACHE_DIR / email_hash / attachment_id[:16] / safe_filename

    def download_attachment(self, user_email: str, email_id: str, attachment_id: str,
                          filename: str, size: int) -> Optional[Path]:
        """下载单个附件，返回本地缓存路径"""
        cache_path = self._get_cache_path(email_id, attachment_id, filename)

        # 检查缓存
        if cache_path.exists() and cache_path.stat().st_size == size:
            return cache_path

        # 使用用户邮箱获取附件 (delegated access)
        url = f"{GRAPH_API_BASE}/users/{user_email}/messages/{email_id}/attachments/{attachment_id}/$value"

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=120)
            resp.raise_for_status()

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(resp.content)

            self.cache_collection.update_one(
                {"email_id": email_id, "attachment_id": attachment_id},
                {"$set": {
                    "filename": filename,
                    "size": size,
                    "cache_path": str(cache_path),
                    "downloaded_at": datetime.utcnow(),
                    "status": "downloaded"
                }},
                upsert=True
            )
            return cache_path

        except Exception as e:
            self.cache_collection.update_one(
                {"email_id": email_id, "attachment_id": attachment_id},
                {"$set": {
                    "filename": filename,
                    "error": str(e),
                    "failed_at": datetime.utcnow(),
                    "status": "failed"
                }},
                upsert=True
            )
            return None

    def download_email_attachments(self, email: Dict) -> List[Dict]:
        """下载一封邮件的所有附件"""
        # 获取邮件ID (email_id 是 Graph API 的 message ID)
        graph_message_id = email.get("email_id") or email.get("graph_id") or str(email.get("_id"))

        # 获取用户邮箱 (user_id 字段存储的是邮箱地址)
        user_email = email.get("user_id") or email.get("user_email") or ""

        if not user_email:
            # 尝试从 to 字段获取
            tos = email.get("to", [])
            if tos and isinstance(tos[0], dict):
                user_email = tos[0].get("address", "")

        attachments = email.get("attachments", [])

        results = []
        for att in attachments:
            att_id = att.get("id", "")
            filename = att.get("name", "unknown")
            size = att.get("size", 0)
            content_type = att.get("content_type", "")

            if att.get("isInline"):
                continue

            if not att_id:
                results.append({
                    "attachment_id": att_id,
                    "filename": filename,
                    "size": size,
                    "content_type": content_type,
                    "local_path": None,
                    "status": "skipped",
                    "reason": "no_attachment_id"
                })
                continue

            local_path = self.download_attachment(user_email, graph_message_id, att_id, filename, size)

            results.append({
                "attachment_id": att_id,
                "filename": filename,
                "size": size,
                "content_type": content_type,
                "local_path": str(local_path) if local_path else None,
                "status": "downloaded" if local_path else "failed"
            })

        return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python downloader.py --test")
        print("       python downloader.py --check-auth")
        sys.exit(1)

    if sys.argv[1] == "--check-auth":
        try:
            client = GraphAPIClient()
            token = client.get_token()
            print(f"✅ 认证成功")
            print(f"   Token: {token[:50]}...")
        except Exception as e:
            print(f"❌ 认证失败: {e}")
        sys.exit(0)

    if sys.argv[1] == "--test":
        db = pymongo.MongoClient("mongodb://localhost:27017/").vulcan_brain

        test_email = db.emails.find_one({
            "processing_status.v2_extracted": True,
            "has_attachments": True
        })

        if not test_email:
            print("No test email found")
            sys.exit(1)

        print(f"Test email: {test_email.get('subject', 'N/A')[:50]}")
        print(f"Attachments: {len(test_email.get('attachments', []))}")

        try:
            downloader = AttachmentDownloader()
            results = downloader.download_email_attachments(test_email)

            for r in results:
                status = "OK" if r["status"] == "downloaded" else r["status"]
                print(f"  [{status}] {r['filename']} ({r['size']/1024:.1f}KB)")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
