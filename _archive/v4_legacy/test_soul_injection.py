# test_soul_injection.py - 灵魂注入系统测试
"""
测试 Vulcan Brain 的双层记忆架构:
1. 静态宪法：boss_constitution.yaml
2. 动态对齐：alignment_memory.json

验证目标：
- Boss 的教导能被记录到 alignment_memory.json
- 下次启动时，教导会自动注入到 System Prompt
"""

import asyncio
import os
from kernel_codeact import VulcanCodeActKernel
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool
from tools.alignment_tools import record_boss_feedback_tool, get_alignment_summary_tool


async def main():
    print("=" * 70)
    print("🧠 Vulcan Brain - 灵魂注入系统测试")
    print("=" * 70)
    
    # 准备工具集
    tools = [
        get_time_tool,
        remember_tool,
        recall_tool,
        record_boss_feedback_tool,
        get_alignment_summary_tool
    ]
    
    # === 阶段 1: 记录 Boss 的教导 ===
    print("\n\n📝 阶段 1: 记录 Boss 的教导")
    print("-" * 70)
    
    agent = VulcanCodeActKernel(model="qwen3-thinking", tools=tools)
    
    # 模拟 Boss 纠正场景
    response = await agent.run("""
请记录一条 Boss 的反馈：

分类: 问题处理
场景: 遇到 LlamaIndex API 错误时，我创建了简化版本
Boss 原话: "为啥要创建简单版本 架构师对你进行了严厉批评 有问题就上报问题就可以了"
核心教训: 遇到问题直接上报，不擅自创建简化版本
重要性: 5
""")
    print(f"\n🤖 回复: {response}")
    
    # === 阶段 2: 验证文件生成 ===
    print("\n\n🔍 阶段 2: 验证 alignment_memory.json 是否生成")
    print("-" * 70)
    
    alignment_file = "alignment_memory.json"
    if os.path.exists(alignment_file):
        print(f"✅ 文件已生成: {alignment_file}")
        
        # 读取并显示内容
        import json
        with open(alignment_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n记录内容预览:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"❌ 文件未生成: {alignment_file}")
    
    # === 阶段 3: 重启 Agent，验证记忆注入 ===
    print("\n\n🔄 阶段 3: 重启 Agent，验证历史教训是否被注入")
    print("-" * 70)
    
    agent_new = VulcanCodeActKernel(model="qwen3-thinking", tools=tools)
    
    # 检查 System Prompt 是否包含教训
    system_prompt = agent_new.get_system_prompt()
    
    if "遇到问题直接上报" in system_prompt:
        print("✅ 检测到教训已注入 System Prompt")
        print(f"\n相关内容片段:")
        # 查找并显示相关段落
        lines = system_prompt.split('\n')
        for i, line in enumerate(lines):
            if "遇到问题直接上报" in line or "Boss 历史教训" in line:
                # 显示前后各 3 行
                start = max(0, i - 3)
                end = min(len(lines), i + 4)
                print('\n'.join(lines[start:end]))
                break
    else:
        print("❌ 教训未注入到 System Prompt")
    
    # === 阶段 4: 测试 Agent 是否会遵循教训 ===
    print("\n\n🧪 阶段 4: 测试 Agent 行为（遇到问题时的反应）")
    print("-" * 70)
    print("场景: 询问 Agent 遇到错误时应该怎么做")
    
    response = await agent_new.run("如果你遇到一个 API 错误，应该怎么处理？")
    print(f"\n🤖 回复: {response}")
    
    # 检查回复是否提到"上报"
    if "上报" in response or "报告" in response:
        print("\n✅ Agent 正确引用了历史教训！")
    else:
        print("\n⚠️  Agent 似乎没有明确提到上报原则")
    
    # === 最终总结 ===
    print("\n\n" + "=" * 70)
    print("📊 测试总结")
    print("=" * 70)
    
    print(f"\n1. 宪法文件: {'✅ 存在' if os.path.exists('boss_constitution.yaml') else '❌ 缺失'}")
    print(f"2. 对齐记忆: {'✅ 生成' if os.path.exists(alignment_file) else '❌ 未生成'}")
    print(f"3. 记忆注入: {'✅ 成功' if '遇到问题直接上报' in system_prompt else '❌ 失败'}")
    
    print("\n🎉 灵魂注入系统测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
