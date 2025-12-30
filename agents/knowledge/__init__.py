"""
Knowledge Agent Package
企业文档智能分析助手 - 支持VLM深度分析
"""

from .agent import (
    KnowledgeAgent,
    get_agent,
    smart_summarize,
    _summary_cache,
)
from .tools import (
    analyze_folder_structure,
    file_to_images,
    get_vlm_type,
    classify_business_type,
)
from .prompts import (
    FOLDER_ANALYSIS_PROMPT,
    DOCUMENT_VLM_PROMPT,
    build_folder_analysis_prompt,
    build_document_vlm_prompt,
)

__all__ = [
    # Agent
    'KnowledgeAgent',
    'get_agent',
    'smart_summarize',
    '_summary_cache',
    # Tools
    'analyze_folder_structure',
    'file_to_images',
    'get_vlm_type',
    'classify_business_type',
    # Prompts
    'FOLDER_ANALYSIS_PROMPT',
    'DOCUMENT_VLM_PROMPT',
    'build_folder_analysis_prompt',
    'build_document_vlm_prompt',
]
