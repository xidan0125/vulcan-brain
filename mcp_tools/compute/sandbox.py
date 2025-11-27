# mcp_tools/compute/sandbox.py
"""
代码执行沙箱模块

接口:
- execute_code(code: str) -> dict: 执行 Python 代码
- execute_code_safe(code: str) -> str: 安全执行并返回结果字符串

安全限制:
- 禁止 os.system, subprocess
- 禁止文件写入
- 30 秒超时
"""

import sys
import json
import traceback
from io import StringIO
from typing import Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# 安全的内置函数
SAFE_BUILTINS = {
    'print': print, 'len': len, 'range': range, 'enumerate': enumerate,
    'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted,
    'reversed': reversed, 'list': list, 'dict': dict, 'set': set,
    'tuple': tuple, 'str': str, 'int': int, 'float': float, 'bool': bool,
    'sum': sum, 'min': min, 'max': max, 'abs': abs, 'round': round,
    'any': any, 'all': all, 'isinstance': isinstance, 'type': type,
    'hasattr': hasattr, 'getattr': getattr, 'setattr': setattr,
    'None': None, 'True': True, 'False': False,
}

# 允许导入的模块
ALLOWED_MODULES = {'json', 'datetime', 'math', 'random', 'collections', 're', 
                   'itertools', 'functools', 'statistics', 'time', 'pandas', 'numpy'}

# 禁止的模式
FORBIDDEN = ['os.system', 'subprocess', 'eval(', 'exec(', 'open(', 'shutil', 'socket']

_executor = ThreadPoolExecutor(max_workers=2)


def _security_check(code: str) -> Optional[str]:
    """安全检查"""
    code_lower = code.lower()
    for pattern in FORBIDDEN:
        if pattern.lower() in code_lower:
            return f'禁止的操作: {pattern}'
    return None


def _create_safe_globals() -> Dict[str, Any]:
    """创建安全的全局命名空间"""
    safe_globals = SAFE_BUILTINS.copy()
    safe_globals['__builtins__'] = SAFE_BUILTINS
    
    # 预导入常用模块
    try:
        import json as json_module
        import datetime as datetime_module
        import math as math_module
        safe_globals['json'] = json_module
        safe_globals['datetime'] = datetime_module
        safe_globals['math'] = math_module
    except ImportError:
        pass
    
    try:
        import pandas as pd
        import numpy as np
        safe_globals['pd'] = pd
        safe_globals['np'] = np
    except ImportError:
        pass
    
    return safe_globals


def _execute_sync(code: str, safe_globals: Dict) -> tuple:
    """同步执行代码"""
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    
    result = None
    error = None
    
    try:
        compiled = compile(code, '<sandbox>', 'exec')
        local_ns = {}
        exec(compiled, safe_globals, local_ns)
        
        # 获取结果变量
        for var in ['result', 'output', 'data', 'answer']:
            if var in local_ns:
                result = local_ns[var]
                break
        
        if result is None and local_ns:
            for name, value in reversed(list(local_ns.items())):
                if not name.startswith('_'):
                    result = value
                    break
    except Exception as e:
        error = f'{type(e).__name__}: {str(e)}'
    finally:
        sys.stdout = old_stdout
    
    return captured.getvalue(), result, error


def execute_code(code: str, timeout: int = 30) -> Dict[str, Any]:
    """
    执行 Python 代码
    
    Args:
        code: Python 代码字符串
        timeout: 超时秒数
    
    Returns:
        {success, output, result, error, execution_time_ms}
    """
    start = datetime.now()
    
    # 安全检查
    security_error = _security_check(code)
    if security_error:
        return {'success': False, 'output': '', 'result': None, 
                'error': security_error, 'execution_time_ms': 0}
    
    safe_globals = _create_safe_globals()
    
    try:
        future = _executor.submit(_execute_sync, code, safe_globals)
        stdout, result, error = future.result(timeout=timeout)
    except FuturesTimeoutError:
        return {'success': False, 'output': '', 'result': None,
                'error': f'执行超时: 超过 {timeout} 秒', 
                'execution_time_ms': timeout * 1000}
    except Exception as e:
        return {'success': False, 'output': '', 'result': None,
                'error': str(e), 
                'execution_time_ms': (datetime.now() - start).total_seconds() * 1000}
    
    exec_time = (datetime.now() - start).total_seconds() * 1000
    
    return {
        'success': error is None,
        'output': stdout[:10000],  # 截断过长输出
        'result': result,
        'error': error,
        'execution_time_ms': exec_time
    }


def execute_code_safe(code: str) -> str:
    """
    安全执行代码并返回结果字符串
    
    用于简单场景，直接返回可读结果
    """
    result = execute_code(code)
    
    if not result['success']:
        return f'执行失败: {result["error"]}'
    
    output_parts = []
    if result['output']:
        output_parts.append(f'输出:\n{result["output"]}')
    if result['result'] is not None:
        output_parts.append(f'结果: {result["result"]}')
    
    return '\n'.join(output_parts) if output_parts else '执行成功，无输出'


__module_info__ = {
    'name': 'sandbox',
    'category': 'compute',
    'description': '安全代码执行沙箱',
    'functions': [
        {'name': 'execute_code', 'desc': '执行代码，返回详细结果字典', 'params': ['code: str', 'timeout: int = 30']},
        {'name': 'execute_code_safe', 'desc': '执行代码，返回简单结果字符串', 'params': ['code: str']},
    ]
}


if __name__ == '__main__':
    # 测试
    print('=== 测试代码执行 ===')
    result = execute_code('result = sum([1,2,3,4,5])')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print('\n=== 测试安全检查 ===')
    result = execute_code('import os; os.system("ls")')
    print(json.dumps(result, ensure_ascii=False, indent=2))
