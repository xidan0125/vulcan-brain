# test_memory.py - Phase 3 记忆系统测试
import asyncio
from kernel import VulcanCodeKernel
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool

async def main():
    print("=" * 60)
    print("Phase 3 - Vulcan Brain 记忆系统测试")
    print("=" * 60)
    
    # 1. 准备工具（包含时间工具 + 记忆工具）
    tools = [
        get_time_tool,
        remember_tool,
        recall_tool
    ]
    
    # 2. 启动内核
    agent = VulcanCodeKernel(model="qwen3-thinking", tools=tools)
    
    # === 测试 1: 记住信息 ===
    print("\n\n📝 测试 1: 记住用户信息")
    print("-" * 60)
    response = await agent.run("请记住：我的项目名称是 Vulcan Brain，我喜欢喝拿铁咖啡。")
    print(f"\n🤖 回复: {response}")
    
    # === 测试 2: 回忆信息 ===
    print("\n\n🧠 测试 2: 回忆之前的信息")
    print("-" * 60)
    response = await agent.run("你还记得我的项目叫什么名字吗？")
    print(f"\n🤖 回复: {response}")
    
    # === 测试 3: 记忆持久化验证 ===
    print("\n\n🔄 测试 3: 重新启动 Agent，验证记忆是否被注入")
    print("-" * 60)
    agent_new = VulcanCodeKernel(model="qwen3-thinking", tools=tools)
    response = await agent_new.run("我喜欢喝什么？")
    print(f"\n🤖 回复: {response}")
    
    print("\n\n✅ Phase 3 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
