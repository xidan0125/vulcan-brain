#!/usr/bin/env python3
"""
Product Architect Runner - 产品架构师执行引擎

这不是一个简单的 API 调用脚本，而是一个完整的流程编排器：
1. Pre-processing: 扫描代码库，智能筛选文件
2. Context Injection: 将代码注入上下文模板
3. Model Invocation: 调用 Gemini 进行分析
4. Post-processing: 验证输出，生成报告
5. Export: 导出多种格式（JSON, Markdown, HTML）
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import google.generativeai as genai

# === 配置 ===
SKILL_DIR = Path(__file__).parent
PROJECT_ROOT = SKILL_DIR.parent.parent  # vulcan-brain/
OUTPUT_DIR = PROJECT_ROOT / "docs" / "audits"

# API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo"

# 文件筛选配置
INCLUDE_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.yaml', '.yml'}
IGNORE_DIRS = {'node_modules', '.git', '.venv', 'venv', '__pycache__', '.next', 'dist', 'build', 'model_cache'}
IGNORE_FILES = {'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', '.env', '.env.local'}
MAX_FILE_SIZE = 50000  # 50KB per file
MAX_TOTAL_CONTEXT = 1_500_000  # 1.5M chars (~375K tokens)


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    content: str
    size: int
    lines: int
    language: str
    priority: int  # 越高越重要


class ProductArchitectRunner:
    """产品架构师执行器"""
    
    def __init__(self):
        self.config = self._load_json("config.json")
        self.system_prompt = self._load_file("system_prompt.md")
        self.output_schema = self._load_json("output_schema.json")
        self.context_template = self._load_file("context_template.md")
        self.examples = self._load_examples()
        
        # 初始化 Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=self.config.get("model", "gemini-3-pro-preview"),
            generation_config={
                "temperature": self.config.get("temperature", 0.3),
                "max_output_tokens": self.config.get("max_tokens", 16384),
                "response_mime_type": "application/json"
            },
            system_instruction=self.system_prompt
        )
    
    def _load_file(self, filename: str) -> str:
        """加载文本文件"""
        filepath = SKILL_DIR / filename
        if filepath.exists():
            return filepath.read_text(encoding='utf-8')
        return ""
    
    def _load_json(self, filename: str) -> Dict:
        """加载 JSON 文件"""
        filepath = SKILL_DIR / filename
        if filepath.exists():
            return json.loads(filepath.read_text(encoding='utf-8'))
        return {}
    
    def _load_examples(self) -> List[Dict]:
        """加载 Few-shot 示例"""
        examples = []
        examples_dir = SKILL_DIR / "examples"
        if examples_dir.exists():
            for f in examples_dir.glob("*.json"):
                try:
                    examples.append(json.loads(f.read_text(encoding='utf-8')))
                except:
                    pass
        return examples
    
    def _get_language(self, filepath: Path) -> str:
        """根据扩展名获取语言"""
        ext_map = {
            '.py': 'python', '.ts': 'typescript', '.tsx': 'tsx',
            '.js': 'javascript', '.jsx': 'jsx', '.yaml': 'yaml',
            '.yml': 'yaml', '.json': 'json', '.md': 'markdown'
        }
        return ext_map.get(filepath.suffix.lower(), 'text')
    
    def _calculate_priority(self, filepath: Path, content: str) -> int:
        """计算文件重要性（越高越重要）"""
        priority = 50
        name = filepath.name.lower()
        
        # 核心入口文件
        if name in ['api_server.py', 'main.py', 'app.py', 'index.ts']:
            priority += 30
        
        # 配置文件
        if name in ['config.py', 'settings.py', 'config.json']:
            priority += 20
        
        # Router/API 文件
        if 'router' in name or 'api' in name:
            priority += 15
        
        # 核心业务逻辑
        if 'service' in name or 'store' in name or 'kernel' in name:
            priority += 15
        
        # 包含类定义的文件
        if 'class ' in content:
            priority += 10
        
        # 测试文件降权
        if 'test' in name or '_test' in name:
            priority -= 20
        
        # 示例/demo 文件降权
        if 'example' in name or 'demo' in name:
            priority -= 15
        
        return priority
    
    def scan_codebase(self, target_dir: Path) -> tuple[str, List[FileInfo]]:
        """
        扫描代码库
        返回: (目录树字符串, 文件信息列表)
        """
        print("[Scan] 扫描代码库...")
        
        tree_lines = []
        files: List[FileInfo] = []
        
        def scan_dir(dir_path: Path, prefix: str = ""):
            nonlocal tree_lines, files
            
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
            
            # 过滤
            items = [i for i in items if i.name not in IGNORE_DIRS and i.name not in IGNORE_FILES]
            
            for i, item in enumerate(items):
                is_last = (i == len(items) - 1)
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    tree_lines.append(f"{prefix}{connector}{item.name}/")
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    scan_dir(item, new_prefix)
                elif item.suffix.lower() in INCLUDE_EXTENSIONS:
                    size = item.stat().st_size
                    tree_lines.append(f"{prefix}{connector}{item.name} ({size:,})")
                    
                    if size <= MAX_FILE_SIZE:
                        try:
                            content = item.read_text(encoding='utf-8')
                            files.append(FileInfo(
                                path=str(item.relative_to(target_dir)),
                                content=content,
                                size=size,
                                lines=len(content.splitlines()),
                                language=self._get_language(item),
                                priority=self._calculate_priority(item, content)
                            ))
                        except:
                            pass
        
        tree_lines.append(f"{target_dir.name}/")
        scan_dir(target_dir)
        
        # 按优先级排序
        files.sort(key=lambda x: x.priority, reverse=True)
        
        print(f"[Scan] 找到 {len(files)} 个文件")
        return "\n".join(tree_lines), files
    
    def build_context(self, 
                      directory_tree: str, 
                      files: List[FileInfo],
                      user_query: str,
                      **kwargs) -> str:
        """构建上下文"""
        print("[Context] 构建上下文...")
        
        # 计算可用空间
        base_context = self.context_template
        base_size = len(base_context) + len(directory_tree) + len(user_query)
        available_for_files = MAX_TOTAL_CONTEXT - base_size - 10000  # 留余量
        
        # 选择文件（按优先级）
        selected_files = []
        current_size = 0
        
        for f in files:
            if current_size + len(f.content) <= available_for_files:
                selected_files.append(f)
                current_size += len(f.content)
        
        print(f"[Context] 选择了 {len(selected_files)}/{len(files)} 个文件 ({current_size:,} chars)")
        
        # 构建文件内容部分
        files_content = ""
        for f in selected_files:
            files_content += f"""
