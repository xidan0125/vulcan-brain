#!/usr/bin/env python3
"""
Vulcan Brain - Gemini 3 Pro 全面审查工具 (Pro Edition v2)

Best Practices:
1. Schema 约束 - 强制结构化 JSON 输出
2. temperature=0 - 确定性输出
3. BLOCK_NONE - 安全过滤全关（代码审查需要）
4. system_instruction - 严厉 CTO 人设
5. Google Search Grounding - 联网获取最新技术
6. Batch Mode - 半价异步处理大型任务
"""

import os
import json
import argparse
import time
from pathlib import Path
from datetime import datetime

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    print("请先安装: pip install google-generativeai")
    exit(1)

# === 配置 ===
GEMINI_API_KEY = "AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo"
MODEL_NAME = "gemini-3-pro-preview"
OUTPUT_DIR = Path.home() / "vulcan-brain" / "docs" / "audits"

# === 安全设置：全部关闭（代码审查需要） ===
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# === 严厉 CTO 人设 ===
SYSTEM_INSTRUCTION = """
你是 Vulcan Brain 系统的首席架构师 (Chief Architect)。

## 性格特征
- 极其严厉，痛恨冗余代码和不安全的逻辑
- 追求卓越，不接受"能跑就行"的心态
- 直接犀利，用数据说话
- 实战派，每个建议必须配具体代码

## 目标
协助用户构建企业级、可扩展的 AI Agent 系统。

## 输出规范
- 指出问题时必须给出：文件路径、行号、问题描述、修复代码
- 给出风险评分 (0-100) 和技术债评分 (0-100)
- 输出严格符合 JSON Schema，不要 Markdown 格式

## 系统背景
Vulcan Brain 是"本地 Qwen + 云端 Claude/Gemini"混合架构的企业级 AI 管理系统：
- 后端：Python FastAPI
- 前端：Next.js + 飞书机器人
- 核心：记忆系统、LightRAG 知识库、MCP Tools、Info Hub
"""

# === JSON Schema (Gemini 兼容) ===
AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning_process": {"type": "string"},
        "overall_health_score": {"type": "integer"},
        "tech_debt_score": {"type": "integer"},
        "architecture_review": {
            "type": "object",
            "properties": {
                "risk_score": {"type": "integer"},
                "brain_split_risk": {"type": "string"},
                "data_flow_issues": {"type": "array", "items": {"type": "string"}},
                "mermaid_diagram": {"type": "string"}
            }
        },
        "code_smells": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "line_number": {"type": "string"},
                    "smell_type": {"type": "string"},
                    "severity": {"type": "string"},
                    "description": {"type": "string"},
                    "fix_code": {"type": "string"}
                }
            }
        },
        "ai_brain_review": {
            "type": "object",
            "properties": {
                "memory_issues": {"type": "array", "items": {"type": "string"}},
                "prompt_issues": {"type": "array", "items": {"type": "string"}},
                "rag_issues": {"type": "array", "items": {"type": "string"}},
                "token_waste_estimate": {"type": "string"}
            }
        },
        "security_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "issue_type": {"type": "string"},
                    "severity": {"type": "string"},
                    "description": {"type": "string"},
                    "fix_suggestion": {"type": "string"}
                }
            }
        },
        "top5_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "integer"},
                    "task_name": {"type": "string"},
                    "problem_description": {"type": "string"},
                    "affected_files": {"type": "array", "items": {"type": "string"}},
                    "solution_approach": {"type": "string"},
                    "implementation_code": {"type": "string"},
                    "expected_benefit": {"type": "string"},
                    "claude_directive": {"type": "string"}
                }
            }
        }
    }
}


def setup_genai():
    """初始化 Gemini API"""
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"✓ Gemini API 配置完成")
    print(f"  Model: {MODEL_NAME}")


