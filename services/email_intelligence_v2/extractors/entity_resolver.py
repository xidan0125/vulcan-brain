"""
Email Intelligence V2.0 - Entity Resolver
实体消歧解析器 - 三级匹配策略

架构师锦囊 A (2025-12-11):
L1: 强规则匹配 (Deterministic) - 置信度 1.0
L2: 模糊文本匹配 (Fuzzy Logic) - 置信度 0.8-0.95
L3: 语义向量匹配 (Embedding) - 置信度 0.6-0.8, 必须人工审核

阈值设置 (保守策略):
- >= 0.98: 自动合并
- 0.75 - 0.98: 进入人工审核队列
- < 0.75: 视为新实体
"""
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .name_normalizer import NameNormalizer, get_normalizer

# 尝试导入 rapidfuzz，如果没有则使用标准库
try:
    from rapidfuzz import fuzz
    from rapidfuzz.distance import Levenshtein
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    # 回退到简单实现
    import difflib

logger = logging.getLogger(__name__)


class MatchLevel(str, Enum):
    """匹配级别"""
    L1_DETERMINISTIC = "L1_DETERMINISTIC"   # 强规则匹配
    L2_FUZZY = "L2_FUZZY"                   # 模糊匹配
    L3_SEMANTIC = "L3_SEMANTIC"             # 语义匹配
    NO_MATCH = "NO_MATCH"                   # 无匹配


@dataclass
class MatchResult:
    """匹配结果"""
    matched: bool
    match_level: MatchLevel
    confidence: float
    matched_party_id: Optional[str]
    matched_party_name: Optional[str]
    evidence: str
    details: Dict[str, Any]

    def should_auto_merge(self) -> bool:
        """是否应该自动合并"""
        return self.confidence >= 0.98 and self.match_level == MatchLevel.L1_DETERMINISTIC

    def should_queue_for_review(self) -> bool:
        """是否应该进入人工审核队列"""
        return 0.75 <= self.confidence < 0.98

    def should_create_new(self) -> bool:
        """是否应该创建新实体"""
        return self.confidence < 0.75 or not self.matched


