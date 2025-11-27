# tools/boss_insight_tool.py
"""
Boss Insight Tool - 快速记录老板观点的简化工具
（补充 alignment_tools.py 中的 record_boss_feedback）
"""

from llama_index.core.tools import FunctionTool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vulcan_libs.alignment import record_feedback


def save_boss_insight(topic: str, insight: str) -> str:
    """
    快速记录老板的日常观点
    
    Args:
        topic: 话题（如 "2026预算", "团队管理"）
        insight: 老板的观点/教导
    
    Returns:
        确认信息
    
    Examples:
        save_boss_insight(topic="2026预算", insight="要激进投入研发")
    """
    # 使用 alignment 系统记录（分类为"日常观点"）
    return record_feedback(
        category="日常观点",
        situation=f"关于 {topic}",
        boss_feedback=insight,
        lesson_learned=insight,  # 简化版：直接用观点作为教训
        importance=3
    )


# 创建工具
save_boss_insight_tool = FunctionTool.from_defaults(
    fn=save_boss_insight,
    name="save_boss_insight",
    description="""快速记录老板的观点或教导。
当老板说"把这个记下来"、"记住XXX"时调用。
参数: topic (话题), insight (观点内容)
"""
)

__all__ = ['save_boss_insight_tool']
