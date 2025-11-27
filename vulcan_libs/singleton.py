# vulcan_libs/singleton.py
"""
Vulcan Brain - 全局单例管理器
确保 Embedding 模型只加载一次（进程级），避免每个会话重复加载
"""

from vulcan_libs.registry import ToolRegistry, ToolPackage
from vulcan_libs.tool_retriever import ToolRetriever

# 全局变量
_GLOBAL_REGISTRY = None
_GLOBAL_RETRIEVER = None
_INITIALIZED = False


def init_global_objects():
    """
    初始化全局对象（只运行一次）
    
    返回: (registry, retriever)
    """
    global _GLOBAL_REGISTRY, _GLOBAL_RETRIEVER, _INITIALIZED
    
    if _INITIALIZED:
        print("⚡ [Singleton] 返回缓存的全局对象")
        return _GLOBAL_REGISTRY, _GLOBAL_RETRIEVER
    
    print("🔥 [Singleton] 正在初始化全局组件 (只运行一次)...")
    
    # 延迟导入工具（避免循环依赖）
    from tools.function_tools import get_time_tool
    from tools.memory_tools import remember_tool, recall_tool, forget_tool
    from tools.rag_tools import add_document_tool, search_knowledge_tool
    from tools.alignment_tools import record_boss_feedback_tool, get_alignment_summary_tool
    from tools.boss_insight_tool import save_boss_insight_tool
    
    # 1. 创建注册表
    registry = ToolRegistry()
    
    # 核心包（常驻）
    registry.register(ToolPackage(
        name="core_tools",
        description="核心基础工具：时间查询、记忆管理",
        tools=[get_time_tool, remember_tool, recall_tool, forget_tool],
        is_core=True,
        category="foundation"
    ))
    
    # RAG 扩展包
    registry.register(ToolPackage(
        name="rag_pkg",
        description="知识库检索能力：文档添加、语义搜索",
        tools=[add_document_tool, search_knowledge_tool],
        is_core=False,
        category="knowledge"
    ))
    
    # 对齐扩展包
    registry.register(ToolPackage(
        name="alignment_pkg",
        description="价值观对齐工具：记录 Boss 反馈、保存洞察",
        tools=[record_boss_feedback_tool, get_alignment_summary_tool, save_boss_insight_tool],
        is_core=False,
        category="alignment"
    ))
    
    # 2. 创建检索器（会加载 Embedding 模型）
    retriever = ToolRetriever(registry, top_k=3)
    
    # 3. 缓存
    _GLOBAL_REGISTRY = registry
    _GLOBAL_RETRIEVER = retriever
    _INITIALIZED = True
    
    print("✅ [Singleton] 全局组件初始化完成")
    print(registry.get_registry_summary())
    
    return registry, retriever


def get_global_objects():
    """获取全局对象（懒加载）"""
    return init_global_objects()
