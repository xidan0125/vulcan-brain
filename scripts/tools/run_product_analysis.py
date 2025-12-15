#!/usr/bin/env python3
"""
使用 product_analyst_v1 技能分析 Vulcan Brain 产品功能
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from gemini_skills.skill_loader import GeminiSkillLoader

# 配置
SNAPSHOT_DIR = Path(__file__).parent / "docs" / "snapshots"
OUTPUT_DIR = Path(__file__).parent / "docs" / "audits"

def load_codebase_context(max_chars: int = 2_000_000) -> str:
    """加载代码库上下文（限制大小）"""
    codebase_file = SNAPSHOT_DIR / "FULL_CODEBASE.txt"
    
    if not codebase_file.exists():
        raise FileNotFoundError("Run system_snapshot.py first!")
    
    content = codebase_file.read_text(encoding='utf-8')
    
    # 如果太大，截取核心部分
    if len(content) > max_chars:
        print(f"[INFO] Codebase too large ({len(content):,} chars), truncating to {max_chars:,}")
        content = content[:max_chars] + "\n\n... [TRUNCATED] ..."
    
    return content

def load_structure() -> str:
    """加载目录结构"""
    tree_file = SNAPSHOT_DIR / "project_structure.tree"
    if tree_file.exists():
        return tree_file.read_text(encoding='utf-8')
    return ""

def main():
    print("=" * 60)
    print("  Vulcan Brain 产品功能分析 (Gemini Skills)")
    print("=" * 60)
    
    # 初始化
    print("\n[1/4] 初始化 Gemini Skills...")
    try:
        loader = GeminiSkillLoader()
        skills = loader.list_skills()
        print(f"  ✓ 可用技能: {[s['name'] for s in skills]}")
    except Exception as e:
        print(f"  ✗ 初始化失败: {e}")
        return
    
    # 加载上下文
    print("\n[2/4] 加载代码库上下文...")
    try:
        structure = load_structure()
        codebase = load_codebase_context(max_chars=1_500_000)  # ~375K tokens
        print(f"  ✓ 目录结构: {len(structure):,} chars")
        print(f"  ✓ 代码内容: {len(codebase):,} chars")
    except Exception as e:
        print(f"  ✗ 加载失败: {e}")
        return
    
    # 构建分析请求
    context = f"""# Project Structure

```
{structure}
```

# Full Codebase

{codebase}
"""
    
    user_prompt = """请全面分析这个 Vulcan Brain 项目，告诉我：

1. 这个产品到底是做什么的？核心价值是什么？
2. 目前实现了哪些功能？每个功能的完成度如何？
3. 有哪些外部集成？（API、数据库、第三方服务）
4. 用户可以完成哪些完整的使用流程？
5. 有哪些功能缺口或待改进的地方？
6. 从代码中的 TODO/FIXME 推断的未来规划？

请用中文回答，输出 JSON 格式。"""

    # 执行分析
    print("\n[3/4] 调用 product_analyst_v1 技能...")
    print("  (这可能需要 3-8 分钟，请耐心等待...)")
    
    try:
        result = loader.execute("product_analyst_v1", user_prompt, context)
        print("  ✓ 分析完成!")
    except Exception as e:
        print(f"  ✗ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 保存结果
    print("\n[4/4] 保存分析结果...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 尝试解析 JSON
    try:
        result_json = json.loads(result)
        output_file = OUTPUT_DIR / f"PRODUCT_ANALYSIS_{timestamp}.json"
        output_file.write_text(json.dumps(result_json, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  ✓ JSON 结果: {output_file}")
        
        # 也保存 latest
        latest_file = OUTPUT_DIR / "PRODUCT_ANALYSIS_LATEST.json"
        latest_file.write_text(json.dumps(result_json, ensure_ascii=False, indent=2), encoding='utf-8')
    except json.JSONDecodeError:
        # 如果不是有效 JSON，保存原始文本
        output_file = OUTPUT_DIR / f"PRODUCT_ANALYSIS_{timestamp}.txt"
        output_file.write_text(result, encoding='utf-8')
        print(f"  ✓ 文本结果: {output_file}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("  分析完成!")
    print("=" * 60)
    
    if isinstance(result_json, dict):
        print(f"\n📦 产品概述: {result_json.get('product_summary', 'N/A')[:200]}...")
        print(f"\n🎯 核心价值: {result_json.get('core_value_proposition', 'N/A')}")
        print(f"\n📊 成熟度: {result_json.get('overall_product_maturity', 'N/A')}")
        
        features = result_json.get('feature_inventory', [])
        print(f"\n✅ 功能数量: {len(features)}")
        for f in features[:5]:
            status_emoji = {"production": "🟢", "beta": "🟡", "mvp": "🟠", "planned": "⚪", "broken": "🔴"}.get(f.get('status', ''), '⚪')
            print(f"   {status_emoji} {f.get('name', 'Unknown')} ({f.get('completeness', 0)}%)")
        if len(features) > 5:
            print(f"   ... 还有 {len(features) - 5} 个功能")

if __name__ == "__main__":
    main()
