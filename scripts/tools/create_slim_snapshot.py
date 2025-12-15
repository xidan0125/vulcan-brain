#!/usr/bin/env python3
"""创建精简版代码库快照 - 只保留核心代码"""
from pathlib import Path

PROJECT_ROOT = Path.home() / "vulcan-brain"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "snapshots"

# 只包含核心代码
INCLUDE_EXTENSIONS = {'.py', '.tsx', '.ts', '.yaml', '.yml'}

# 排除的目录和文件
IGNORE_DIRS = {
    'node_modules', '.git', '.venv', 'venv', '__pycache__',
    '.next', 'dist', 'build', 'model_cache', 'rag_storage',
    'kb_storage', '_archive', '_deprecated', '.vscode', 'data',  # 排除 data 目录
    'static'  # 排除静态文件
}

IGNORE_FILES = {
    'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
    '.env', '.env.local', '.env.production'
}

def should_include(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORE_DIRS:
            return False
    if path.name in IGNORE_FILES:
        return False
    return path.suffix.lower() in INCLUDE_EXTENSIONS

files = []
for p in PROJECT_ROOT.rglob('*'):
    if p.is_file() and should_include(p):
        files.append(p)

files.sort()
print(f"Found {len(files)} core code files")

# 生成精简版
parts = ["# VULCAN BRAIN - SLIM CODEBASE (Core Code Only)\n"]
for f in files:
    try:
        content = f.read_text(encoding='utf-8')
        rel = f.relative_to(PROJECT_ROOT)
        parts.append(f"\n{'='*80}\nFILE: {rel}\n{'='*80}\n{content}")
    except Exception as e:
        print(f"Skip {f}: {e}")

output = "".join(parts)
out_file = OUTPUT_DIR / "SLIM_CODEBASE.txt"
out_file.write_text(output, encoding='utf-8')
print(f"Saved to: {out_file}")
print(f"Size: {len(output):,} chars")
