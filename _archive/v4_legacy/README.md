# V4 Legacy 归档

这个目录包含 V5.1 Bicameral 架构升级前的旧代码。

## 归档时间
2025-12-04

## 归档原因
V5.1 引入了全新的 Bicameral (CEO-CTO) 双脑架构，替代了原有的:
- kernel_codeact.py - CodeAct 内核
- kernel_mcp_v5.py - MCP 内核
- api_server_mcp.py - MCP API 路由

## 新架构
- vulcan_libs/bicameral_graph.py - CEO-CTO LangGraph 实现
- vulcan_libs/ceo_soul.py - CEO 思考节点
- vulcan_libs/cto_executor.py - CTO 执行节点
- bicameral_api.py - Bicameral REST API

## 注意
这些文件仅作参考保留，不应在生产环境中使用。
如需恢复，请先仔细评估兼容性。
