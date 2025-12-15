#!/usr/bin/env python3
"""
Vulcan Brain 架构深度调研 - Gemini 版本
"""

import google.generativeai as genai
from pathlib import Path
from datetime import datetime

API_KEY = 'AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM'
genai.configure(api_key=API_KEY)

RESEARCH_PROMPT = """
# Vulcan Brain AI 架构深度调研任务

## 背景

我正在构建 **Vulcan Brain** - 一个企业级 AI 助手系统。现在需要基于实际硬件做一次深度的技术选型和架构设计。

## 硬件配置（已确认）

```yaml
GPU:
  型号: NVIDIA GeForce RTX 5090
  数量: 2 张（双卡）
  单卡显存: 32GB
  总显存: 64GB
  NVLink: 无

CPU:
  型号: AMD Ryzen Threadripper PRO 7975WX
  核心: 32 核 64 线程

内存:
  总量: 256GB DDR5

存储:
  系统盘: NVMe SSD
```

## 核心需求

### 1. 本地 LLM 推理
- 需要运行 **Thinking/CoT 模型**（思维链是刚需）
- 倾向 Qwen 系列（中文优秀）
- 需要双卡并行以运行更大模型

### 2. 多 Agent 系统
- 曾尝试 "CEO + CTO 双脑模式"：
  - CEO Agent: 战略决策、任务分解（需要 Thinking 能力）
  - CTO Agent: 代码生成、技术执行（需要 Coder 能力）
- 遇到的问题：
  - 两个 Agent 协作不顺畅
  - 通信协议不清晰
  - 状态同步困难

### 3. 高并发推理
- Ollama 并发效果差
- 需要支持多用户同时访问

### 4. 工具调用
- 需要 Agent 能调用外部工具（文件操作、代码执行、API 调用等）
- 考虑 MCP (Model Context Protocol) 或 Function Calling

## 我的痛点（已踩过的坑）

1. **MoE 模型双卡问题**
   - Qwen3 32B Thinking 是 MoE 架构
   - MoE 对双卡 Tensor Parallel 支持差
   - 只能用 Ollama + GGUF，但性能不理想

2. **量化精度损失**
   - 试过 AWQ 量化，感觉效果一般
   - 不确定 GGUF Q4/Q5/Q6 哪个最优

3. **推理引擎选择困难**
   - Ollama: 简单但并发差
   - vLLM: 高性能但配置复杂
   - SGLang: 结构化输出好但生态小

## 调研要求

### Part 1: 模型选型

请推荐适合我硬件的模型组合，回答：

1. **主力 Thinking 模型**
   - 哪个开源模型的 Thinking/CoT 能力最强？
   - 能否跑满 64GB 显存？用什么量化？
   - Qwen3 vs DeepSeek-R1 vs 其他？

2. **代码生成模型**
   - 独立部署还是和 Thinking 模型合一？
   - Qwen2.5-Coder vs DeepSeek-Coder vs 其他？

3. **轻量模型（可选）**
   - 是否需要一个小模型做路由/分类？
   - 推荐哪个？

### Part 2: 推理引擎选型

1. **vLLM vs SGLang vs Ollama**
   - 基于我的硬件，哪个最优？
   - MoE 模型双卡支持情况？
   - 具体部署命令？

2. **量化方案**
   - GGUF vs AWQ vs GPTQ，哪个最适合 RTX 5090？
   - 推荐的量化级别？

### Part 3: 多 Agent 架构设计

1. **Agent 编排框架**
   - LangGraph vs AutoGen vs CrewAI vs 自研？
   - 推荐架构图（Mermaid）

2. **CEO + CTO 模式优化**
   - 两个 Agent 应该如何分工？
   - 通信协议设计（JSON Schema？自然语言？）
   - 共享上下文如何管理？
   - 任务分解和结果合并策略

3. **工具调用方案**
   - MCP vs Function Calling？
   - 推荐的工具集设计

### Part 4: 完整架构方案

请给出一个完整的系统架构设计，包括：

1. **架构图**（Mermaid 格式）
2. **组件清单**
3. **部署配置**（Docker Compose 或具体命令）
4. **数据流设计**
5. **预估性能指标**

## 输出格式

请按以下结构输出：

```markdown
# Vulcan Brain 架构设计方案

## Executive Summary
[一句话总结推荐方案]

## Part 1: 模型选型
### 推荐组合
### 备选方案
### 选型理由

## Part 2: 推理引擎
### 推荐方案
### 部署配置
### 性能预估

## Part 3: Agent 架构
### 架构图
### 组件设计
### 通信协议

## Part 4: 完整方案
### 系统架构图
### 部署清单
### 实施步骤

## 风险与建议
```

## 特别要求

1. **必须联网搜索 2024-2025 最新信息**
2. **以社区实践为准**（Reddit r/LocalLLaMA, GitHub Issues, HuggingFace）
3. **给出具体可执行的命令和配置**
4. **标注信息来源**
"""

def main():
    print("=" * 70)
    print("  Vulcan Brain 架构深度调研")
    print("  Gemini 2.0 Flash")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 70)
    print("\n正在进行深度调研，预计需要 2-3 分钟...\n")

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction="""你是顶尖的 AI 基础设施架构师。
你必须联网搜索获取 2024-2025 年最新的信息。
以社区实践（Reddit r/LocalLLaMA, GitHub, HuggingFace）为准。
给出具体的、可执行的技术方案和配置。
必须标注信息来源。"""
    )

    response = model.generate_content(
        RESEARCH_PROMPT,
        generation_config={
            'temperature': 0.3,
            'max_output_tokens': 20000
        }
    )

    print(response.text)

    # Save report
    output_path = Path.home() / 'vulcan-brain' / 'docs' / 'audits' / 'ARCHITECTURE_RESEARCH_GEMINI.md'

    content = f"""# Vulcan Brain 架构调研报告 - Gemini 版本

Generated: {datetime.now().isoformat()}
Model: gemini-2.0-flash

---

{response.text}
"""
    output_path.write_text(content)
    print(f"\n{'=' * 70}")
    print(f"Report saved: {output_path}")

if __name__ == '__main__':
    main()