def load_codebase() -> str:
    """加载精简版代码库"""
    slim_path = Path.home() / "vulcan-brain" / "docs" / "snapshots" / "SLIM_CODEBASE.txt"
    tree_path = Path.home() / "vulcan-brain" / "docs" / "snapshots" / "project_structure.tree"

    if not slim_path.exists():
        print("✗ 未找到 SLIM_CODEBASE.txt")
        print("  请先运行: python create_slim_snapshot.py")
        exit(1)

    codebase = slim_path.read_text(encoding='utf-8')
    tree = tree_path.read_text(encoding='utf-8') if tree_path.exists() else ""

    context = f"# PROJECT STRUCTURE\n```\n{tree}\n```\n\n# CODEBASE\n{codebase}"

    char_count = len(context)
    token_estimate = char_count // 4

    print(f"✓ 代码库加载完成")
    print(f"  大小: {char_count:,} 字符 (~{token_estimate:,} tokens)")

    return context


def create_model(enable_search: bool = False):
    """创建 Gemini 模型"""
    tools = None
    if enable_search:
        # 启用 Google Search Grounding
        tools = [{"google_search": {}}]
        print("✓ Google Search 已启用（联网模式）")

    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
        safety_settings=SAFETY_SETTINGS,
        tools=tools,
    )


def build_audit_prompt(context: str) -> str:
    """构建审查提示词"""
    return f"""
请对以下代码库进行全面审查，严格按照 JSON Schema 输出。

{context}

---

## 审查要求

### Chapter 1: 架构与代码健康度
- 审查 Qwen/Claude 混合编排逻辑，分析脑裂风险
- 找出代码异味：重复逻辑、硬编码、结构混乱
- 生成核心流程的 Mermaid Sequence Diagram

### Chapter 2: AI 大脑与认知系统
- 审查 Memory 实现，分析短期/长期记忆冲突
- 检查核心 Prompt，评估模型分工是否清晰
- 评估 RAG/LightRAG 检索逻辑的盲区

### Chapter 3: 安全风险
- 检查 API Key 裸露风险
- 检查 MongoDB/PostgreSQL 安全配置

### Chapter 4: Top 5 行动计划
- 最高优先级的 5 个重构任务
- 每个任务包含可直接执行的 Claude Code 指令

**重要：先在 reasoning_process 中详细写出分析过程，然后再给出结论。**
"""


def run_standard_audit(context: str, enable_search: bool = False) -> dict:
    """Standard 模式：即时响应（原价）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "="*60)
    print("  Vulcan Brain 全面审查 (Standard Mode)")
    print("="*60)

    model = create_model(enable_search=enable_search)
    prompt = build_audit_prompt(context)

    print("\n正在分析... (预计 3-8 分钟)")

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "max_output_tokens": 65536,
                "response_mime_type": "application/json",
                "response_schema": AUDIT_SCHEMA,
            }
        )

        result = json.loads(response.text)

        # 保存结果
        save_results(result, timestamp)
        print_summary(result, response)

        return result

    except Exception as e:
        print(f"\n✗ 审查失败: {e}")
        raise


def run_batch_audit(context: str) -> str:
    """Batch 模式：异步处理（半价）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "="*60)
    print("  Vulcan Brain 全面审查 (Batch Mode - 50% OFF)")
    print("="*60)

    prompt = build_audit_prompt(context)

    # 准备 batch 请求文件
    batch_input = {
        "requests": [{
            "customId": f"vulcan-audit-{timestamp}",
            "model": MODEL_NAME,
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 65536,
                "responseMimeType": "application/json",
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        }]
    }

    # 保存 batch 输入文件
    batch_file = OUTPUT_DIR / f"batch_input_{timestamp}.jsonl"
    with open(batch_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(batch_input["requests"][0], ensure_ascii=False) + "\n")

    print(f"\n✓ Batch 请求文件已准备: {batch_file}")

    try:
        # 创建 batch job
        # 注意：google-generativeai SDK 的 batch API 可能有不同实现
        # 这里使用文件上传方式

        print("\n正在提交 Batch Job...")

        # 上传输入文件
        uploaded_file = genai.upload_file(batch_file)
        print(f"  文件已上传: {uploaded_file.name}")

        # 创建 batch job（使用 genai 的 batch 接口）
        batch_job = genai.create_batch(
            model=MODEL_NAME,
            src=uploaded_file.uri,
            config={
                "display_name": f"vulcan-audit-{timestamp}",
            }
        )

        job_id = batch_job.name
        print(f"\n✓ Batch Job 已创建!")
        print(f"  Job ID: {job_id}")
        print(f"\n  查询状态: python {__file__} --check-batch {job_id}")

        # 保存 job info
        job_info = {
            "job_id": job_id,
            "timestamp": timestamp,
            "status": "PENDING",
            "input_file": str(batch_file),
        }
        job_file = OUTPUT_DIR / f"batch_job_{timestamp}.json"
        job_file.write_text(json.dumps(job_info, indent=2), encoding='utf-8')

        return job_id

    except AttributeError:
        # SDK 可能不支持 batch API，回退到轮询模式
        print("\n! Batch API 不可用，使用轮询模式...")
        return run_polling_audit(context, timestamp)
    except Exception as e:
        print(f"\n✗ Batch 创建失败: {e}")
        print("  回退到 Standard 模式...")
        return run_standard_audit(context)


