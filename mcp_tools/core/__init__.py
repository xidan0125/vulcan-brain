# mcp_tools/core/__init__.py
"""
核心工具模块 - 始终加载

包含:
- time: 时间日期查询
- memory: 长期记忆管理
- web_search: 联网搜索
- code_exec: 代码执行
"""

from .time import get_current_time, get_current_date, get_datetime_info
from .memory import remember, recall, forget, list_memories
from .web_search import web_search
from .code_exec import run_python, execute_code, execute_code_safe

__all__ = [
    # 时间
    'get_current_time', 
    'get_current_date',
    'get_datetime_info',
    # 记忆
    'remember', 
    'recall', 
    'forget', 
    'list_memories',
    # 搜索
    'web_search',
    # 代码执行
    'run_python',
    'execute_code',
    'execute_code_safe'
]
