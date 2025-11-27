# vulcan_libs/memory.py
"""
Vulcan Brain - Episodic Memory Manager (情景记忆管理器)

灵感来源: EverMemOS 的分层记忆架构
实现策略: 极简 JSON 存储 + Prompt 注入

功能:
- remember(key, value): 存储长期记忆
- recall(key): 回忆特定记忆
- get_all_memories(): 获取所有记忆（用于 System Prompt 注入）
- reflect_and_save(conversation): 让 AI 自我反思并提炼核心记忆
"""

import json
import os
from typing import Dict, Optional
from datetime import datetime

# 默认存储路径
DEFAULT_MEMORY_FILE = "user_profile.json"

class EpisodicMemoryManager:
    """轻量级情景记忆管理器 - Vulcan MemOS v0.1"""
    
    def __init__(self, memory_file: str = DEFAULT_MEMORY_FILE):
        self.memory_file = memory_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """确保记忆文件存在"""
        if not os.path.exists(self.memory_file):
            self._save({})
    
    def _load(self) -> Dict:
        """加载记忆数据"""
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save(self, data: Dict):
        """保存记忆数据"""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def remember(self, key: str, value: str, metadata: Optional[Dict] = None) -> str:
        """
        写入长期记忆
        
        Args:
            key: 记忆键（如 "project_name", "user_preference"）
            value: 记忆内容
            metadata: 可选元数据（时间戳、重要性等）
        
        Returns:
            确认信息
        """
        data = self._load()
        
        # 构建记忆条目
        entry = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        data[key] = entry
        self._save(data)
        
        return f"✅ 已记住: {key} = {value}"
    
    def recall(self, key: str) -> str:
        """
        回忆特定记忆
        
        Args:
            key: 记忆键
        
        Returns:
            记忆内容，如果不存在则返回提示
        """
        data = self._load()
        
        if key in data:
            entry = data[key]
            return entry["value"]
        else:
            return f"❌ 我没有关于 '{key}' 的记忆。"
    
    def get_all_memories(self) -> str:
        """
        获取所有核心记忆（用于注入 System Prompt）
        
        Returns:
            格式化的记忆摘要
        """
        data = self._load()
        
        if not data:
            return "【暂无长期记忆】"
        
        # 格式化输出
        memory_lines = []
        for key, entry in data.items():
            value = entry["value"]
            memory_lines.append(f"- {key}: {value}")
        
        return "\n".join(memory_lines)
    
    def forget(self, key: str) -> str:
        """
        删除特定记忆
        
        Args:
            key: 要删除的记忆键
        
        Returns:
            确认信息
        """
        data = self._load()
        
        if key in data:
            del data[key]
            self._save(data)
            return f"✅ 已忘记: {key}"
        else:
            return f"❌ 没有找到要删除的记忆: {key}"
    
    def clear_all(self) -> str:
        """清空所有记忆（危险操作）"""
        self._save({})
        return "✅ 已清空所有记忆"
    
    def get_memory_count(self) -> int:
        """获取记忆条目数量"""
        data = self._load()
        return len(data)


# === 便捷函数接口（供工具调用）===

_default_manager = None

def get_manager(memory_file: str = DEFAULT_MEMORY_FILE) -> EpisodicMemoryManager:
    """获取全局记忆管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = EpisodicMemoryManager(memory_file)
    return _default_manager


def remember(key: str, value: str) -> str:
    """便捷函数：写入记忆"""
    return get_manager().remember(key, value)


def recall(key: str) -> str:
    """便捷函数：回忆记忆"""
    return get_manager().recall(key)


def get_all_memories() -> str:
    """便捷函数：获取所有记忆"""
    return get_manager().get_all_memories()


def forget(key: str) -> str:
    """便捷函数：删除记忆"""
    return get_manager().forget(key)


# === 测试代码 ===
if __name__ == "__main__":
    # 测试记忆管理器
    manager = EpisodicMemoryManager("test_memory.json")
    
    print("=== Vulcan Memory Manager 测试 ===\n")
    
    # 测试 1: 写入记忆
    print(manager.remember("project_name", "Vulcan Brain v2.0"))
    print(manager.remember("user_preference", "喜欢喝拿铁"))
    print(manager.remember("deployment_server", "192.168.31.7"))
    
    # 测试 2: 回忆记忆
    print(f"\n回忆 project_name: {manager.recall('project_name')}")
    print(f"回忆不存在的键: {manager.recall('nonexistent')}")
    
    # 测试 3: 获取所有记忆
    print(f"\n所有记忆:\n{manager.get_all_memories()}")
    
    # 测试 4: 记忆数量
    print(f"\n当前记忆条目数: {manager.get_memory_count()}")
    
    # 清理测试文件
    os.remove("test_memory.json")
    print("\n✅ 测试完成")