class EntityResolver:
    """
    实体消歧解析器

    三级匹配策略:
    1. L1 强规则匹配: Domain/TaxID/精确名称
    2. L2 模糊匹配: Levenshtein + Token Overlap
    3. L3 语义匹配: Embedding (可选，需要人工审核)
    """

    # 阈值配置 (架构师评审 2025-12-11)
    THRESHOLD_AUTO_MERGE = 0.98          # 自动合并阈值
    THRESHOLD_MANUAL_REVIEW = 0.75       # 人工审核阈值

    # L2 模糊匹配阈值
    FUZZY_NAME_THRESHOLD = 0.85          # 名称相似度阈值
    FUZZY_TOKEN_THRESHOLD = 0.70         # 词元重叠阈值

    def __init__(self, db=None, embedding_service=None):
        """
        初始化解析器

        Args:
            db: MongoDB 数据库连接 (用于查询现有 parties)
            embedding_service: 向量嵌入服务 (可选，用于 L3 语义匹配)
        """
        self.db = db
        self.embedding_service = embedding_service
        self.normalizer = get_normalizer()

        # 缓存已加载的 parties (避免重复查询)
        self._party_cache: Dict[str, Any] = {}
        self._domain_index: Dict[str, List[str]] = {}  # domain -> party_ids
        self._alias_index: Dict[str, str] = {}         # normalized_alias -> party_id

    async def resolve(
        self,
        name: str,
        email: Optional[str] = None,
        additional_context: Optional[Dict] = None
    ) -> MatchResult:
        """
        解析实体，尝试匹配现有 party

        Args:
            name: 实体名称 (公司名或人名)
            email: 关联邮箱 (用于提取域名)
            additional_context: 额外上下文 (税号等)

        Returns:
            MatchResult: 匹配结果
        """
        if not name:
            return MatchResult(
                matched=False,
                match_level=MatchLevel.NO_MATCH,
                confidence=0.0,
                matched_party_id=None,
                matched_party_name=None,
                evidence="Empty name provided",
                details={}
            )

        # 标准化名称
        normalized = self.normalizer.normalize(name)
        domain = self.normalizer.extract_domain_from_email(email) if email else None

        # L1: 强规则匹配
        l1_result = await self._match_l1_deterministic(
            normalized.normalized,
            domain,
            additional_context
        )
        if l1_result.matched and l1_result.confidence >= self.THRESHOLD_AUTO_MERGE:
            return l1_result

        # L2: 模糊文本匹配
        l2_result = await self._match_l2_fuzzy(
            normalized.normalized,
            normalized.original
        )
        if l2_result.matched:
            # 如果 L1 也有部分匹配，结合两者
            if l1_result.matched:
                combined_confidence = max(l1_result.confidence, l2_result.confidence)
                return MatchResult(
                    matched=True,
                    match_level=l2_result.match_level,
                    confidence=combined_confidence,
                    matched_party_id=l2_result.matched_party_id,
                    matched_party_name=l2_result.matched_party_name,
                    evidence=f"L1 + L2 combined: {l1_result.evidence}; {l2_result.evidence}",
                    details={**l1_result.details, **l2_result.details}
                )
            return l2_result

        # L3: 语义匹配 (如果有嵌入服务)
        if self.embedding_service:
            l3_result = await self._match_l3_semantic(
                normalized.normalized,
                normalized.original
            )
            if l3_result.matched:
                return l3_result

        # 无匹配
        return MatchResult(
            matched=False,
            match_level=MatchLevel.NO_MATCH,
            confidence=0.0,
            matched_party_id=None,
            matched_party_name=None,
            evidence="No match found at any level",
            details={
                "normalized_name": normalized.normalized,
                "domain": domain,
                "is_japanese": normalized.is_japanese,
                "is_chinese": normalized.is_chinese
            }
        )

    async def _match_l1_deterministic(
        self,
        normalized_name: str,
        domain: Optional[str],
        context: Optional[Dict]
    ) -> MatchResult:
        """
        L1: 强规则匹配

        - Domain 精确匹配 (置信度 1.0)
        - Tax ID 匹配 (置信度 1.0)
        - 精确名称匹配 (标准化后) (置信度 0.99)
        """
        # 1. Domain 匹配
        if domain:
            party = await self._find_by_domain(domain)
            if party:
                return MatchResult(
                    matched=True,
                    match_level=MatchLevel.L1_DETERMINISTIC,
                    confidence=1.0,
                    matched_party_id=str(party.get("_id")),
                    matched_party_name=party.get("canonical_name"),
                    evidence=f"Domain exact match: {domain}",
                    details={"match_type": "DOMAIN_EXACT", "domain": domain}
                )

        # 2. Tax ID 匹配
        if context and context.get("tax_id"):
            party = await self._find_by_tax_id(context["tax_id"])
            if party:
                return MatchResult(
                    matched=True,
                    match_level=MatchLevel.L1_DETERMINISTIC,
                    confidence=1.0,
                    matched_party_id=str(party.get("_id")),
                    matched_party_name=party.get("canonical_name"),
                    evidence=f"Tax ID exact match: {context['tax_id']}",
                    details={"match_type": "TAX_ID_EXACT", "tax_id": context["tax_id"]}
                )

        # 3. 精确名称匹配 (别名索引)
        party = await self._find_by_alias(normalized_name)
        if party:
            return MatchResult(
                matched=True,
                match_level=MatchLevel.L1_DETERMINISTIC,
                confidence=0.99,
                matched_party_id=str(party.get("_id")),
                matched_party_name=party.get("canonical_name"),
                evidence=f"Alias exact match: {normalized_name}",
                details={"match_type": "ALIAS_EXACT", "matched_alias": normalized_name}
            )

        return MatchResult(
            matched=False,
            match_level=MatchLevel.L1_DETERMINISTIC,
            confidence=0.0,
            matched_party_id=None,
            matched_party_name=None,
            evidence="No L1 match",
            details={}
        )

    async def _match_l2_fuzzy(
        self,
        normalized_name: str,
        original_name: str
    ) -> MatchResult:
        """
        L2: 模糊文本匹配

        - Levenshtein 相似度
        - Token 重叠率
        - 结合两者计算最终置信度
        """
        best_match = None
        best_confidence = 0.0
        best_details = {}

        # 获取所有 parties 进行模糊匹配
        parties = await self._get_all_parties()

        for party in parties:
            party_name = party.get("canonical_name", "")
            party_normalized = self.normalizer.normalize(party_name).normalized
            party_aliases = party.get("aliases", [])

            # 计算与 canonical_name 的相似度
            similarity, details = self._calculate_fuzzy_similarity(
                normalized_name, party_normalized
            )

            # 也检查别名
            for alias in party_aliases:
                alias_normalized = self.normalizer.normalize(alias).normalized
                alias_sim, alias_details = self._calculate_fuzzy_similarity(
                    normalized_name, alias_normalized
                )
                if alias_sim > similarity:
                    similarity = alias_sim
                    details = alias_details
                    details["matched_via"] = "alias"
                    details["matched_alias"] = alias

            if similarity > best_confidence:
                best_confidence = similarity
                best_match = party
                best_details = details

        if best_match and best_confidence >= self.THRESHOLD_MANUAL_REVIEW:
            return MatchResult(
                matched=True,
                match_level=MatchLevel.L2_FUZZY,
                confidence=best_confidence,
                matched_party_id=str(best_match.get("_id")),
                matched_party_name=best_match.get("canonical_name"),
                evidence=f"Fuzzy match (confidence: {best_confidence:.2f})",
                details=best_details
            )

        return MatchResult(
            matched=False,
            match_level=MatchLevel.L2_FUZZY,
            confidence=best_confidence,
            matched_party_id=None,
            matched_party_name=None,
            evidence="No L2 fuzzy match above threshold",
            details={"best_confidence": best_confidence}
        )

    def _calculate_fuzzy_similarity(
        self,
        name1: str,
        name2: str
    ) -> Tuple[float, Dict]:
        """
        计算模糊相似度

        结合:
        - Levenshtein 相似度 (字符级)
        - Token 重叠率 (词级)
        """
        if not name1 or not name2:
            return 0.0, {}

        # Levenshtein 相似度
        if HAS_RAPIDFUZZ:
            levenshtein_sim = fuzz.ratio(name1, name2) / 100.0
            token_sim = fuzz.token_set_ratio(name1, name2) / 100.0
        else:
            # 回退到标准库
            levenshtein_sim = difflib.SequenceMatcher(None, name1, name2).ratio()
            # 简单的 token 重叠
            tokens1 = set(name1.split())
            tokens2 = set(name2.split())
            if tokens1 and tokens2:
                token_sim = len(tokens1 & tokens2) / len(tokens1 | tokens2)
            else:
                token_sim = 0.0

        # 加权平均 (Levenshtein 权重 0.6, Token 权重 0.4)
        combined = levenshtein_sim * 0.6 + token_sim * 0.4

        return combined, {
            "levenshtein_similarity": levenshtein_sim,
            "token_similarity": token_sim,
            "combined_score": combined,
            "name1": name1,
            "name2": name2
        }

    async def _match_l3_semantic(
        self,
        normalized_name: str,
        original_name: str
    ) -> MatchResult:
        """
        L3: 语义向量匹配

        使用 embedding 服务计算语义相似度
        注意: 这个级别的匹配必须进入人工审核
        """
        if not self.embedding_service:
            return MatchResult(
                matched=False,
                match_level=MatchLevel.L3_SEMANTIC,
                confidence=0.0,
                matched_party_id=None,
                matched_party_name=None,
                evidence="No embedding service available",
                details={}
            )

        # TODO: 实现语义匹配
        # 1. 获取 normalized_name 的 embedding
        # 2. 与所有 parties 的 embedding 计算余弦相似度
        # 3. 返回最佳匹配

        return MatchResult(
            matched=False,
            match_level=MatchLevel.L3_SEMANTIC,
            confidence=0.0,
            matched_party_id=None,
            matched_party_name=None,
            evidence="L3 semantic matching not yet implemented",
            details={}
        )

    # ==================== 数据库查询方法 ====================

    async def _find_by_domain(self, domain: str) -> Optional[Dict]:
        """通过域名查找 party"""
        if self.db is None:
            return None
        return await self.db.parties.find_one({
            "domain": domain.lower(),
            "party_type": "COMPANY",
            "entity_resolution.is_canonical": True
        })

    async def _find_by_tax_id(self, tax_id: str) -> Optional[Dict]:
        """通过税号查找 party"""
        if self.db is None:
            return None
        return await self.db.parties.find_one({
            "company_info.tax_id": tax_id,
            "entity_resolution.is_canonical": True
        })

    async def _find_by_alias(self, normalized_name: str) -> Optional[Dict]:
        """通过别名查找 party"""
        if self.db is None:
            return None

        # 查找 canonical_name 或 aliases 匹配的
        return await self.db.parties.find_one({
            "$or": [
                {"canonical_name": {"$regex": f"^{normalized_name}$", "$options": "i"}},
                {"aliases": {"$regex": f"^{normalized_name}$", "$options": "i"}}
            ],
            "entity_resolution.is_canonical": True
        })

    async def _get_all_parties(self) -> List[Dict]:
        """获取所有 canonical parties"""
        if self.db is None:
            return []

        cursor = self.db.parties.find({
            "entity_resolution.is_canonical": True
        })
        return await cursor.to_list(length=10000)

    # ==================== 递归解析 (路径压缩) ====================

    async def resolve_canonical(self, party_id: str) -> str:
        """
        递归解析到 canonical 记录

        架构师提醒: 如果 A → B → C，查询 A 时直接返回 C
        同时做路径压缩，把 A 直接指向 C
        """
        if self.db is None:
            return party_id

        visited = set()
        current_id = party_id

        while current_id not in visited:
            visited.add(current_id)

            party = await self.db.parties.find_one({"_id": current_id})
            if not party:
                break

            canonical_id = party.get("entity_resolution", {}).get("canonical_id")
            if not canonical_id or party.get("entity_resolution", {}).get("is_canonical"):
                # 找到 canonical 记录
                # 路径压缩: 更新所有中间节点直接指向 canonical
                if len(visited) > 1:
                    await self._compress_path(visited, current_id)
                return current_id

            current_id = canonical_id

        return party_id  # 回退

    async def _compress_path(self, visited_ids: set, canonical_id: str):
        """路径压缩: 所有中间节点直接指向 canonical"""
        for vid in visited_ids:
            if vid != canonical_id:
                await self.db.parties.update_one(
                    {"_id": vid},
                    {"$set": {
                        "entity_resolution.canonical_id": canonical_id,
                        "updated_at": datetime.utcnow()
                    }}
                )


    async def resolve_company(
        self,
        name: str,
        domain: Optional[str] = None,
    ) -> MatchResult:
        """
        解析公司实体 (便捷方法)

        Args:
            name: 公司名称
            domain: 邮箱域名 (可选)

        Returns:
            MatchResult: 匹配结果
        """
        email = f"info@{domain}" if domain else None
        return await self.resolve(name, email)


# 便捷函数
async def resolve_entity(
    name: str,
    email: Optional[str] = None,
    db=None,
    **kwargs
) -> MatchResult:
    """便捷函数: 解析实体"""
    resolver = EntityResolver(db=db)
    return await resolver.resolve(name, email, kwargs)
