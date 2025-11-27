# tools/memory_tools.py
"""
Vulcan Brain - Memory Tools (记忆工具)

将 vulcan_libs.memory 封装为 LlamaIndex FunctionTool
供 Qwen3 通过 CodeAct 调用
"""

from llama_index.core.tools import FunctionTool
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vulcan_libs.memory import remember as _remember, recall as _recall, forget as _forget


def remember_info(key: str, value: str) -> str:
    """
    记住重要信息（存入长期记忆）
    
    Args:
        key: 记忆键（如 "user_name", "project_name", "preference"）
        value: 记忆内容
    
    Returns:
        确认信息
    
    Examples:
        remember_info("user_name", "张三")
        remember_info("favorite_drink", "拿铁咖啡")
    """
    return _remember(key, value)


def recall_info(key: str) -> str:
    """
    回忆之前记住的信息
    
    Args:
        key: 记忆键
    
    Returns:
        记忆内容，如果不存在则返回提示
    
    Examples:
        recall_info("user_name")
        recall_info("project_name")
    """
    return _recall(key)


def forget_info(key: str) -> str:
    """
    忘记某条信息（删除记忆）
    
    Args:
        key: 要删除的记忆键
    
    Returns:
        确认信息
    
    Examples:
        forget_info("old_preference")
    """
    return _forget(key)


# === 创建 LlamaIndex Tool ===

remember_tool = FunctionTool.from_defaults(
    fn=remember_info,
    name="remember_info",
    description="""记住重要信息（存入长期记忆）。
当用户说"记住XXX"、"我喜欢XXX"、"我的名字是XXX"时，调用此工具。
参数: key (记忆键), value (记忆内容)
"""
)

recall_tool = FunctionTool.from_defaults(
    fn=recall_info,
    name="recall_info",
    description="""回忆之前记住的信息。
当用户问"你还记得XXX吗？"、"我之前说过什么？"时，调用此工具。
参数: key (记忆键)
"""
)

forget_tool = FunctionTool.from_defaults(
    fn=forget_info,
    name="forget_info",
    description="""忘记某条信息（删除记忆）。
当用户说"忘了XXX"、"删除XXX记忆"时，调用此工具。
参数: key (要删除的记忆键)
"""
)


# === 导出 ===
__all__ = ['remember_tool', 'recall_tool', 'forget_tool']


# === 测试代码 ===
if __name__ == "__main__":
    print("=== Memory Tools 测试 ===\n")
    
    # 测试记住
    print(remember_info("test_key", "test_value"))
    
    # 测试回忆
    print(recall_info("test_key"))
    print(recall_info("nonexistent"))
    
    # 测试忘记
    print(forget_info("test_key"))
    print(recall_info("test_key"))  # 应该提示不存在
    
    print("\n✅ 测试完成")