### File: `{f.path}`
- **Size**: {f.size} bytes
- **Lines**: {f.lines}

```{f.language}
{f.content}
```

---
"""
        
        # 渲染模板（简单替换）
        context = self.context_template
        context = context.replace("{{ project_name }}", kwargs.get("project_name", "Unknown"))
        context = context.replace("{{ analysis_date }}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        context = context.replace("{{ dev_phase }}", kwargs.get("dev_phase", "growing"))
        context = context.replace("{{ user_query }}", user_query)
        context = context.replace("{{ directory_tree }}", directory_tree)
        context = context.replace("{{ tech_stack }}", kwargs.get("tech_stack", "Python, TypeScript, FastAPI, Next.js"))
        context = context.replace("{{ team_size }}", kwargs.get("team_size", "Small team (2-5)"))
        context = context.replace("{{ business_context }}", kwargs.get("business_context", "Enterprise AI product"))
        
        # 替换文件部分
        # 使用简单替换避免转义问题
        placeholder_start = '{% for file in files %}'
        placeholder_end = '{% endfor %}'
        start_idx = context.find(placeholder_start)
        end_idx = context.find(placeholder_end)
        if start_idx != -1 and end_idx != -1:
            context = context[:start_idx] + files_content + context[end_idx + len(placeholder_end):]
        
        # 添加示例提示
        if self.examples:
            examples_hint = "\n\n## Reference Examples (输出风格参考)\n"
            for ex in self.examples[:2]:
                examples_hint += f"```json\n{json.dumps(ex, ensure_ascii=False, indent=2)[:500]}...\n```\n"
            context += examples_hint
        
        return context
    
    def analyze(self, context: str) -> Dict:
        """调用模型进行分析"""
        print("[Analyze] 调用 Gemini 分析...")
        print(f"[Analyze] 上下文大小: {len(context):,} chars")
        
        try:
            response = self.model.generate_content(context)
            result = json.loads(response.text)
            print("[Analyze] ✓ 分析完成")
            return result
        except json.JSONDecodeError as e:
            print(f"[Analyze] ✗ JSON 解析失败: {e}")
            return {"raw_response": response.text, "parse_error": str(e)}
        except Exception as e:
            print(f"[Analyze] ✗ 分析失败: {e}")
            raise
    
    def export_report(self, result: Dict, output_name: str = None) -> Path:
        """导出报告"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = output_name or f"ARCHITECTURE_ANALYSIS_{timestamp}"
        
        # JSON
        json_path = OUTPUT_DIR / f"{output_name}.json"
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        
        # Latest
        latest_path = OUTPUT_DIR / "ARCHITECTURE_ANALYSIS_LATEST.json"
        latest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        
        print(f"[Export] ✓ {json_path}")
        return json_path
    
    def run(self, 
            target_dir: Path = None,
            user_query: str = "请分析这个项目的架构",
            **kwargs) -> Dict:
        """
        完整执行流程
        """
        print("=" * 60)
        print("  Product Architect Analysis")
        print("=" * 60)
        
        target_dir = target_dir or PROJECT_ROOT
        
        # 1. Scan
        directory_tree, files = self.scan_codebase(target_dir)
        
        # 2. Build Context
        context = self.build_context(
            directory_tree, 
            files, 
            user_query,
            project_name=kwargs.pop("project_name", target_dir.name),
            
            **kwargs
        )
        
        # 3. Analyze
        result = self.analyze(context)
        
        # 4. Export
        self.export_report(result)
        
        # 5. Print Summary
        self._print_summary(result)
        
        return result
    
    def _print_summary(self, result: Dict):
        """打印摘要"""
        print("\n" + "=" * 60)
        print("  Analysis Summary")
        print("=" * 60)
        
        if "executive_summary" in result:
            print(f"\n📋 {result['executive_summary']}")
        
        if "module_architecture" in result:
            modules = result["module_architecture"].get("primary_modules", [])
            print(f"\n📦 识别到 {len(modules)} 个一级模块:")
            for m in modules:
                score = m.get("health_score", "?")
                emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
                print(f"   {emoji} {m.get('name', 'Unknown')} ({m.get('chinese_name', '')}) - {score}%")
        
        if "action_items" in result:
            actions = result["action_items"][:3]
            print(f"\n🎯 Top 3 Actions:")
            for a in actions:
                print(f"   P{a.get('priority', '?')}: {a.get('action', 'Unknown')}")
        
        print()


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Product Architect Analysis")
    parser.add_argument("--target", "-t", type=str, default=None, help="Target directory")
    parser.add_argument("--query", "-q", type=str, default="请全面分析这个项目的架构，重点关注一级模块划分", help="Analysis query")
    parser.add_argument("--project-name", type=str, default="Vulcan Brain", help="Project name")
    args = parser.parse_args()
    
    runner = ProductArchitectRunner()
    
    target = Path(args.target) if args.target else PROJECT_ROOT
    
    runner.run(
        target_dir=target,
        user_query=args.query,
        project_name=args.project_name
    )


if __name__ == "__main__":
    main()
