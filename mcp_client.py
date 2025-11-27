# mcp_client.py - Vulcan Brain MCP Client
"""
MCP (Model Context Protocol) 客户端

让 Vulcan Brain 可以连接外部 MCP 服务器
参考: https://docs.anthropic.com/en/docs/mcp

支持的传输方式:
- HTTP + SSE (Server-Sent Events)
- Stdio (本地进程通信)
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"


class MCPClient:
    """
    MCP 客户端

    用于连接外部 MCP 服务器，获取工具和资源
    """

    def __init__(self, server_url: str, timeout: int = 30):
        """
        初始化 MCP 客户端

        Args:
            server_url: MCP 服务器地址 (如 http://localhost:3000)
            timeout: 请求超时秒数
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self._tools_cache: List[MCPTool] = []
        self._resources_cache: List[MCPResource] = []
        self._initialized = False

    async def _ensure_session(self):
        """确保 HTTP session 存在"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

    async def _request(self, method: str, params: Dict = None) -> Dict:
        """发送 MCP JSON-RPC 请求"""
        await self._ensure_session()

        payload = {
            "jsonrpc": "2.0",
            "id": str(datetime.now().timestamp()),
            "method": method,
            "params": params or {}
        }

        async with self.session.post(
            f"{self.server_url}/mcp",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            if "error" in result:
                raise Exception(f"MCP Error: {result['error']}")
            return result.get("result", {})

    async def initialize(self) -> Dict:
        """
        初始化连接

        Returns:
            服务器信息 (name, version, capabilities)
        """
        result = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "clientInfo": {
                "name": "Vulcan Brain",
                "version": "5.0.0"
            }
        })
        self._initialized = True
        return result

    async def list_tools(self) -> List[MCPTool]:
        """获取可用工具列表"""
        if not self._initialized:
            await self.initialize()

        result = await self._request("tools/list")
        tools = []
        for tool in result.get("tools", []):
            tools.append(MCPTool(
                name=tool["name"],
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {})
            ))
        self._tools_cache = tools
        return tools

    async def call_tool(self, name: str, arguments: Dict = None) -> Any:
        """
        调用工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if not self._initialized:
            await self.initialize()

        result = await self._request("tools/call", {
            "name": name,
            "arguments": arguments or {}
        })
        return result.get("content", [])

    async def list_resources(self) -> List[MCPResource]:
        """获取可用资源列表"""
        if not self._initialized:
            await self.initialize()

        result = await self._request("resources/list")
        resources = []
        for res in result.get("resources", []):
            resources.append(MCPResource(
                uri=res["uri"],
                name=res["name"],
                description=res.get("description", ""),
                mime_type=res.get("mimeType", "text/plain")
            ))
        self._resources_cache = resources
        return resources

    async def read_resource(self, uri: str) -> str:
        """
        读取资源内容

        Args:
            uri: 资源 URI

        Returns:
            资源内容
        """
        if not self._initialized:
            await self.initialize()

        result = await self._request("resources/read", {"uri": uri})
        contents = result.get("contents", [])
        if contents:
            return contents[0].get("text", "")
        return ""

    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()
            self.session = None
        self._initialized = False


class MCPServerManager:
    """
    MCP 服务器管理器

    管理多个 MCP 服务器连接
    """

    def __init__(self):
        self.servers: Dict[str, MCPClient] = {}

    async def add_server(self, name: str, url: str) -> MCPClient:
        """添加 MCP 服务器"""
        client = MCPClient(url)
        await client.initialize()
        self.servers[name] = client
        return client

    async def remove_server(self, name: str):
        """移除 MCP 服务器"""
        if name in self.servers:
            await self.servers[name].close()
            del self.servers[name]

    async def list_all_tools(self) -> Dict[str, List[MCPTool]]:
        """列出所有服务器的工具"""
        result = {}
        for name, client in self.servers.items():
            result[name] = await client.list_tools()
        return result

    async def call_tool(self, server: str, tool: str, arguments: Dict = None) -> Any:
        """调用指定服务器的工具"""
        if server not in self.servers:
            raise ValueError(f"Server '{server}' not found")
        return await self.servers[server].call_tool(tool, arguments)

    async def close_all(self):
        """关闭所有连接"""
        for client in self.servers.values():
            await client.close()
        self.servers.clear()


# === 测试 ===
if __name__ == "__main__":
    async def test():
        # 测试连接本地 MCP 服务器
        client = MCPClient("http://localhost:8001")
        try:
            info = await client.initialize()
            print(f"Server info: {info}")

            tools = await client.list_tools()
            print(f"Available tools: {[t.name for t in tools]}")

        except Exception as e:
            print(f"Connection failed: {e}")
        finally:
            await client.close()

    asyncio.run(test())
