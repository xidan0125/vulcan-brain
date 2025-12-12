"""
实体抽取服务 - Phase 2
使用 GLiNER 进行零样本 NER 抽取

功能:
1. 从邮件中提取: 人名、公司、项目、金额、日期
2. 邮件分类
3. 实体消歧
4. 存储到 MongoDB
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from gliner import GLiNER
import os

logger = logging.getLogger("EntityService")

# 实体类型定义
ENTITY_LABELS = [
    "person",           # 人名
    "company",          # 公司/组织
    "project",          # 项目名称
    "money",            # 金额
    "date",             # 日期
    "product",          # 产品
    "location",         # 地点
    "email_address",    # 邮箱地址
    "phone_number",     # 电话
]

# 邮件分类类型
EMAIL_CATEGORIES = [
    "sales",        # 销售相关
    "procurement",  # 采购
    "hr",           # 人事
    "internal",     # 内部沟通
    "external",     # 外部沟通
    "finance",      # 财务
    "legal",        # 法务
    "technical",    # 技术
    "marketing",    # 市场营销
    "other",        # 其他
]


class EntityService:
    """实体抽取服务"""
    
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
        self.entities = self.db.entities  # 实体集合
        self.emails = self.db.emails
        
        # 加载 GLiNER 模型
        logger.info("Loading GLiNER model...")
        self.model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
        self.model.to("cuda:1")  # 移动到GPU
        logger.info("GLiNER model loaded")
        
        self._initialized = True
    
    async def init_indexes(self):
        """初始化索引"""
        await self.entities.create_index("email_id")
        await self.entities.create_index("type")
        await self.entities.create_index("text")
        await self.entities.create_index([("type", 1), ("text", 1)])
        await self.entities.create_index("extracted_at")
        logger.info("Entity indexes created")
    
    def extract_entities(self, text: str, threshold: float = 0.5) -> List[Dict]:
        """
        从文本中抽取实体
        
        Args:
            text: 输入文本
            threshold: 置信度阈值
        
        Returns:
            实体列表 [{"text": "...", "type": "...", "score": 0.9}, ...]
        """
        if not text or len(text.strip()) < 10:
            return []
        
        # 截断过长文本
        text = text[:5000]
        
        try:
            entities = self.model.predict_entities(
                text,
                ENTITY_LABELS,
                threshold=threshold
            )
            
            results = []
            for ent in entities:
                results.append({
                    "text": ent["text"].strip(),
                    "type": ent["label"],
                    "score": round(ent["score"], 3),
                    "start": ent["start"],
                    "end": ent["end"],
                })
            
            return results
        except Exception as e:
            logger.error(f"Entity extraction error: {e}")
            return []
    
    def classify_email(self, subject: str, body: str, from_addr: str, to_addrs: List[str]) -> str:
        """
        对邮件进行分类
        
        基于规则 + 关键词的简单分类
        """
        text = f"{subject} {body}".lower()
        
        # 规则匹配
        if any(kw in text for kw in ["invoice", "payment", "发票", "付款", "报销", "费用"]):
            return "finance"
        if any(kw in text for kw in ["contract", "合同", "agreement", "协议", "法律"]):
            return "legal"
        if any(kw in text for kw in ["offer", "salary", "工资", "入职", "离职", "招聘", "面试"]):
            return "hr"
        if any(kw in text for kw in ["quote", "quotation", "报价", "订单", "order", "销售"]):
            return "sales"
        if any(kw in text for kw in ["purchase", "采购", "供应商", "vendor", "procurement"]):
            return "procurement"
        if any(kw in text for kw in ["bug", "fix", "deploy", "api", "code", "开发", "技术"]):
            return "technical"
        if any(kw in text for kw in ["campaign", "marketing", "广告", "推广", "品牌"]):
            return "marketing"
        
        # 判断内部/外部
        company_domain = from_addr.split("@")[-1] if "@" in from_addr else ""
        is_external = any(
            "@" in addr and addr.split("@")[-1] != company_domain 
            for addr in to_addrs
        )
        
        return "external" if is_external else "internal"
    
    def normalize_entity(self, entity_text: str, entity_type: str) -> str:
        """
        实体规范化/消歧
        
        - 统一大小写
        - 去除多余空格
        - 合并同义词
        """
        text = entity_text.strip()
        
        # 公司名规范化
        if entity_type == "company":
            # 去除常见后缀
            text = re.sub(r'\s*(Inc\.?|Ltd\.?|LLC|Co\.?|Corp\.?|Limited|有限公司|股份公司)$', '', text, flags=re.I)
            text = text.strip()
        
        # 人名规范化
        if entity_type == "person":
            # 标题大小写
            text = text.title()
        
        # 金额规范化
        if entity_type == "money":
            # 统一格式
            text = re.sub(r'[\s,]', '', text)
        
        return text
    
    async def process_email(self, email_id: str, force: bool = False) -> Dict:
        """
        处理单封邮件，抽取实体并存储
        
        Args:
            email_id: 邮件ID
            force: 是否强制重新处理
        
        Returns:
            处理结果
        """
        # 检查是否已处理
        if not force:
            existing = await self.entities.find_one({"email_id": email_id})
            if existing:
                return {"status": "skipped", "reason": "already processed"}
        
        # 获取邮件
        email = await self.emails.find_one({"email_id": email_id})
        if not email:
            return {"status": "error", "reason": "email not found"}
        
        # 准备文本
        subject = email.get("subject", "") or ""
        body = email.get("body_clean", "") or email.get("body", "") or ""
        full_text = f"{subject}\n\n{body}"
        
        # 抽取实体
        raw_entities = self.extract_entities(full_text)
        
        # 规范化实体
        entities = []
        seen = set()
        for ent in raw_entities:
            normalized = self.normalize_entity(ent["text"], ent["type"])
            key = f"{ent['type']}:{normalized.lower()}"
            if key not in seen and len(normalized) > 1:
                seen.add(key)
                entities.append({
                    "text": normalized,
                    "original": ent["text"],
                    "type": ent["type"],
                    "score": ent["score"],
                })
        
        # 邮件分类
        from_addr = email.get("from", {}).get("address", "") if isinstance(email.get("from"), dict) else ""
        to_addrs = [t.get("address", "") for t in email.get("to", []) if isinstance(t, dict)]
        category = self.classify_email(subject, body, from_addr, to_addrs)
        
        # 存储
        doc = {
            "email_id": email_id,
            "entities": entities,
            "category": category,
            "entity_count": len(entities),
            "extracted_at": datetime.now(),
        }
        
        await self.entities.update_one(
            {"email_id": email_id},
            {"$set": doc},
            upsert=True
        )
        
        # 更新邮件文档
        await self.emails.update_one(
            {"email_id": email_id},
            {"$set": {
                "entities": entities,
                "category": category,
                "entities_extracted": True,
            }}
        )
        
        return {
            "status": "success",
            "email_id": email_id,
            "entity_count": len(entities),
            "category": category,
            "entities": entities[:10],  # 返回前10个
        }
    
    async def process_batch(self, limit: int = 100, skip_processed: bool = True) -> Dict:
        """
        批量处理邮件
        
        Args:
            limit: 处理数量限制
            skip_processed: 是否跳过已处理的
        
        Returns:
            处理统计
        """
        query = {"body_clean": {"$exists": True, "$ne": ""}}
        if skip_processed:
            query["entities_extracted"] = {"$ne": True}
        
        cursor = self.emails.find(query, {"email_id": 1}).limit(limit)
        
        processed = 0
        errors = 0
        
        async for doc in cursor:
            try:
                result = await self.process_email(doc["email_id"])
                if result["status"] == "success":
                    processed += 1
                    if processed % 50 == 0:
                        logger.info(f"Processed {processed} emails...")
            except Exception as e:
                logger.error(f"Error processing {doc['email_id']}: {e}")
                errors += 1
        
        return {
            "processed": processed,
            "errors": errors,
        }
    
    async def get_entity_stats(self) -> Dict:
        """获取实体统计"""
        pipeline = [
            {"$unwind": "$entities"},
            {"$group": {
                "_id": "$entities.type",
                "count": {"$sum": 1},
                "unique_values": {"$addToSet": "$entities.text"}
            }},
            {"$project": {
                "type": "$_id",
                "count": 1,
                "unique_count": {"$size": "$unique_values"},
            }}
        ]
        
        stats = {}
        async for doc in self.entities.aggregate(pipeline):
            stats[doc["_id"]] = {
                "total": doc["count"],
                "unique": doc["unique_count"],
            }
        
        # 分类统计
        cat_pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        categories = {}
        async for doc in self.entities.aggregate(cat_pipeline):
            categories[doc["_id"]] = doc["count"]
        
        total_emails = await self.entities.count_documents({})
        
        return {
            "total_processed": total_emails,
            "entity_types": stats,
            "categories": categories,
        }
    
    async def search_entities(
        self, 
        entity_type: str = None, 
        text: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """搜索实体"""
        pipeline = [{"$unwind": "$entities"}]
        
        match_stage = {}
        if entity_type:
            match_stage["entities.type"] = entity_type
        if text:
            match_stage["entities.text"] = {"$regex": text, "$options": "i"}
        
        if match_stage:
            pipeline.append({"$match": match_stage})
        
        pipeline.extend([
            {"$group": {
                "_id": {
                    "type": "$entities.type",
                    "text": "$entities.text"
                },
                "count": {"$sum": 1},
                "emails": {"$push": "$email_id"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ])
        
        results = []
        async for doc in self.entities.aggregate(pipeline):
            results.append({
                "type": doc["_id"]["type"],
                "text": doc["_id"]["text"],
                "count": doc["count"],
                "sample_emails": doc["emails"][:5],
            })
        
        return results


# ===== 便捷函数 =====

_service = None

def get_entity_service() -> EntityService:
    """获取实体服务实例"""
    global _service
    if _service is None:
        _service = EntityService()
    return _service
