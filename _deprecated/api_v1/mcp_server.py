# mcp_server.py - Vulcan Brain MCP Server Endpoints
"""
MCP (Model Context Protocol) 服务端

让外部 AI 系统可以连接 Vulcan Brain 的工具

实现 MCP JSON-RPC 2.0 协议:
- initialize: 握手
- tools/list: 列出工具
- tools/call: 调用工具
- resources/list: 列出资源
- resources/read: 读取资源
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Request
from pydantic import BaseModel

# MCP 工具目录
MCP_TOOLS_PATH = os.path.expanduser('~/vulcan_brain_v2/mcp_tools')

router = APIRouter()


# === Pydantic Models ===

class MCPRequest(BaseModel):
    """MCP JSON-RPC 请求"""
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Optional[Dict] = None


class MCPResponse(BaseModel):
    """MCP JSON-RPC 响应"""
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Dict] = None
    error: Optional[Dict] = None


# === 工具注册表 ===

def _discover_tools() -> List[Dict]:
    """发现所有可用工具（通过动态导入模块）"""
    tools = []

    if not os.path.exists(MCP_TOOLS_PATH):
        return tools

    # 确保 mcp_tools 可以被导入
    import sys
    parent_path = os.path.dirname(MCP_TOOLS_PATH)
    if parent_path not in sys.path:
        sys.path.insert(0, parent_path)

    for category in os.listdir(MCP_TOOLS_PATH):
        cat_path = os.path.join(MCP_TOOLS_PATH, category)
        if not os.path.isdir(cat_path) or category.startswith('_'):
            continue

        for file in os.listdir(cat_path):
            if not file.endswith('.py') or file.startswith('_'):
                continue

            module_name = file[:-3]

            try:
                # 动态导入模块获取 __module_info__
                import importlib
                full_module_name = f"mcp_tools.{category}.{module_name}"
                module = importlib.import_module(full_module_name)

                info = getattr(module, '__module_info__', None)
                if not info:
                    continue

                for func in info.get('functions', []):
                    tools.append({
                        "name": f"{category}.{module_name}.{func['name']}",
                        "description": func.get('desc', ''),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                p.split(':')[0].strip(): {"type": "string"}
                                for p in func.get('params', [])
                            },
                            "required": []
                        }
                    })
            except Exception as e:
                print(f"[MCP] Error importing {category}.{module_name}: {e}")

    return tools


def _discover_resources() -> List[Dict]:
    """发现可用资源"""
    resources = []

    # 知识库文档作为资源
    kb_path = os.path.expanduser('~/vulcan_brain_v2/kb_storage')
    meta_path = os.path.join(kb_path, 'metadata.json')

    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        for doc_id, doc_info in metadata.items():
            resources.append({
                "uri": f"knowledge://{doc_id}",
                "name": doc_info.get('title', doc_info.get('filename', doc_id)),
                "description": f"知识库文档: {doc_info.get('filename', '')}",
                "mimeType": "text/plain"
            })

    # 记忆作为资源
    resources.append({
        "uri": "memory://user",
        "name": "用户记忆",
        "description": "用户的长期记忆",
        "mimeType": "application/json"
    })

    resources.append({
        "uri": "memory://alignment",
        "name": "对齐记录",
        "description": "Boss 反馈和对齐历史",
        "mimeType": "application/json"
    })

    return resources


def _call_tool(name: str, arguments: Dict) -> Any:
    """调用工具"""
    # 解析工具路径: category.module.function
    parts = name.split('.')
    if len(parts) != 3:
        return {"error": f"Invalid tool name: {name}"}

    category, module_name, func_name = parts

    # 动态导入模块
    try:
        import importlib
        module = importlib.import_module(f"mcp_tools.{category}.{module_name}")
        func = getattr(module, func_name)
        result = func(**arguments)
        return [{"type": "text", "text": str(result)}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {str(e)}"}]


def _read_resource(uri: str) -> str:
    """读取资源"""
    if uri.startswith("knowledge://"):
        doc_id = uri.replace("knowledge://", "")
        kb_path = os.path.expanduser('~/vulcan_brain_v2/kb_storage')
        meta_path = os.path.join(kb_path, 'metadata.json')

        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            if doc_id in metadata:
                file_path = metadata[doc_id].get('file_path')
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()

        return f"Document {doc_id} not found"

    elif uri == "memory://user":
        memory_file = os.path.expanduser('~/vulcan_brain_v2/data/user_memory.json')
        if os.path.exists(memory_file):
            with open(memory_file, 'r', encoding='utf-8') as f:
                return json.dumps(json.load(f), ensure_ascii=False, indent=2)
        return "[]"

    elif uri == "memory://alignment":
        align_file = os.path.expanduser('~/vulcan_brain_v2/data/alignment_feedback.json')
        if os.path.exists(align_file):
            with open(align_file, 'r', encoding='utf-8') as f:
                return json.dumps(json.load(f), ensure_ascii=False, indent=2)
        return "[]"

    return f"Resource not found: {uri}"


# === MCP 端点 ===

@router.post("/mcp")
async def mcp_endpoint(request: MCPRequest):
    """
    MCP JSON-RPC 端点

    支持的方法:
    - initialize: 初始化连接
    - tools/list: 列出工具
    - tools/call: 调用工具
    - resources/list: 列出资源
    - resources/read: 读取资源
    """
    method = request.method
    params = request.params or {}

    try:
        if method == "initialize":
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Vulcan Brain",
                        "version": "5.0.0"
                    },
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": False, "listChanged": True}
                    }
                }
            )

        elif method == "tools/list":
            tools = _discover_tools()
            return MCPResponse(
                id=request.id,
                result={"tools": tools}
            )

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            content = _call_tool(tool_name, arguments)
            return MCPResponse(
                id=request.id,
                result={"content": content}
            )

        elif method == "resources/list":
            resources = _discover_resources()
            return MCPResponse(
                id=request.id,
                result={"resources": resources}
            )

        elif method == "resources/read":
            uri = params.get("uri", "")
            content = _read_resource(uri)
            return MCPResponse(
                id=request.id,
                result={
                    "contents": [{"uri": uri, "text": content, "mimeType": "text/plain"}]
                }
            )

        else:
            return MCPResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )

    except Exception as e:
        return MCPResponse(
            id=request.id,
            error={"code": -32603, "message": str(e)}
        )


@router.get("/mcp/info")
async def mcp_info():
    """MCP 服务器信息"""
    tools = _discover_tools()
    resources = _discover_resources()

    return {
        "name": "Vulcan Brain MCP Server",
        "version": "5.0.0",
        "protocol": "2024-11-05",
        "tools_count": len(tools),
        "resources_count": len(resources),
        "endpoint": "/mcp",
        "documentation": "https://docs.anthropic.com/en/docs/mcp"
    }
