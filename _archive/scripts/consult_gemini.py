#!/usr/bin/env python3
"""与 Gemini 讨论架构决策"""

import google.generativeai as genai
import json

GEMINI_API_KEY = "AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo"
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-3-pro-preview",
    generation_config={"temperature": 0.4, "max_output_tokens": 4096},
    system_instruction="""你是 Vulcan Brain 项目的架构顾问。
你之前分析过这个项目，现在 Claude（另一个 AI 助手）提出了一些问题和不同意见。
请基于你对项目的了解，给出专业、务实的建议。
用中文回答，保持简洁有力。"""
)

discussion_prompt = """
# 架构决策讨论

## 背景
你之前对 Vulcan Brain 做了架构分析，提出了 3 阶段重构计划。
Claude 提出了一些不同意见，我们需要讨论达成共识。

## 讨论点

### 1. feishu_api.py 删除策略
**你的建议**: 立即删除 feishu_api.py
**Claude 的担忧**: 新的 feishu/ 模块是否 100% 覆盖了旧功能？直接删除风险太大

请回答：
- 你能从代码中确认 feishu/ 已经覆盖了 feishu_api.py 的所有功能吗？
- 如果不能确认，你同意先标记 deprecated 而不是直接删除吗？

### 2. Soul 模块的优先级
**你的计划**: Soul 没有被特别强调
**Claude 的观点**: 老板很在意"价值观对齐"，Soul 应该提升为一级模块，优先级应该更高

请回答：
- 你同意将 Soul 从普通功能提升为一级模块吗？
- Soul 模块应该如何约束所有 AI 输出？设计建议？

### 3. store.py 拆分顺序
**你的建议**: 拆分为多个 Repository
**Claude 的担忧**: 没有测试覆盖，直接拆分风险大

请回答：
- 应该先写测试还是先拆分？
- 如果要拆分，建议的顺序是什么？（哪个领域先拆？）

### 4. 综合时间表
Claude 提出的修订计划：
- Phase 0: 验证（确认覆盖度、调用关系）
- Phase 1: 安全清理（删 _archive、标记 deprecated）
- Phase 1.5: Soul 模块升级（优先！）
- Phase 2: 基础设施稳定化（写测试、逐步拆分 store.py）

你认为这个修订计划合理吗？有什么调整建议？

## 请给出你的回应
格式要求：
1. 对每个讨论点给出明确立场
2. 如果同意 Claude，说明为什么
3. 如果不同意，给出具体理由
4. 最后给出一个综合建议的执行清单
"""

print("=" * 60)
print("  与 Gemini 讨论架构决策")
print("=" * 60)
print("\n正在咨询 Gemini...\n")

response = model.generate_content(discussion_prompt)
print(response.text)

# 保存讨论结果
with open("/home/xinyue/vulcan-brain/docs/audits/ARCHITECTURE_DISCUSSION.md", "w") as f:
    f.write("# 架构决策讨论记录\n\n")
    f.write(f"日期: 2024-12-12\n\n")
    f.write("## Gemini 的回应\n\n")
    f.write(response.text)

print("\n" + "=" * 60)
print("讨论记录已保存到: docs/audits/ARCHITECTURE_DISCUSSION.md")
