# mcp_tools/alignment/__init__.py
"""
对齐模块

包含:
- feedback: Boss 反馈记录
- insight: 洞察保存
"""

from .feedback import record_feedback, get_alignment_summary
from .insight import save_insight, get_insights

__all__ = ['record_feedback', 'get_alignment_summary', 'save_insight', 'get_insights']
