#!/usr/bin/env python3
"""
Vulcan Brain - 统一技能调用入口
Usage: python run_skill.py <skill_name> '<task>' [options]
       python run_skill.py <skill_name> --stdin [options]  # 从stdin读取任务

Examples:
  python run_skill.py ai_frontiers '设计一个多Agent系统'
  python run_skill.py ai_engineer '调研vLLM 0.8新特性' --search
  python run_skill.py architect '审计这个代码库' --context /path/to/code

  # 长文本/特殊字符用 stdin:
  python run_skill.py email --stdin << 'EOF'
  分析这个JSON: {"key": "value"}
  EOF
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Gemini API
from google import genai
from google.genai import types

# === 配置 ===
API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM')
SKILLS_DIR = Path(__file__).parent / "gemini_skills"

# 技能别名映射
SKILL_ALIASES = {
    "ai": "ai_engineer_v1",
    "ai_engineer": "ai_engineer_v1",
    "frontiers": "ai_frontiers_v1",
    "ai_frontiers": "ai_frontiers_v1",
    "agent": "ai_frontiers_v1",
    "arch": "architect_v1",
    "architect": "architect_v1",
    "code_review": "architect_v1",
    "pa": "product_analyst_v1",
    "product_analyst": "product_analyst_v1",
    "feature_audit": "product_analyst_v1",
    "product": "product_architect_v1",
    "product_architect": "product_architect_v1",
    "email": "email_intelligence_expert",
    "email_intel": "email_intelligence_expert",
    "graph": "email_intelligence_expert",
    "research": "tech_researcher",
    "researcher": "tech_researcher",
    "survey": "tech_researcher",
    "ops": "enterprise_integrator",
    "feishu": "enterprise_integrator",
    "integrate": "enterprise_integrator",
    "ms365": "enterprise_integrator",
}


def list_skills():
    """列出所有可用技能"""
    print("\n📦 可用技能列表:\n")
    print(f"{'技能名称':<25} {'别名':<20} {'描述'}")
    print("-" * 80)
    
    skill_info = {
        "ai_engineer_v1": ("ai, ai_engineer", "AI基础设施工程师 - vLLM/Ollama/开源模型部署"),
        "ai_frontiers_v1": ("frontiers, agent", "Agent架构专家 - MCP/多Agent/编排模式"),
        "architect_v1": ("arch, code_review", "软件架构师 - 代码审计/技术债务评估"),
        "product_analyst_v1": ("pa, feature_audit", "产品分析师 - 功能审计/用户旅程分析"),
        "product_architect_v1": ("product", "产品架构师 - 产品设计/PRD生成"),
        "email_intelligence_expert": ("email, graph", "邮件数据智能架构师 - 知识图谱/实体提取/图数据库"),
        "tech_researcher": ("research, survey", "技术调研专家 - 选型分析/论文解读/竞品调研"),
        "enterprise_integrator": ("ops, feishu", "企业集成专家 - 飞书/MS365/SaaS API对接"),
    }
    
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.is_dir() and not skill_dir.name.startswith('_'):
            prompt_file = skill_dir / "system_prompt.md"
            if prompt_file.exists():
                info = skill_info.get(skill_dir.name, ("", ""))
                print(f"{skill_dir.name:<25} {info[0]:<20} {info[1]}")
    
    print("\n💡 使用示例:")
    print("  python run_skill.py frontiers '设计多Agent客服系统'")
    print("  python run_skill.py arch '审计代码质量' --context ./src")
    print("  python run_skill.py ai '调研最新推理引擎' --search")
    print()


def resolve_skill_name(name: str) -> str:
    """解析技能名称（支持别名）"""
    return SKILL_ALIASES.get(name.lower(), name)


def load_skill(skill_name: str) -> dict:
    """加载技能配置"""
    skill_dir = SKILLS_DIR / skill_name
    
    if not skill_dir.exists():
        raise FileNotFoundError(f"技能不存在: {skill_name}")
    
    # 读取系统提示词
    prompt_file = skill_dir / "system_prompt.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"缺少 system_prompt.md: {skill_name}")
    
    system_prompt = prompt_file.read_text(encoding='utf-8')
    
    # 读取配置
    config_file = skill_dir / "config.json"
    config = {
        "model": "gemini-2.0-flash",
        "temperature": 0.4,
        "max_tokens": 16000,
        "web_search": False
    }
    if config_file.exists():
        user_config = json.loads(config_file.read_text(encoding='utf-8'))
        config.update(user_config)
        # 处理嵌套的 features
        if "features" in user_config:
            config["web_search"] = user_config["features"].get("web_search", False)
    
    # 读取输出 schema
    schema_file = skill_dir / "output_schema.json"
    output_schema = None
    if schema_file.exists():
        output_schema = json.loads(schema_file.read_text(encoding='utf-8'))
    
    return {
        "name": skill_name,
        "dir": skill_dir,
        "system_prompt": system_prompt,
        "config": config,
        "output_schema": output_schema
    }


def gather_context(context_path: str, max_chars: int = 50000) -> str:
    """收集代码上下文"""
    path = Path(context_path)
    if not path.exists():
        return f"[Error: Path not found: {context_path}]"
    
    context_parts = []
    total_chars = 0
    
    # 支持的文件类型
    extensions = {'.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.json', '.yaml', '.yml'}
    
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.rglob('*'))
    
    for file in files:
        if file.is_file() and file.suffix in extensions:
            # 跳过 node_modules, __pycache__ 等
            if any(skip in str(file) for skip in ['node_modules', '__pycache__', '.git', 'dist', 'build']):
                continue
            
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                if total_chars + len(content) > max_chars:
                    content = content[:max_chars - total_chars] + "\n... [truncated]"
                
                rel_path = file.relative_to(path) if path.is_dir() else file.name
                context_parts.append(f"### {rel_path}\n```{file.suffix[1:]}\n{content}\n```\n")
                total_chars += len(content)
                
                if total_chars >= max_chars:
                    break
            except Exception as e:
                continue
    
    return "\n".join(context_parts) if context_parts else "[No matching files found]"


def run_skill(
    skill_name: str,
    task: str,
    context: Optional[str] = None,
    use_search: bool = False,
    output_json: bool = False,
    save_to: Optional[str] = None
) -> str:
    """执行技能"""
    
    # 解析别名
    skill_name = resolve_skill_name(skill_name)
    skill = load_skill(skill_name)
    config = skill["config"]
    
    # 初始化客户端
    client = genai.Client(api_key=API_KEY)
    
    # 构建提示
    full_prompt = skill["system_prompt"]
    
    if context:
        context_content = gather_context(context) if Path(context).exists() else context
        full_prompt += f"\n\n## 代码/上下文\n\n{context_content}"
    
    full_prompt += f"\n\n## 当前任务\n\n{task}"
    
    if use_search or config.get("web_search"):
        full_prompt += "\n\n请联网搜索获取 2025 年最新信息。"
    
    # 准备生成配置
    gen_config = types.GenerateContentConfig(
        temperature=config.get("temperature", 0.4),
        max_output_tokens=config.get("max_tokens", 16000)
    )
    
    # 工具配置
    tools = []
    if use_search or config.get("web_search"):
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    
    if tools:
        gen_config = types.GenerateContentConfig(
            tools=tools,
            temperature=config.get("temperature", 0.4),
            max_output_tokens=config.get("max_tokens", 16000)
        )
    
    # JSON 输出模式
    if output_json and skill["output_schema"]:
        gen_config.response_mime_type = "application/json"
    
    # 打印头部
    print("=" * 60)
    print(f"🧠 Vulcan Brain - {skill_name}")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if use_search:
        print("   🔍 联网搜索已启用")
    if context:
        print(f"   📁 上下文: {context}")
    print("=" * 60)
    print()
    
    # 调用模型
    response = client.models.generate_content(
        model=config.get("model", "gemini-2.0-flash"),
        contents=full_prompt,
        config=gen_config
    )
    
    result = response.text
    print(result)
    
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
        output = f"""# {skill_name} Report

