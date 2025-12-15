#!/usr/bin/env python3
"""
AI Engineer Skill Runner - 支持联网搜索
"""

import sys
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types

# 配置
API_KEY = 'AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM'
SKILL_DIR = Path(__file__).parent

def load_system_prompt():
    """加载系统提示词"""
    prompt_file = SKILL_DIR / "system_prompt.md"
    return prompt_file.read_text(encoding='utf-8')

def run_research(task: str, save_to: str = None):
    """执行调研任务"""
    client = genai.Client(api_key=API_KEY)
    google_search_tool = types.Tool(google_search=types.GoogleSearch())
    
    system_prompt = load_system_prompt()
    
    # 读取硬件配置作为上下文
    hw_config = (SKILL_DIR / "HARDWARE_CONFIG.md").read_text(encoding='utf-8')
    
    full_prompt = f"""
{system_prompt}

## 硬件配置详情
{hw_config}

## 当前任务
{task}

请联网搜索 2025年12月最新信息，给出详细方案。
"""
    
    print("=" * 60)
    print("🔧 AI Engineer Skill - Research Mode")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print("\n🔍 正在联网搜索...\n")
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0.3,
            max_output_tokens=16000
        )
    )
    
    print(response.text)
    
    # 打印来源
    print("\n" + "=" * 60)
    print("📚 参考来源:")
    if hasattr(response, 'candidates') and response.candidates:
        for candidate in response.candidates:
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                gm = candidate.grounding_metadata
                if hasattr(gm, 'grounding_chunks'):
                    for chunk in gm.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            print(f"  - {chunk.web.title}: {chunk.web.uri}")
    
    # 保存结果
    if save_to:
        output = f"""# AI Engineer Research Report

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
        print("Usage: python run_research.py '<task>' [output_file]")
        sys.exit(1)
    
    task = sys.argv[1]
    save_to = sys.argv[2] if len(sys.argv) > 2 else None
    run_research(task, save_to)
