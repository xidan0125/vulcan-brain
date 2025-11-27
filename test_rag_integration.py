# test_rag_integration.py - RAG 集成测试
"""
架构师指定测试: 让 Agent 查阅本地文档
"""

import asyncio
from kernel_codeact import VulcanCodeActKernel
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool
from tools.alignment_tools import record_boss_feedback_tool
from tools.boss_insight_tool import save_boss_insight_tool
from tools.rag_tools import add_document_tool, search_knowledge_tool, RAG_AVAILABLE


async def main():
    print("=" * 80)
    print("🧪 RAG 集成测试 - 架构师指定场景")
    print("=" * 80)
    
    if not RAG_AVAILABLE:
        print("\n❌ RAG 功能不可用，测试终止")
        return
    
    # 准备完整工具集
    tools = [
        get_time_tool,
        remember_tool,
        recall_tool,
        record_boss_feedback_tool,
        save_boss_insight_tool,
        add_document_tool,        # [NEW] RAG 工具
        search_knowledge_tool,    # [NEW] RAG 工具
    ]
    
    agent = VulcanCodeActKernel(model="qwen3-thinking", tools=tools)
    
    # === 阶段 1: 添加文档到知识库 ===
    print("\n\n📝 阶段 1: 添加文档到知识库")
    print("-" * 80)
    
    doc_content = """
    Vulcan Brain v2.0 架构说明
    
    本系统采用五层汉堡架构:
    - Layer 1 (交互表现层): UI 界面、指令接收
    - Layer 2 (认知内核层): kernel_codeact.py，负责思考、规划、代码执行
    - Layer 3 (价值观对齐层): 宪法(boss_constitution.yaml) + 动态对齐(alignment_memory.json)
    - Layer 4 (能力工具层): RAG、时间工具等业务功能
    - Layer 5 (基础设施层): Ollama + 双 RTX 5090
    
    核心特点:
    1. CodeAct 范式: 模型通过编写 Python 代码调用工具
    2. 极简内核: 仅 163 行代码
    3. 价值观驱动: 加载 Boss 的宪法和教导
    """
    
    response = await agent.run(f"""
请把以下文档添加到知识库:

标题: Vulcan Brain 架构文档
内容:
{doc_content}
""")
    print(f"\n🤖 Agent 回复: {response}")
    
    # === 阶段 2: 查询知识库 ===
    print("\n\n🔍 阶段 2: 查询知识库")
    print("-" * 80)
    
    response = await agent.run("Vulcan Brain 的核心架构有几层？每一层叫什么名字？")
    print(f"\n🤖 Agent 回复: {response}")
    
    # === 阶段 3: 摘要查询 ===
    print("\n\n📊 阶段 3: 摘要查询")
    print("-" * 80)
    
    response = await agent.run("总结一下 Vulcan Brain 的核心特点")
    print(f"\n🤖 Agent 回复: {response}")
    
    print("\n\n" + "=" * 80)
    print("✅ RAG 集成测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
