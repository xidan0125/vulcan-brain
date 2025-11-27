# mcp_tools/compute/__init__.py
"""
计算模块

包含:
- sandbox: 安全代码执行沙箱
"""

from .sandbox import execute_code, execute_code_safe

__all__ = ['execute_code', 'execute_code_safe']
