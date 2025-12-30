"""
飞书消息存储模块 - 五纬度信息收集系统 (维度1: 聊天记录)

功能:
1. 存储群聊消息到 MongoDB (去重)
2. 定时批量收集群聊消息
3. 手动触发收集
4. 收集完成后发送群通知
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import httpx
import os

logger = logging.getLogger("MessageStore")
# 实时分析触发器
_realtime_analyzer = None


# 飞书 Brain Bot 配置
BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")


class MessageStore:
    """飞书消息存储管理器"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, mongo_uri: str = None):
        if hasattr(self, "_initialized"):
            return
        
        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.vulcan_brain
        self.collection = self.db.feishu_messages
        self._initialized = True
        logger.info("✅ MessageStore initialized")
    
    async def init_indexes(self):
        """初始化索引"""
        # message_id 唯一索引 (用于去重)
        await self.collection.create_index("message_id", unique=True)
        # chat_id + timestamp 联合索引 (用于按群按时间查询)
        await self.collection.create_index([("chat_id", ASCENDING), ("timestamp", DESCENDING)])
        # 创建时间TTL索引 (1年后自动删除)
        await self.collection.create_index("created_at", expireAfterSeconds=365*24*60*60)
        logger.info("✅ Message indexes created")
    
    async def save_message(self, msg: Dict[str, Any]) -> bool:
        """
        保存单条消息 (自动去重)
        
        Args:
            msg: 消息数据，必须包含 message_id
            
        Returns:
            bool: True=新插入, False=已存在
        """
        message_id = msg.get("message_id")
        if not message_id:
            logger.warning("消息缺少 message_id，跳过")
            return False
        
        # 检查是否已存在
        existing = await self.collection.find_one({"message_id": message_id})
        if existing:
            return False
        
        # 添加元数据
        msg["created_at"] = datetime.now()
        msg.setdefault("extracted", {
            "processed": False,
            "is_business": None,
            "topics": [],
            "entities": [],
            "intent": None,
            "action_items": []
        })
        
        try:
            await self.collection.insert_one(msg)
            # 触发实时分析
            try:
                from services.realtime_analyzer import get_realtime_analyzer
                chat_id = msg.get("chat_id")
                if chat_id:
                    analyzer = get_realtime_analyzer()
                    import asyncio
                    asyncio.create_task(analyzer.on_message_saved(chat_id))
            except Exception as e:
                logger.debug(f"实时分析触发失败(非阻塞): {e}")
            
            return True
        except Exception as e:
            if "duplicate key" in str(e):
                return False
            logger.error(f"保存消息失败: {e}")
            raise
    
    async def save_messages_batch(self, messages: List[Dict]) -> Dict[str, int]:
        """
        批量保存消息 (自动去重)
        
        Returns:
            {"inserted": 新插入数, "skipped": 跳过数}
        """
        inserted = 0
        skipped = 0
        
        for msg in messages:
            result = await self.save_message(msg)
            if result:
                inserted += 1
            else:
                skipped += 1
        
        return {"inserted": inserted, "skipped": skipped}
    
    async def get_chat_history(
        self,
        chat_id: str,
        limit: int = 50,
        since: datetime = None,
        until: datetime = None
    ) -> List[Dict]:
        """
        获取群聊历史消息
        
        Args:
            chat_id: 群聊ID
            limit: 最大返回条数
            since: 开始时间
            until: 结束时间
        """
        query = {"chat_id": chat_id}
        
        if since or until:
            query["timestamp"] = {}
            if since:
                query["timestamp"]["$gte"] = since
            if until:
                query["timestamp"]["$lte"] = until
        
        cursor = self.collection.find(query).sort("timestamp", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_today_messages(self, chat_id: str) -> List[Dict]:
        """获取今天的消息"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.get_chat_history(chat_id, limit=500, since=today_start)
    
    async def get_uncollected_count(self, chat_id: str, last_collected_at: datetime) -> int:
        """获取上次收集后的新消息数量"""
        query = {
            "chat_id": chat_id,
            "timestamp": {"$gt": last_collected_at}
        }
        return await self.collection.count_documents(query)
    
    async def search_messages(
        self,
        keyword: str,
        chat_id: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        搜索消息
        
        Args:
            keyword: 搜索关键词
            chat_id: 可选，限定群聊
            limit: 最大返回条数
        """
        query = {"content": {"$regex": keyword, "$options": "i"}}
        if chat_id:
            query["chat_id"] = chat_id
        
        cursor = self.collection.find(query).sort("timestamp", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_stats(self, chat_id: str = None) -> Dict:
        """获取消息统计"""
        match = {"chat_id": chat_id} if chat_id else {}
        
        pipeline = [
            {"$match": match} if match else {"$match": {}},
            {"$group": {
                "_id": "$chat_id",
                "total": {"$sum": 1},
                "first_msg": {"$min": "$timestamp"},
                "last_msg": {"$max": "$timestamp"}
            }}
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(length=100)
        return results


# ===== 飞书消息收集器 =====

class FeishuMessageCollector:
    """飞书群聊消息收集器"""
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or BRAIN_APP_ID
        self.app_secret = app_secret or BRAIN_APP_SECRET
        self.store = MessageStore()
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
    
    async def get_chat_members_map(self, chat_id: str) -> Dict[str, str]:
        """
        获取群聊成员的 open_id -> name 映射
        
        Args:
            chat_id: 群聊ID
            
        Returns:
            {open_id: name} 字典
        """
        try:
            token = await self.get_token()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}/members",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"member_id_type": "open_id", "page_size": 100}
                )
                data = resp.json()
                
                if data.get("code") == 0:
                    members = {}
                    for item in data.get("data", {}).get("items", []):
                        member_id = item.get("member_id")
                        name = item.get("name")
                        if member_id and name:
                            members[member_id] = name
                            self._user_cache[member_id] = name
                    return members
        except Exception as e:
            logger.debug(f"获取群成员失败: {chat_id} - {e}")
        
        return {}
    
    async def get_user_name(self, open_id: str) -> str:
        """
        获取用户名称 (从缓存)
        
        Args:
            open_id: 用户的open_id
            
        Returns:
            用户名称，获取失败返回None
        """
        if not open_id:
            return None
        return self._user_cache.get(open_id)
    


    async def get_configured_chat_ids(self) -> List[str]:
        """
        获取机器人加入的所有群聊ID
        
        通过飞书API获取机器人所在的群聊列表
        
        Returns:
            群聊ID列表
        """
        token = await self.get_token()
        chat_ids = []
        page_token = None
        
        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                params = {"page_size": 100}
                if page_token:
                    params["page_token"] = page_token
                
                resp = await client.get(
                    "https://open.larksuite.com/open-apis/im/v1/chats",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                data = resp.json()
                
                if data.get("code") != 0:
                    logger.error(f"获取群聊列表失败: {data}")
                    break
                
                items = data.get("data", {}).get("items", [])
                for item in items:
                    chat_id = item.get("chat_id")
                    if chat_id:
                        chat_ids.append(chat_id)
                
                page_token = data.get("data", {}).get("page_token")
                if not page_token or not data.get("data", {}).get("has_more"):
                    break
        
        logger.info(f"[MessageCollector] 获取到 {len(chat_ids)} 个群聊")
        return chat_ids

    async def collect_chat_messages(
        self,
        chat_id: str,
        since: datetime = None,
        container_id_type: str = "chat"
    ) -> Dict[str, Any]:
        """
        收集群聊消息
        
        Args:
            chat_id: 群聊ID
            since: 从什么时间开始收集 (默认今天0点)
            container_id_type: 容器类型
            
        Returns:
            {"collected": 收集数, "inserted": 新增数, "skipped": 跳过数}
        """
        if not since:
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        token = await self.get_token()
        
        messages = []
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
                    logger.error(f"获取消息失败: {data}")
                    break
                
                items = data.get("data", {}).get("items", [])
                
                for item in items:
                    # 解析消息
                    msg = self._parse_message(item, chat_id)
                    if msg:
                        messages.append(msg)
                
                page_token = data.get("data", {}).get("page_token")
                if not page_token or not data.get("data", {}).get("has_more"):
                    break
        
        # 从群成员列表获取用户名
        user_names = await self.get_chat_members_map(chat_id)
        # 填充用户名到消息
        for msg in messages:
            sender_id = msg.get("sender", {}).get("id")
            if sender_id:
                if sender_id in user_names:
                    msg["sender"]["name"] = user_names[sender_id]
                elif sender_id == self.app_id:
                    msg["sender"]["name"] = "Vulcan Brain Bot"
        
        # 批量保存
        result = await self.store.save_messages_batch(messages)
        result["collected"] = len(messages)
        
        logger.info(f"[MessageCollector] chat={chat_id}, collected={len(messages)}, inserted={result['inserted']}, skipped={result['skipped']}")
        
        return result
    
    def _parse_message(self, item: Dict, chat_id: str) -> Optional[Dict]:
        """解析飞书消息格式"""
        try:
            msg_type = item.get("msg_type", "")
            
            # 只处理文本消息
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
                    "sender_type": sender.get("sender_type", ""),
                    "tenant_key": sender.get("tenant_key", "")
                },
                "content": content,
                "content_type": msg_type,
                "timestamp": datetime.fromtimestamp(int(item.get("create_time", "0")) / 1000),
                "mentions": item.get("mentions", []),
                "parent_id": item.get("parent_id"),
                "root_id": item.get("root_id")
            }
        except Exception as e:
            logger.error(f"解析消息失败: {e}")
            return None
    
    async def send_collection_notice(self, chat_id: str, result: Dict) -> bool:
        """
        发送收集完成通知到群
        
        Args:
            chat_id: 群聊ID
            result: 收集结果
        """
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
                if data.get("code") == 0:
                    logger.info(f"[MessageCollector] 通知已发送到 {chat_id}")
                    return True
                else:
                    logger.error(f"发送通知失败: {data}")
                    return False
        except Exception as e:
            logger.error(f"发送通知异常: {e}")
            return False


# ===== 便捷函数 =====

def get_message_store() -> MessageStore:
    """获取消息存储实例"""
    return MessageStore()

def get_message_collector() -> FeishuMessageCollector:
    """获取消息收集器实例"""
    return FeishuMessageCollector()


# ===== 定时任务支持 =====

async def scheduled_collect_job(chat_ids: List[str]):
    """
    定时收集任务 (在日报生成前调用)
    
    Args:
        chat_ids: 需要收集的群聊ID列表
    """
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

# Singleton instance
store = MessageStore()
