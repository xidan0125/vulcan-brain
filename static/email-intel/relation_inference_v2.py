"""
关系类型推理 V2 - 使用更长超时和更好的错误处理
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
MODEL = "qwen3:30b-a3b"


async def infer_relation(entity1: dict, entity2: dict, count: int) -> str:
    """使用 LLM 推断关系类型"""

    # 根据实体类型构建更精确的 prompt
    e1_type, e2_type = entity1['type'], entity2['type']

    if e1_type == 'person' and e2_type == 'person':
        prompt = f"""两个人: {entity1['text']} 和 {entity2['text']}
在邮件中共同出现 {count} 次。
他们最可能的关系是什么？
只回答一个词: colleague/supervisor/subordinate/contact
回答:"""
    elif e1_type == 'company' or e2_type == 'company':
        prompt = f"""实体: {entity1['text']} ({e1_type}) 和 {entity2['text']} ({e2_type})
在邮件中共同出现 {count} 次。
他们最可能的关系是什么？
只回答一个词: employee/client/vendor/partner
回答:"""
    else:
        prompt = f"""实体: {entity1['text']} 和 {entity2['text']}
在邮件中共同出现 {count} 次。
他们最可能的关系是什么？
只回答一个词: related/unknown
回答:"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_ctx": 1024, "temperature": 0.1, "num_predict": 20}
                }
            )
            result = resp.json().get("response", "").strip().lower()

            # 提取关系类型
            valid_types = ["colleague", "supervisor", "subordinate", "contact",
                          "employee", "client", "vendor", "partner", "related", "unknown"]
            for t in valid_types:
                if t in result:
                    return t
            return "related"
    except Exception as e:
        return "error"


async def main():
    print("=" * 60)
    print("关系类型推理 V2")
    print("=" * 60)

    with open("/tmp/smart_graph_v4.json", "r") as f:
        data = json.load(f)

    relationships = data["top_relationships"]

    # 处理 TOP 100
    to_process = relationships[:100]
    print(f"处理 TOP {len(to_process)} 个关系\n")

    results = []
    for i, rel in enumerate(to_process, 1):
        e1 = {"type": rel["entity1_type"], "text": rel["entity1"]}
        e2 = {"type": rel["entity2_type"], "text": rel["entity2"]}

        print(f"[{i}/{len(to_process)}] {e1['text'][:15]} ↔ {e2['text'][:15]}...", end=" ", flush=True)

        relation_type = await infer_relation(e1, e2, rel["count"])

        print(f"→ {relation_type}")

        results.append({
            "entity1": e1["text"],
            "entity1_type": e1["type"],
            "entity2": e2["text"],
            "entity2_type": e2["type"],
            "count": rel["count"],
            "relation_type": relation_type
        })

        # 每10个保存一次
        if i % 10 == 0:
            with open("/tmp/relation_types.json", "w") as f:
                json.dump({"results": results, "progress": i}, f, ensure_ascii=False, indent=2)

    # 最终保存
    output = {
        "generated_at": datetime.now().isoformat(),
        "total": len(results),
        "results": results
    }

    with open("/tmp/relation_types.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 统计
    print("\n" + "=" * 60)
    print("统计")
    print("=" * 60)

    type_counts = {}
    for r in results:
        t = r["relation_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    print(f"\n结果已保存到: /tmp/relation_types.json")


if __name__ == "__main__":
    asyncio.run(main())
