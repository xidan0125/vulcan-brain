"""
Microsoft 365 服务 - 通过 Graph API 访问邮件、日历、用户等

使用 Client Credentials Flow (应用程序权限)
"""

import os
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from functools import lru_cache


class MS365Service:
    def __init__(self):
        self.client_id = os.getenv("MS365_CLIENT_ID")
        self.tenant_id = os.getenv("MS365_TENANT_ID")
        self.client_secret = os.getenv("MS365_CLIENT_SECRET")
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
    
    async def _get_token(self) -> str:
        """获取或刷新 access token"""
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials"
                }
            )
            data = response.json()
            
            if "access_token" not in data:
                raise Exception(f"获取 token 失败: {data.get('error_description', data)}")
            
            self.token = data["access_token"]
            self.token_expires = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 60)
            return self.token
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送 Graph API 请求"""
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.graph_url}{endpoint}",
                headers=headers,
                **kwargs
            )
            
            if response.status_code >= 400:
                raise Exception(f"Graph API 错误: {response.status_code} - {response.text}")
            
            return response.json() if response.text else {}
    
    # ===== 用户相关 =====
    
    async def get_users(self, top: int = 100) -> List[Dict]:
        """获取组织所有用户"""
        data = await self._request("GET", f"/users?={top}&=id,displayName,mail,jobTitle,department")
        return data.get("value", [])
    
    async def get_user(self, user_id: str) -> Dict:
        """获取单个用户信息"""
        return await self._request("GET", f"/users/{user_id}")
    
    # ===== 邮件相关 =====
    
    async def get_user_messages(
        self, 
        user_id: str, 
        top: int = 20,
        folder: str = "inbox",
        since: Optional[datetime] = None
    ) -> List[Dict]:
        """获取用户邮件"""
        endpoint = f"/users/{user_id}/mailFolders/{folder}/messages?={top}&=receivedDateTime desc"
        
        if since:
            endpoint += f"&=receivedDateTime ge {since.isoformat()}Z"
        
        data = await self._request("GET", endpoint)
        return data.get("value", [])
    
    async def send_mail(
        self,
        from_user_id: str,
        to: List[str],
        subject: str,
        body: str,
        body_type: str = "HTML"
    ) -> bool:
        """代发邮件"""
        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": body_type,
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in to
                ]
            }
        }
        
        await self._request("POST", f"/users/{from_user_id}/sendMail", json=message)
        return True
    
    # ===== 日历相关 =====
    
    async def get_user_events(
        self,
        user_id: str,
        top: int = 20,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """获取用户日历事件"""
        if start_time and end_time:
            endpoint = f"/users/{user_id}/calendarView?startDateTime={start_time.isoformat()}Z&endDateTime={end_time.isoformat()}Z&={top}"
        else:
            endpoint = f"/users/{user_id}/events?={top}&=start/dateTime"
        
        data = await self._request("GET", endpoint)
        return data.get("value", [])
    
    # ===== 联系人相关 =====
    
    async def get_user_contacts(self, user_id: str, top: int = 100) -> List[Dict]:
        """获取用户联系人"""
        data = await self._request("GET", f"/users/{user_id}/contacts?={top}")
        return data.get("value", [])
    
    # ===== 组织架构 =====
    
    async def get_groups(self, top: int = 100) -> List[Dict]:
        """获取组织的所有组"""
        data = await self._request("GET", f"/groups?={top}")
        return data.get("value", [])
    
    async def get_group_members(self, group_id: str) -> List[Dict]:
        """获取组成员"""
        data = await self._request("GET", f"/groups/{group_id}/members")
        return data.get("value", [])


# 单例
_ms365_service: Optional[MS365Service] = None

def get_ms365_service() -> MS365Service:
    global _ms365_service
    if _ms365_service is None:
        _ms365_service = MS365Service()
    return _ms365_service