Generated: {datetime.now().isoformat()}
Task: {task}

---

{result}
"""
        Path(save_to).write_text(output, encoding='utf-8')
        print(f"\n📄 已保存: {save_to}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Vulcan Brain - 统一技能调用入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_skill.py frontiers '设计多Agent系统'
  python run_skill.py arch '审计代码' --context ./src
  python run_skill.py ai '调研vLLM' --search --save report.md
  python run_skill.py --list
        """
    )
    
    parser.add_argument("skill", nargs="?", help="技能名称 (支持别名)")
    parser.add_argument("task", nargs="?", help="任务描述")
    parser.add_argument("--stdin", action="store_true", help="从stdin读取任务 (支持长文本/特殊字符)")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有可用技能")
    parser.add_argument("--context", "-c", help="代码/文件上下文路径")
    parser.add_argument("--search", "-s", action="store_true", help="启用联网搜索")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--save", "-o", help="保存结果到文件")
    
    args = parser.parse_args()
    
    if args.list:
        list_skills()
        return

    # 获取任务描述
    task = args.task
    if args.stdin:
        task = sys.stdin.read().strip()
        if not task:
            print("❌ 错误: stdin 为空")
            sys.exit(1)

    if not args.skill or not task:
        parser.print_help()
        print("\n❌ 错误: 需要提供技能名称和任务描述")
        print("   使用 --list 查看可用技能")
        print("   或使用 --stdin 从标准输入读取任务")
        sys.exit(1)

    try:
        run_skill(
            skill_name=args.skill,
            task=task,
            context=args.context,
            use_search=args.search,
            output_json=args.json,
            save_to=args.save
        )
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("   使用 --list 查看可用技能")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
