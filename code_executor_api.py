"""
Code Executor API - 在Docker沙箱中安全执行Python代码
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any
import subprocess
import tempfile
import base64
import json
import os
import re

router = APIRouter(prefix="/api/code-exec", tags=["code-executor"])

# Docker镜像名
SANDBOX_IMAGE = "vulcan-code-sandbox"

class CodeRequest(BaseModel):
    code: str
    data: Optional[List[Any]] = None  # KuzuDB查询结果
    columns: Optional[List[str]] = None  # 列名 (从Cypher RETURN提取)
    timeout: int = 60  # 超时秒数

class CodeResult(BaseModel):
    success: bool
    image_base64: Optional[str] = None
    chart_html: Optional[str] = None  # 交互式Plotly HTML
    output: Optional[str] = None
    error: Optional[str] = None


def build_full_code(user_code: str, data: Optional[List[Any]] = None, columns: Optional[List[str]] = None) -> str:
    """构建完整的可执行代码，注入数据和图表保存逻辑

    Args:
        user_code: LLM生成的Python代码
        data: KuzuDB查询结果 (嵌套列表)
        columns: 列名列表 (从Cypher RETURN提取)
    """

    setup_code = '''
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import json
import base64
from io import BytesIO

# Plotly 支持
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
pio.kaleido.scope.default_format = "png"

# 中文支持
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
'''

    # 注入数据 - 带列名和边缘处理
    columns_json = json.dumps(columns, ensure_ascii=False) if columns else "None"
    data_json = json.dumps(data, ensure_ascii=False, default=str).replace("null", "None") if data else "[]"

    setup_code += f'''
# 注入数据
_raw_data = {data_json}
_columns = {columns_json}

# 边缘情况: 空数据
if not _raw_data:
    df = pd.DataFrame()
    print("警告: 数据为空，无法生成图表")
# 智能转换为DataFrame (带列名!)
elif isinstance(_raw_data[0], (list, tuple)):
    if _columns and len(_columns) == len(_raw_data[0]):
        df = pd.DataFrame(_raw_data, columns=_columns)
        print(f"数据加载完成: {{len(df)}} 行, 列名: {{list(df.columns)}}")
    else:
        df = pd.DataFrame(_raw_data)
        print(f"数据加载完成: {{len(df)}} 行 (列名数量不匹配, 使用索引0,1,2...)")
else:
    df = pd.DataFrame(_raw_data)
    print(f"数据加载完成: {{len(df)}} 行")

# 数据清洗: 处理NULL值
df = df.fillna("未知")  # 将NULL替换为"未知"
'''

    # 图表保存逻辑 - 优先HTML交互式
    save_code = '''

# 自动保存图表 (优先交互式HTML)
import os

# 方法1: Plotly HTML (交互式)
if os.path.exists('/tmp/chart.html'):
    with open('/tmp/chart.html', 'r', encoding='utf-8') as f:
        print("__CHART_HTML__" + f.read())
# 方法2: Plotly PNG (静态备选)
elif os.path.exists('/tmp/chart.png'):
    with open('/tmp/chart.png', 'rb') as f:
        print("__CHART_BASE64__" + base64.b64encode(f.read()).decode())
else:
    # 方法3: Matplotlib图表
    _fig = plt.gcf()
    if _fig.get_axes():
        _buf = BytesIO()
        plt.savefig(_buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        _buf.seek(0)
        print("__CHART_BASE64__" + base64.b64encode(_buf.read()).decode())
        plt.close()
'''

    return setup_code + "\n" + user_code + "\n" + save_code


@router.post("/execute", response_model=CodeResult)
async def execute_code(request: CodeRequest):
    """
    在Docker沙箱中执行Python代码

    安全措施:
    - 网络隔离 (--network none)
    - 内存限制 (512MB)
    - CPU限制 (1核)
    - 执行超时 (默认15秒)
    - 只读挂载代码文件
    """

    # 1. 构建完整代码 (带列名)
    full_code = build_full_code(request.code, request.data, request.columns)

    # 2. 写入临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(full_code)
        script_path = f.name

    try:
        # 3. Docker执行
        result = subprocess.run([
            'docker', 'run', '--rm',
            '--network', 'none',           # 禁止网络访问
            '--memory', '512m',            # 内存限制
            '--cpus', '1',                 # CPU限制
            '--read-only',                 # 只读文件系统
            '--tmpfs', '/tmp:size=64m',    # 临时目录
            '-v', f'{script_path}:/tmp/script.py:ro',
            SANDBOX_IMAGE,
            'python3', '/tmp/script.py'
        ], capture_output=True, text=True, timeout=request.timeout)

        stdout = result.stdout
        stderr = result.stderr

        # 4. 解析输出
        # 优先检查交互式HTML
        if '__CHART_HTML__' in stdout:
            parts = stdout.split('__CHART_HTML__')
            output_text = parts[0].strip()
            html_content = parts[1]
            return CodeResult(
                success=True,
                chart_html=html_content,
                output=output_text if output_text else None
            )

        # 其次检查静态PNG
        if '__CHART_BASE64__' in stdout:
            parts = stdout.split('__CHART_BASE64__')
            output_text = parts[0].strip()
            img_b64 = parts[1].strip()
            return CodeResult(
                success=True,
                image_base64=img_b64,
                output=output_text if output_text else None
            )

        # 没有图表但执行成功
        if result.returncode == 0:
            return CodeResult(success=True, output=stdout[:2000] if stdout else None)

        # 执行失败
        error_msg = stderr[:1000] if stderr else "Unknown error"
        return CodeResult(success=False, error=error_msg)

    except subprocess.TimeoutExpired:
        return CodeResult(success=False, error=f"代码执行超时({request.timeout}秒)")
    except FileNotFoundError:
        return CodeResult(success=False, error="Docker未安装或vulcan-code-sandbox镜像不存在")
    except Exception as e:
        return CodeResult(success=False, error=str(e)[:500])
    finally:
        # 清理临时文件
        try:
            os.unlink(script_path)
        except:
            pass


@router.get("/health")
async def health_check():
    """检查Docker沙箱是否可用"""
    try:
        result = subprocess.run(
            ['docker', 'images', '-q', SANDBOX_IMAGE],
            capture_output=True, text=True, timeout=5
        )
        image_exists = bool(result.stdout.strip())
        return {
            "status": "ok" if image_exists else "image_missing",
            "image": SANDBOX_IMAGE,
            "image_exists": image_exists
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
