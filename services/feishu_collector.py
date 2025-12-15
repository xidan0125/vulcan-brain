"""
飞书消息收集模块 - MongoDB 版
功能:
1. 从飞书的群聊中收集消息
2. 将消息存入 MongoDB (MessageStore)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
import os

# 使用 MessageStore 存储
from services.message_store import get_message_store

logger = logging.getLogger("MessageCollector")

# 飞书 Brain Bot 配置
BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")


class FeishuMessageCollector:
    """飞书群聊消息收集器 (MongoDB Backend)"""
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or BRAIN_APP_ID
        self.app_secret = app_secret or BRAIN_APP_SECRET
        self.store = get_message_store()  # 改用 MessageStore
        self._token_cache = {"token": None, "expires": 0}
        self._user_cache = {}
    
    async def get_token(self) -> str:
        """获取飞书 tenant_access_token"""
        now = datetime.now().timestamp()
        if self._token_cache["token"] and self._token_cache["expires"] > now:
            return self._token_cache["token"]
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret}
            )
            data = resp.json()
            token = data.get("tenant_access_token")
            expire = data.get("expire", 7200)
            
            self._token_cache = {
                "token": token,
                "expires": now + expire - 60
            }
            return token

    async def collect_chat_messages(
        self,
        chat_id: str,
        since: datetime = None,
        container_id_type: str = "chat"
    ) -> Dict[str, Any]:
        """
        收集群聊消息并存入 MongoDB
        """
        if not since:
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        token = await self.get_token()
        
        feishu_messages = []
        page_token = None
        
        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                params = {
                    "container_id_type": container_id_type,
                    "container_id": chat_id,
                    "start_time": str(int(since.timestamp())),
                    "page_size": 50
                }
                if page_token:
                    params["page_token"] = page_token
                
                resp = await client.get(
                    "https://open.larksuite.com/open-apis/im/v1/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                data = resp.json()
                
                if data.get("code") != 0:
                    logger.error(f"获取飞书消息失败: {data}")
                    break
                
                items = data.get("data", {}).get("items", [])
                for item in items:
                    msg = self._parse_message(item, chat_id)
                    if msg:
                        feishu_messages.append(msg)
                
                page_token = data.get("data", {}).get("page_token")
                if not page_token or not data.get("data", {}).get("has_more"):
                    break
        
        # 批量保存到 MongoDB
        result = await self.store.save_messages_batch(feishu_messages)
        result["collected"] = len(feishu_messages)
        
        logger.info(f"[MessageCollector] chat={chat_id}, collected={len(feishu_messages)}, inserted={result['inserted']}, skipped={result['skipped']}")
        
        return result

    def _parse_message(self, item: Dict, chat_id: str) -> Optional[Dict]:
        """解析飞书消息格式"""
        try:
            msg_type = item.get("msg_type", "")
            if msg_type != "text":
                return None
            
            content_str = item.get("body", {}).get("content", "{}")
            try:
                content = json.loads(content_str).get("text", "")
            except:
                content = content_str
            
            if not content.strip():
                return None
            
            sender = item.get("sender", {})
            return {
                "message_id": item.get("message_id"),
                "chat_id": chat_id,
                "sender": {
                    "id": sender.get("id", ""),
                    "id_type": sender.get("id_type", ""),
                    "sender_type": sender.get("sender_type", "")
                },
                "content": content,
                "timestamp": datetime.fromtimestamp(int(item.get("create_time", "0")) / 1000),
            }
        except Exception as e:
            logger.error(f"解析消息失败: {e}")
            return None

    async def send_collection_notice(self, chat_id: str, result: Dict) -> bool:
        """发送收集完成通知到群"""
        token = await self.get_token()
        notice_text = (
            f"📊 聊天记录已收集\n"
            f"━━━━━━━━━━\n"
            f"📥 本次扫描: {result.get('collected', 0)} 条\n"
            f"✅ 新增入库: {result.get('inserted', 0)} 条\n"
            f"⏭️ 已存在跳过: {result.get('skipped', 0)} 条\n"
            f"━━━━━━━━━━\n"
            f"⏰ 收集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://open.larksuite.com/open-apis/im/v1/messages",
                    params={"receive_id_type": "chat_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": notice_text})
                    }
                )
                data = resp.json()
                return data.get("code") == 0
        except Exception as e:
            logger.error(f"发送通知异常: {e}")
            return False


# 便捷函数
def get_message_collector() -> FeishuMessageCollector:
    """获取消息收集器实例"""
    return FeishuMessageCollector()


# 定时任务支持
async def scheduled_collect_job(chat_ids: List[str]):
    """定时收集任务"""
    collector = get_message_collector()
    results = {}
    for chat_id in chat_ids:
        try:
            result = await collector.collect_chat_messages(chat_id)
            await collector.send_collection_notice(chat_id, result)
            results[chat_id] = result
        except Exception as e:
            logger.error(f"收集 {chat_id} 失败: {e}")
            results[chat_id] = {"error": str(e)}
    return results
