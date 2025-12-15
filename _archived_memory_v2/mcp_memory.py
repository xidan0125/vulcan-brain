# mcp_tools/core/memory.py
"""
记忆工具模块 - 长期记忆管理

接口:
- remember(key, value) -> str: 存储记忆
- recall(key) -> str: 召回记忆
- forget(key) -> str: 删除记忆
- list_memories() -> list: 列出所有记忆
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

MEMORY_DIR = os.path.expanduser('~/vulcan-brain/memory_store')
MEMORY_FILE = os.path.join(MEMORY_DIR, 'memories.json')


def _load_memories() -> Dict[str, Any]:
    """加载记忆文件"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_memories(memories: Dict[str, Any]):
    """保存记忆文件"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)


def remember(key: str, value: str) -> str:
    """
    存储一条记忆
    
    Args:
        key: 记忆键名（唯一标识）
        value: 记忆内容
    
    Returns:
        操作结果
    """
    memories = _load_memories()
    memories[key] = {
        'value': value,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    _save_memories(memories)
    return f'✅ 已记住: {key}'


def recall(key: str) -> str:
    """
    召回一条记忆
    
    Args:
        key: 记忆键名
    
    Returns:
        记忆内容，或提示未找到
    """
    memories = _load_memories()
    if key in memories:
        return memories[key]['value']
    return f'❌ 没有找到记忆: {key}'


def forget(key: str) -> str:
    """
    删除一条记忆
    
    Args:
        key: 记忆键名
    
    Returns:
        操作结果
    """
    memories = _load_memories()
    if key in memories:
        del memories[key]
        _save_memories(memories)
        return f'✅ 已删除记忆: {key}'
    return f'❌ 没有找到记忆: {key}'


def list_memories() -> List[str]:
    """
    列出所有记忆键名
    
    Returns:
        记忆键名列表
    """
    memories = _load_memories()
    return list(memories.keys())


# === 模块接口描述 ===
__module_info__ = {
    'name': 'memory',
    'category': 'core',
    'description': '长期记忆管理',
    'functions': [
        {'name': 'remember', 'desc': '存储一条记忆 (key, value)'},
        {'name': 'recall', 'desc': '召回一条记忆 (key)'},
        {'name': 'forget', 'desc': '删除一条记忆 (key)'},
        {'name': 'list_memories', 'desc': '列出所有记忆键名'},
    ]
}


if __name__ == '__main__':
    print('=== Memory 工具测试 ===')
    print(remember('test_key', '这是一条测试记忆'))
    print(f'召回: {recall("test_key")}')
    print(f'所有记忆: {list_memories()}')
    print(forget('test_key'))
