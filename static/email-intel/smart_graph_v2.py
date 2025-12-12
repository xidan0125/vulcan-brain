"""
智能关系图构建器 V2 - 实体合并 + 关系推理
"""

import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict
from datetime import datetime
import json
import re

uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(uri)
db = client.vulcan_brain
emails = db.emails


def normalize_entity(entity_type: str, text: str) -> str:
    """实体标准化/合并"""
    text = text.strip()

    if entity_type == "person":
        # 移除邮箱后缀
        text = re.sub(r'@[\w.-]+', '', text).strip()
        # 移除 Vsg 后缀
        text = re.sub(r'\s*Vsg$', '', text, flags=re.IGNORECASE).strip()
        # 移除中间的点 (Barry.Claypool -> Barry Claypool)
        if '.' in text and '@' not in text:
            parts = text.split('.')
            if len(parts) == 2 and all(p[0].isupper() if p else False for p in parts):
                text = ' '.join(parts)
        # 首字母大写
        text = ' '.join(word.capitalize() for word in text.split())

    elif entity_type == "company":
        # 标准化公司名
        text = re.sub(r'\s+(Pte\.?|Ltd\.?|Inc\.?|Corp\.?|LLC)\.?$', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\s+', ' ', text)

    return text


async def build_smart_graph():
    """构建智能关系图"""
    print("=" * 60)
    print("智能关系图 V2 - 实体合并 + 关系推理")
    print("=" * 60)

    # 第一步：收集所有实体并标准化
    print("\n[1/4] 收集并标准化实体...")

    entity_map = {}  # normalized -> {original variants, count}
    cooccurrence = defaultdict(lambda: {"count": 0, "contexts": []})

    cursor = emails.find(
        {"entities": {"$exists": True, "$ne": []}},
        {"email_id": 1, "entities": 1, "subject": 1, "from": 1, "received_at": 1, "body_clean": 1}
    )

    processed = 0
    async for doc in cursor:
        entities = doc.get("entities", [])

        # 标准化实体
        normalized = []
        for e in entities:
            etype = e.get("type", "")
            etext = e.get("text", "").strip()

            if etype not in ["person", "company", "project"] or len(etext) < 2:
                continue

            norm_text = normalize_entity(etype, etext)
            if len(norm_text) < 2:
                continue

            key = f"{etype}:{norm_text}"
            normalized.append(key)

            if key not in entity_map:
                entity_map[key] = {"type": etype, "text": norm_text, "variants": set(), "count": 0}
            entity_map[key]["variants"].add(etext)
            entity_map[key]["count"] += 1

        # 构建共现
        normalized = list(set(normalized))
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                e1, e2 = sorted([normalized[i], normalized[j]])
                pair_key = f"{e1}||{e2}"
                cooccurrence[pair_key]["count"] += 1

                # 保存上下文用于关系推理
                if len(cooccurrence[pair_key]["contexts"]) < 3:
                    from_addr = doc.get("from", {})
                    if isinstance(from_addr, dict):
                        from_addr = from_addr.get("address", "")
                    cooccurrence[pair_key]["contexts"].append({
                        "subject": doc.get("subject", "")[:100],
                        "from": from_addr,
                        "snippet": (doc.get("body_clean") or "")[:200]
                    })

        processed += 1
        if processed % 10000 == 0:
            print(f"  已处理: {processed:,}")

    # 第二步：统计
    print(f"\n[2/4] 统计结果...")
    print(f"  - 标准化后唯一实体: {len(entity_map):,}")
    print(f"  - 标准化后唯一实体对: {len(cooccurrence):,}")

    # 只保留强关系 (5+ 次共现)
    strong_pairs = {k: v for k, v in cooccurrence.items() if v["count"] >= 5}
    print(f"  - 强关系 (5+次共现): {len(strong_pairs):,}")

    # 第三步：识别核心实体
    print(f"\n[3/4] 识别核心实体...")

    entity_importance = defaultdict(int)
    for pair_key, data in strong_pairs.items():
        e1, e2 = pair_key.split("||")
        entity_importance[e1] += data["count"]
        entity_importance[e2] += data["count"]

    top_entities = sorted(entity_importance.items(), key=lambda x: -x[1])[:50]

    print("\nTOP 20 核心实体:")
    for i, (entity, score) in enumerate(top_entities[:20], 1):
        etype, text = entity.split(":", 1)
        variants = entity_map[entity]["variants"]
        variant_str = f" (变体: {', '.join(list(variants)[:3])})" if len(variants) > 1 else ""
        print(f"  {i}. [{etype}] {text} - 关系强度:{score}{variant_str}")

    # 第四步：准备关系推理数据
    print(f"\n[4/4] 准备关系数据...")

    relationships = []
    for pair_key, data in sorted(strong_pairs.items(), key=lambda x: -x[1]["count"])[:500]:
        e1, e2 = pair_key.split("||")
        e1_type, e1_text = e1.split(":", 1)
        e2_type, e2_text = e2.split(":", 1)

        relationships.append({
            "entity1": {"type": e1_type, "text": e1_text},
            "entity2": {"type": e2_type, "text": e2_text},
            "cooccurrence_count": data["count"],
            "contexts": data["contexts"]
        })

    # 保存结果
    result = {
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "emails_processed": processed,
            "unique_entities_raw": len(entity_map),
            "unique_pairs_raw": len(cooccurrence),
            "strong_relationships": len(strong_pairs),
        },
        "top_entities": [
            {
                "entity": entity,
                "importance_score": score,
                "type": entity.split(":")[0],
                "text": entity.split(":")[1],
                "variants": list(entity_map[entity]["variants"])
            }
            for entity, score in top_entities
        ],
        "relationships": relationships
    }

    output_path = "/tmp/smart_graph_v2.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")

    # 输出摘要
    print("\n" + "=" * 60)
    print("关系网络摘要")
    print("=" * 60)

    # 按类型统计
    person_count = sum(1 for e in entity_map if e.startswith("person:"))
    company_count = sum(1 for e in entity_map if e.startswith("company:"))
    project_count = sum(1 for e in entity_map if e.startswith("project:"))

    print(f"""
实体统计:
  - 人员: {person_count:,}
  - 公司: {company_count:,}
  - 项目: {project_count:,}

关系统计:
  - 总实体对: {len(cooccurrence):,}
  - 强关系(5+次): {len(strong_pairs):,}
  - 中等关系(10+次): {sum(1 for v in cooccurrence.values() if v['count'] >= 10):,}
  - 核心关系(50+次): {sum(1 for v in cooccurrence.values() if v['count'] >= 50):,}

下一步: 对 {len(strong_pairs):,} 个强关系进行类型推理
预计时间: {len(strong_pairs) // 60 // 60} 小时 (假设 1秒/关系)
    """)

    return result


async def main():
    await build_smart_graph()


if __name__ == "__main__":
    asyncio.run(main())
