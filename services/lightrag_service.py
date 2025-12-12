"""
LightRAG 知识图谱问答服务 - Phase 4
基于邮件数据构建知识图谱，支持复杂问答
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc
import numpy as np

logger = logging.getLogger("LightRAGService")


class EmailLightRAG:
    """邮件知识图谱问答服务"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, working_dir: str = None, mongo_uri: str = None):
        if hasattr(self, "_initialized"):
            return
        
        self.working_dir = working_dir or os.path.expanduser("~/vulcan-brain/data/lightrag")
        os.makedirs(self.working_dir, exist_ok=True)
        
        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.vulcan_brain
        self.emails = self.db.emails
        
        # Ollama 配置
        self.llm_model = os.getenv("LLM_MODEL_NAME", "qwen3:30b-a3b")
        self.ollama_host = os.getenv("LLM_BASE_URL", "http://localhost:11434")
        
        # 初始化 LightRAG
        self.rag = None
        self._initialized = True
        logger.info(f"EmailLightRAG initialized, working_dir: {self.working_dir}")
    
    async def init_rag(self):
        """初始化 LightRAG 实例"""
        if self.rag:
            return
        
        logger.info(f"Initializing LightRAG with model: {self.llm_model}")
        
        # 自定义 embedding 函数，使用 Ollama
        async def embedding_func(texts: list[str]) -> np.ndarray:
            embeddings = []
            for text in texts:
                resp = await ollama_embed(
                    text,
                    embed_model="nomic-embed-text",
                    host=self.ollama_host,
                )
                # ollama_embed 返回的可能是列表或 np.array，确保是1D数组
                if isinstance(resp, np.ndarray):
                    embeddings.append(resp.flatten())
                elif isinstance(resp, list):
                    embeddings.append(np.array(resp).flatten())
                else:
                    embeddings.append(resp)
            # 返回 2D array: (num_texts, embedding_dim)
            return np.vstack(embeddings)
        
        self.rag = LightRAG(
            working_dir=self.working_dir,
            llm_model_func=ollama_model_complete,
            llm_model_name=self.llm_model,
            llm_model_kwargs={
                "host": self.ollama_host,
                "options": {"num_ctx": 32768}
            },
            embedding_func=EmbeddingFunc(
                embedding_dim=768,
                max_token_size=8192,
                func=embedding_func
            ),
        )

        # 新版本 LightRAG 需要初始化存储
        await self.rag.initialize_storages()

        # 初始化 pipeline 状态
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()

        logger.info("LightRAG initialized successfully")
    
    async def index_emails(self, limit: int = 1000, days: int = 90) -> Dict:
        """
        索引邮件到知识图谱
        
        Args:
            limit: 最大处理数量
            days: 处理最近多少天的邮件
        """
        await self.init_rag()
        
        since = datetime.now() - timedelta(days=days)
        query = {
            "received_at": {"$gte": since},
            "body_clean": {"$exists": True, "$ne": ""},
            "lightrag_indexed": {"$ne": True}
        }
        
        cursor = self.emails.find(
            query,
            {"email_id": 1, "subject": 1, "body_clean": 1, "from": 1, "to": 1, "received_at": 1, "category": 1, "entities": 1}
        ).limit(limit)
        
        indexed = 0
        errors = 0
        
        async for doc in cursor:
            try:
                # 构建文档内容
                from_addr = doc.get("from", {}).get("address", "") if isinstance(doc.get("from"), dict) else ""
                to_addrs = ", ".join([t.get("address", "") for t in doc.get("to", []) if isinstance(t, dict)])
                date_str = doc.get("received_at").strftime("%Y-%m-%d %H:%M") if doc.get("received_at") else ""
                
                # 提取实体信息
                entities_str = ""
                if doc.get("entities"):
                    entity_texts = [f"{e['type']}:{e['text']}" for e in doc["entities"][:10]]
                    entities_str = f"\n实体: {', '.join(entity_texts)}"
                
                content = f"""
邮件ID: {doc['email_id']}
日期: {date_str}
发件人: {from_addr}
收件人: {to_addrs}
分类: {doc.get('category', 'unknown')}
主题: {doc.get('subject', '')}
{entities_str}

内容:
{doc.get('body_clean', '')[:3000]}
""".strip()
                
                # 插入到 LightRAG
                await self.rag.ainsert(content)
                
                # 标记已索引
                await self.emails.update_one(
                    {"email_id": doc["email_id"]},
                    {"$set": {"lightrag_indexed": True, "lightrag_indexed_at": datetime.now()}}
                )
                
                indexed += 1
                if indexed % 50 == 0:
                    logger.info(f"Indexed {indexed} emails...")
                    
            except Exception as e:
                logger.error(f"Error indexing {doc.get('email_id')}: {e}")
                errors += 1
        
        return {
            "indexed": indexed,
            "errors": errors,
            "status": "success"
        }
    
    async def query(
        self, 
        question: str, 
        mode: str = "hybrid",
        only_need_context: bool = False
    ) -> Dict:
        """
        问答查询
        
        Args:
            question: 问题
            mode: 查询模式 - naive/local/global/hybrid
            only_need_context: 仅返回上下文，不生成回答
        """
        await self.init_rag()
        
        try:
            param = QueryParam(
                mode=mode,
                only_need_context=only_need_context,
            )
            
            result = await self.rag.aquery(question, param=param)
            
            return {
                "question": question,
                "answer": result,
                "mode": mode,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Query error: {e}")
            return {
                "question": question,
                "answer": f"查询出错: {str(e)}",
                "mode": mode,
                "status": "error"
            }
    
    async def get_stats(self) -> Dict:
        """获取索引统计"""
        indexed_count = await self.emails.count_documents({"lightrag_indexed": True})
        total_count = await self.emails.count_documents({})
        
        return {
            "indexed_emails": indexed_count,
            "total_emails": total_count,
            "index_ratio": round(indexed_count / total_count * 100, 2) if total_count > 0 else 0,
            "working_dir": self.working_dir,
        }
    
    async def summarize_recent(self, days: int = 1) -> Dict:
        """
        总结最近邮件
        
        Args:
            days: 总结最近多少天的邮件
        """
        await self.init_rag()
        
        since = datetime.now() - timedelta(days=days)
        
        # 获取邮件统计
        pipeline = [
            {"$match": {"received_at": {"$gte": since}}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }}
        ]
        
        category_stats = {}
        async for doc in self.emails.aggregate(pipeline):
            category_stats[doc["_id"] or "unknown"] = doc["count"]
        
        total = sum(category_stats.values())
        
        # 生成总结提示
        prompt = f"""请总结最近{days}天的邮件情况。

邮件统计:
- 总数: {total}封
- 分类分布: {category_stats}

请提供以下分析:
1. 主要沟通内容概述
2. 重要的人员/公司/项目提及
3. 需要关注的事项
4. 建议的后续行动"""
        
        result = await self.query(prompt, mode="global")
        
        return {
            "period": f"最近{days}天",
            "email_count": total,
            "category_stats": category_stats,
            "summary": result.get("answer", ""),
            "status": result.get("status")
        }


# ===== 便捷函数 =====

_service = None

def get_lightrag_service() -> EmailLightRAG:
    """获取 LightRAG 服务实例"""
    global _service
    if _service is None:
        _service = EmailLightRAG()
    return _service
