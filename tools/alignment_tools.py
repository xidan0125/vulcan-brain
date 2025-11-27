# tools/alignment_tools.py
"""
Vulcan Brain - Alignment Tools (对齐工具)

将 vulcan_libs.alignment 封装为 LlamaIndex FunctionTool
让 Qwen3 能记录 Boss 的反馈和教导
"""

from llama_index.core.tools import FunctionTool
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vulcan_libs.alignment import (
    record_feedback as _record_feedback,
    get_alignment_summary as _get_summary
)


def record_boss_feedback(
    category: str,
    situation: str,
    boss_feedback: str,
    lesson_learned: str,
    importance: int = 3
) -> str:
    """
    记录 Boss 的反馈/纠正（用于价值观对齐）
    
    Args:
        category: 分类（"问题处理" / "代码实现" / "架构决策"）
        situation: 场景描述（发生了什么）
        boss_feedback: Boss 的原话
        lesson_learned: 提炼的教训（1-2 句话核心要点）
        importance: 重要性（1-5，5 最重要）
    
    Returns:
        确认信息
    
    Examples:
        record_boss_feedback(
            category="问题处理",
            situation="遇到 API 错误时创建了简化版本",
            boss_feedback="为啥要创建简单版本 架构师对你进行了严厉批评 有问题就上报问题就可以了",
            lesson_learned="遇到问题直接上报，不擅自创建简化版本",
            importance=5
        )
    """
    return _record_feedback(
        category=category,
        situation=situation,
        boss_feedback=boss_feedback,
        lesson_learned=lesson_learned,
        importance=importance
    )


def get_alignment_summary() -> str:
    """
    获取对齐记忆摘要（查看已记录的教训统计）
    
    Returns:
        对齐记忆的摘要信息
    
    Examples:
        get_alignment_summary()
    """
    return _get_summary()


# === 创建 LlamaIndex Tool ===

record_boss_feedback_tool = FunctionTool.from_defaults(
    fn=record_boss_feedback,
    name="record_boss_feedback",
    description="""记录 Boss 的反馈或纠正（用于价值观对齐）。
当 Boss 表扬、批评、纠正、或提出新原则时，立即调用此工具记录。
这些记录会在下次启动时自动加载到 System Prompt，确保不会重复犯错。

参数:
- category: 分类（"问题处理"/"代码实现"/"架构决策"）
- situation: 场景描述
- boss_feedback: Boss 的原话
- lesson_learned: 提炼的核心教训（1-2 句话）
- importance: 重要性（1-5，默认 3）
"""
)

get_alignment_summary_tool = FunctionTool.from_defaults(
    fn=get_alignment_summary,
    name="get_alignment_summary",
    description="""获取对齐记忆摘要。
查看已记录的 Boss 反馈数量和分类分布。
"""
)


# === 导出 ===
__all__ = ['record_boss_feedback_tool', 'get_alignment_summary_tool']


# === 测试代码 ===
if __name__ == "__main__":
    print("=== Alignment Tools 测试 ===\n")
    
    # 测试记录反馈
    print(record_boss_feedback(
        category="问题处理",
        situation="测试场景",
        boss_feedback="这是一个测试反馈",
        lesson_learned="测试教训",
        importance=3
    ))
    
    # 测试获取摘要
    print("\n摘要:")
    print(get_alignment_summary())
    
    print("\n✅ 测试完成")
