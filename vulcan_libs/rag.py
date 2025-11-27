# vulcan_libs/rag.py
"""
Vulcan Brain - RAG 2.0 (Semantic Memory / 语义记忆)

升级点:
1. 双索引架构: Vector Index (细节) + Summary Index (大意)
2. 混合检索: 向量相似度 + 关键词匹配
3. 分层查询: LOD-0 (摘要) → LOD-1 (细节)

解决传统 RAG 的"碎片化灾难"问题
"""

from typing import List, Optional, Tuple
from llama_index.core import (
    VectorStoreIndex, 
    SummaryIndex,
    Document,
    Settings,
    StorageContext,
    load_index_from_storage
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import os


class VulcanRAG:
    """Vulcan Brain RAG 2.0 - 双流索引知识库"""
    
    def __init__(
        self, 
        embed_model: str = "BAAI/bge-small-zh-v1.5",
        persist_dir: Optional[str] = None
    ):
        """
        初始化 RAG 系统
        
        Args:
            embed_model: 嵌入模型名称（推荐中文模型）
            persist_dir: 索引持久化目录（如果为 None 则不持久化）
        """
        # 配置嵌入模型
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=embed_model,
            cache_folder="./model_cache"
        )
        
        # 配置文本分割器
        Settings.node_parser = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50
        )
        
        self.persist_dir = persist_dir
        self.vector_index = None
        self.summary_index = None
        
        # 如果有持久化目录，尝试加载
        if persist_dir and os.path.exists(persist_dir):
            self._load_indices()
    
    def build_knowledge_base(self, documents: List[Document]) -> Tuple[VectorStoreIndex, SummaryIndex]:
        """
        构建双索引知识库
        
        Args:
            documents: 文档列表
        
        Returns:
            (vector_index, summary_index)
        """
        print("🔨 [RAG 2.0] 正在构建知识库...")
        
        # 1. 向量索引 (查细节)
        print("  ├─ 构建 Vector Index (细节检索)...")
        self.vector_index = VectorStoreIndex.from_documents(documents)
        
        # 2. 摘要索引 (查大意)
        print("  └─ 构建 Summary Index (宏观检索)...")
        self.summary_index = SummaryIndex.from_documents(documents)
        
        # 3. 持久化（如果配置了）
        if self.persist_dir:
            self._save_indices()
        
        print(f"✅ [RAG 2.0] 知识库构建完成！文档数: {len(documents)}")
        return self.vector_index, self.summary_index
    
    def search(
        self, 
        query: str, 
        mode: str = "vector",
        top_k: int = 3
    ) -> str:
        """
        智能检索
        
        Args:
            query: 查询问题
            mode: 检索模式
                - "vector": 向量检索（查细节，如"第三章第二节讲了什么？"）
                - "summary": 摘要检索（查大意，如"这本书的核心思想是什么？"）
                - "auto": 自动选择（根据问题类型）
            top_k: 返回结果数量
        
        Returns:
            检索结果文本
        """
        if not self.vector_index or not self.summary_index:
            return "❌ 知识库尚未构建。请先调用 build_knowledge_base()"
        
        # 自动模式：根据关键词判断
        if mode == "auto":
            summary_keywords = ["总结", "核心", "主要", "大意", "概括", "整体"]
            if any(kw in query for kw in summary_keywords):
                mode = "summary"
            else:
                mode = "vector"
        
        print(f"🔍 [RAG 2.0] 检索模式: {mode}")
        
        if mode == "summary":
            # 摘要检索：适合宏观问题
            query_engine = self.summary_index.as_query_engine()
            response = query_engine.query(query)
            return str(response)
        
        else:  # vector
            # 向量检索：适合细节问题
            query_engine = self.vector_index.as_query_engine(
                similarity_top_k=top_k
            )
            response = query_engine.query(query)
            return str(response)
    
    def _save_indices(self):
        """持久化索引"""
        if not self.persist_dir:
            return
        
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # 分别保存两个索引
        vector_dir = os.path.join(self.persist_dir, "vector")
        summary_dir = os.path.join(self.persist_dir, "summary")
        
        if self.vector_index:
            self.vector_index.storage_context.persist(persist_dir=vector_dir)
        
        if self.summary_index:
            self.summary_index.storage_context.persist(persist_dir=summary_dir)
        
        print(f"💾 [RAG 2.0] 索引已保存到: {self.persist_dir}")
    
    def _load_indices(self):
        """从磁盘加载索引"""
        vector_dir = os.path.join(self.persist_dir, "vector")
        summary_dir = os.path.join(self.persist_dir, "summary")
        
        try:
            if os.path.exists(vector_dir):
                storage_context = StorageContext.from_defaults(persist_dir=vector_dir)
                self.vector_index = load_index_from_storage(storage_context)
                print("✅ [RAG 2.0] Vector Index 已加载")
            
            if os.path.exists(summary_dir):
                storage_context = StorageContext.from_defaults(persist_dir=summary_dir)
                self.summary_index = load_index_from_storage(storage_context)
                print("✅ [RAG 2.0] Summary Index 已加载")
        
        except Exception as e:
            print(f"⚠️  [RAG 2.0] 加载索引失败: {e}")
            self.vector_index = None
            self.summary_index = None


