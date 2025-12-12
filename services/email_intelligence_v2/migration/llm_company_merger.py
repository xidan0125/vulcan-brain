"""
LLM 驱动的公司合并检测
用大模型判断两家公司是否应该合并
"""
import asyncio
import json
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MergeCandidate:
    """合并候选"""
    company_a: Dict
    company_b: Dict
    similarity_hint: str  # 为什么认为可能相似

@dataclass
class MergeDecision:
    """合并决策"""
    should_merge: bool
    confidence: float  # 0-1
    reasoning: str
    suggested_canonical: str  # 建议保留哪个名字


class LLMCompanyMerger:
    """LLM 驱动的公司合并器"""

    MERGE_PROMPT = """判断这两家公司是否应该合并为同一实体:

公司A: {name_a} ({domain_a})
公司B: {name_b} ({domain_b})
线索: {similarity_hint}

合并条件: 同一公司不同写法、同一集团营销域名、同一服务不同域名
不合并: 完全不同的公司、不确定时

用JSON回复: {{"should_merge": true/false, "confidence": 0.0-1.0, "reasoning": "理由", "suggested_canonical": "保留名称"}}
只输出JSON。"""

    def __init__(self, db, vllm_host: str = "http://localhost:30000"):
        self.db = db
        self.vllm_host = vllm_host
        self.model = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

    async def find_candidates(self, limit: int = 100) -> List[MergeCandidate]:
        """找出可能需要合并的公司对"""
        candidates = []

        # 获取所有公司
        companies = await self.db.parties.find({
            "party_type": "COMPANY",
            "entity_resolution.is_canonical": True
        }).to_list(length=None)

        logger.info(f"共 {len(companies)} 家公司，开始查找候选对...")

        # 建立索引
        by_prefix = {}  # 前缀 -> 公司列表
        by_domain_root = {}  # 域名根 -> 公司列表

        for c in companies:
            name = (c.get("canonical_name") or "").lower().strip()
            domain = (c.get("identifiers", {}).get("domain") or "").lower()

            # 按名字前缀分组（前4个字符）
            if len(name) >= 4:
                prefix = name[:4]
                if prefix not in by_prefix:
                    by_prefix[prefix] = []
                by_prefix[prefix].append(c)

            # 按域名根分组（去掉常见后缀）
            if domain:
                # 提取域名核心部分
                domain_root = domain.split('.')[0]
                # 去掉常见的邮件营销后缀
                for suffix in ['-info', '-mail', 'mail', '-news', '-marketing']:
                    if domain_root.endswith(suffix):
                        domain_root = domain_root[:-len(suffix)]
                        break

                if domain_root and len(domain_root) >= 3:
                    if domain_root not in by_domain_root:
                        by_domain_root[domain_root] = []
                    by_domain_root[domain_root].append(c)

        seen_pairs = set()

        # 从前缀分组找候选
        for prefix, group in by_prefix.items():
            if len(group) > 1 and len(group) <= 10:  # 避免太大的组
                for i, a in enumerate(group):
                    for b in group[i+1:]:
                        pair_key = tuple(sorted([str(a["_id"]), str(b["_id"])]))
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            candidates.append(MergeCandidate(
                                company_a=a,
                                company_b=b,
                                similarity_hint=f"名称前缀相同: '{prefix}'"
                            ))

        # 从域名根分组找候选
        for domain_root, group in by_domain_root.items():
            if len(group) > 1 and len(group) <= 10:
                for i, a in enumerate(group):
                    for b in group[i+1:]:
                        pair_key = tuple(sorted([str(a["_id"]), str(b["_id"])]))
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            candidates.append(MergeCandidate(
                                company_a=a,
                                company_b=b,
                                similarity_hint=f"域名根相似: '{domain_root}'"
                            ))

        # 额外检查：一个名字是另一个的子串
        for i, a in enumerate(companies):
            name_a = (a.get("canonical_name") or "").lower()
            if len(name_a) < 3:
                continue

            for b in companies[i+1:]:
                name_b = (b.get("canonical_name") or "").lower()
                if len(name_b) < 3:
                    continue

                # 检查子串关系
                if name_a in name_b or name_b in name_a:
                    pair_key = tuple(sorted([str(a["_id"]), str(b["_id"])]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        candidates.append(MergeCandidate(
                            company_a=a,
                            company_b=b,
                            similarity_hint=f"名称包含关系: '{name_a}' / '{name_b}'"
                        ))

        logger.info(f"找到 {len(candidates)} 个候选对")
        return candidates[:limit]

    async def ask_llm(self, candidate: MergeCandidate) -> Optional[MergeDecision]:
        """用 LLM 判断是否应该合并"""
        import aiohttp

        a = candidate.company_a
        b = candidate.company_b

        prompt = self.MERGE_PROMPT.format(
            name_a=a.get("canonical_name") or a.get("display_name") or "未知",
            domain_a=a.get("identifiers", {}).get("domain") or "无域名",
            name_b=b.get("canonical_name") or b.get("display_name") or "未知",
            domain_b=b.get("identifiers", {}).get("domain") or "无域名",
            similarity_hint=candidate.similarity_hint
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.vllm_host}/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 300
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"vLLM 返回错误: {resp.status}")
                        return None

                    result = await resp.json()
                    response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                    # 解析 JSON
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1

                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        data = json.loads(json_str)

                        return MergeDecision(
                            should_merge=data.get("should_merge", False),
                            confidence=float(data.get("confidence", 0)),
                            reasoning=data.get("reasoning", ""),
                            suggested_canonical=data.get("suggested_canonical", "")
                        )
                    else:
                        logger.warning(f"无法解析 LLM 响应: {response_text[:200]}")
                        return None

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

    async def queue_for_review(
        self,
        candidate: MergeCandidate,
        decision: MergeDecision
    ):
        """将合并建议加入审核队列"""
        a = candidate.company_a
        b = candidate.company_b

        # 决定谁是 source（被合并）谁是 target（保留）
        if decision.suggested_canonical:
            suggested = decision.suggested_canonical.lower()
            name_a = (a.get("canonical_name") or "").lower()
            name_b = (b.get("canonical_name") or "").lower()

            if suggested in name_b or name_b in suggested:
                source, target = a, b
            else:
                source, target = b, a
        else:
            # 默认：名字短的保留，长的合并过去
            if len(a.get("canonical_name", "")) <= len(b.get("canonical_name", "")):
                source, target = b, a
            else:
                source, target = a, b

        queue_item = {
            "status": "PENDING",
            "merge_suggestion": {
                "source_party_id": str(source["_id"]),
                "source_name": source.get("canonical_name") or source.get("display_name"),
                "source_aliases": source.get("aliases", []),
                "source_domain": source.get("identifiers", {}).get("domain"),
                "target_party_id": str(target["_id"]),
                "target_name": target.get("canonical_name") or target.get("display_name"),
                "target_aliases": target.get("aliases", []),
                "target_domain": target.get("identifiers", {}).get("domain"),
            },
            "match_evidence": {
                "match_type": "LLM_ANALYSIS",
                "confidence": decision.confidence,
                "details": {
                    "domain_match": source.get("identifiers", {}).get("domain") == target.get("identifiers", {}).get("domain"),
                    "name_similarity": 0,  # LLM 判断不用这个
                    "token_overlap": 0,
                    "ai_reasoning": decision.reasoning,
                    "similarity_hint": candidate.similarity_hint
                },
                "common_emails": []
            },
            "risk_assessment": {
                "impact_level": "LOW",
                "affected_fulfillments": 0,
                "affected_shipments": 0,
                "affected_finance_docs": 0,
                "affected_compliance_docs": 0,
                "warning": None
            },
            "review": {
                "reviewed_by": None,
                "reviewed_at": None,
                "decision": None,
                "rejection_reason": None,
                "notes": None
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # 检查是否已存在
        existing = await self.db.entity_merge_queue.find_one({
            "$or": [
                {
                    "merge_suggestion.source_party_id": str(source["_id"]),
                    "merge_suggestion.target_party_id": str(target["_id"])
                },
                {
                    "merge_suggestion.source_party_id": str(target["_id"]),
                    "merge_suggestion.target_party_id": str(source["_id"])
                }
            ]
        })

        if existing:
            logger.info(f"跳过已存在: {source.get('canonical_name')} → {target.get('canonical_name')}")
            return False

        await self.db.entity_merge_queue.insert_one(queue_item)
        logger.info(f"已加入队列: {source.get('canonical_name')} → {target.get('canonical_name')} (置信度: {decision.confidence:.2f})")
        return True

    async def run(self, limit: int = 100, min_confidence: float = 0.7):
        """运行 LLM 合并检测"""
        logger.info("=== 开始 LLM 公司合并检测 ===")

        # 1. 找候选对
        candidates = await self.find_candidates(limit=limit)

        if not candidates:
            logger.info("没有找到候选对")
            return

        # 2. 逐个用 LLM 判断
        stats = {"total": len(candidates), "merged": 0, "skipped": 0, "error": 0}

        for i, candidate in enumerate(candidates):
            logger.info(f"\n[{i+1}/{len(candidates)}] 检查: {candidate.company_a.get('canonical_name')} vs {candidate.company_b.get('canonical_name')}")

            decision = await self.ask_llm(candidate)

            if decision is None:
                stats["error"] += 1
                continue

            logger.info(f"  LLM 判断: should_merge={decision.should_merge}, confidence={decision.confidence:.2f}")
            logger.info(f"  理由: {decision.reasoning[:100]}...")

            if decision.should_merge and decision.confidence >= min_confidence:
                added = await self.queue_for_review(candidate, decision)
                if added:
                    stats["merged"] += 1
                else:
                    stats["skipped"] += 1
            else:
                stats["skipped"] += 1

            # 避免太快
            await asyncio.sleep(0.5)

        logger.info(f"\n=== 完成 ===")
        logger.info(f"总候选: {stats['total']}")
        logger.info(f"加入队列: {stats['merged']}")
        logger.info(f"跳过: {stats['skipped']}")
        logger.info(f"错误: {stats['error']}")


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain

    merger = LLMCompanyMerger(db)
    await merger.run(limit=50, min_confidence=0.7)


if __name__ == "__main__":
    asyncio.run(main())
