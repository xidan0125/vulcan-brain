# mcp_tools/alignment/insight.py
"""
Boss 洞察保存模块
"""

import os
import json
from datetime import datetime
from typing import List

INSIGHT_FILE = os.path.expanduser('~/vulcan_brain_v2/data/boss_insights.json')

def _load_insights() -> List[dict]:
    if os.path.exists(INSIGHT_FILE):
        with open(INSIGHT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_insights(insights: List[dict]):
    os.makedirs(os.path.dirname(INSIGHT_FILE), exist_ok=True)
    with open(INSIGHT_FILE, 'w', encoding='utf-8') as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)


def save_insight(insight: str, category: str = 'general') -> str:
    """
    保存关于 Boss 的洞察
    
    Args:
        insight: 洞察内容
        category: 分类 (preference/style/priority/general)
    """
    insights = _load_insights()
    entry = {
        'id': len(insights) + 1,
        'insight': insight,
        'category': category,
        'timestamp': datetime.now().isoformat()
    }
    insights.append(entry)
    _save_insights(insights)
    return f'已保存洞察: {insight[:50]}...'


def get_insights(category: str = '') -> List[dict]:
    """
    获取洞察列表
    
    Args:
        category: 可选分类过滤
    """
    insights = _load_insights()
    if category:
        insights = [i for i in insights if i.get('category') == category]
    return insights


__module_info__ = {
    'name': 'insight',
    'category': 'alignment',
    'description': 'Boss 洞察管理',
    'functions': [
        {'name': 'save_insight', 'desc': '保存洞察', 'params': ['insight: str', 'category: str = "general"']},
        {'name': 'get_insights', 'desc': '获取洞察列表', 'params': ['category: str = ""']},
    ]
}
