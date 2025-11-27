# code_executor.py - Vulcan Brain Code Execution Sandbox
"""
Code Execution Sandbox for Vulcan Brain V3

核心功能：
1. 安全执行 AI 生成的 Python 代码
2. 超时保护（防止无限循环）
3. 输出捕获（stdout + 返回值）
4. 沙箱限制（禁止危险操作）

使用场景：
- AI 需要处理大量数据时，生成代码来批处理
- 避免将原始数据塞入 Context Window
- 只返回精炼结果给 AI

架构思想来源：Anthropic "Programmatic Tool Calling"
"""

import sys
import json
import traceback
import asyncio
from io import StringIO
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import threading

# 预装安全库（AI 代码可以使用这些）
SAFE_BUILTINS = {
    'print': print,
    'len': len,
    'range': range,
    'enumerate': enumerate,
    'zip': zip,
    'map': map,
    'filter': filter,
    'sorted': sorted,
    'reversed': reversed,
    'list': list,
    'dict': dict,
    'set': set,
    'tuple': tuple,
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'sum': sum,
    'min': min,
    'max': max,
    'abs': abs,
    'round': round,
    'any': any,
    'all': all,
    'isinstance': isinstance,
    'type': type,
    'hasattr': hasattr,
    'getattr': getattr,
    'setattr': setattr,
    'None': None,
    'True': True,
    'False': False,
    '__import__': __import__,  # 受限导入
}

# 允许导入的模块白名单
ALLOWED_MODULES = {
    'json',
    'datetime',
    'math',
    'random',
    'collections',
    're',
    'itertools',
    'functools',
    'statistics',
    'time',
    'pandas',
    'numpy',
    'requests',  # HTTP 请求（用于 API 调用）
}

# 禁止的关键字/模式（安全检查）
FORBIDDEN_PATTERNS = [
    'os.system',
    'subprocess',
    'eval(',
    'exec(',
    '__import__("os")',
    '__import__("subprocess")',
    'open(',  # 禁止文件写入（可选择性放开读取）
    'shutil',
    'pathlib',
    'socket',
    'asyncio.subprocess',
    'multiprocessing',
]


class CodeExecutionResult:
    """代码执行结果"""
    def __init__(
        self,
        success: bool,
        output: str = "",
        result: Any = None,
        error: Optional[str] = None,
        execution_time_ms: float = 0
    ):
        self.success = success
        self.output = output  # stdout 输出
        self.result = result  # 最后一个表达式的值
        self.error = error
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class SecureImporter:
    """安全的模块导入器"""

    def __init__(self, allowed_modules: set):
        self.allowed_modules = allowed_modules
        self._cache = {}

    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        # 检查是否在白名单中
        base_module = name.split('.')[0]
        if base_module not in self.allowed_modules:
            raise ImportError(f"Module '{name}' is not allowed in sandbox")

        # 使用缓存
        if name in self._cache:
            return self._cache[name]

        # 动态导入
        module = __import__(name, globals, locals, fromlist, level)
        self._cache[name] = module
        return module


class VulcanCodeSandbox:
    """
    Vulcan Brain 代码执行沙箱

    特性：
    - 超时保护（默认30秒）
    - 安全的内置函数
    - 模块白名单
    - 禁止危险操作
    - 输出捕获
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_output_length: int = 10000,
        allowed_modules: Optional[set] = None
    ):
        self.timeout_seconds = timeout_seconds
        self.max_output_length = max_output_length
        self.allowed_modules = allowed_modules or ALLOWED_MODULES
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _security_check(self, code: str) -> Optional[str]:
        """
        静态安全检查

        Returns:
            None if safe, error message if dangerous
        """
        code_lower = code.lower()

        for pattern in FORBIDDEN_PATTERNS:
            if pattern.lower() in code_lower:
                return f"Forbidden pattern detected: '{pattern}'"

        # 检查危险的 dunder 方法
        dangerous_dunders = ['__class__', '__bases__', '__subclasses__', '__mro__']
        for dunder in dangerous_dunders:
            if dunder in code:
                return f"Dangerous dunder access: '{dunder}'"

        return None

    def _create_safe_globals(self) -> Dict[str, Any]:
        """创建安全的全局命名空间"""
        safe_globals = SAFE_BUILTINS.copy()

        # 添加安全的 import
        safe_globals['__builtins__'] = SAFE_BUILTINS
        safe_globals['__import__'] = SecureImporter(self.allowed_modules)

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

        # 尝试导入数据处理库
        try:
            import pandas as pd
            safe_globals['pd'] = pd
            safe_globals['pandas'] = pd
        except ImportError:
            pass

        try:
            import numpy as np
            safe_globals['np'] = np
            safe_globals['numpy'] = np
        except ImportError:
            pass

        try:
            import requests
            safe_globals['requests'] = requests
        except ImportError:
            pass

        return safe_globals

    def _execute_code_sync(self, code: str, safe_globals: Dict) -> Tuple[str, Any, Optional[str]]:
        """
        同步执行代码（在线程中运行）

        Returns:
            (stdout_output, result, error)
        """
        # 捕获 stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        result = None
        error = None

        try:
            # 编译代码
            compiled = compile(code, '<sandbox>', 'exec')

            # 创建本地命名空间
            local_ns = {}

            # 执行代码
            exec(compiled, safe_globals, local_ns)

            # 尝试获取结果变量（约定：result 或 output 或 data）
            for var_name in ['result', 'output', 'data', 'answer']:
                if var_name in local_ns:
                    result = local_ns[var_name]
                    break

            # 如果没有约定变量，尝试获取最后一个赋值
            if result is None and local_ns:
                # 获取最后一个非下划线变量
                for name, value in reversed(list(local_ns.items())):
                    if not name.startswith('_'):
                        result = value
                        break

        except Exception as e:
            error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout

        stdout_content = captured_output.getvalue()
        return stdout_content, result, error

    def execute(self, code: str) -> CodeExecutionResult:
        """
        执行代码（带超时保护）

        Args:
            code: Python 代码字符串

        Returns:
            CodeExecutionResult
        """
        start_time = datetime.now()

        # 1. 安全检查
        security_error = self._security_check(code)
        if security_error:
            return CodeExecutionResult(
                success=False,
                error=f"Security violation: {security_error}",
                execution_time_ms=0
            )

        # 2. 创建安全环境
        safe_globals = self._create_safe_globals()

        # 3. 带超时执行
        try:
            future = self._executor.submit(
                self._execute_code_sync, code, safe_globals
            )
            stdout_output, result, error = future.result(timeout=self.timeout_seconds)

        except FuturesTimeoutError:
            return CodeExecutionResult(
                success=False,
                error=f"Execution timeout: exceeded {self.timeout_seconds} seconds",
                execution_time_ms=self.timeout_seconds * 1000
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

        # 4. 计算执行时间
        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # 5. 截断过长输出
        if len(stdout_output) > self.max_output_length:
            stdout_output = stdout_output[:self.max_output_length] + "\n... [OUTPUT TRUNCATED]"

        # 6. 返回结果
        return CodeExecutionResult(
            success=error is None,
            output=stdout_output,
            result=result,
            error=error,
            execution_time_ms=execution_time_ms
        )

    async def execute_async(self, code: str) -> CodeExecutionResult:
        """异步执行接口"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, code)


