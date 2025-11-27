# tools/__init__.py
"""
Vulcan Brain - Tools Package
Layer 4: 能力工具层
"""

# Function Tools
from .function_tools import get_current_time

# Memory Tools  
from .memory_tools import remember_info, recall_info, forget_info

# Alignment Tools
from .alignment_tools import record_boss_feedback, get_alignment_summary

# Boss Insight Tool
from .boss_insight_tool import save_boss_insight

# RAG Tools
from .rag_tools import add_document_to_kb, search_knowledge_base

__all__ = [
    # Function Tools
    'get_current_time',
    
    # Memory Tools
    'remember_info',
    'recall_info',
    'forget_info',
    
    # Alignment Tools
    'record_boss_feedback',
    'get_alignment_summary',
    'save_boss_insight',
    
    # RAG Tools
    'add_document_to_kb',
    'search_knowledge_base',
]
