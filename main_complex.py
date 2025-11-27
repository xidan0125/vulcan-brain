# main.py
import asyncio
from kernel import VulcanCodeKernel
from tools.function_tools import get_time_tool

async def main():
    # 1. 准备工具
    tools = [get_time_tool]
    
    # 2. 启动原生内核
    agent = VulcanCodeKernel(model="qwen3-thinking", tools=tools)
    
    # 3. 执行复杂测试 - 架构师的场景
    response = await agent.run("帮我查查现在上海几点，然后计算一下再过 18888 秒是几点？")
    print(f"\n🤖 最终回复: {response}")

if __name__ == "__main__":
    asyncio.run(main())
