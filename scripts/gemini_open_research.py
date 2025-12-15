#!/usr/bin/env python3
"""Vulcan Brain Open Research - Gemini"""

import google.generativeai as genai
from pathlib import Path
from datetime import datetime

API_KEY = 'AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM'
genai.configure(api_key=API_KEY)

PROMPT = """
# Vulcan Brain AI 系统架构 - Open Research

## 任务

你是一名独立的 AI 基础设施顾问。请基于 **2025年12月** 的最新信息，为以下硬件配置设计最优的本地 AI 系统架构。

**要求：不带任何预设立场，完全基于社区实践和性能数据做推荐。**

## 硬件配置

```
GPU: NVIDIA GeForce RTX 5090 × 2
     - 单卡显存: 32GB
     - 总显存: 64GB
     - 无 NVLink

CPU: AMD Ryzen Threadripper PRO 7975WX
     - 32 核 64 线程

RAM: 256GB DDR5

存储: NVMe SSD
```

## 系统目标

构建一个企业级 AI 助手系统，需要：

1. **思维链推理能力** - 复杂任务分解、多步推理
2. **代码生成能力** - 高质量代码编写和重构
3. **多 Agent 协作** - 多个专业 Agent 协同工作
4. **高并发服务** - 支持多用户同时访问
5. **工具调用** - Agent 能操作文件、执行代码、调用 API

## 已踩过的坑（供参考）

- MoE 架构模型在双卡上的 Tensor Parallel 支持不佳
- Ollama 的并发处理能力有限
- 某些量化方案（如 AWQ）在实际使用中精度损失明显

## 调研问题

### Q1: 模型选型

**完全开放调研，不限定任何厂商或系列。**

请回答：
- 2025年12月，哪些开源模型的思维链(Thinking/CoT)能力最强？
- 哪些开源模型的代码生成能力最强？
- 基于 64GB 总显存，推荐哪些模型组合？
- Dense 模型 vs MoE 模型，哪个更适合双卡无 NVLink 配置？

### Q2: 推理引擎

请对比 2025年12月 主流推理引擎：
- vLLM
- SGLang
- TensorRT-LLM
- Ollama
- llama.cpp
- 其他新兴引擎？

评估维度：
- 双卡支持（特别是无 NVLink）
- MoE 模型支持
- 并发性能
- 部署复杂度
- 社区活跃度

### Q3: 量化方案

2025年最优量化方案是什么？
- GGUF (Q4/Q5/Q6/Q8)
- AWQ
- GPTQ
- 其他新方案？

哪种量化在 RTX 5090 上性能最好？精度损失最小？

### Q4: 多 Agent 架构

如何设计高效的多 Agent 系统？
- 单模型多角色 vs 多模型分工？
- Agent 间通信协议设计？
- 主流框架对比（LangGraph, AutoGen, CrewAI, 其他？）
- 共享上下文管理？

### Q5: 完整架构设计

请给出：
1. 推荐的完整技术栈
2. 系统架构图（Mermaid 格式）
3. 具体部署配置和命令
4. 预估性能指标

## 输出要求

1. **必须标注信息来源**（Reddit 帖子、GitHub Issue、HuggingFace 讨论等）
2. **给出具体的命令和配置**，可直接执行
3. **列出不确定的点**，标明需要进一步验证
4. **不要编造信息**，如果搜索不到就说明

## 搜索关键词建议

- "RTX 5090 LLM inference 2025"
- "dual GPU no NVLink vLLM"
- "best open source reasoning model December 2025"
- "MoE tensor parallel dual GPU"
- "vLLM vs SGLang benchmark 2025"
- "multi agent framework production 2025"
"""

print("=" * 70)
print("  Vulcan Brain Open Research")
print("  Gemini 2.0 Flash | " + datetime.now().strftime("%Y-%m-%d %H:%M"))
print("=" * 70)
print("\nSearching latest info (Dec 2025)...\n")

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction="You are an independent AI infrastructure consultant. Search for the latest information from December 2025. Be objective, cite sources, and give specific executable commands. If you cannot find information, say so honestly."
)

response = model.generate_content(
    PROMPT,
    generation_config={'temperature': 0.2, 'max_output_tokens': 20000}
)

print(response.text)

out = Path.home() / 'vulcan-brain' / 'docs' / 'audits' / 'OPEN_RESEARCH_GEMINI.md'
out.write_text(f"# Vulcan Brain Open Research - Gemini\n\nGenerated: {datetime.now().isoformat()}\n\n---\n\n{response.text}")
print(f"\n{'=' * 70}\nSaved: {out}")
