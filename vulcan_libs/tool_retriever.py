# vulcan_libs/tool_retriever.py
"""
Vulcan Brain - 工具检索引擎 (Tool Retriever) V4.1
修复：添加置信度阈值，避免闲聊触发工具加载
"""

from typing import List, Set
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from vulcan_libs.registry import ToolRegistry

# 置信度阈值：低于此分数的工具不会被加载
SCORE_THRESHOLD = 0.45


class ToolRetriever:
    """工具检索引擎 - 基于语义相似度的包推荐系统"""
    
    def __init__(
        self, 
        registry: ToolRegistry,
        embed_model: str = "BAAI/bge-small-zh-v1.5",
        top_k: int = 3
    ):
        self.registry = registry
        self.top_k = top_k
        
        print(f"🔧 [ToolRetriever] 正在加载嵌入模型: {embed_model}")
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=embed_model,
            cache_folder="./model_cache"
        )
        
        self.index = self._build_index()
        self.retriever = self.index.as_retriever(similarity_top_k=top_k)
        
        print("✅ [ToolRetriever] 工具检索引擎初始化完成")
    
    def _build_index(self) -> VectorStoreIndex:
        print("🔍 [ToolRetriever] 正在构建工具向量索引...")
        
        docs = []
        tool_count = 0
        
        for pkg_name, pkg in self.registry.packages.items():
            if pkg.is_core:
                print(f"   ├─ 跳过核心包: {pkg_name} (常驻内存)")
                continue
            
            for tool in pkg.tools:
                doc_text = (
                    f"Tool: {tool.metadata.name}\n"
                    f"Description: {tool.metadata.description}\n"
                    f"Function Schema: {tool.metadata.fn_schema_str}"
                )
                
                doc = Document(
                    text=doc_text,
                    metadata={
                        "parent_package": pkg_name,
                        "tool_name": tool.metadata.name,
                        "package_description": pkg.description
                    }
                )
                docs.append(doc)
                tool_count += 1
        
        print(f"   └─ 已索引 {tool_count} 个扩展工具")
        
        if not docs:
            print("⚠️  [ToolRetriever] 警告：没有扩展工具可索引")
            docs = [Document(text="Empty", metadata={"parent_package": "none"})]
        
        return VectorStoreIndex.from_documents(docs)
    
    def retrieve_package_names(self, query: str, score_threshold: float = SCORE_THRESHOLD, debug: bool = True) -> List[str]:
        """
        根据用户查询检索相关的工具包名称
        
        【V4.1 修复】添加置信度阈值，低相似度不加载
        """
        if debug:
            print(f"🕵️  [ToolRetriever] Query: {query}")
            print(f"   ├─ 置信度阈值: {score_threshold}")
        
        nodes = self.retriever.retrieve(query)
        packages: Set[str] = set()
        
        for node in nodes:
            pkg_name = node.metadata.get("parent_package")
            tool_name = node.metadata.get("tool_name")
            score = getattr(node, "score", 0.0)
            
            # 【关键修复】置信度过滤
            if score < score_threshold:
                if debug:
                    print(f"   ├─ 📉 [Skip] {tool_name} (score={score:.3f} < {score_threshold})")
                continue
            
            if pkg_name and pkg_name != "none":
                packages.add(pkg_name)
                if debug:
                    print(f"   ├─ 🎯 [Hit] {tool_name} → {pkg_name} (score={score:.3f})")
        
        result = list(packages)
        
        if debug:
            if result:
                print(f"   └─ ✅ 推荐加载: {result}")
            else:
                print(f"   └─ 💬 无匹配工具包，将使用纯聊天模式")
        
        return result
    
    def get_retriever_stats(self) -> str:
        total_docs = len(self.index.docstore.docs)
        return f"📊 检索器统计: {total_docs} docs, top_k={self.top_k}, threshold={SCORE_THRESHOLD}"


# === 全局单例 ===
_default_retriever = None

def get_global_retriever(registry: ToolRegistry = None) -> ToolRetriever:
    """获取全局检索器实例（单例模式）"""
    global _default_retriever
    if _default_retriever is None:
        if registry is None:
            raise ValueError("首次调用必须提供 registry")
        _default_retriever = ToolRetriever(registry)
    return _default_retriever
