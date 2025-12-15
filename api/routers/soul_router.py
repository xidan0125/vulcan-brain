"""
Vulcan Brain API - 灵魂配置路由
P4 Soul Config API - AI 人格配置
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter
from typing import Optional

router = APIRouter(tags=["Soul Config"])


# === 存储配置 ===
SOUL_CONFIG_FILE = './soul_config.json'

# 默认灵魂配置
_default_soul_config = {
    'system_prompt': """你是 Vulcan Brain，一个高性能 AI Agent。

核心价值观:
- 专业性：提供准确、可靠的信息和分析
- 效率：快速响应，直击问题核心
- 透明度：清晰展示思考过程和不确定性
- 主动性：预判需求，提供前瞻性建议

工作方式:
1. 使用 <think> 标签展示内部推理过程
2. 调用工具时说明理由和预期效果
3. 提供多角度分析，必要时给出备选方案
4. 对不确定的内容明确标注""",
    'creativity': 70,
    'reasoning_depth': 80,
    'tool_use_preference': 60,
    'memory_retention': 75,
    'updated_at': None
}

# 加载/初始化配置
if os.path.exists(SOUL_CONFIG_FILE):
    with open(SOUL_CONFIG_FILE, 'r', encoding='utf-8') as f:
        _soul_config = json.load(f)
else:
    _soul_config = _default_soul_config.copy()


def _save_soul_config():
    """保存 Soul Config 到磁盘"""
    with open(SOUL_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(_soul_config, f, ensure_ascii=False, indent=2)


# === API Endpoints ===
@router.get('/api/soul/config')
async def get_soul_config():
    """P4 - 获取当前灵魂配置"""
    return {
        'config': _soul_config,
        'is_default': _soul_config.get('updated_at') is None
    }


@router.post('/api/soul/update')
async def update_soul_config(
    system_prompt: Optional[str] = None,
    creativity: Optional[int] = None,
    reasoning_depth: Optional[int] = None,
    tool_use_preference: Optional[int] = None,
    memory_retention: Optional[int] = None
):
    """P4 - 更新灵魂配置"""
    if system_prompt is not None:
        _soul_config['system_prompt'] = system_prompt
    if creativity is not None:
        _soul_config['creativity'] = max(0, min(100, creativity))
    if reasoning_depth is not None:
        _soul_config['reasoning_depth'] = max(0, min(100, reasoning_depth))
    if tool_use_preference is not None:
        _soul_config['tool_use_preference'] = max(0, min(100, tool_use_preference))
    if memory_retention is not None:
        _soul_config['memory_retention'] = max(0, min(100, memory_retention))

    _soul_config['updated_at'] = datetime.now().isoformat()
    _save_soul_config()

    return {
        'success': True,
        'config': _soul_config,
        'message': '灵魂配置已更新'
    }


@router.post('/api/soul/reset')
async def reset_soul_config():
    """P4 - 重置灵魂配置为默认值"""
    global _soul_config
    _soul_config = _default_soul_config.copy()
    _soul_config['updated_at'] = None
    _save_soul_config()

    return {
        'success': True,
        'config': _soul_config,
        'message': '灵魂配置已重置为默认值'
    }
