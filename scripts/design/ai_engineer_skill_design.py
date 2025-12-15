#!/usr/bin/env python3
"""
AI Engineer Skill 设计咨询
"""

import google.generativeai as genai
from pathlib import Path
from datetime import datetime

API_KEY = 'AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo'
MODEL = 'gemini-3-pro-preview'

genai.configure(api_key=API_KEY)

CONTEXT = """
# AI Engineer Skill 设计咨询

## 背景
我们正在为 Vulcan Brain 系统开发一套 Gemini Skills。已有：
- product_architect_v1: 产品架构设计
- product_analyst_v1: 产品分析

现在需要开发 **ai_engineer_v1** skill，专注于 LLM/Agent 技术栈。

## 当前系统现状
- **双 LLM 架构**:
  - CEO (Ollama qwen3:30b-a3b) - 决策、规划
  - CTO (SGLang Qwen2.5-Coder-32B) - 代码生成
- **通信方式**: 文本解析，脆弱
- **Soul 系统**: 刚完成重构，需要与 LLM 层集成

## AI Engineer Skill 需要覆盖的知识领域

### 1. Agent 编排
- 单 Agent vs 多 Agent
- Agent 通信协议（消息队列、直接调用）
- 任务分解与协调
- 错误恢复与重试

### 2. 工具调用
- OpenAI Function Calling
- Anthropic Tool Use
- MCP (Model Context Protocol)
- 自定义工具注册

### 3. 推理引擎选型
- Ollama (本地简单部署)
- vLLM (高吞吐)
- SGLang (结构化生成)
- TensorRT-LLM (NVIDIA 优化)
- llama.cpp (边缘设备)

### 4. 开源模型选型
- Qwen 系列 (通用、Coder、VL)
- Llama 系列 (Meta)
- DeepSeek (代码、数学)
- Mistral/Mixtral
- 国产模型 (GLM, Yi, Baichuan)

### 5. 联网调研能力
- HuggingFace 模型排行榜
- GitHub trending
- arXiv 最新论文
- 开源社区动态

### 6. 其他重要领域
- 上下文管理 (长对话、记忆)
- Prompt Engineering
- RAG 架构
- 成本优化 (Token、缓存)
- 评估与监控

## 问题

1. **Skill 结构设计**: 这个 AI Engineer skill 应该包含哪些文件？system_prompt 应该如何组织？

2. **知识更新机制**: 如何保持对最新开源动态的了解？是否需要联网搜索能力？

3. **与 Soul 系统的集成**: AI Engineer 如何帮助设计 Soul 与 LLM 的集成方案？

4. **输出格式**: 这个 skill 的典型输出应该是什么？代码？架构图？选型报告？

5. **实际应用场景**: 列举 3-5 个这个 skill 会被调用的典型场景

6. **你认为我遗漏了什么重要的知识领域？**

请给出详细的设计建议。
"""

def main():
    print("=" * 60)
    print("  AI Engineer Skill 设计咨询")
    print("=" * 60)

    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction="你是资深 AI 基础设施工程师，精通 LLM 部署、Agent 开发、开源模型生态。"
    )

    # 启用联网搜索
    response = model.generate_content(
        CONTEXT,
        generation_config={
            'temperature': 0.7,
            'max_output_tokens': 8000
        },
        tools=[{"google_search_retrieval": {}}]  # 启用搜索
    )

    print("\n" + response.text)

    # 保存结果
    output_path = Path.home() / 'vulcan-brain' / 'docs' / 'audits' / 'AI_ENGINEER_SKILL_DESIGN.md'

    content = f"""# AI Engineer Skill 设计方案

Generated: {datetime.now().isoformat()}

---

{response.text}
"""
    output_path.write_text(content)
    print(f"\n✓ 设计方案已保存: {output_path}")

if __name__ == '__main__':
    main()
