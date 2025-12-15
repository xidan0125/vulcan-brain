#!/usr/bin/env python3
"""
Vulcan Brain 系统快照工具
生成项目结构树 + 合并代码 + 敏感信息扫描
"""

import os
import re
from pathlib import Path
from datetime import datetime

# === 配置 ===
PROJECT_ROOT = Path.home() / "vulcan-brain"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "snapshots"

# 要扫描的文件类型
INCLUDE_EXTENSIONS = {'.py', '.tsx', '.ts', '.yaml', '.yml', '.json'}

# 要忽略的目录
IGNORE_DIRS = {
    'node_modules', '.git', '.venv', 'venv', '__pycache__',
    '.next', 'dist', 'build', 'model_cache', 'rag_storage',
    'kb_storage', '_archive', '_deprecated', '.vscode'
}

# 要忽略的文件模式
IGNORE_FILES = {
    'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
    '.env', '.env.local', '.env.production'
}

# 敏感信息模式
SENSITIVE_PATTERNS = [
    (r'["\']?[A-Za-z_]*(?:API_KEY|API_SECRET|SECRET_KEY|PASSWORD|TOKEN|CREDENTIALS)["\']?\s*[:=]\s*["\'][^"\']+["\']', 'API Key/Secret'),
    (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI API Key'),
    (r'xoxb-[a-zA-Z0-9-]+', 'Slack Bot Token'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Token'),
    (r'mongodb(\+srv)?://[^\s"\']+', 'MongoDB URI'),
    (r'postgres(ql)?://[^\s"\']+', 'PostgreSQL URI'),
    (r'redis://[^\s"\']+', 'Redis URI'),
    (r'Bearer\s+[a-zA-Z0-9._-]+', 'Bearer Token'),
    (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', 'Private Key'),
    (r'["\']?app_id["\']?\s*[:=]\s*["\'][^"\']+["\']', 'App ID'),
    (r'["\']?app_secret["\']?\s*[:=]\s*["\'][^"\']+["\']', 'App Secret'),
]


def should_include_file(path: Path) -> bool:
    """判断文件是否应该被包含"""
    # 检查目录
    for part in path.parts:
        if part in IGNORE_DIRS:
            return False

    # 检查文件名
    if path.name in IGNORE_FILES:
        return False

    # 检查扩展名
    return path.suffix.lower() in INCLUDE_EXTENSIONS


def generate_tree(root: Path, prefix: str = "", is_last: bool = True) -> list:
    """递归生成目录树"""
    lines = []

    if root == PROJECT_ROOT:
        lines.append(f"{root.name}/")
    else:
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{root.name}/")

    if root.is_dir():
        # 过滤并排序子项
        children = []
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir():
                    if child.name not in IGNORE_DIRS:
                        children.append(child)
                elif should_include_file(child):
                    children.append(child)
        except PermissionError:
            pass

        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            new_prefix = prefix + ("    " if is_last else "│   ")

            if child.is_dir():
                lines.extend(generate_tree(child, new_prefix, is_last_child))
            else:
                connector = "└── " if is_last_child else "├── "
                size = child.stat().st_size
                size_str = f"{size:,}" if size < 10000 else f"{size//1024}KB"
                lines.append(f"{new_prefix}{connector}{child.name} ({size_str})")

    return lines


def scan_sensitive_info(content: str, filepath: str) -> list:
    """扫描敏感信息"""
    findings = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        for pattern, desc in SENSITIVE_PATTERNS:
            matches = re.findall(pattern, line, re.IGNORECASE)
            if matches:
                # 脱敏处理
                masked_line = line.strip()
                if len(masked_line) > 100:
                    masked_line = masked_line[:100] + "..."
                findings.append({
                    'file': filepath,
                    'line': line_num,
                    'type': desc,
                    'preview': masked_line
                })

    return findings


def collect_files(root: Path) -> list:
    """收集所有需要处理的文件"""
    files = []
    for path in root.rglob('*'):
        if path.is_file() and should_include_file(path):
            files.append(path)
    return sorted(files)


def main():
    print("=" * 60)
    print("  Vulcan Brain System Snapshot Tool")
    print("=" * 60)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # === 1. 生成目录树 ===
    print("\n[1/4] Generating project structure tree...")
    tree_lines = generate_tree(PROJECT_ROOT)
    tree_content = "\n".join(tree_lines)

    tree_file = OUTPUT_DIR / f"project_structure_{timestamp}.tree"
    tree_file.write_text(tree_content, encoding='utf-8')
    print(f"  -> Saved to: {tree_file}")

    # 同时保存一个 latest 版本
    latest_tree = OUTPUT_DIR / "project_structure.tree"
    latest_tree.write_text(tree_content, encoding='utf-8')

    # === 2. 收集文件 ===
    print("\n[2/4] Collecting code files...")
    files = collect_files(PROJECT_ROOT)
    print(f"  -> Found {len(files)} files")

    # === 3. 合并代码 ===
    print("\n[3/4] Merging codebase...")
    all_sensitive = []
    codebase_parts = []

    codebase_parts.append(f"""
{'='*80}
  VULCAN BRAIN - FULL CODEBASE SNAPSHOT
  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
  Total Files: {len(files)}
{'='*80}
""")

    for i, filepath in enumerate(files, 1):
        rel_path = filepath.relative_to(PROJECT_ROOT)

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            content = f"[ERROR reading file: {e}]"

        # 扫描敏感信息
        sensitive = scan_sensitive_info(content, str(rel_path))
        all_sensitive.extend(sensitive)

        # 添加到合并文件
        separator = "=" * 80
        codebase_parts.append(f"""
{separator}
FILE: {rel_path}
SIZE: {len(content)} bytes
{separator}

{content}
""")

        if i % 20 == 0:
            print(f"  -> Processed {i}/{len(files)} files...")

    # 保存合并文件
    codebase_content = "\n".join(codebase_parts)
    codebase_file = OUTPUT_DIR / f"FULL_CODEBASE_{timestamp}.txt"
    codebase_file.write_text(codebase_content, encoding='utf-8')
    print(f"  -> Saved to: {codebase_file}")
    print(f"  -> Total size: {len(codebase_content):,} bytes")

    # 同时保存 latest 版本
    latest_codebase = OUTPUT_DIR / "FULL_CODEBASE.txt"
    latest_codebase.write_text(codebase_content, encoding='utf-8')

    # === 4. 敏感信息报告 ===
    print("\n[4/4] Generating sensitive info report...")

    report_lines = [
        "=" * 80,
        "  SENSITIVE INFORMATION SCAN REPORT",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 80,
        "",
        f"Total potential sensitive items found: {len(all_sensitive)}",
        "",
        "IMPORTANT: Review these items before sharing the codebase!",
        "",
        "-" * 80,
    ]

    if all_sensitive:
        # 按类型分组
        by_type = {}
        for item in all_sensitive:
            t = item['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(item)

        for sens_type, items in sorted(by_type.items()):
            report_lines.append(f"\n## {sens_type} ({len(items)} found)")
            report_lines.append("-" * 40)
            for item in items[:10]:  # 每类最多显示10个
                report_lines.append(f"  File: {item['file']}")
                report_lines.append(f"  Line: {item['line']}")
                report_lines.append(f"  Preview: {item['preview'][:80]}...")
                report_lines.append("")
            if len(items) > 10:
                report_lines.append(f"  ... and {len(items) - 10} more")
    else:
        report_lines.append("\nNo sensitive information detected!")
        report_lines.append("(This doesn't guarantee safety - manual review recommended)")

    report_content = "\n".join(report_lines)
    report_file = OUTPUT_DIR / f"SENSITIVE_SCAN_{timestamp}.txt"
    report_file.write_text(report_content, encoding='utf-8')
    print(f"  -> Saved to: {report_file}")

    # 同时保存 latest 版本
    latest_report = OUTPUT_DIR / "SENSITIVE_SCAN.txt"
    latest_report.write_text(report_content, encoding='utf-8')

    # === 完成 ===
    print("\n" + "=" * 60)
    print("  SNAPSHOT COMPLETE!")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nGenerated files:")
    print(f"  - project_structure.tree  (目录结构)")
    print(f"  - FULL_CODEBASE.txt       (合并代码)")
    print(f"  - SENSITIVE_SCAN.txt      (敏感信息报告)")

    if all_sensitive:
        print(f"\n⚠️  WARNING: Found {len(all_sensitive)} potential sensitive items!")
        print("    Please review SENSITIVE_SCAN.txt before sharing!")

    print()


if __name__ == "__main__":
    main()
