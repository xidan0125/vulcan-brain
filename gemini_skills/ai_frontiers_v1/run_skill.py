#!/usr/bin/env python3
"""
AI Frontiers Skill - Agent 架构专家
支持联网搜索 + 本地知识库
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types

# 配置
API_KEY = 'AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM'
SKILL_DIR = Path(__file__).parent
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / ".knowledge" / "ai-frontiers"


def load_system_prompt():
    """加载系统提示词"""
    prompt_file = SKILL_DIR / "system_prompt.md"
    return prompt_file.read_text(encoding='utf-8')


def load_knowledge_base():
    """加载知识库"""
    kb_file = KNOWLEDGE_DIR / "digests" / "_combined_knowledge.json"
    if kb_file.exists():
        data = json.loads(kb_file.read_text(encoding='utf-8'))
        # 提取核心概念作为上下文
        context_parts = []
        for section_key, section_data in data.items():
            if isinstance(section_data, dict) and 'core_concepts' in section_data:
                title = section_data.get('title', section_key)
                context_parts.append(f"\n## {title}\n")
                for concept in section_data['core_concepts'][:5]:  # 取前5个概念
                    context_parts.append(f"- **{concept['name']}**: {concept['definition']}")
        return "\n".join(context_parts)
    return ""


def run_skill(task: str, use_search: bool = True, save_to: str = None):
    """执行 AI Frontiers 技能"""
    client = genai.Client(api_key=API_KEY)
    
    # 准备工具
    tools = []
    if use_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    
    # 加载系统提示和知识库
    system_prompt = load_system_prompt()
    knowledge_context = load_knowledge_base()
    
    full_prompt = f"""
{system_prompt}

## 内置知识库摘要
{knowledge_context}

## 当前任务
{task}

请结合知识库内容和联网搜索（如需要）给出专业解答。优先使用 2025 年最新信息。
"""
    
    print("=" * 60)
    print("🧠 AI Frontiers Skill - Agent Architecture Expert")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    if use_search:
        print("\n🔍 启用联网搜索...\n")
    
    config = types.GenerateContentConfig(
        temperature=0.4,
        max_output_tokens=16000
    )
    if tools:
        config = types.GenerateContentConfig(
            tools=tools,
            temperature=0.4,
            max_output_tokens=16000
        )
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=full_prompt,
        config=config
    )
    
    print(response.text)
    
    # 打印搜索来源
    if use_search and hasattr(response, 'candidates') and response.candidates:
        print("\n" + "=" * 60)
        print("📚 参考来源:")
        for candidate in response.candidates:
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                gm = candidate.grounding_metadata
                if hasattr(gm, 'grounding_chunks'):
                    for chunk in gm.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            print(f"  - {chunk.web.title}: {chunk.web.uri}")
    
    # 保存结果
    if save_to:
        output = f"""# AI Frontiers Expert Report

Generated: {datetime.now().isoformat()}
Task: {task[:100]}...

---

{response.text}
"""
        Path(save_to).write_text(output, encoding='utf-8')
        print(f"\n📄 报告已保存: {save_to}")
    
    return response.text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_skill.py '<task>' [--no-search] [--save output.md]")
        print("")
        print("Examples:")
        print("  python run_skill.py '设计一个多 Agent 客服系统'")
        print("  python run_skill.py '对比 MCP 和传统 Function Calling' --no-search")
        print("  python run_skill.py '2025年最新的Agent框架有哪些' --save report.md")
        sys.exit(1)
    
    task = sys.argv[1]
    use_search = "--no-search" not in sys.argv
    
    save_to = None
    if "--save" in sys.argv:
        save_idx = sys.argv.index("--save")
        if save_idx + 1 < len(sys.argv):
            save_to = sys.argv[save_idx + 1]
    
    run_skill(task, use_search=use_search, save_to=save_to)
