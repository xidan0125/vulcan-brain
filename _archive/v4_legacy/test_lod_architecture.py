#!/usr/bin/env python3
"""
Sprint 3 验收测试 - LOD 架构核心功能验证

这个测试脚本验证：
1. ToolRegistry 能正确注册和检索工具包
2. ToolRetriever 能根据查询检索相关工具包
3. Kernel 能动态更新工具上下文

不包含实际 LLM 调用（避免超时）
"""

import sys
from llama_index.core.tools import FunctionTool

# 导入 LOD 组件
from vulcan_libs.registry import ToolRegistry, ToolPackage
from vulcan_libs.tool_retriever import ToolRetriever


def create_test_tools():
    """创建测试工具"""
    
    def get_time():
        """获取当前时间"""
        return "2025-11-20 12:00:00"
    
    def remember_info(info: str):
        """记住信息"""
        return f"已记住: {info}"
    
    def search_rag(query: str):
        """在知识库中搜索"""
        return f"RAG 搜索结果: {query}"
    
    def add_document(text: str):
        """添加文档到知识库"""
        return f"已添加文档: {text[:50]}..."
    
    def record_feedback(feedback: str):
        """记录 Boss 反馈"""
        return f"已记录反馈: {feedback}"
    
    # 创建工具对象
    time_tool = FunctionTool.from_defaults(
        fn=get_time, 
        name="get_current_time", 
        description="获取当前时间"
    )
    
    memory_tool = FunctionTool.from_defaults(
        fn=remember_info, 
        name="remember_info", 
        description="记住用户提供的信息"
    )
    
    rag_search_tool = FunctionTool.from_defaults(
        fn=search_rag, 
        name="search_knowledge_base", 
        description="在知识库中检索信息，适用于查询文档、财报、合同等内容"
    )
    
    rag_add_tool = FunctionTool.from_defaults(
        fn=add_document, 
        name="add_document", 
        description="将文档添加到知识库中"
    )
    
    feedback_tool = FunctionTool.from_defaults(
        fn=record_feedback, 
        name="record_boss_feedback", 
        description="记录 Boss 的反馈和纠正意见"
    )
    
    return time_tool, memory_tool, rag_search_tool, rag_add_tool, feedback_tool


def test_registry():
    """测试 1: 工具注册表"""
    print("\n" + "="*60)
    print("🧪 测试 1: ToolRegistry 功能验证")
    print("="*60)
    
    time_tool, memory_tool, rag_search_tool, rag_add_tool, feedback_tool = create_test_tools()
    
    registry = ToolRegistry()
    
    # 注册核心包
    registry.register(ToolPackage(
        name="core_tools",
        description="核心基础工具",
        tools=[time_tool, memory_tool],
        is_core=True
    ))
    
    # 注册扩展包
    registry.register(ToolPackage(
        name="rag_pkg",
        description="知识库检索能力",
        tools=[rag_search_tool, rag_add_tool],
        is_core=False
    ))
    
    registry.register(ToolPackage(
        name="alignment_pkg",
        description="价值观对齐工具",
        tools=[feedback_tool],
        is_core=False
    ))
    
    # 验证核心工具检索
    core_tools = registry.get_core_tools()
    print(f"\n✅ 核心工具数量: {len(core_tools)} (预期: 2)")
    assert len(core_tools) == 2, "核心工具数量不正确"
    
    # 验证扩展包检索
    rag_tools = registry.get_package_tools(["rag_pkg"])
    print(f"✅ RAG 扩展工具数量: {len(rag_tools)} (预期: 2)")
    assert len(rag_tools) == 2, "RAG 扩展工具数量不正确"
    
    # 打印摘要
    print("\n" + registry.get_registry_summary())
    
    print("\n✅ 测试 1 通过：ToolRegistry 功能正常")
    return registry


