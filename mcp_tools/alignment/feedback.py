# mcp_tools/alignment/feedback.py
"""
Boss 反馈记录模块
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any

FEEDBACK_FILE = os.path.expanduser('~/vulcan_brain_v2/data/alignment_feedback.json')

def _load_feedback() -> List[dict]:
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_feedback(feedback: List[dict]):
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback, f, ensure_ascii=False, indent=2)


def record_feedback(situation: str, my_response: str, boss_feedback: str, lesson: str = '') -> str:
    """
    记录 Boss 的反馈用于价值观对齐

    Args:
        situation: 发生的情况
        my_response: 我的回应
        boss_feedback: Boss 的反馈
        lesson: 学到的教训
    """
    feedback_list = _load_feedback()
    entry = {
        'id': len(feedback_list) + 1,
        'situation': situation,
        'my_response': my_response,
        'boss_feedback': boss_feedback,
        'lesson': lesson,
        'timestamp': datetime.now().isoformat()
    }
    feedback_list.append(entry)
    _save_feedback(feedback_list)
    return f'已记录反馈: {lesson or boss_feedback[:50]}'


def get_alignment_summary(limit: int = 5) -> str:
    """获取最近的对齐学习总结"""
    feedback_list = _load_feedback()
    if not feedback_list:
        return '暂无对齐记录'

    recent = feedback_list[-limit:]
    lines = ['最近的对齐学习:']
    for fb in recent:
        lesson_text = fb.get('lesson', fb['boss_feedback'][:50])
        lines.append(f"- [{fb['timestamp'][:10]}] {lesson_text}")
    return '\n'.join(lines)


__module_info__ = {
    'name': 'feedback',
    'category': 'alignment',
    'description': 'Boss 反馈记录',
    'functions': [
        {'name': 'record_feedback', 'desc': '记录反馈', 'params': ['situation', 'my_response', 'boss_feedback', 'lesson']},
        {'name': 'get_alignment_summary', 'desc': '获取对齐总结', 'params': ['limit: int = 5']},
    ]
}
