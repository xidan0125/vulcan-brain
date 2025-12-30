"""
关系类型推理 - 使用 LLM 推断实体间关系类型
只处理 TOP 关系，快速完成
"""

import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

import json
import httpx
from datetime import datetime

OLLAMA_HOST = os.getenv("LLM_BASE_URL", "http://localhost:8000")
MODEL = os.getenv("LLM_MODEL_NAME", "qwen3:30b-a3b")


async def infer_relation(entity1: dict, entity2: dict, count: int, contexts: list = None) -> str:
    """使用 LLM 推断关系类型"""

    prompt = f"""分析以下两个实体的关系类型。

实体1: [{entity1['type']}] {entity1['text']}
实体2: [{entity2['type']}] {entity2['text']}
共现次数: {count}

请从以下类型中选择最可能的关系（只输出类型名，不要解释）:
- colleague (同事)
- reports_to (汇报给)
- manages (管理)
- works_at (工作于)
- client (客户)
- vendor (供应商)
- partner (合作伙伴)
- contact (联系人)
- unknown (未知)

关系类型:"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_ctx": 2048, "temperature": 0.1}
                }
            )
            result = resp.json().get("response", "").strip().lower()

            # 提取关系类型
            valid_types = ["colleague", "reports_to", "manages", "works_at",
                          "client", "vendor", "partner", "contact", "unknown"]
            for t in valid_types:
                if t in result:
                    return t
            return "unknown"
    except Exception as e:
        print(f"  Error: {e}")
        return "unknown"


async def main():
    print("=" * 60)
    print("关系类型推理")
    print("=" * 60)

    # 加载关系数据
    with open("/tmp/smart_graph_v4.json", "r") as f:
        data = json.load(f)

    relationships = data["top_relationships"]
    print(f"\n共 {len(relationships)} 个关系待推理")

    # 只处理 TOP 50 (演示)
    to_process = relationships[:50]
    print(f"处理 TOP {len(to_process)} 个关系\n")

    results = []
    for i, rel in enumerate(to_process, 1):
        e1 = {"type": rel["entity1_type"], "text": rel["entity1"]}
        e2 = {"type": rel["entity2_type"], "text": rel["entity2"]}

        print(f"[{i}/{len(to_process)}] {e1['text']} ↔ {e2['text']}...", end=" ", flush=True)

        relation_type = await infer_relation(e1, e2, rel["count"])

        print(f"→ {relation_type}")

        results.append({
            "entity1": e1,
            "entity2": e2,
            "count": rel["count"],
            "relation_type": relation_type
        })

    # 统计
    print("\n" + "=" * 60)
    print("关系类型统计")
    print("=" * 60)

    type_counts = {}
    for r in results:
        t = r["relation_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    # 按类型展示
    print("\n" + "=" * 60)
    print("按类型展示关系")
    print("=" * 60)

    for rel_type in ["colleague", "works_at", "client", "vendor", "partner"]:
        rels = [r for r in results if r["relation_type"] == rel_type]
        if rels:
            print(f"\n【{rel_type}】")
            for r in rels[:5]:
                print(f"  {r['entity1']['text']} ↔ {r['entity2']['text']} ({r['count']}次)")

    # 保存
    output = {
        "generated_at": datetime.now().isoformat(),
        "processed": len(results),
        "type_distribution": type_counts,
        "relationships": results
    }

    with open("/tmp/relation_types.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: /tmp/relation_types.json")


if __name__ == "__main__":
    asyncio.run(main())
