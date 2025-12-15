#!/usr/bin/env python3
"""
全息数据底座架构师 Agent
调用 Gemini 3 Pro Preview 生成架构设计和工程规划文档
"""

import os
import json
import requests
from pathlib import Path

# 配置
API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
MODEL = "gemini-3-pro-preview"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# 路径
AGENT_DIR = Path(__file__).parent.parent
CONTEXT_DIR = AGENT_DIR / "context"
OUTPUT_DIR = AGENT_DIR.parent / "architecture"

def load_file(path):
    """加载文件内容"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def load_context():
    """加载所有上下文"""
    system_prompt = load_file(AGENT_DIR / "SYSTEM_PROMPT.md")
    research_summary = load_file(CONTEXT_DIR / "research_summary.md")
    v2_status = load_file(CONTEXT_DIR / "v2_status.md")
    data_sample = load_file(CONTEXT_DIR / "data_sample.json")
    
    return f"""
{system_prompt}

---

# 上下文数据

## 研究文档摘要
{research_summary}

## V2现状
{v2_status}

## 数据样本
```json
{data_sample}
```
"""

def call_gemini(prompt, task_description):
    """调用Gemini API"""
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 8192
        }
    }
    
    print(f"\n🚀 正在调用 Gemini {MODEL}...")
    print(f"📋 任务: {task_description}")
    
    response = requests.post(
        f"{API_URL}?key={API_KEY}",
        headers=headers,
        json=payload,
        timeout=120
    )
    
    if response.status_code != 200:
        print(f"❌ API错误: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    
    if "candidates" in result and len(result["candidates"]) > 0:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return text
    
    print("❌ 无有效响应")
    return None

def generate_architecture_design():
    """生成架构设计文档"""
    context = load_context()
    
    prompt = f"""
{context}

---

# 当前任务

请生成 **架构设计文档 (architecture_design.md)**，包含以下内容:

1. **技术栈最终决策**
   - 在 KùzuDB vs Neo4j vs MongoDB 中选择图/文档存储方案
   - 在 SGLang vs vLLM 中选择推理引擎
   - 向量存储方案
   - 给出选择理由

2. **数据模型最终Schema**
   - Event 结构
   - Fact 结构  
   - Provenance 结构
   - 完整JSON Schema示例

3. **系统架构图**
   - 使用 Mermaid 或 ASCII 绘制
   - 展示数据流和模块关系

4. **模块划分**
   - 附件下载模块
   - VLM提取模块
   - 事实融合模块
   - 冲突仲裁模块
   - 存储模块
   - 查询模块

5. **接口设计**
   - 核心API端点
   - 输入输出格式

请直接输出Markdown格式的文档内容，不要有多余的解释。
"""
    
    return call_gemini(prompt, "生成架构设计文档")

def generate_engineering_plan():
    """生成工程规划文档"""
    context = load_context()
    
    prompt = f"""
{context}

---

# 当前任务

请生成 **工程规划文档 (engineering_plan.md)**，包含以下内容:

1. **五步策略详细实施计划**

   对于每个Phase，给出:
   - 具体任务列表
   - 输入和输出
   - 验收标准
   - 预计工作量

   Phase 1: 调查 (已完成，简要总结)
   Phase 2: Schema (详细)
   Phase 3: 提取 (详细)
   Phase 4: 构建 (详细)
   Phase 5: 开发 (详细)

2. **PoC验证方案**
   - 选择1封典型邮件+PDF附件
   - 端到端验证流程
   - 成功标准

3. **风险识别与应对**
   - 技术风险
   - 数据风险
   - 资源风险
   - 应对策略

4. **里程碑定义**
   - 关键检查点
   - 交付物清单

5. **工具和脚本清单**
   - 需要开发的Python脚本
   - 配置文件
   - 测试用例

请直接输出Markdown格式的文档内容，不要有多余的解释。
"""
    
    return call_gemini(prompt, "生成工程规划文档")

def save_output(content, filename):
    """保存输出到文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已保存: {output_path}")
    return output_path

def main():
    print("=" * 60)
    print("🏗️  全息数据底座架构师 Agent")
    print("=" * 60)
    
    # 生成架构设计
    print("\n[1/2] 生成架构设计文档...")
    arch_content = generate_architecture_design()
    if arch_content:
        save_output(arch_content, "architecture_design.md")
    else:
        print("❌ 架构设计生成失败")
    
    # 生成工程规划
    print("\n[2/2] 生成工程规划文档...")
    plan_content = generate_engineering_plan()
    if plan_content:
        save_output(plan_content, "engineering_plan.md")
    else:
        print("❌ 工程规划生成失败")
    
    print("\n" + "=" * 60)
    print("✨ Agent任务完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