def run_polling_audit(context: str, timestamp: str) -> dict:
    """轮询模式：模拟 batch 的异步体验"""
    print("\n使用轮询模式（后台处理）...")

    model = create_model(enable_search=False)
    prompt = build_audit_prompt(context)

    print("正在提交请求...")

    try:
        # 使用 generate_content_async 或普通调用
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "max_output_tokens": 65536,
                "response_mime_type": "application/json",
                "response_schema": AUDIT_SCHEMA,
            }
        )

        result = json.loads(response.text)
        save_results(result, timestamp)
        print_summary(result, response)

        return result

    except Exception as e:
        print(f"\n✗ 失败: {e}")
        raise


def check_batch_status(job_id: str):
    """检查 Batch Job 状态"""
    print(f"\n检查 Batch Job: {job_id}")

    try:
        job = genai.get_batch(job_id)
        print(f"  状态: {job.state}")

        if job.state == "JOB_STATE_SUCCEEDED":
            print("  ✓ 完成！正在下载结果...")
            # 下载并解析结果
            # ...
        elif job.state == "JOB_STATE_FAILED":
            print(f"  ✗ 失败: {job.error}")
        else:
            print(f"  进度: {job.state}")

    except Exception as e:
        print(f"  ✗ 查询失败: {e}")


