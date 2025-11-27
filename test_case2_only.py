# test_case2_only.py - 单独测试用例 2（修复后）
import asyncio
import os
import json
from kernel_codeact import VulcanCodeActKernel
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool
from tools.alignment_tools import record_boss_feedback_tool
from tools.boss_insight_tool import save_boss_insight_tool

async def main():
    print("=" * 80)
    print("🧪 测试用例 2 (重试): 动态对齐 - 记录老板观点")
    print("=" * 80)
    
    tools = [
        get_time_tool,
        remember_tool,
        recall_tool,
        record_boss_feedback_tool,
        save_boss_insight_tool
    ]
    
    agent = VulcanCodeActKernel(model="qwen3-thinking", tools=tools)
    
    query = "老板说：对于明年的预算，我们要激进一点，投入研发。把这句话记下来。"
    
    print(f"\n📋 输入: {query}")
    print("\n预期行为:")
    print("  - 调用 save_boss_insight(topic='2026预算', insight='要激进投入研发')")
    print("  - alignment_memory.json 生成记录")
    print("-" * 80)
    
    response = await agent.run(query)
    
    print(f"\n🤖 Agent 回复:\n{response}")
    
    # 验证
    print("\n📊 验证结果:")
    
    alignment_file = "alignment_memory.json"
    if os.path.exists(alignment_file):
        print(f"✅ {alignment_file} 存在")
        
        with open(alignment_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        budget_records = [
            entry for entry in data 
            if "预算" in entry.get('situation', '') or "预算" in entry.get('boss_feedback', '')
        ]
        
        if budget_records:
            print(f"✅ 找到 {len(budget_records)} 条预算相关记录")
            print("\n最新记录:")
            print(json.dumps(budget_records[-1], ensure_ascii=False, indent=2))
        else:
            print("❌ 未找到预算相关记录")
    else:
        print(f"❌ {alignment_file} 不存在")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
