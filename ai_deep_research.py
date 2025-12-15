#!/usr/bin/env python3
import google.generativeai as genai
from pathlib import Path
from datetime import datetime

API_KEY = 'AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM'
genai.configure(api_key=API_KEY)

RESEARCH_TASK = """
# AI Engineer 深度调研任务

## 背景
我是 Vulcan Brain 系统的 AI 工程师。现在是 2025年12月13日。
请联网搜索 2024-2025 年最新的 LLM 部署和 Agent 开发实践。

## 硬件配置
- GPU: NVIDIA RTX 5090 32GB x 2 (双卡)
- CPU: AMD Threadripper PRO 7975WX 32核64线程
- RAM: 256GB DDR5

## 我的实际痛点

### 1. MoE 模型双卡部署问题
- Qwen3 32B thinking 是 MoE 模型，很聪明有思维链
- 但 MoE 对双卡支持很差，只能用 Ollama 跑 GGUF
- 请搜索: 2025年 vLLM/SGLang 对 MoE 双卡的支持情况？有什么新方案？

### 2. 思维链(Thinking/CoT)模型是刚需
- 现在 thinking 能力已经是刚需
- 请搜索: 2025年哪些开源模型支持 thinking？QwQ? DeepSeek-R1? 部署方案？

### 3. Ollama 高并发问题
- Ollama 并发效果不好
- 请搜索: 2025年生产环境推理引擎对比？SGLang vs vLLM 最新性能？

### 4. CEO+CTO 双脑模式
- 尝试过但效果不理想
- 请搜索: 2025年多 Agent 编排最佳实践？社区成功案例？

### 5. 量化方案
- AWQ 效果一般
- 请搜索: 2025年最佳量化方案？GGUF vs AWQ vs GPTQ？

## 要求
1. 必须基于联网搜索的最新信息
2. 以 Reddit r/LocalLLaMA、GitHub、HuggingFace 社区实践为准
3. 给出具体可执行的建议（命令、配置）
4. 标注信息来源
"""

print("=" * 60)
print("  AI Engineer 深度联网调研")
print("  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
print("=" * 60)
print("\n正在联网调研，请稍候...\n")

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction="你是顶尖 AI 基础设施工程师。必须联网搜索 2024-2025 最新信息，以社区实践为准。给出具体可执行的建议。"
)

response = model.generate_content(
    RESEARCH_TASK,
    generation_config={"temperature": 0.3, "max_output_tokens": 12000}
)

print(response.text)

output_path = Path.home() / "vulcan-brain" / "docs" / "audits" / "AI_ENGINEER_DEEP_RESEARCH.md"
content = f"# AI Engineer 深度调研报告\n\nGenerated: {datetime.now().isoformat()}\n\n---\n\n{response.text}"
output_path.write_text(content)
print("\n" + "=" * 60)
print(f"Report saved: {output_path}")
