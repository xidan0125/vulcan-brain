# vulcan_libs/alignment.py
"""
Vulcan Brain - 动态对齐系统 (Dynamic Alignment System)

这是 Vulcan 的"成长记录"，记录 Boss 的具体教导和纠正
灵感来源: RLHF (Reinforcement Learning from Human Feedback)

核心机制:
1. 每次 Boss 纠正/表扬时，记录到 alignment_memory.json
2. 下次遇到类似场景，自动引用历史教训
3. 定期反思，提炼核心原则
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import yaml


# 默认文件路径
DEFAULT_ALIGNMENT_FILE = "alignment_memory.json"
DEFAULT_CONSTITUTION_FILE = "boss_constitution.yaml"


class AlignmentManager:
    """动态对齐记忆管理器"""
    
    def __init__(
        self, 
        alignment_file: str = DEFAULT_ALIGNMENT_FILE,
        constitution_file: str = DEFAULT_CONSTITUTION_FILE
    ):
        self.alignment_file = alignment_file
        self.constitution_file = constitution_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """确保记忆文件存在"""
        if not os.path.exists(self.alignment_file):
            self._save([])
    
    def _load(self) -> List[Dict]:
        """加载对齐记忆"""
        try:
            with open(self.alignment_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save(self, data: List[Dict]):
        """保存对齐记忆"""
        with open(self.alignment_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_constitution(self) -> str:
        """
        加载静态宪法（Boss 的核心价值观）
        
        Returns:
            格式化的宪法文本（用于 System Prompt 注入）
        """
        if not os.path.exists(self.constitution_file):
            return "【宪法文件缺失】"
        
        try:
            with open(self.constitution_file, 'r', encoding='utf-8') as f:
                constitution = yaml.safe_load(f)
            
            # 提炼核心原则
            lines = ["【Vulcan 宪法 - 核心价值观】"]
            
            # 核心价值观
            if 'core_values' in constitution:
                for value in constitution['core_values']:
                    lines.append(f"\n{value['name']}: {value['description']}")
                    for principle in value['principles'][:2]:  # 只取前两条，避免过长
                        lines.append(f"  • {principle}")
            
            # 禁止行为
            if 'prohibited_actions' in constitution:
                lines.append("\n【禁止行为】")
                for action in constitution['prohibited_actions'][:3]:  # 取前三条
                    lines.append(f"  ✗ {action}")
            
            return "\n".join(lines)
        
        except Exception as e:
            return f"【宪法加载失败】{str(e)}"
    
    def record_feedback(
        self, 
        category: str,
        situation: str,
        boss_feedback: str,
        lesson_learned: str,
        importance: int = 3
    ) -> str:
        """
        记录 Boss 的反馈/纠正
        
        Args:
            category: 分类（如 "问题处理", "代码实现", "架构决策"）
            situation: 场景描述
            boss_feedback: Boss 的原话
            lesson_learned: 提炼的教训（1-2 句话）
            importance: 重要性（1-5，5 最重要）
        
        Returns:
            确认信息
        """
        data = self._load()
        
        entry = {
            "id": len(data) + 1,
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "situation": situation,
            "boss_feedback": boss_feedback,
            "lesson_learned": lesson_learned,
            "importance": importance,
            "referenced_count": 0  # 记录被引用次数
        }
        
        data.append(entry)
        self._save(data)
        
        return f"✅ 已记录 Boss 反馈（ID: {entry['id']}）- {lesson_learned}"
    
    def get_relevant_lessons(
        self, 
        category: Optional[str] = None,
        top_k: int = 3
    ) -> str:
        """
        获取相关教训（用于 System Prompt 注入）
        
        Args:
            category: 筛选分类（如果为 None，返回全部重要教训）
            top_k: 返回数量
        
        Returns:
            格式化的教训文本
        """
        data = self._load()
        
        if not data:
            return "【暂无历史教训】"
        
        # 筛选分类
        if category:
            filtered = [d for d in data if d['category'] == category]
        else:
            filtered = data
        
        # 按重要性排序
        sorted_data = sorted(filtered, key=lambda x: x['importance'], reverse=True)
        
        # 取前 K 条
        top_lessons = sorted_data[:top_k]
        
        # 格式化输出
        lines = ["【Boss 历史教训】"]
        for lesson in top_lessons:
            lines.append(f"\n[{lesson['category']}] {lesson['lesson_learned']}")
            lines.append(f"  场景: {lesson['situation']}")
            lines.append(f"  Boss: \"{lesson['boss_feedback']}\"")
        
        return "\n".join(lines)
    
    def mark_referenced(self, lesson_id: int):
        """标记某条教训被引用（用于统计学习效果）"""
        data = self._load()
        for entry in data:
            if entry['id'] == lesson_id:
                entry['referenced_count'] += 1
                self._save(data)
                break
    
    def get_alignment_summary(self) -> str:
        """获取对齐记忆摘要"""
        data = self._load()
        
        if not data:
            return "暂无对齐记忆"
        
        total = len(data)
        categories = {}
        for entry in data:
            cat = entry['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        summary = [f"总记录数: {total}"]
        summary.append("分类分布:")
        for cat, count in categories.items():
            summary.append(f"  - {cat}: {count} 条")
        
        return "\n".join(summary)


# === 便捷函数接口 ===

_default_manager = None

def get_alignment_manager() -> AlignmentManager:
    """获取全局对齐管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = AlignmentManager()
    return _default_manager


