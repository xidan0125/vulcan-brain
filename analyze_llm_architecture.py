#!/usr/bin/env python3
"""分析 LLM 和 Agent 架构"""

import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo"
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-3-pro-preview",
    generation_config={"temperature": 0.3, "max_output_tokens": 4096},
    system_instruction="你是 AI 系统架构专家，精通 LLM 应用和 Agent 编排设计。用中文回答。"
)

# 读取关键文件
import os
from pathlib import Path

root = Path("/home/xinyue/vulcan-brain")
files_to_analyze = [
    "config.py",
    "kernel_bicameral_v5.py", 
    "bicameral_api.py",
    "vulcan_libs/ai_service.py",
    "vulcan_libs/ceo_soul.py",
]

context = "# Vulcan Brain LLM/Agent 架构分析\n\n"
for f in files_to_analyze:
    fp = root / f
    if fp.exists():
        content = fp.read_text()[:8000]  # 限制大小
        context += f"## File: {f}\n```python\n{content}\n```\n\n"

prompt = context + """
请分析以上代码，回答：

## 1. 当前 LLM 选型现状
- 用了哪些模型？各自用途？
- 模型配置是否统一管理？

## 2. Agent 编排架构
- 当前的 Agent 模式是什么？（如 ReAct, Bicameral, etc.）
- 架构的优点和问题？

## 3. 建议的标准化方案
- LLM 调用应该如何统一？
- Agent 编排应该如何优化？
- 需要创建哪些新模块？

## 4. 优先级排序
- 给出 3-5 个具体的改进任务，按优先级排序

请用结构化的格式输出。
"""

print("=" * 60)
print("  LLM/Agent 架构分析")
print("=" * 60)
print("\n正在分析...\n")

response = model.generate_content(prompt)
print(response.text)

# 保存
with open(root / "docs/audits/LLM_AGENT_ANALYSIS.md", "w") as f:
    f.write("# LLM/Agent 架构分析报告\n\n")
    f.write(response.text)

print("\n报告已保存: docs/audits/LLM_AGENT_ANALYSIS.md")
