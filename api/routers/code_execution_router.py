"""
Vulcan Brain API - 代码执行路由
Sandbox API for Programmatic Tool Calling
"""
from typing import Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tools.code_executor import VulcanCodeSandbox
from api.routers.auth_router import get_current_user

router = APIRouter(tags=["Code Execution"])


# === Pydantic Models ===
class CodeExecutionRequest(BaseModel):
    """代码执行请求"""
    code: str
    timeout: int = 30


class CodeExecutionResponse(BaseModel):
    """代码执行响应"""
    success: bool
    output: str
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float


# === Sandbox 单例 ===
_sandbox_instance: Optional[VulcanCodeSandbox] = None


def get_sandbox() -> VulcanCodeSandbox:
    """获取 Sandbox 单例"""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = VulcanCodeSandbox(timeout_seconds=30)
    return _sandbox_instance


# === API Endpoints ===
@router.post('/api/execute', response_model=CodeExecutionResponse)
async def execute_code(request: CodeExecutionRequest, current_user: dict = Depends(get_current_user)):
    """
    Code Execution Sandbox API
    
    执行 Python 代码并返回结果。用于：
    - AI 生成代码后需要执行
    - 数据处理和批量计算
    - 避免大量数据进入 LLM Context Window
    
    安全限制：
    - 禁止 os.system, subprocess
    - 禁止文件写入
    - 默认 30 秒超时
    """
    try:
        sandbox = get_sandbox()
        
        # 如果请求指定了不同的超时时间，创建新的 sandbox
        if request.timeout != 30:
            sandbox = VulcanCodeSandbox(timeout_seconds=request.timeout)
        
        result = await sandbox.execute_async(request.code)
        
        return CodeExecutionResponse(
            success=result.success,
            output=result.output,
            result=result.result,
            error=result.error,
            execution_time_ms=result.execution_time_ms
        )
    except Exception as e:
        return CodeExecutionResponse(
            success=False,
            output="",
            result=None,
            error=str(e),
            execution_time_ms=0
        )
