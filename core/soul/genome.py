"""
Genome Manager - 六维度人格管理

负责从 MongoDB 读取/更新用户的 current_genome
"""

from typing import Optional, Dict, List
from datetime import datetime

from core.soul.types import Genome, Dimension, DIMENSION_META


class GenomeManager:
    """
    管理用户的六维度人格基因

    数据源: MongoDB user_genesis.current_genome
    """

    def __init__(self):
        # 延迟导入，避免循环依赖
        self._store = None

    @property
    def store(self):
        """懒加载 store"""
        if self._store is None:
            from vulcan_libs.store import store
            self._store = store
        return self._store

    async def get(self, user_id: str) -> Genome:
        """
        获取用户当前人格

        Args:
            user_id: 用户ID

        Returns:
            Genome 对象，如果用户不存在则返回中性默认值
        """
        data = await self.store.get_user_genesis(user_id)
        if data and "current_genome" in data:
            return Genome.from_dict(data["current_genome"])
        return Genome()  # 返回中性默认值 (all 50)

    async def get_initial(self, user_id: str) -> Optional[Genome]:
        """
        获取用户初始人格（Genesis 20问时的结果）
        """
        data = await self.store.get_user_genesis(user_id)
        if data and "initial_genome" in data:
            return Genome.from_dict(data["initial_genome"])
        return None

    async def update(self, user_id: str, genome: Genome):
        """
        更新用户人格（校准后调用）

        Args:
            user_id: 用户ID
            genome: 新的人格数据
        """
        await self.store.db.user_genesis.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "current_genome": genome.to_dict(),
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )

    async def get_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取人格变化历史（如果有记录）
        """
        cursor = self.store.db.genome_history.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def record_change(self, user_id: str, old_genome: Genome,
                            new_genome: Genome, reason: str):
        """
        记录人格变化（用于追溯和分析）
        """
        await self.store.db.genome_history.insert_one({
            "user_id": user_id,
            "old_genome": old_genome.to_dict(),
            "new_genome": new_genome.to_dict(),
            "reason": reason,
            "timestamp": datetime.now()
        })

    # ==================== 人格描述生成 ====================

    def describe(self, genome: Genome) -> str:
        """
        将数值转为自然语言描述（给 LLM 看）

        只描述偏离中性（>60 或 <40）的维度
        """
        descriptions = []

        for dim in Dimension:
            value = genome.get_value(dim)
            meta = DIMENSION_META[dim]

            if value > 60:
                descriptions.append(meta["high_desc"])
            elif value < 40:
                descriptions.append(meta["low_desc"])

        return "；".join(descriptions) if descriptions else "人格均衡，无明显偏好"

    def describe_detailed(self, genome: Genome) -> str:
        """
        详细描述所有维度（用于 Debug 或展示）
        """
        lines = []

        for dim in Dimension:
            value = genome.get_value(dim)
            meta = DIMENSION_META[dim]

            if value > 60:
                tendency = meta["high"]
                strength = "强烈" if value > 75 else "偏向"
            elif value < 40:
                tendency = meta["low"]
                strength = "强烈" if value < 25 else "偏向"
            else:
                tendency = "中性"
                strength = ""

            lines.append(f"- {meta['name']}: {strength}{tendency} ({value:.0f})")

        return "\n".join(lines)

    def get_dominant_traits(self, genome: Genome, threshold: float = 60) -> List[Dict]:
        """
        获取主导特质（偏离中性超过阈值的维度）
        """
        traits = []

        for dim in Dimension:
            value = genome.get_value(dim)
            meta = DIMENSION_META[dim]

            if value > threshold:
                traits.append({
                    "dimension": dim.value,
                    "name": meta["name"],
                    "value": value,
                    "trait": meta["high"],
                    "direction": "high"
                })
            elif value < (100 - threshold):
                traits.append({
                    "dimension": dim.value,
                    "name": meta["name"],
                    "value": value,
                    "trait": meta["low"],
                    "direction": "low"
                })

        return sorted(traits, key=lambda x: abs(x["value"] - 50), reverse=True)

    def get_response_hints(self, genome: Genome) -> List[str]:
        """
        根据人格生成回复风格提示（给 LLM 的指令）
        """
        hints = []

        # 风险偏好
        if genome.risk_appetite > 60:
            hints.append("用户倾向激进决策，可以提供大胆建议，不必过度强调风险")
        elif genome.risk_appetite < 40:
            hints.append("用户偏保守，建议强调风险和备选方案，提供安全选项")

        # 时间视界
        if genome.time_horizon > 60:
            hints.append("用户注重长期价值，可以讨论长远规划和延迟收益")
        elif genome.time_horizon < 40:
            hints.append("用户关注短期收益，强调即时成果和快速回报")

        # 控制风格
        if genome.control_style > 60:
            hints.append("用户喜欢结构化方案，提供清晰步骤和流程")
        elif genome.control_style < 40:
            hints.append("用户适应不确定性，可以探索多种可能，不必太拘泥")

        # 战略驱动
        if genome.strategic_drive > 60:
            hints.append("用户重视战略规划，提供深度分析和长期布局")
        elif genome.strategic_drive < 40:
            hints.append("用户偏好快速行动，简洁直接，少说多做")

        # 人际哲学
        if genome.people_philosophy > 60:
            hints.append("用户重视团队协作，强调共赢和协同")
        elif genome.people_philosophy < 40:
            hints.append("用户独立决策型，尊重其个人判断")

        # 伦理边界
        if genome.ethical_boundary > 60:
            hints.append("用户原则性强，避免建议灰色地带操作")
        elif genome.ethical_boundary < 40:
            hints.append("用户务实灵活，可以讨论权宜之计")

        return hints

    def compare(self, genome1: Genome, genome2: Genome) -> Dict:
        """
        比较两个人格的差异（用于展示变化）
        """
        changes = []

        for dim in Dimension:
            v1 = genome1.get_value(dim)
            v2 = genome2.get_value(dim)
            diff = v2 - v1

            if abs(diff) > 1:  # 忽略微小变化
                meta = DIMENSION_META[dim]
                changes.append({
                    "dimension": dim.value,
                    "name": meta["name"],
                    "old": v1,
                    "new": v2,
                    "diff": diff,
                    "direction": "increase" if diff > 0 else "decrease"
                })

        return {
            "total_change": sum(abs(c["diff"]) for c in changes),
            "dimensions_changed": len(changes),
            "changes": changes
        }


# 全局单例
_genome_manager: Optional[GenomeManager] = None


def get_genome_manager() -> GenomeManager:
    """获取 GenomeManager 单例"""
    global _genome_manager
    if _genome_manager is None:
        _genome_manager = GenomeManager()
    return _genome_manager
