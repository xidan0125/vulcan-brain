"""
智能关系图 V3 - 加入别名合并
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

# ===== 别名映射表 =====
COMPANY_ALIASES = {
    # VSG 变体
    'vsg': 'Vulcan Shield Global',
    'vsg pte': 'Vulcan Shield Global',
    'vulcan shield global pte': 'Vulcan Shield Global',
    'vulcan shield globalpte': 'Vulcan Shield Global',
    'vulcanshieldglobal': 'Vulcan Shield Global',

    # Microsoft 变体
    'microsoft': 'Microsoft',
    'microsoft corporation': 'Microsoft',
    'microsoft teams': 'Microsoft Teams',  # 这个保留独立

    # 其他
    '3m': '3M',
}

# 人名别名 - 首名 -> 全名
PERSON_ALIASES = {
    'barry': 'Barry Claypool',
    'david': 'David Kneale',
    'david james kneale': 'David Kneale',
    'daniel': 'Daniel Hu',  # 假设只有一个 Daniel
    'matthias': 'Matthias Blaess',
    'renee': 'Renee Loke',
    'cindy': 'Cindy Wang',
    'shermaine': 'Shermaine Yeo',
    'glenn': 'Glenn',  # 保持
    'amanda': 'Amanda',  # 保持
    'widodo': 'Widodo',  # 保持
    'sheng kai': 'Fong Shengkai',
    'fong shengkai': 'Fong Shengkai',
    'loke siew fong': 'Renee Loke',  # 同一人
}


def normalize_entity_v3(entity_type: str, text: str) -> str:
    """实体标准化 V3 - 带别名合并"""
    text = text.strip()

    # 清理
    text = re.sub(r'@[\w.-]+', '', text).strip()  # 移除邮箱
    text = re.sub(r'\s*Vsg$', '', text, flags=re.IGNORECASE).strip()
    if '.' in text and '@' not in text and entity_type == 'person':
        parts = text.split('.')
        if len(parts) == 2:
            text = ' '.join(parts)
    text = ' '.join(word.capitalize() for word in text.split())

    # 别名查找
    text_lower = text.lower().strip()

    if entity_type == 'company':
        # 移除后缀再查
        clean = re.sub(r'\s*(pte\.?|ltd\.?|inc\.?|corp\.?)\.?$', '', text_lower, flags=re.IGNORECASE).strip()
        clean = re.sub(r'\s+', ' ', clean)
        if clean in COMPANY_ALIASES:
            return COMPANY_ALIASES[clean]
        if text_lower in COMPANY_ALIASES:
            return COMPANY_ALIASES[text_lower]

    elif entity_type == 'person':
        if text_lower in PERSON_ALIASES:
            return PERSON_ALIASES[text_lower]
        # 检查首名
        first_name = text_lower.split()[0] if text_lower.split() else ''
        if first_name in PERSON_ALIASES and len(first_name) >= 4:
            # 只有首名且首名足够长
            if len(text_lower.split()) == 1:
                return PERSON_ALIASES[first_name]

    return text


async def build_smart_graph_v3():
    """构建智能关系图 V3"""
    print("=" * 60)
    print("智能关系图 V3 - 别名合并")
    print("=" * 60)

    entity_map = {}
    cooccurrence = defaultdict(lambda: {"count": 0, "contexts": []})

    cursor = emails.find(
        {"entities": {"$exists": True, "$ne": []}},
        {"email_id": 1, "entities": 1, "subject": 1, "from": 1, "received_at": 1, "body_clean": 1}
    )

    processed = 0
    async for doc in cursor:
        entities = doc.get("entities", [])

        normalized = []
        for e in entities:
            etype = e.get("type", "")
            etext = e.get("text", "").strip()

            if etype not in ["person", "company", "project"] or len(etext) < 2:
                continue

            norm_text = normalize_entity_v3(etype, etext)
            if len(norm_text) < 2:
                continue

            key = f"{etype}:{norm_text}"
            normalized.append(key)

            if key not in entity_map:
                entity_map[key] = {"type": etype, "text": norm_text, "variants": set(), "count": 0}
            entity_map[key]["variants"].add(etext)
            entity_map[key]["count"] += 1

        normalized = list(set(normalized))
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                e1, e2 = sorted([normalized[i], normalized[j]])
                pair_key = f"{e1}||{e2}"
                cooccurrence[pair_key]["count"] += 1

                if len(cooccurrence[pair_key]["contexts"]) < 3:
                    from_addr = doc.get("from", {})
                    if isinstance(from_addr, dict):
                        from_addr = from_addr.get("address", "")
                    cooccurrence[pair_key]["contexts"].append({
                        "subject": doc.get("subject", "")[:100],
                        "from": from_addr,
                    })

        processed += 1
        if processed % 10000 == 0:
            print(f"  已处理: {processed:,}")

    # 统计
    print(f"\n标准化后唯一实体: {len(entity_map):,}")
    print(f"标准化后唯一实体对: {len(cooccurrence):,}")

    strong_pairs = {k: v for k, v in cooccurrence.items() if v["count"] >= 5}
    print(f"强关系 (5+次共现): {len(strong_pairs):,}")

    # 核心实体
    entity_importance = defaultdict(int)
    for pair_key, data in strong_pairs.items():
        e1, e2 = pair_key.split("||")
        entity_importance[e1] += data["count"]
        entity_importance[e2] += data["count"]

    top_entities = sorted(entity_importance.items(), key=lambda x: -x[1])[:30]

    print("\n" + "=" * 60)
    print("TOP 30 核心实体 (合并后)")
    print("=" * 60)

    for i, (entity, score) in enumerate(top_entities, 1):
        etype, text = entity.split(":", 1)
        variants = list(entity_map[entity]["variants"])[:5]
        variant_str = f" ← {variants}" if len(variants) > 1 else ""
        print(f"{i:2}. [{etype:7}] {text:25} 强度:{score:,}{variant_str}")

    # TOP 关系
    print("\n" + "=" * 60)
    print("TOP 20 关系 (合并后)")
    print("=" * 60)

    sorted_pairs = sorted(strong_pairs.items(), key=lambda x: -x[1]["count"])
    for pair_key, data in sorted_pairs[:20]:
        e1, e2 = pair_key.split("||")
        e1_text = e1.split(":")[1]
        e2_text = e2.split(":")[1]
        print(f"[{data['count']:4}次] {e1_text} ↔ {e2_text}")

    # 保存
    result = {
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "emails_processed": processed,
            "unique_entities": len(entity_map),
            "unique_pairs": len(cooccurrence),
            "strong_relationships": len(strong_pairs),
        },
        "top_entities": [
            {"entity": e, "importance": s, "type": e.split(":")[0], "text": e.split(":")[1]}
            for e, s in top_entities
        ],
        "top_relationships": [
            {
                "entity1": pk.split("||")[0].split(":")[1],
                "entity1_type": pk.split("||")[0].split(":")[0],
                "entity2": pk.split("||")[1].split(":")[1],
                "entity2_type": pk.split("||")[1].split(":")[0],
                "count": d["count"]
            }
            for pk, d in sorted_pairs[:200]
        ]
    }

    with open("/tmp/smart_graph_v3.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: /tmp/smart_graph_v3.json")

    # 检查是否还有重复
    print("\n" + "=" * 60)
    print("重复检查")
    print("=" * 60)

    # 公司检查
    companies = [e for e in top_entities if e[0].startswith("company:")]
    print("\n公司列表:")
    for e, s in companies:
        print(f"  {e.split(':')[1]}: {s}")

    # 人名检查
    persons = [e for e in top_entities if e[0].startswith("person:")]
    print("\n人员列表:")
    for e, s in persons[:15]:
        print(f"  {e.split(':')[1]}: {s}")

    return result


if __name__ == "__main__":
    asyncio.run(build_smart_graph_v3())