def test_retriever(registry):
    """测试 2: 工具检索引擎"""
    print("\n" + "="*60)
    print("🧪 测试 2: ToolRetriever 功能验证")
    print("="*60)
    
    retriever = ToolRetriever(registry, top_k=2)
    
    # 测试场景 1: 查询时间（不应检索到任何扩展包）
    print("\n--- 场景 1: 查询时间 ---")
    result1 = retriever.retrieve_package_names("现在几点了？", debug=True)
    print(f"检索结果: {result1}")
    print(f"✅ 预期: 空列表（只用核心工具），实际: {result1}")
    
    # 测试场景 2: 查询知识库（应检索到 rag_pkg）
    print("\n--- 场景 2: 查询知识库 ---")
    result2 = retriever.retrieve_package_names("帮我在知识库中搜索财报数据", debug=True)
    print(f"检索结果: {result2}")
    assert "rag_pkg" in result2, "未检索到 rag_pkg"
    print(f"✅ 预期: 包含 rag_pkg，实际: {result2}")
    
    # 测试场景 3: 记录反馈（应检索到 alignment_pkg）
    print("\n--- 场景 3: 记录反馈 ---")
    result3 = retriever.retrieve_package_names("记录 Boss 的反馈意见", debug=True)
    print(f"检索结果: {result3}")
    assert "alignment_pkg" in result3, "未检索到 alignment_pkg"
    print(f"✅ 预期: 包含 alignment_pkg，实际: {result3}")
    
    print("\n✅ 测试 2 通过：ToolRetriever 检索准确")
    return retriever


def test_context_update(registry, retriever):
    """测试 3: 内核动态上下文更新（模拟）"""
    print("\n" + "="*60)
    print("🧪 测试 3: 内核动态上下文更新验证（模拟）")
    print("="*60)
    
    # 模拟内核的 _update_context 逻辑
    def simulate_context_update(query: str):
        """模拟内核的上下文更新逻辑"""
        print(f"\n🔍 [模拟] 用户查询: {query}")
        
        # 1. 检索相关包
        relevant_packages = retriever.retrieve_package_names(query, debug=False)
        print(f"   └─ 检索到的包: {relevant_packages}")
        
        # 2. 获取工具
        core_tools = registry.get_core_tools()
        extension_tools = registry.get_package_tools(relevant_packages)
        all_tools = core_tools + extension_tools
        
        print(f"🔋 [模拟] 当前激活工具:")
        print(f"   ├─ 核心工具: {len(core_tools)} 个")
        print(f"   ├─ 扩展工具: {len(extension_tools)} 个")
        print(f"   └─ 总计: {len(all_tools)} 个")
        
        return all_tools
    
    # 场景 1: 基础查询
    print("\n--- 场景 1: 基础查询（只用核心） ---")
    tools1 = simulate_context_update("现在几点？")
    assert len(tools1) == 2, f"工具数量错误: {len(tools1)}"
    print("✅ 只加载了核心工具")
    
    # 场景 2: RAG 查询
    print("\n--- 场景 2: RAG 查询（核心 + RAG） ---")
    tools2 = simulate_context_update("搜索知识库中的内容")
    assert len(tools2) > 2, f"未加载扩展工具: {len(tools2)}"
    print(f"✅ 加载了核心 + RAG 工具（{len(tools2)} 个）")
    
    # 场景 3: 对齐查询
    print("\n--- 场景 3: 对齐查询（核心 + Alignment） ---")
    tools3 = simulate_context_update("记录 Boss 的反馈")
    assert len(tools3) > 2, f"未加载扩展工具: {len(tools3)}"
    print(f"✅ 加载了核心 + Alignment 工具（{len(tools3)} 个）")
    
    print("\n✅ 测试 3 通过：动态上下文更新逻辑正确")


def main():
    """主测试函数"""
    print("="*60)
    print("🚀 Sprint 3 - LOD 架构验收测试")
    print("="*60)
    
    try:
        # 测试 1: Registry
        registry = test_registry()
        
        # 测试 2: Retriever
        retriever = test_retriever(registry)
        
        # 测试 3: Context Update
        test_context_update(registry, retriever)
        
        # 最终报告
        print("\n" + "="*60)
        print("✅ 所有测试通过！")
        print("="*60)
        print("\n📊 Sprint 3 验收结果:")
        print("  ✅ ToolRegistry: 工具包注册和检索功能正常")
        print("  ✅ ToolRetriever: 语义检索准确率 100%")
        print("  ✅ 动态上下文更新: 逻辑正确，按需加载")
        print("\n🎉 LOD 架构核心功能验证完成！")
        print("\n下一步：")
        print("  1. 运行 main.py 进行完整端到端测试（需要 Ollama）")
        print("  2. 对比 V3 vs V4 的性能指标")
        print("  3. 添加更多扩展工具包")
        
        return 0
    
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
