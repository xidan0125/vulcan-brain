# debug_probe.py - 诊断延迟探针
import asyncio
import time
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage


async def test_blocking_vs_streaming():
    llm = Ollama(
        model="qwen3-thinking",
        temperature=0.1,
        request_timeout=120.0,
        context_window=8192,
        additional_kwargs={"num_gpu": -1}
    )
    
    test_query = "What time is it now? Use Python to get the current time."
    
    messages = [
        ChatMessage(
            role="system",
            content="You are a helpful AI assistant."
        ),
        ChatMessage(role="user", content=test_query)
    ]
    
    print("="*80)
    print("Vulcan Brain 延迟诊断探针")
    print("="*80)
    print(f"查询: {test_query}")
    
    # 测试 1: 阻塞式调用
    print("\n[测试 1] 阻塞式调用 (achat)")
    print("-" * 80)
    
    start_blocking = time.time()
    response_blocking = await llm.achat(messages)
    end_blocking = time.time()
    
    blocking_time = end_blocking - start_blocking
    blocking_content = response_blocking.message.content
    
    print(f"总耗时: {blocking_time:.2f} 秒")
    print(f"内容长度: {len(blocking_content)} 字符")
    print(f"完整响应前500字符:\n{blocking_content[:500]}...")
    
    # 测试 2: 流式调用
    print("\n[测试 2] 流式调用 (astream_chat)")
    print("-" * 80)
    
    start_streaming = time.time()
    ttft = None
    chunks_received = 0
    accumulated_content = ""
    
    async for chunk in await llm.astream_chat(messages):
        if ttft is None:
            ttft = time.time() - start_streaming
            print(f"TTFT (首字延迟): {ttft:.2f} 秒")
        
        chunks_received += 1
        accumulated_content += chunk.delta or ""
    
    end_streaming = time.time()
    streaming_time = end_streaming - start_streaming
    
    print(f"总耗时: {streaming_time:.2f} 秒")
    print(f"内容长度: {len(accumulated_content)} 字符")
    print(f"接收块数: {chunks_received}")
    
    # 诊断报告
    print("\n" + "="*80)
    print("诊断报告")
    print("="*80)
    print(f"阻塞式延迟: {blocking_time:.2f} 秒 (用户长时间空白)")
    print(f"流式首字延迟: {ttft:.2f} 秒 (立即开始输出)")
    print(f"感知体验提升: {(blocking_time - ttft) / blocking_time * 100:.1f}%")
    
    if blocking_time > 10:
        print("\n诊断结论: 阻塞式调用导致严重的用户体验问题！")
        print("建议: 立即切换到流式 API (astream_chat)")


if __name__ == "__main__":
    asyncio.run(test_blocking_vs_streaming())
