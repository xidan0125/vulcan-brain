# tools/rag_tools.py
"""
Vulcan Brain - RAG (知识库) 工具

Layer 4: 能力工具层
职责: 封装文档上传、知识检索功能
"""

from llama_index.core.tools import FunctionTool
from llama_index.core import Document
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 注意: RAG 模块需要 HuggingFace embeddings
# 如果未安装，将使用 SimpleRAG 后备方案
try:
    from vulcan_libs.rag import VulcanRAG, get_rag_instance
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  RAG 模块依赖缺失: {e}")
    RAG_AVAILABLE = False


def add_document_to_kb(content: str, title: str = "Untitled") -> str:
    """
    将文档内容添加到知识库
    
    Args:
        content: 文档内容（纯文本）
        title: 文档标题（可选）
    
    Returns:
        确认信息
    
    Examples:
        add_document_to_kb(
            content="Vulcan Brain 是一个基于 CodeAct 的 AI 系统...",
            title="项目介绍"
        )
    """
    if not RAG_AVAILABLE:
        return "❌ RAG 功能未启用（缺少 llama-index-embeddings-huggingface）"
    
    try:
        # 创建文档
        doc = Document(text=content, metadata={"title": title})
        
        # 获取 RAG 实例并构建索引
        rag = get_rag_instance()
        rag.build_knowledge_base([doc])
        
        return f"✅ 已添加文档到知识库: {title}"
    except Exception as e:
        return f"❌ 添加文档失败: {str(e)}"


def search_knowledge_base(query: str, mode: str = "auto") -> str:
    """
    搜索知识库
    
    Args:
        query: 查询问题
        mode: 检索模式
            - "vector": 向量检索（查细节）
            - "summary": 摘要检索（查大意）
            - "auto": 自动选择（默认）
    
    Returns:
        检索结果
    
    Examples:
        search_knowledge_base("Vulcan Brain 的核心架构是什么？")
        search_knowledge_base("总结这份文档的核心观点", mode="summary")
    """
    if not RAG_AVAILABLE:
        return "❌ RAG 功能未启用（缺少 llama-index-embeddings-huggingface）"
    
    try:
        rag = get_rag_instance()
        result = rag.search(query, mode=mode)
        return result
    except Exception as e:
        return f"❌ 检索失败: {str(e)}"


# === 创建 LlamaIndex Tools ===

add_document_tool = FunctionTool.from_defaults(
    fn=add_document_to_kb,
    name="add_document_to_kb",
    description="""将文档内容添加到知识库（用于后续检索）。
当用户说"记住这份文档"、"把这个存起来"时调用。
参数: content (文档内容), title (标题，可选)
"""
)

search_knowledge_tool = FunctionTool.from_defaults(
    fn=search_knowledge_base,
    name="search_knowledge_base",
    description="""搜索知识库中的文档。
当用户问"我之前存的XXX文档说了什么？"时调用。
支持两种模式:
- vector: 查细节（如"第三章讲了什么？"）
- summary: 查大意（如"总结这份文档的核心思想"）
- auto: 自动选择（默认）
参数: query (查询问题), mode (检索模式，默认 auto)
"""
)


# === 导出 ===
__all__ = ['add_document_tool', 'search_knowledge_tool', 'RAG_AVAILABLE']


# === 测试代码 ===
if __name__ == "__main__":
    print("=== RAG Tools 测试 ===\n")
    
    if not RAG_AVAILABLE:
        print("❌ RAG 功能不可用")
        print("安装命令: pip install llama-index-embeddings-huggingface")
    else:
        # 测试添加文档
        result = add_document_to_kb(
            content="Vulcan Brain 采用五层汉堡架构: Layer 1 (UI), Layer 2 (Kernel), Layer 3 (Soul), Layer 4 (Tools), Layer 5 (Infra).",
            title="架构说明"
        )
        print(result)
        
        # 测试检索
        result = search_knowledge_base("Vulcan Brain 的架构有几层？")
        print(f"\n检索结果: {result}")
    
    print("\n✅ 测试完成")
