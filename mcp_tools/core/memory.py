# mcp_tools/core/memory.py
"""
长期记忆模块

接口:
- remember(info: str, value: str = None) -> str: 记住信息
- recall(query: str) -> str: 回忆信息
- forget(info: str) -> str: 删除记忆
- list_memories() -> list: 列出所有记忆
"""

import json
import os
from typing import List, Optional
from datetime import datetime

MEMORY_FILE = os.path.expanduser("~/vulcan_brain_v2/data/user_memory.json")

def _load_memories() -> List[dict]:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_memories(memories: List[dict]):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)


def remember(info: str, value: str = None) -> str:
    """
    记住一条信息
    
    支持两种调用方式：
    - remember("完整的信息内容")
    - remember("标签", "详细内容")  -> 存储为 "标签: 详细内容"
    """
    memories = _load_memories()
    
    # 如果传了两个参数，合并为 "key: value" 格式
    if value is not None:
        content = f"{info}: {value}"
    else:
        content = info
    
    entry = {
        "content": content,
        "created_at": datetime.now().isoformat(),
        "id": len(memories) + 1
    }
    memories.append(entry)
    _save_memories(memories)
    return f"已记住: {content}"


def recall(query: str = "") -> str:
    """回忆信息，可选关键词过滤"""
    memories = _load_memories()
    if not memories:
        return "暂无记忆"
    
    if query:
        matched = [m for m in memories if query.lower() in m["content"].lower()]
        if matched:
            return "\n".join([f"- {m['content']}" for m in matched])
        return f"没有找到与 \"{query}\" 相关的记忆"
    
    return "\n".join([f"- {m['content']}" for m in memories[-10:]])


def forget(info: str) -> str:
    """删除包含特定内容的记忆"""
    memories = _load_memories()
    original_count = len(memories)
    memories = [m for m in memories if info.lower() not in m["content"].lower()]
    _save_memories(memories)
    deleted = original_count - len(memories)
    return f"已删除 {deleted} 条相关记忆"


def list_memories() -> List[dict]:
    """列出所有记忆"""
    return _load_memories()


__module_info__ = {
    "name": "memory",
    "category": "core",
    "description": "长期记忆管理",
    "functions": [
        {"name": "remember", "desc": "记住信息", "params": ["info: str", "value: str = None"]},
        {"name": "recall", "desc": "回忆信息", "params": ["query: str = \"\""]},
        {"name": "forget", "desc": "删除记忆", "params": ["info: str"]},
        {"name": "list_memories", "desc": "列出所有记忆"},
    ]
}
