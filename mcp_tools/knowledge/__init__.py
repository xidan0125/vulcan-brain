# mcp_tools/knowledge/__init__.py
"""
知识库模块

包含:
- rag: RAG 检索增强生成
"""

from .rag import search_knowledge, add_document, list_documents

__all__ = ['search_knowledge', 'add_document', 'list_documents']
