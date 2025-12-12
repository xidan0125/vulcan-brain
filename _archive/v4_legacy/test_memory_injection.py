# test_memory_injection.py - 验证记忆注入功能
import asyncio
from kernel import VulcanCodeKernel
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool

async def main():
    print("=" * 60)
    print("记忆注入测试 - Agent 是否'生来就知道'用户偏好？")
    print("=" * 60)
    
    # 准备工具
    tools = [get_time_tool, remember_tool, recall_tool]
    
    # === 测试场景：无需调用 recall_info，直接回答 ===
    print("\n📋 测试问题: 我的项目叫什么名字？")
    print("期望: Agent 直接从 System Prompt 中的【长期记忆】回答")
    print("-" * 60)
    
    agent = VulcanCodeKernel(model="qwen3-thinking", tools=tools)
    response = await agent.run("我的项目叫什么名字？")
    print(f"\n🤖 回复: {response}")
    
    # === 验证 System Prompt 是否包含记忆 ===
    print("\n\n🔍 验证：System Prompt 是否包含记忆？")
    print("-" * 60)
    if "project_name: Vulcan Brain" in agent.system_prompt:
        print("✅ 检测到记忆注入：project_name: Vulcan Brain")
    else:
        print("❌ 记忆未注入到 System Prompt")
    
    if "favorite_drink: 拿铁咖啡" in agent.system_prompt:
        print("✅ 检测到记忆注入：favorite_drink: 拿铁咖啡")
    else:
        print("❌ 记忆未注入到 System Prompt")
    
    print("\n\n✅ 记忆注入测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
