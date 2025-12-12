"""
飞书消息收集模块 - Acontext 重构版
功能:
1. 从飞书的群聊中收集消息
2. 将消息存入 Acontext Session (用于历史记录)
3. 将消息作为文档存入 Acontext Space (用于语义搜索)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
import os

# Acontext Integration
from acontext_integration import get_acontext_manager, ACONTEXT_API_URL

logger = logging.getLogger("MessageCollector")

# 飞书 Brain Bot 配置
BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")


# ===== 飞书消息收集器 (Acontext Powered) =====

class FeishuMessageCollector:
    """飞书群聊消息收集器 (Acontext Backend)"""
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or BRAIN_APP_ID
        self.app_secret = app_secret or BRAIN_APP_SECRET
        self.acontext = get_acontext_manager()
        self._token_cache = {"token": None, "expires": 0}
        self._user_cache = {}  # 用户名缓存 {open_id: name}
    
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

    async def get_user_space_id(self, chat_id: str) -> str:
        """获取或创建与群聊关联的 Acontext Knowledge Space."""
        space_id = f"feishu_chat_{chat_id}"
        try:
            await self.acontext.client.create_space(name=space_id, description=f"Knowledge base for Feishu chat {chat_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409: # Conflict, already exists
                pass
            else:
                raise
        return space_id

    async def collect_chat_messages(
        self,
        chat_id: str,
        since: datetime = None,
        container_id_type: str = "chat"
    ) -> Dict[str, Any]:
        """
        收集群聊消息并存入 Acontext
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
        
        # --- Acontext 保存逻辑 ---
        inserted_count = 0
        if feishu_messages:
            space_id = await self.get_user_space_id(chat_id)
            user_id = f"feishu_chat_{chat_id}" # Use chat_id as a synthetic user_id

            for msg in feishu_messages:
                try:
                    # 1. Save to session for conversational history
                    await self.acontext.save_message(
                        user_id=user_id,
                        session_id=chat_id, # Use chat_id as session_id
                        role="user", # Assume all collected messages are from users
                        content=msg['content']
                    )
                    
                    # 2. Save to space for semantic search
                    await self.acontext.client.add_document(
                        space_id=space_id,
                        content=msg['content'],
                        title=f"Message from {msg['sender'].get('name', 'unknown')} at {msg['timestamp']}",
                        metadata={
                            "message_id": msg["message_id"],
                            "sender_id": msg["sender"].get("id"),
                            "sender_name": msg["sender"].get("name"),
                            "timestamp": msg["timestamp"].isoformat()
                        }
                    )
                    inserted_count += 1
                except Exception as e:
                    logger.error(f"保存消息到 Acontext 失败: {e}")

        result = {"collected": len(feishu_messages), "inserted": inserted_count, "skipped": len(feishu_messages) - inserted_count}
        logger.info(f"[MessageCollector] chat={chat_id}, collected={len(feishu_messages)}, inserted_to_acontext={inserted_count}")
        
        return result

    def _parse_message(self, item: Dict, chat_id: str) -> Optional[Dict]:
        """解析飞书消息格式 (no change from original)"""
        try:
            msg_type = item.get("msg_type", "")
            if msg_type != "text": return None
            
            content_str = item.get("body", {}).get("content", "{}")
            try:
                content = json.loads(content_str).get("text", "")
            except:
                content = content_str
            
            if not content.strip(): return None
            
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
        """发送收集完成通知到群 (no change from original)"""
        token = await self.get_token()
        notice_text = (
            f"📊 聊天记录已同步至 Acontext\n"
            f"━━━━━━━━━━\n"
            f"📥 本次扫描: {result.get('collected', 0)} 条\n"
            f"✅ 新增处理: {result.get('inserted', 0)} 条\n"
            f"⏭️ 异常跳过: {result.get('skipped', 0)} 条\n"
            f"━━━━━━━━━━\n"
            f"⏰ 同步时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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

# ===== 便捷函数 =====

def get_message_collector() -> FeishuMessageCollector:
    """获取消息收集器实例"""
    return FeishuMessageCollector()


# ===== 定时任务支持 =====

async def scheduled_collect_job(chat_ids: List[str]):
    """定时收集任务 (在日报生成前调用)"""
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