# === 便捷函数接口（供工具调用）===

_default_rag = None

def get_rag_instance(persist_dir: str = "./rag_storage") -> VulcanRAG:
    """获取全局 RAG 实例"""
    global _default_rag
    if _default_rag is None:
        _default_rag = VulcanRAG(persist_dir=persist_dir)
    return _default_rag


def build_kb_from_texts(texts: List[str]) -> str:
    """
    从文本列表构建知识库
    
    Args:
        texts: 文本列表
    
    Returns:
        确认信息
    """
    documents = [Document(text=text) for text in texts]
    rag = get_rag_instance()
    rag.build_knowledge_base(documents)
    return f"✅ 知识库构建完成，包含 {len(texts)} 个文档"


def search_knowledge(query: str, mode: str = "auto") -> str:
    """
    检索知识库
    
    Args:
        query: 查询问题
        mode: 检索模式 ("vector" / "summary" / "auto")
    
    Returns:
        检索结果
    """
    rag = get_rag_instance()
    return rag.search(query, mode=mode)


# === 测试代码 ===
if __name__ == "__main__":
    print("=== Vulcan RAG 2.0 测试 ===\n")
    
    # 测试文档
    test_docs = [
        Document(text="""
        Vulcan Brain v2.0 是一个基于 Qwen3-30B-Thinking 模型的智能助手系统。
        它采用 CodeAct 范式，让模型通过编写 Python 代码来调用工具。
        核心架构包括：Kernel（100行循环）、Memory（情景记忆）、RAG（语义记忆）。
        """),
        Document(text="""
        CodeAct 范式的优势在于：
        1. 利用 Python 解释器进行精确计算
        2. 模型可以自我修复代码错误
        3. 调试体验极佳（直接看 traceback）
        相比 XML/JSON 工具调用，CodeAct 更适合数理能力强的模型。
        """),
        Document(text="""
        Vulcan Brain 的记忆系统分为两流：
        - 流 A: 语义记忆（RAG 2.0，存储文档知识）
        - 流 B: 情景记忆（Memory Manager，存储用户偏好）
        这种设计灵感来源于 EverMemOS 的分层架构。
        """)
    ]
    
    # 构建知识库
    rag = VulcanRAG(persist_dir=None)  # 不持久化，仅测试
    rag.build_knowledge_base(test_docs)
    
    # 测试向量检索（细节问题）
    print("\n--- 测试 1: 向量检索（细节） ---")
    result = rag.search("CodeAct 范式有什么优势？", mode="vector")
    print(f"结果: {result}\n")
    
    # 测试摘要检索（宏观问题）
    print("\n--- 测试 2: 摘要检索（宏观） ---")
    result = rag.search("Vulcan Brain 的核心架构是什么？", mode="summary")
    print(f"结果: {result}\n")
    
    print("✅ 测试完成")
