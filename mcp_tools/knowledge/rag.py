# mcp_tools/knowledge/rag.py
"""
RAG 知识库模块

接口:
- search_knowledge(query: str) -> str: 语义搜索知识库
- add_document(content: str, title: str) -> str: 添加文档
- list_documents() -> list: 列出所有文档
"""

import os
import json
from typing import List, Optional

KB_DIR = os.path.expanduser('~/vulcan_brain_v2/kb_storage')
KB_METADATA = os.path.join(KB_DIR, 'metadata.json')


def _load_metadata() -> dict:
    if os.path.exists(KB_METADATA):
        with open(KB_METADATA, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def search_knowledge(query: str, top_k: int = 3) -> str:
    """
    在知识库中搜索相关内容
    
    Args:
        query: 搜索查询
        top_k: 返回结果数量
    
    Returns:
        搜索结果文本
    """
    try:
        from vulcan_libs.rag import VulcanRAG
        rag = VulcanRAG(persist_dir=os.path.join(KB_DIR, 'rag_index'))
        results = rag.query(query, top_k=top_k)
        return results if results else '知识库中没有找到相关内容'
    except Exception as e:
        return f'搜索出错: {str(e)}'


def add_document(content: str, title: str = 'Untitled') -> str:
    """
    添加文档到知识库
    
    Args:
        content: 文档内容
        title: 文档标题
    
    Returns:
        操作结果
    """
    import hashlib
    from datetime import datetime
    
    os.makedirs(KB_DIR, exist_ok=True)
    
    doc_id = hashlib.md5(content.encode()).hexdigest()[:16]
    file_path = os.path.join(KB_DIR, f'{doc_id}_{title}.txt')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    metadata = _load_metadata()
    metadata[doc_id] = {
        'id': doc_id,
        'title': title,
        'file_path': file_path,
        'created_at': datetime.now().isoformat()
    }
    
    with open(KB_METADATA, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return f'文档 "{title}" 已添加到知识库 (ID: {doc_id})'


def list_documents() -> List[dict]:
    """列出知识库中的所有文档"""
    metadata = _load_metadata()
    return list(metadata.values())


__module_info__ = {
    'name': 'rag',
    'category': 'knowledge',
    'description': 'RAG 知识库检索',
    'functions': [
        {'name': 'search_knowledge', 'desc': '语义搜索知识库', 'params': ['query: str', 'top_k: int = 3']},
        {'name': 'add_document', 'desc': '添加文档', 'params': ['content: str', 'title: str']},
        {'name': 'list_documents', 'desc': '列出所有文档'},
    ]
}
