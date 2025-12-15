"""
Calibration Engine - EMA 校准算法

使用指数移动平均（EMA）平滑更新用户人格
"""

from typing import Dict, Optional
from datetime import datetime

from core.soul.types import Genome, Dimension, CalibrationAnswer
from core.soul.genome import GenomeManager, get_genome_manager


class CalibrationEngine:
    """
    指数移动平均（EMA）校准算法

    公式: P_new = P_old * (1-α) + target * α
    α (学习率): 控制新数据对总人格的影响程度

    默认 α=0.15，意味着：
    - 每道题影响约 15% 的人格
    - 需要约 7 道题才能将人格从一个极端移到另一个极端
    - 人格变化平滑，不会因单题剧变
    """

    def __init__(self, learning_rate: float = 0.15):
        """
        Args:
            learning_rate: 学习率 α (0.1-0.3 推荐)
        """
        self.alpha = learning_rate
        self.genome_mgr = get_genome_manager()

    def calibrate(self, current: Genome, option_weights: Dict[str, float]) -> Genome:
        """
        根据用户选择更新人格

        Args:
            current: 当前人格
            option_weights: 选项权重，如 {"risk_appetite": 10, "time_horizon": -5}
                           范围通常是 -30 到 +30

        Returns:
            更新后的人格
        """
        new_values = {}

        for dim in Dimension:
            current_val = current.get_value(dim)
            weight = option_weights.get(dim.value, 0)

            # EMA 公式
            # weight 作为"拉力"，表示这个选择倾向于把人格往哪个方向拉
            # 正值拉向高端，负值拉向低端
            target = current_val + weight
            new_val = current_val * (1 - self.alpha) + target * self.alpha

            # 边界钳制 (0-100)
            new_values[dim.value] = max(0, min(100, new_val))

        return Genome(**new_values)

    async def process_answer(self, user_id: str, answer: CalibrationAnswer,
                             record_history: bool = True) -> Dict:
        """
        处理用户的校准答案

        Args:
            user_id: 用户ID
            answer: 校准答案
            record_history: 是否记录变化历史

        Returns:
            {
                "old_genome": {...},
                "new_genome": {...},
                "changes": {...}
            }
        """
        # 获取当前人格
        old_genome = await self.genome_mgr.get(user_id)

        # 计算新人格
        new_genome = self.calibrate(old_genome, answer.weights)

        # 更新数据库
        await self.genome_mgr.update(user_id, new_genome)

        # 记录历史
        if record_history:
            await self.genome_mgr.record_change(
                user_id=user_id,
                old_genome=old_genome,
                new_genome=new_genome,
                reason=f"calibration_question_{answer.question_id}"
            )

        # 计算变化
        changes = self.genome_mgr.compare(old_genome, new_genome)

        return {
            "old_genome": old_genome.to_dict(),
            "new_genome": new_genome.to_dict(),
            "changes": changes
        }

    def preview_calibration(self, current: Genome,
                            option_weights: Dict[str, float]) -> Dict:
        """
        预览校准结果（不实际更新）

        用于在用户选择前展示"如果选这个，人格会如何变化"
        """
        new_genome = self.calibrate(current, option_weights)
        changes = self.genome_mgr.compare(current, new_genome)

        return {
            "preview_genome": new_genome.to_dict(),
            "changes": changes,
            "description": self.genome_mgr.describe(new_genome)
        }

    def estimate_questions_needed(self, current: Genome, target: Genome) -> int:
        """
        估算需要多少道题才能从当前人格到达目标人格

        基于 EMA 收敛特性：
        - 每道题移动约 α * 差距
        - 需要 ln(残差) / ln(1-α) 道题
        """
        import math

        max_diff = 0
        for dim in Dimension:
            diff = abs(current.get_value(dim) - target.get_value(dim))
            max_diff = max(max_diff, diff)

        if max_diff < 1:
            return 0

        # 假设需要将差距缩小到 5 以内
        target_diff = 5
        if max_diff <= target_diff:
            return 0

        # 计算需要的步数
        # 每步后剩余差距 = 差距 * (1-α)
        # n 步后剩余 = 差距 * (1-α)^n
        # 求 n 使得 差距 * (1-α)^n <= target_diff
        n = math.log(target_diff / max_diff) / math.log(1 - self.alpha)

        return max(1, int(math.ceil(n)))


class AdaptiveCalibrationEngine(CalibrationEngine):
    """
    自适应校准引擎

    根据用户的校准历史动态调整学习率：
    - 新用户：较高学习率 (0.25)，快速建立人格
    - 老用户：较低学习率 (0.10)，稳定微调
    """

    def __init__(self):
        super().__init__(learning_rate=0.15)  # 默认中等

    async def get_adaptive_rate(self, user_id: str) -> float:
        """
        根据用户历史计算自适应学习率
        """
        # 获取用户已回答的题目数
        genesis_data = await self.genome_mgr.store.get_user_genesis(user_id)

        if not genesis_data:
            return 0.25  # 新用户，高学习率

        questions_answered = genesis_data.get("questions_answered", 0)

        if questions_answered < 20:
            return 0.25  # 仍在建立阶段
        elif questions_answered < 50:
            return 0.15  # 稳定阶段
        else:
            return 0.10  # 成熟阶段，微调

    async def process_answer(self, user_id: str, answer: CalibrationAnswer,
                             record_history: bool = True) -> Dict:
        """
        使用自适应学习率处理答案
        """
        # 动态调整学习率
        self.alpha = await self.get_adaptive_rate(user_id)

        # 调用父类方法
        result = await super().process_answer(user_id, answer, record_history)

        # 更新已回答题目数
        await self.genome_mgr.store.db.user_genesis.update_one(
            {"user_id": user_id},
            {"$inc": {"questions_answered": 1}}
        )

        result["learning_rate_used"] = self.alpha
        return result


# 全局单例
_calibration_engine: Optional[CalibrationEngine] = None


def get_calibration_engine(adaptive: bool = True) -> CalibrationEngine:
    """获取校准引擎单例"""
    global _calibration_engine
    if _calibration_engine is None:
        if adaptive:
            _calibration_engine = AdaptiveCalibrationEngine()
        else:
            _calibration_engine = CalibrationEngine()
    return _calibration_engine