def load_constitution() -> str:
    """加载宪法"""
    return get_alignment_manager().load_constitution()


def record_feedback(
    category: str,
    situation: str,
    boss_feedback: str,
    lesson_learned: str,
    importance: int = 3
) -> str:
    """记录 Boss 反馈"""
    return get_alignment_manager().record_feedback(
        category, situation, boss_feedback, lesson_learned, importance
    )


def get_relevant_lessons(category: Optional[str] = None, top_k: int = 3) -> str:
    """获取相关教训"""
    return get_alignment_manager().get_relevant_lessons(category, top_k)


def get_alignment_summary() -> str:
    """获取摘要"""
    return get_alignment_manager().get_alignment_summary()


# === 测试代码 ===
if __name__ == "__main__":
    print("=== Vulcan Alignment System 测试 ===\n")
    
    manager = AlignmentManager(
        alignment_file="test_alignment.json",
        constitution_file="boss_constitution.yaml"
    )
    
    # 测试 1: 加载宪法
    print("--- 测试 1: 加载宪法 ---")
    constitution = manager.load_constitution()
    print(constitution)
    
    # 测试 2: 记录反馈
    print("\n--- 测试 2: 记录 Boss 反馈 ---")
    print(manager.record_feedback(
        category="问题处理",
        situation="遇到 API 错误时创建了简化版本",
        boss_feedback="为啥要创建简单版本 架构师对你进行了严厉批评 有问题就上报问题就可以了",
        lesson_learned="遇到问题直接上报，不要擅自创建简化版本",
        importance=5
    ))
    
    print(manager.record_feedback(
        category="代码实现",
        situation="选择框架 vs 自研",
        boss_feedback="CodeAct 范式 + 原生 while 循环是唯一解",
        lesson_learned="优先自研极简内核，框架只用于工具封装",
        importance=4
    ))
    
    # 测试 3: 获取教训
    print("\n--- 测试 3: 获取历史教训 ---")
    lessons = manager.get_relevant_lessons()
    print(lessons)
    
    # 测试 4: 摘要
    print("\n--- 测试 4: 对齐记忆摘要 ---")
    print(manager.get_alignment_summary())
    
    # 清理测试文件
    if os.path.exists("test_alignment.json"):
        os.remove("test_alignment.json")
    
    print("\n✅ 测试完成")
