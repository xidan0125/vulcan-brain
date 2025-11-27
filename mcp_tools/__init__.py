# mcp_tools/__init__.py
"""
Vulcan Brain MCP Tools - 模块化工具库

架构: 文件系统式工具发现 (参考 Anthropic Code Execution with MCP)
Agent 通过浏览目录结构发现工具，按需 import 使用

目录结构:
mcp_tools/
├── core/         # 核心工具: 时间、记忆
├── knowledge/    # 知识库: RAG、文档管理  
├── alignment/    # 对齐: Boss 反馈、洞察
└── compute/      # 计算: 代码执行、数据处理
"""

__version__ = '2.0.0'
__architecture__ = 'MCP Code Execution Pattern'