# ==================== LlamaIndex Tool 封装 ====================

def create_code_execution_tool():
    """
    创建 LlamaIndex 格式的代码执行工具

    用法示例（AI 生成的代码）：
    ```python
    # 查询飞书考勤数据并筛选迟到人员
    import requests
    import json

    # 模拟 API 调用
    attendance_data = [
        {"name": "张三", "late_count": 3},
        {"name": "李四", "late_count": 0},
        {"name": "王五", "late_count": 2},
    ]

    # 筛选迟到的人
    result = [p["name"] for p in attendance_data if p["late_count"] > 0]
    print(json.dumps(result))
    ```
    """
    from llama_index.core.tools import FunctionTool

    sandbox = VulcanCodeSandbox(timeout_seconds=30)

    def execute_python_code(code: str) -> str:
        """
        在安全沙箱中执行 Python 代码。

        使用场景：
        - 需要处理大量数据（如查询结果）时
        - 需要进行计算、筛选、聚合操作时
        - 需要调用外部 API 并处理响应时

        注意：
        - 最终结果应该赋值给 `result` 变量或使用 print() 输出
        - 可以使用: json, datetime, pandas (pd), numpy (np), requests
        - 禁止: 文件操作、系统命令、subprocess

        示例：
        ```
        import json
        data = [{"name": "A", "score": 80}, {"name": "B", "score": 90}]
        result = [d["name"] for d in data if d["score"] > 85]
        ```

        Args:
            code: 要执行的 Python 代码

        Returns:
            执行结果的 JSON 字符串，包含 output 和 result
        """
        exec_result = sandbox.execute(code)
        return exec_result.to_json()

    return FunctionTool.from_defaults(
        fn=execute_python_code,
        name="execute_python_code",
        description="""在安全沙箱中执行 Python 代码。用于处理大量数据、进行计算和筛选。

使用规则：
1. 最终结果赋值给 `result` 变量
2. 可用库: json, datetime, math, pandas (pd), numpy (np), requests
3. 禁止: 文件操作、系统命令

示例 - 筛选迟到员工:
```python
data = [{"name": "张三", "late": 3}, {"name": "李四", "late": 0}]
result = [d["name"] for d in data if d["late"] > 0]
```"""
    )


# ==================== 测试代码 ====================

if __name__ == "__main__":
    sandbox = VulcanCodeSandbox()

    # 测试 1: 基本计算
    print("=== Test 1: Basic Calculation ===")
    result = sandbox.execute("""
import math
result = math.sqrt(144) + 10
print(f"Square root of 144 is {math.sqrt(144)}")
    """)
    print(result.to_json())

    # 测试 2: 数据处理
    print("\n=== Test 2: Data Processing ===")
    result = sandbox.execute("""
import json
data = [
    {"name": "张三", "late_count": 3, "dept": "技术部"},
    {"name": "李四", "late_count": 0, "dept": "产品部"},
    {"name": "王五", "late_count": 2, "dept": "技术部"},
    {"name": "赵六", "late_count": 5, "dept": "运营部"},
]

# 筛选迟到超过2次的人
result = [
    {"name": p["name"], "late": p["late_count"]}
    for p in data
    if p["late_count"] > 2
]
print(json.dumps(result, ensure_ascii=False))
    """)
    print(result.to_json())

    # 测试 3: 安全检查（应该失败）
    print("\n=== Test 3: Security Check ===")
    result = sandbox.execute("""
import os
os.system('ls -la')
    """)
    print(result.to_json())

    # 测试 4: 超时测试
    print("\n=== Test 4: Timeout Test ===")
    sandbox_short = VulcanCodeSandbox(timeout_seconds=2)
    result = sandbox_short.execute("""
import time
time.sleep(10)
result = "done"
    """)
    print(result.to_json())

    print("\n=== All tests completed ===")
