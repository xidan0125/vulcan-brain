# test_stream.py - 流式输出测试脚本
"""
测试目标：
1. 验证 run_stream() 能实时输出 token（打字机效果）
2. 验证事件协议的完整性
3. 测量实际 TTFT
"""

import asyncio
import time
from kernel_codeact import VulcanCodeActKernel
from vulcan_libs.registry import ToolRegistry, ToolPackage
from vulcan_libs.tool_retriever import ToolRetriever

# 导入工具
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool, forget_tool
from tools.alignment_tools import record_boss_feedback_tool


async def test_streaming():
    """测试流式输出"""
    print("=" * 80)
    print("🧪 Vulcan Brain v4.5 流式输出测试")
    print("=" * 80)
    
    # 1. 初始化内核
    registry = ToolRegistry()
    
    # 注册核心工具包
    registry.register(ToolPackage(
        name="core_tools",
        description="核心基础工具：时间查询、记忆管理",
        tools=[get_time_tool, remember_tool, recall_tool, forget_tool],
        is_core=True,
        category="foundation"
    ))
    
    kernel = VulcanCodeActKernel(
        model="qwen3-thinking",
        registry=registry,
        retriever=None,  # 禁用 LOD（简化测试）
        enable_lod=False
    )
    
    # 2. 测试查询
    test_query = "What time is it now? Use Python to get the current time."
    
    print(f"\n📝 测试查询: {test_query}")
    print("-" * 80)
    
    # 3. 流式执行
    start_time = time.time()
    ttft = None
    event_count = 0
    token_count = 0
    
    print("\n🌊 流式输出开始（实时显示）:\n")
    
    try:
        async for event in kernel.run_stream(test_query):
            # 记录首字延迟
            if ttft is None:
                ttft = time.time() - start_time
                print(f"\n⚡ TTFT (首字延迟): {ttft:.3f} 秒\n")
            
            event_count += 1
            event_type = event["type"]
            content = event["content"]
            is_thinking = event.get("is_thinking", False)
            
            # 根据事件类型渲染
            if event_type == "token":
                token_count += 1
                # 实时打印（不换行）
                prefix = "💭 " if is_thinking else ""
                print(f"{prefix}{content}", end="", flush=True)
            
            elif event_type == "code":
                print(f"\n\n💻 [代码块检测到]\n```python\n{content}\n```\n")
            
            elif event_type == "tool_output":
                print(f"\n✅ [工具执行结果]\n{content}\n")
            
            elif event_type == "final_answer":
                print(f"\n\n🏁 [最终答案]\n{content}\n")
            
            elif event_type == "error":
                print(f"\n\n❌ [错误]\n{content}\n")
        
        total_time = time.time() - start_time
        
        # 4. 统计报告
        print("\n" + "=" * 80)
        print("📊 测试统计")
        print("=" * 80)
        print(f"⚡ TTFT (首字延迟): {ttft:.3f} 秒")
        print(f"⏱️  总执行时间: {total_time:.2f} 秒")
        print(f"🧩 事件总数: {event_count}")
        print(f"📝 Token 总数: {token_count}")
        print(f"🚀 流式速度: {token_count / total_time:.1f} tokens/s")
        
        if ttft < 0.5:
            print("\n✅ 测试通过！首字延迟 < 0.5 秒")
        else:
            print(f"\n⚠️  测试警告：首字延迟较高 ({ttft:.2f}s)")
        
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_backward_compatibility():
    """测试向后兼容性（run 方法）"""
    print("\n" + "=" * 80)
    print("🔄 向后兼容性测试（run 方法）")
    print("=" * 80)
    
    registry = ToolRegistry()
    registry.register(ToolPackage(
        name="core_tools",
        description="核心工具",
        tools=[get_time_tool],
        is_core=True
    ))
    
    kernel = VulcanCodeActKernel(
        model="qwen3-thinking",
        registry=registry,
        enable_lod=False
    )
    
    test_query = "What time is it?"
    
    print(f"\n📝 测试查询: {test_query}")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        response = await kernel.run(test_query)
        total_time = time.time() - start_time
        
        print(f"\n✅ 响应:\n{response}")
        print(f"\n⏱️  耗时: {total_time:.2f} 秒")
        print("\n✅ 向后兼容性测试通过！")
        
    except Exception as e:
        print(f"\n❌ 向后兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🚀 开始测试...\n")
    
    # 测试 1: 流式输出
    asyncio.run(test_streaming())
    
    # 测试 2: 向后兼容性
    # asyncio.run(test_backward_compatibility())
    
    print("\n✅ 所有测试完成！")
