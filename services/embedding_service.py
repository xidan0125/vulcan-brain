"""
Email Embedding Service
使用 sentence-transformers 生成向量，存入 Qdrant
"""
import logging
import uuid
import hashlib
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

logger = logging.getLogger(__name__)

# 使用多语言模型，支持中英文
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "emails"
VECTOR_SIZE = 384
BATCH_SIZE = 100

class EmbeddingService:
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", qdrant_host: str = "localhost", qdrant_port: int = 6333):
        self.mongo_client = AsyncIOMotorClient(mongo_uri)
        self.db = self.mongo_client.vulcan_brain
        self.emails = self.db.emails
        
        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.model = None  # Lazy load
        
    def _get_model(self):
        if self.model is None:
            logger.info(f"加载模型: {MODEL_NAME}")
            self.model = SentenceTransformer(MODEL_NAME)
        return self.model
    
    def init_collection(self):
        """初始化 Qdrant collection"""
        collections = self.qdrant.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        
        if not exists:
            self.qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            logger.info(f"创建 collection: {COLLECTION_NAME}")
        else:
            logger.info(f"Collection {COLLECTION_NAME} 已存在")
        
        return True
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量"""
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    
    async def vectorize_emails(self, batch_size: int = BATCH_SIZE) -> Dict:
        """向量化所有邮件"""
        self.init_collection()
        
        # 获取已向量化的邮件 ID
        existing_ids = set()
        try:
            scroll_result = self.qdrant.scroll(
                collection_name=COLLECTION_NAME,
                limit=100000,
                with_payload=False
            )
            existing_ids = {p.id for p in scroll_result[0]}
        except Exception:
            pass
        
        logger.info(f"已有 {len(existing_ids)} 个向量")
        
        # 获取需要向量化的邮件（有清洗后内容的）
        cursor = self.emails.find(
            {"body_clean": {"$exists": True, "$ne": ""}},
            {"email_id": 1, "subject": 1, "body_clean": 1, "from": 1, "user_id": 1, "received_at": 1}
        )
        
        total = 0
        added = 0
        skipped = 0
        batch = []
        
        async for email in cursor:
            total += 1
            email_id = email.get("email_id")
            
            if email_id in existing_ids:
                skipped += 1
                continue
            
            # 组合文本：主题 + 正文
            subject = email.get("subject", "")
            body = email.get("body_clean", "")[:2000]  # 限制长度
            text = f"{subject}\n{body}".strip()
            
            if not text:
                skipped += 1
                continue
            
            batch.append({
                "id": email_id,
                "text": text,
                "payload": {
                    "email_id": email_id,
                    "subject": str(subject or "")[:200],
                    "from": email.get("from", ""),
                    "user_id": email.get("user_id", ""),
                    "received_at": email.get("received_at").isoformat() if email.get("received_at") else None
                }
            })
            
            if len(batch) >= batch_size:
                added += self._process_batch(batch)
                batch = []
                
                if added % 1000 == 0:
                    logger.info(f"已处理: {total}, 已添加: {added}")
        
        # 处理剩余
        if batch:
            added += self._process_batch(batch)
        
        logger.info(f"向量化完成: 总数={total}, 添加={added}, 跳过={skipped}")
        return {"total": total, "added": added, "skipped": skipped}
    
    def _process_batch(self, batch: List[Dict]) -> int:
        """处理一批数据"""
        texts = [item["text"] for item in batch]
        embeddings = self.embed_texts(texts)
        
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, item["id"])),
                vector=emb,
                payload=item["payload"]
            )
            for item, emb in zip(batch, embeddings)
        ]
        
        self.qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        return len(points)
    
    def search(self, query: str, limit: int = 10, user_id: Optional[str] = None) -> List[Dict]:
        """语义搜索"""
        query_vector = self.embed_texts([query])[0]
        
        search_filter = None
        if user_id:
            search_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )
        
        results = self.qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=search_filter,
            with_payload=True
        ).points
        
        return [
            {
                "email_id": r.payload.get("email_id"),
                "subject": r.payload.get("subject"),
                "from": r.payload.get("from"),
                "score": r.score
            }
            for r in results
        ]
    
    def get_stats(self) -> Dict:
        """获取向量库统计"""
        info = self.qdrant.get_collection(COLLECTION_NAME)
        return {
            "vectors_count": info.points_count,
            "points_count": info.points_count,
            "status": info.status
        }


_instance = None

def get_embedding_service() -> EmbeddingService:
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
