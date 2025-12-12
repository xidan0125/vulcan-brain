# mcp_tools/compute/sandbox.py
"""
代码执行沙箱模块 V2.2

V2.1: 递归函数支持
V2.2: extra_globals 支持工具函数注入
"""

import sys
import json
import traceback
from io import StringIO
from typing import Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# 允许导入的模块白名单
ALLOWED_MODULES = {
    'json', 'datetime', 'math', 'random', 'collections', 're', 
    'itertools', 'functools', 'statistics', 'time', 'decimal',
    'fractions', 'copy', 'operator', 'string', 'textwrap',
    'pandas', 'numpy', 'scipy'
}

# 禁止的模式
FORBIDDEN = ['os.system', 'subprocess', 'open(', 'shutil', 'socket', '__import__("os']

_executor = ThreadPoolExecutor(max_workers=2)


def _safe_import(name, globals_dict=None, locals_dict=None, fromlist=(), level=0):
    """受控导入函数 - 只允许白名单模块"""
    if name.split('.')[0] not in ALLOWED_MODULES:
        raise ImportError(f"Module '{name}' not in whitelist")
    return __builtins__['__import__'](name, globals_dict, locals_dict, fromlist, level)


def _security_check(code: str) -> Optional[str]:
    """安全检查"""
    code_lower = code.lower()
    for pattern in FORBIDDEN:
        if pattern.lower() in code_lower:
            return f'Forbidden operation: {pattern}'
    return None


def _create_safe_globals(extra_globals: Optional[Dict] = None) -> Dict[str, Any]:
    """创建安全的全局命名空间"""
    safe_builtins = {
        # 基础函数
        'print': print, 'len': len, 'range': range, 'enumerate': enumerate,
        'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted,
        'reversed': reversed, 'list': list, 'dict': dict, 'set': set,
        'tuple': tuple, 'str': str, 'int': int, 'float': float, 'bool': bool,
        'sum': sum, 'min': min, 'max': max, 'abs': abs, 'round': round,
        'any': any, 'all': all, 'isinstance': isinstance, 'type': type,
        'hasattr': hasattr, 'getattr': getattr, 'setattr': setattr,
        'callable': callable, 'repr': repr, 'hash': hash, 'id': id,
        'ord': ord, 'chr': chr, 'hex': hex, 'oct': oct, 'bin': bin,
        'pow': pow, 'divmod': divmod, 'complex': complex,
        'bytes': bytes, 'bytearray': bytearray, 'memoryview': memoryview,
        'frozenset': frozenset, 'slice': slice, 'object': object,
        'format': format, 'vars': vars, 'dir': dir,
        'iter': iter, 'next': next, 'input': lambda x='': '',
        'None': None, 'True': True, 'False': False,
        '__import__': _safe_import,
        '__name__': '__main__',
        '__doc__': None,
    }
    
    safe_globals = safe_builtins.copy()
    safe_globals['__builtins__'] = safe_builtins
    
    # 预导入常用模块
    try:
        import json as json_module
        import datetime as datetime_module
        import math as math_module
        import statistics as statistics_module
        import random as random_module
        import re as re_module
        import collections as collections_module
        import itertools as itertools_module
        import functools as functools_module
        
        safe_globals['json'] = json_module
        safe_globals['datetime'] = datetime_module
        safe_globals['math'] = math_module
        safe_globals['statistics'] = statistics_module
        safe_globals['random'] = random_module
        safe_globals['re'] = re_module
        safe_globals['collections'] = collections_module
        safe_globals['itertools'] = itertools_module
        safe_globals['functools'] = functools_module
    except ImportError:
        pass
    
    try:
        import pandas as pd
        import numpy as np
        safe_globals['pd'] = pd
        safe_globals['np'] = np
        safe_globals['pandas'] = pd
        safe_globals['numpy'] = np
    except ImportError:
        pass
    
    # 注入额外的全局变量（如工具函数）
    if extra_globals:
        safe_globals.update(extra_globals)
    
    return safe_globals


def _execute_sync(code: str, safe_globals: Dict) -> tuple:
    """同步执行代码 - 修复递归函数支持"""
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    
    result = None
    error = None
    
    try:
        compiled = compile(code, '<sandbox>', 'exec')
        exec(compiled, safe_globals)
        
        # 获取结果变量
        for var in ['result', 'output', 'data', 'answer']:
            if var in safe_globals and not callable(safe_globals[var]):
                result = safe_globals[var]
                break
    except Exception as e:
        error = f'{type(e).__name__}: {str(e)}'
    finally:
        sys.stdout = old_stdout
    
    return captured.getvalue(), result, error


def execute_code(
    code: str, 
    timeout: int = 30, 
    extra_globals: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    执行 Python 代码
    
    Args:
        code: Python 代码字符串
        timeout: 超时秒数
        extra_globals: 额外的全局变量（如工具函数）
    
    Returns:
        {success, output, result, error, execution_time_ms}
    """
    start = datetime.now()
    
    # 安全检查
    security_error = _security_check(code)
    if security_error:
        return {'success': False, 'output': '', 'result': None, 
                'error': security_error, 'execution_time_ms': 0}
    
    safe_globals = _create_safe_globals(extra_globals)
    
    try:
        future = _executor.submit(_execute_sync, code, safe_globals)
        stdout, result, error = future.result(timeout=timeout)
    except FuturesTimeoutError:
        return {'success': False, 'output': '', 'result': None,
                'error': f'Timeout: exceeded {timeout} seconds', 
                'execution_time_ms': timeout * 1000}
    except Exception as e:
        return {'success': False, 'output': '', 'result': None,
                'error': str(e), 
                'execution_time_ms': (datetime.now() - start).total_seconds() * 1000}
    
    exec_time = (datetime.now() - start).total_seconds() * 1000
    
    return {
        'success': error is None,
        'output': stdout[:10000],
        'result': result,
        'error': error,
        'execution_time_ms': exec_time
    }


def execute_code_safe(code: str, extra_globals: Optional[Dict] = None) -> str:
    """安全执行代码并返回结果字符串"""
    result = execute_code(code, extra_globals=extra_globals)
    
    if not result['success']:
        return f'Execution failed: {result["error"]}'
    
    output_parts = []
    if result['output']:
        output_parts.append(f'Output:\n{result["output"]}')
    if result['result'] is not None:
        output_parts.append(f'Result: {result["result"]}')
    
    return '\n'.join(output_parts) if output_parts else 'Executed successfully, no output'


# === 模块接口描述 ===
__module_info__ = {
    'name': 'sandbox',
    'category': 'compute',
    'description': '安全代码执行沙盒',
    'functions': [
        {'name': 'execute_code', 'desc': '执行 Python 代码并返回结果'},
        {'name': 'execute_code_safe', 'desc': '安全执行代码并返回结果字符串'},
    ]
}


if __name__ == '__main__':
    print('=== Test recursive function ===')
    code = '''
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

result = quicksort([5, 2, 8, 1, 9])
print("Sorted:", result)
'''
    result = execute_code(code)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print('\n=== Test with extra_globals ===')
    def my_tool(x):
        return x * 2
    
    code2 = '''
result = my_tool(21)
print("Result:", result)
'''
    result2 = execute_code(code2, extra_globals={'my_tool': my_tool})
    print(json.dumps(result2, ensure_ascii=False, indent=2))
