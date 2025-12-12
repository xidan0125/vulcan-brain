"""
智能关系图 V5 - 完整版 (导出所有强关系)
修复: V4只导出200条，V5导出全部6,722条
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
import re
import json
from datetime import datetime

uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(uri)
db = client.vulcan_brain
emails = db.emails

# 公司别名 - 全部映射到标准名
COMPANY_CANONICAL = {
    'vulcan shield global': 'VSG',
    'vulcan shield global pte': 'VSG',
    'vulcan shield global pte.': 'VSG',
    'vulcan shield globalpte': 'VSG',
    'vulcan shield globalpte.': 'VSG',
    'vsg': 'VSG',
    'vsg pte': 'VSG',
    'microsoft corporation': 'Microsoft',
    'microsoft': 'Microsoft',
}

# 应该是人名而非公司
PERSON_NOT_COMPANY = {'sheng kai', 'sheng kai vsg'}

# 人名别名
PERSON_CANONICAL = {
    'david kneale': 'David Kneale',
    'david james kneale': 'David Kneale',
    'david': 'David Kneale',
    'barry claypool': 'Barry Claypool',
    'barry': 'Barry Claypool',
    'daniel hu': 'Daniel Hu',
    'daniel': 'Daniel Hu',
    'matthias blaess': 'Matthias Blaess',
    'matthias': 'Matthias Blaess',
    'renee loke': 'Renee Loke',
    'renee': 'Renee Loke',
    'loke siew fong': 'Renee Loke',
    'cindy wang': 'Cindy Wang',
    'cindy': 'Cindy Wang',
    'shermaine yeo': 'Shermaine Yeo',
    'shermaine': 'Shermaine Yeo',
    'fong shengkai': 'Shengkai Fong',
    'sheng kai': 'Shengkai Fong',
}


def normalize_v4(etype, text):
    text = text.strip()
    text = re.sub(r'@[\w.-]+', '', text).strip()
    text = re.sub(r'\s*Vsg$', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'[\xa0\n]', ' ', text)
    text = ' '.join(text.split())

    if '.' in text and '@' not in text and etype == 'person':
        parts = text.split('.')
        if len(parts) == 2:
            text = ' '.join(parts)

    text_lower = text.lower()

    # 检查是否误判为公司
    if etype == 'company' and text_lower in PERSON_NOT_COMPANY:
        etype = 'person'
        text_lower = text_lower

    if etype == 'company':
        clean = re.sub(r'\s*(pte\.?|ltd\.?|inc\.?|corp\.?)\s*$', '', text_lower).strip()
        if clean in COMPANY_CANONICAL:
            return etype, COMPANY_CANONICAL[clean]
        if text_lower in COMPANY_CANONICAL:
            return etype, COMPANY_CANONICAL[text_lower]

    if etype == 'person':
        if text_lower in PERSON_CANONICAL:
            return etype, PERSON_CANONICAL[text_lower]
        first = text_lower.split()[0] if text_lower.split() else ''
        if first in PERSON_CANONICAL and len(text_lower.split()) == 1:
            return etype, PERSON_CANONICAL[first]

    return etype, ' '.join(w.capitalize() for w in text.split())


async def main():
    entity_map = {}
    cooccurrence = defaultdict(int)

    cursor = emails.find(
        {"entities": {"$exists": True, "$ne": []}},
        {"entities": 1}
    )

    processed = 0
    async for doc in cursor:
        normalized = []
        for e in doc.get("entities", []):
            etype = e.get("type", "")
            etext = e.get("text", "").strip()
            if etype not in ["person", "company", "project"] or len(etext) < 2:
                continue
            etype, norm = normalize_v4(etype, etext)
            if len(norm) < 2:
                continue
            key = f"{etype}:{norm}"
            normalized.append(key)
            if key not in entity_map:
                entity_map[key] = {"type": etype, "text": norm, "count": 0}
            entity_map[key]["count"] += 1

        normalized = list(set(normalized))
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                e1, e2 = sorted([normalized[i], normalized[j]])
                cooccurrence[f"{e1}||{e2}"] += 1

        processed += 1
        if processed % 10000 == 0:
            print(f"  已处理: {processed:,}")

    # 强关系 = 5次以上共现
    strong = {k: v for k, v in cooccurrence.items() if v >= 5}

    # 计算实体重要性
    importance = defaultdict(int)
    for pk, cnt in strong.items():
        e1, e2 = pk.split("||")
        importance[e1] += cnt
        importance[e2] += cnt

    top = sorted(importance.items(), key=lambda x: -x[1])[:50]

    print("=" * 60)
    print("智能关系图 V5 - 完整版 (导出所有强关系)")
    print("=" * 60)
    print(f"\n处理邮件: {processed:,}")
    print(f"唯一实体: {len(entity_map):,}")
    print(f"唯一实体对: {len(cooccurrence):,}")
    print(f"强关系(5+): {len(strong):,}")

    print("\n" + "=" * 60)
    print("TOP 50 核心实体")
    print("=" * 60)
    for i, (e, s) in enumerate(top, 1):
        etype, text = e.split(":", 1)
        print(f"{i:2}. [{etype:7}] {text:25} 强度:{s:,}")

    # 保存结果 - V5: 导出所有强关系，不限制200
    sorted_rels = sorted(strong.items(), key=lambda x: -x[1])
    
    result = {
        "generated_at": datetime.now().isoformat(),
        "version": "v5",
        "stats": {
            "emails_processed": processed,
            "unique_entities": len(entity_map),
            "unique_pairs": len(cooccurrence),
            "strong_relationships": len(strong),
        },
        "top_entities": [
            {"entity": e, "importance": s, "type": e.split(":")[0], "text": e.split(":")[1]}
            for e, s in top
        ],
        "top_relationships": [
            {
                "entity1": pk.split("||")[0].split(":")[1],
                "entity1_type": pk.split("||")[0].split(":")[0],
                "entity2": pk.split("||")[1].split(":")[1],
                "entity2_type": pk.split("||")[1].split(":")[0],
                "count": cnt
            }
            for pk, cnt in sorted_rels  # 全部导出，不限制[:200]
        ]
    }

    output_file = "/home/xinyue/vulcan-brain/static/email-intel/smart_graph_v5.json"
    with open(output_file, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 {len(sorted_rels):,} 条关系到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
