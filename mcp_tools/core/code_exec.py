# mcp_tools/core/code_exec.py
"""
代码执行工具 - 核心工具包装器
从 compute/sandbox 导入，确保始终可用
"""

from mcp_tools.compute.sandbox import execute_code, execute_code_safe


def run_python(code: str, timeout: int = 30) -> str:
    """
    执行 Python 代码
    
    Args:
        code: Python 代码字符串
        timeout: 超时秒数 (默认30)
    
    Returns:
        执行结果字符串
    
    Examples:
        >>> run_python("print(1 + 1)")
        'Output:\n2\n'
        >>> run_python("result = sum(range(101))")
        'Result: 5050'
    """
    result = execute_code(code, timeout=timeout)
    
    if not result['success']:
        return f'执行失败: {result["error"]}'
    
    output_parts = []
    if result['output']:
        output_parts.append(f'Output:\n{result["output"]}')
    if result['result'] is not None:
        output_parts.append(f'Result: {result["result"]}')
    
    return '\n'.join(output_parts) if output_parts else '执行成功，无输出'


# 导出
__all__ = ['run_python', 'execute_code', 'execute_code_safe']
