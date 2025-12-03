import os
import json
import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

# 配置日志
logger = logging.getLogger("VulcanStore")

class VulcanStore:
    _instance = None

    def __new__(cls, *args, **kwargs):
        """实现单例模式，确保全局只有一个数据库连接池"""
        if not cls._instance:
            cls._instance = super(VulcanStore, cls).__new__(cls)
        return cls._instance

    def __init__(self, mongo_uri: str = None):
        """
        初始化连接池
        注意：mongo_uri 默认从环境变量 MONGO_URI 读取，或者是 localhost
        """
        if hasattr(self, "client"):
            return  # 避免重复初始化

        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        try:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client.vulcan_brain
            logger.info(f"✅ MongoDB connected to {self.db.name}")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise e

    async def initialize_indexes(self):
        """
        初始化索引 (建议在应用启动时调用)
        解决技术债务：为高频查询字段建立索引
        """
        # 1. Users: username 必须唯一
        await self.db.users.create_index("username", unique=True)
        
        # 2. Sessions: user_id 和 updated_at 用于列表查询
        await self.db.chat_sessions.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
        
        # 3. Memories: user_id 用于检索
        await self.db.memories.create_index("user_id")
        
        # 4. Souls: user_id 唯一
        await self.db.user_souls.create_index("user_id", unique=True)
        
        logger.info("✅ MongoDB indexes initialized")

    # =========================================================================
    # User & Soul Management (用户与灵魂)
    # =========================================================================

    async def get_user(self, username: str) -> Optional[Dict]:
        """通过 username 获取用户信息"""
        return await self.db.users.find_one({"username": username})

    async def create_user(self, user_data: Dict) -> str:
        """创建新用户"""
        if "created_at" not in user_data:
            user_data["created_at"] = datetime.now()
        result = await self.db.users.insert_one(user_data)
        return str(result.inserted_id)

    async def get_soul(self, user_id: str) -> Dict:
        """
        获取用户的灵魂配置 (Soul)
        策略：优先读 MongoDB -> 降级读 YAML (兼容旧配置) -> 返回默认值
        """
        # 1. 尝试从 DB 读取
        soul = await self.db.user_souls.find_one({"user_id": user_id})
        if soul:
            return soul

        # 2. 降级：尝试读取本地静态 YAML (作为默认模板)
        yaml_path = Path("boss_constitution.yaml")
        if yaml_path.exists():
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    default_config = yaml.safe_load(f)
                    # 可以在这里做个自动迁移：把 YAML 存入 DB
                    default_config["user_id"] = user_id
                    default_config["source"] = "yaml_migration"
                    await self.update_soul(user_id, default_config)
                    return default_config
            except Exception as e:
                logger.warning(f"Failed to load yaml constitution: {e}")

        # 3. 返回空默认值
        return {"user_id": user_id, "core_values": [], "redlines": []}

    async def update_soul(self, user_id: str, soul_data: Dict):
        """更新灵魂配置 (Upsert)"""
        soul_data["updated_at"] = datetime.now()
        await self.db.user_souls.update_one(
            {"user_id": user_id},
            {"$set": soul_data},
            upsert=True
        )

    # =========================================================================
    # Chat Session Management (对话历史)
    # 兼容 Schema: 嵌套 messages 数组，user_id 为 String
    # =========================================================================

    async def create_session(self, user_id: str, provider: str = "vulcan", title: str = "New Chat") -> str:
        """创建新会话"""
        session_doc = {
            "user_id": user_id,  # String type (username)
            "provider": provider,
            "title": title,
            "messages": [],
            "message_count": 0,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        result = await self.db.chat_sessions.insert_one(session_doc)
        return str(result.inserted_id)

    async def add_message(self, session_id: str, role: str, content: str, provider: str = None):
        """
        向现有会话追加消息
        注意：这里更新了 updated_at，让会话在列表中置顶
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        # 构建更新操作
        update_op = {
            "$push": {"messages": message},
            "$inc": {"message_count": 1},
            "$set": {"updated_at": datetime.now()}
        }
        
        # 如果提供了 provider (例如切换模型)，顺便更新
        if provider:
            update_op["$set"]["provider"] = provider

        await self.db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)},
            update_op
        )

    async def add_messages_batch(self, session_id: str, messages: List[Dict]):
        """批量追加消息 (用于完整对话保存)"""
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", int(datetime.now().timestamp() * 1000))
            })
        
        # 自动生成标题
        title_update = {}
        first_user_msg = next((m for m in formatted_messages if m["role"] == "user"), None)
        if first_user_msg:
            content = first_user_msg["content"]
            title = content[:30] + ("..." if len(content) > 30 else "")
            title_update = {"title": title}
        
        await self.db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$push": {"messages": {"$each": formatted_messages}},
                "$inc": {"message_count": len(formatted_messages)},
                "$set": {"updated_at": datetime.now(), **title_update}
            }
        )

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """获取完整会话详情"""
        try:
            doc = await self.db.chat_sessions.find_one({"_id": ObjectId(session_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except:
            return None

    async def list_sessions(self, user_id: str, provider: str = None, limit: int = 20, skip: int = 0) -> List[Dict]:
        """获取会话列表 (只返回元数据，不返回 messages 以节省流量)"""
        query = {"user_id": user_id}
        if provider:
            query["provider"] = provider
            
        cursor = self.db.chat_sessions.find(
            query,
            {"messages": 0}  # Projection: 不返回消息体
        ).sort("updated_at", DESCENDING).skip(skip).limit(limit)
        
        sessions = await cursor.to_list(length=limit)
        for s in sessions:
            s["_id"] = str(s["_id"])
        return sessions

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """删除会话"""
        try:
            result = await self.db.chat_sessions.delete_one({
                "_id": ObjectId(session_id),
                "user_id": user_id
            })
            return result.deleted_count > 0
        except:
            return False

    # =========================================================================
    # Memory Management (用户记忆)
    # =========================================================================

    async def add_memory(self, user_id: str, content: str, category: str = "general"):
        """添加一条情景记忆"""
        memory_doc = {
            "user_id": user_id,
            "content": content,
            "category": category,
            "created_at": datetime.now(),
            "access_count": 0
        }
        result = await self.db.memories.insert_one(memory_doc)
        return str(result.inserted_id)

    async def get_memories(self, user_id: str, limit: int = 20) -> List[Dict]:
        """获取用户记忆列表"""
        cursor = self.db.memories.find(
            {"user_id": user_id}
        ).sort("created_at", DESCENDING).limit(limit)
        
        memories = await cursor.to_list(length=limit)
        for m in memories:
            m["_id"] = str(m["_id"])
        return memories

    async def search_memories(self, user_id: str, query: str = None, limit: int = 5) -> List[Dict]:
        """
        检索记忆
        TODO: 未来这里接入 MongoDB Atlas Search 或本地 Vector Search
        目前仅返回最近的记忆
        """
        cursor = self.db.memories.find(
            {"user_id": user_id}
        ).sort("created_at", DESCENDING).limit(limit)
        
        memories = await cursor.to_list(length=limit)
        for m in memories:
            m["_id"] = str(m["_id"])
        return memories

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """删除记忆"""
        try:
            result = await self.db.memories.delete_one({
                "_id": ObjectId(memory_id),
                "user_id": user_id
            })
            return result.deleted_count > 0
        except:
            return False

    # =========================================================================
    # Alignment Management (对齐记录)
    # =========================================================================

    async def add_alignment(self, user_id: str, situation: str, boss_feedback: str, lesson: str = ""):
        """添加对齐反馈"""
        doc = {
            "user_id": user_id,
            "situation": situation,
            "boss_feedback": boss_feedback,
            "lesson": lesson,
            "created_at": datetime.now()
        }
        result = await self.db.alignment_feedback.insert_one(doc)
        return str(result.inserted_id)

    async def get_alignments(self, user_id: str, limit: int = 10) -> List[Dict]:
        """获取对齐记录"""
        cursor = self.db.alignment_feedback.find(
            {"user_id": user_id}
        ).sort("created_at", DESCENDING).limit(limit)
        
        alignments = await cursor.to_list(length=limit)
        for a in alignments:
            a["_id"] = str(a["_id"])
        return alignments

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> Dict:
        """数据库健康检查"""
        try:
            await self.client.admin.command("ping")
            collections = await self.db.list_collection_names()
            return {
                "status": "healthy",
                "database": self.db.name,
                "collections": collections
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


    # =========================================================================
    # User Extended Operations (用户扩展操作)
    # =========================================================================

    async def update_user(self, username: str, updates: Dict) -> bool:
        """更新用户信息"""
        updates["updated_at"] = datetime.now()
        result = await self.db.users.update_one(
            {"username": username},
            {"$set": updates}
        )
        return result.modified_count > 0

    async def get_user_genesis(self, user_id: str) -> Optional[Dict]:
        """获取用户 Genesis 数据"""
        return await self.db.user_genesis.find_one({"user_id": user_id}, {"_id": 0})

    async def update_user_genesis(self, user_id: str, data: Dict):
        """更新 Genesis 数据"""
        data["updated_at"] = datetime.now()
        await self.db.user_genesis.update_one(
            {"user_id": user_id},
            {"$set": data},
            upsert=True
        )

    async def get_user_constitution(self, user_id: str) -> Optional[Dict]:
        """获取用户宪法"""
        return await self.db.user_constitution.find_one({"user_id": user_id}, {"_id": 0})

    async def update_user_constitution(self, user_id: str, items: List[Dict]):
        """更新用户宪法"""
        await self.db.user_constitution.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "items": items,
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )

    async def get_soul_twin(self, user_id: str) -> Optional[Dict]:
        """获取 SoulTwin"""
        return await self.db.soul_twin.find_one({"user_id": user_id}, {"_id": 0})

    async def update_soul_twin(self, user_id: str, data: Dict):
        """更新 SoulTwin"""
        data["updated_at"] = datetime.now()
        await self.db.soul_twin.update_one(
            {"user_id": user_id},
            {"$set": data},
            upsert=True
        )

    async def add_user_alignment_response(self, user_id: str, response: Dict):
        """添加用户对齐响应记录"""
        await self.db.user_alignments.update_one(
            {"user_id": user_id},
            {
                "$push": {"responses": response},
                "$set": {"updated_at": datetime.now()}
            },
            upsert=True
        )

    async def delete_user_genesis(self, user_id: str):
        """删除 Genesis 数据（重置用）"""
        await self.db.user_genesis.delete_one({"user_id": user_id})

    async def delete_user_constitution(self, user_id: str):
        """删除宪法（重置用）"""
        await self.db.user_constitution.delete_one({"user_id": user_id})

    # =========================================================================
    # Agent Session Management (Agent 会话)
    # =========================================================================

    async def get_agent_session(self, user_id: str, session_id: str) -> List[Dict]:
        """获取用户的 Agent 会话历史"""
        doc = await self.db.agent_sessions.find_one({
            "user_id": user_id,
            "session_id": session_id
        })
        return doc.get("messages", []) if doc else []

    async def save_agent_session(self, user_id: str, session_id: str, messages: List[Dict], agent_type: str):
        """保存用户的 Agent 会话"""
        await self.db.agent_sessions.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$set": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "agent_type": agent_type,
                    "messages": messages[-20:],
                    "updated_at": datetime.now()
                },
                "$setOnInsert": {"created_at": datetime.now()}
            },
            upsert=True
        )

    async def delete_agent_session(self, user_id: str, session_id: str) -> bool:
        """删除用户的 Agent 会话"""
        result = await self.db.agent_sessions.delete_one({
            "user_id": user_id,
            "session_id": session_id
        })
        return result.deleted_count > 0

    async def list_user_agent_sessions(self, user_id: str, agent_type: str = None, limit: int = 50) -> List[Dict]:
        """列出用户的所有 Agent 会话"""
        query = {"user_id": user_id}
        if agent_type:
            query["agent_type"] = agent_type
        
        cursor = self.db.agent_sessions.find(
            query,
            {"_id": 0, "session_id": 1, "agent_type": 1, "updated_at": 1}
        ).sort("updated_at", DESCENDING).limit(limit)
        
        return await cursor.to_list(length=limit)

    # =========================================================================
    # Soul Interaction & Prediction (Soul 交互和预测)
    # =========================================================================

    async def get_soul_interactions(self, user_id: str, interaction_type: str = None, limit: int = 20) -> List[Dict]:
        """获取 Soul 交互记录"""
        query = {"user_id": user_id}
        if interaction_type:
            query["type"] = interaction_type
        
        cursor = self.db.soul_interactions.find(query).sort("created_at", DESCENDING).limit(limit)
        interactions = await cursor.to_list(length=limit)
        for i in interactions:
            i["_id"] = str(i["_id"])
        return interactions

    async def count_soul_interactions(self, user_id: str) -> int:
        """统计 Soul 交互次数"""
        return await self.db.soul_interactions.count_documents({"user_id": user_id})

    async def get_sandbox_question(self, question_id: str) -> Optional[Dict]:
        """获取沙盘题目"""
        try:
            doc = await self.db.sandbox_questions.find_one({"_id": ObjectId(question_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except:
            return None



    async def count_user_constitution(self, user_id: str) -> int:
        """统计用户宪法条目数量"""
        return await self.db.user_constitution.count_documents({"user_id": user_id})


    async def get_sandbox_question_by_id(self, question_id: str) -> Optional[Dict]:
        """获取沙盒题目（通过ObjectId）"""
        from bson import ObjectId
        try:
            doc = await self.db.sandbox_questions.find_one({"_id": ObjectId(question_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except:
            return None

    async def get_soul_interactions_by_type(self, user_id: str, interaction_type: str = None, limit: int = 20) -> List[Dict]:
        """获取用户灵魂交互记录（按类型过滤）"""
        query = {"user_id": user_id}
        if interaction_type:
            query["type"] = interaction_type
        cursor = self.db.soul_interactions.find(query).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def get_soul_interactions_with_match(self, user_id: str, limit: int = 20) -> List[Dict]:
        """获取有匹配结果的灵魂交互记录"""
        query = {"user_id": user_id, "is_match": {"$exists": True}}
        cursor = self.db.soul_interactions.find(query).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results


# 全局单例导出

    # =========================================================================
    # Soul User Stats (灵魂用户统计)
    # =========================================================================

    async def get_soul_stats(self, user_id: str) -> Optional[Dict]:
        """获取用户灵魂统计"""
        doc = await self.db.soul_user_stats.find_one({"user_id": user_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def create_soul_stats(self, data: Dict) -> str:
        """创建用户灵魂统计"""
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        result = await self.db.soul_user_stats.insert_one(data)
        return str(result.inserted_id)

    async def update_soul_stats(self, user_id: str, update: Dict) -> bool:
        """更新用户灵魂统计"""
        result = await self.db.soul_user_stats.update_one(
            {"user_id": user_id},
            update
        )
        return result.modified_count > 0

    async def upsert_soul_stats(self, user_id: str, data: Dict) -> bool:
        """更新或创建用户灵魂统计"""
        data["updated_at"] = datetime.now()
        await self.db.soul_user_stats.update_one(
            {"user_id": user_id},
            {"$set": data},
            upsert=True
        )
        return True

    # =========================================================================
    # Sandbox Questions (沙盒题库)
    # =========================================================================

    async def get_sandbox_questions(self, query: Dict = {}, limit: int = 10, sort_field: str = "created_at", sort_dir: int = -1) -> List[Dict]:
        """获取沙盒题目列表"""
        cursor = self.db.sandbox_questions.find(query).sort(sort_field, sort_dir).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def insert_sandbox_question(self, data: Dict) -> str:
        """插入单个沙盒题目"""
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        result = await self.db.sandbox_questions.insert_one(data)
        return str(result.inserted_id)

    async def insert_sandbox_questions_batch(self, questions: List[Dict]) -> int:
        """批量插入沙盒题目"""
        if not questions:
            return 0
        for q in questions:
            if "created_at" not in q:
                q["created_at"] = datetime.now()
        result = await self.db.sandbox_questions.insert_many(questions)
        return len(result.inserted_ids)

    async def delete_all_sandbox_questions(self) -> int:
        """删除所有沙盒题目"""
        result = await self.db.sandbox_questions.delete_many({})
        return result.deleted_count

    async def count_sandbox_questions(self, query: Dict = {}) -> int:
        """统计沙盒题目数量"""
        return await self.db.sandbox_questions.count_documents(query)

    # =========================================================================
    # Soul Interactions Extended (灵魂交互扩展)
    # =========================================================================

    async def insert_soul_interaction(self, data: Dict) -> str:
        """插入灵魂交互记录"""
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        result = await self.db.soul_interactions.insert_one(data)
        return str(result.inserted_id)

    async def get_soul_interactions_since(self, user_id: str, since: datetime, interaction_type: str = None) -> List[Dict]:
        """获取指定日期后的交互记录"""
        query = {"user_id": user_id, "created_at": {"$gte": since}}
        if interaction_type:
            query["type"] = interaction_type
        cursor = self.db.soul_interactions.find(query)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    # =========================================================================
    # News Cache (新闻缓存)
    # =========================================================================

    async def get_news_cache(self, limit: int = 10) -> List[Dict]:
        """获取缓存的新闻"""
        cursor = self.db.news_cache.find().sort("fetched_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results


# 全局单例导出
store = VulcanStore()