def save_results(result: dict, timestamp: str):
    """保存审查结果"""
    # JSON
    json_file = OUTPUT_DIR / f"VULCAN_AUDIT_{timestamp}.json"
    json_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    # Markdown
    md_report = generate_markdown(result)
    md_file = OUTPUT_DIR / f"VULCAN_AUDIT_{timestamp}.md"
    md_file.write_text(md_report, encoding='utf-8')

    # Latest
    (OUTPUT_DIR / "VULCAN_AUDIT_LATEST.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (OUTPUT_DIR / "VULCAN_AUDIT_LATEST.md").write_text(md_report, encoding='utf-8')

    print(f"\n✓ 结果已保存:")
    print(f"  {json_file}")
    print(f"  {md_file}")


def generate_markdown(result: dict) -> str:
    """生成 Markdown 报告"""
    lines = [
        "# Vulcan Brain 系统诊断报告",
        f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n## 总体评分",
        f"\n| 指标 | 分数 |",
        f"|------|------|",
        f"| 系统健康度 | **{result.get('overall_health_score', 'N/A')}**/100 |",
        f"| 技术债评分 | **{result.get('tech_debt_score', 'N/A')}**/100 |",
    ]

    if arch := result.get('architecture_review'):
        lines.append(f"\n## 架构审查")
        lines.append(f"\n**风险评分:** {arch.get('risk_score', 'N/A')}/100")
        lines.append(f"\n### 脑裂风险\n{arch.get('brain_split_risk', 'N/A')}")
        if issues := arch.get('data_flow_issues'):
            lines.append("\n### 数据流问题")
            for i in issues: lines.append(f"- {i}")
        if d := arch.get('mermaid_diagram'):
            lines.append(f"\n### 流程图\n```mermaid\n{d}\n```")

    if smells := result.get('code_smells'):
        lines.append(f"\n## 代码异味 ({len(smells)})")
        for s in smells:
            sev = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}.get(s.get('severity'),"⚪")
            lines.append(f"\n### {sev} {s.get('file_path')} - {s.get('smell_type')}")
            lines.append(f"{s.get('description','')}")
            if c := s.get('fix_code'): lines.append(f"```python\n{c}\n```")

    if sec := result.get('security_issues'):
        lines.append(f"\n## 安全问题 ({len(sec)})")
        for s in sec:
            sev = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}.get(s.get('severity'),"⚪")
            lines.append(f"\n### {sev} {s.get('file_path')} - {s.get('issue_type')}")
            lines.append(f"{s.get('description','')}")

    if actions := result.get('top5_actions'):
        lines.append(f"\n## Top 5 行动计划")
        for a in actions:
            lines.append(f"\n### P{a['priority']}: {a['task_name']}")
            lines.append(f"**问题:** {a.get('problem_description','')}")
            lines.append(f"**方案:** {a.get('solution_approach','')}")
            if c := a.get('claude_directive'):
                lines.append(f"**Claude 指令:**\n```\n{c}\n```")

    if r := result.get('reasoning_process'):
        lines.append(f"\n## 分析过程\n{r}")

    return "\n".join(lines)


def print_summary(result: dict, response=None):
    """打印摘要"""
    print(f"\n{'='*60}")
    print(f"  审查完成!")
    print(f"{'='*60}")
    print(f"  健康度: {result.get('overall_health_score', '?')}/100")
    print(f"  技术债: {result.get('tech_debt_score', '?')}/100")
    print(f"  代码异味: {len(result.get('code_smells', []))} 个")
    print(f"  安全问题: {len(result.get('security_issues', []))} 个")

    if actions := result.get('top5_actions'):
        print(f"\n  Top 5 行动:")
        for a in actions:
            print(f"    {a['priority']}. {a['task_name']}")

    if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
        m = response.usage_metadata
        print(f"\n  Token: 输入 {m.prompt_token_count:,} / 输出 {m.candidates_token_count:,}")
        cost = m.prompt_token_count/1e6*2 + m.candidates_token_count/1e6*12
        print(f"  费用: ~${cost:.2f}")


def main():
    parser = argparse.ArgumentParser(description='Vulcan Brain Gemini 审查工具 v2')
    parser.add_argument('--audit', action='store_true', help='Standard 模式审查')
    parser.add_argument('--batch', action='store_true', help='Batch 模式审查（半价）')
    parser.add_argument('--search', action='store_true', help='启用 Google Search（联网）')
    parser.add_argument('--check-batch', type=str, help='检查 Batch Job 状态')
    parser.add_argument('-i', '--interactive', action='store_true', help='交互模式')

    args = parser.parse_args()

    setup_genai()

    if args.check_batch:
        check_batch_status(args.check_batch)
        return

    context = load_codebase()

    if args.batch:
        run_batch_audit(context)
    elif args.audit or not any([args.batch, args.interactive]):
        run_standard_audit(context, enable_search=args.search)
    elif args.interactive:
        print("\n交互模式 - 输入问题，输入 quit 退出")
        model = create_model(enable_search=args.search)
        while True:
            q = input("\n> ").strip()
            if q.lower() == 'quit': break
            if not q: continue
            try:
                r = model.generate_content(f"{context}\n\n---\n\n{q}")
                print(r.text)
            except Exception as e:
                print(f"错误: {e}")


if __name__ == "__main__":
    main()
