"""
智能关系图构建器 - 基于 Phase 2 实体数据
不重复做实体抽取，利用已有数据构建关系网络
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

# MongoDB 连接
uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(uri)
db = client.vulcan_brain
emails = db.emails


async def analyze_entity_cooccurrence():
    """
    分析实体共现关系
    如果两个实体出现在同一封邮件中，它们就有关联
    """
    print("=" * 60)
    print("智能关系图构建 - 基于共现分析")
    print("=" * 60)

    # 统计已有实体的邮件数量
    total_with_entities = await emails.count_documents({
        "entities": {"$exists": True, "$ne": []}
    })
    print(f"\n已有实体数据的邮件: {total_with_entities:,}")

    # 收集实体共现
    cooccurrence = defaultdict(lambda: {"count": 0, "emails": []})
    entity_info = {}  # 存储实体详情

    print("\n正在分析共现关系...")

    cursor = emails.find(
        {"entities": {"$exists": True, "$ne": []}},
        {"email_id": 1, "entities": 1, "subject": 1, "received_at": 1}
    )

    processed = 0
    async for doc in cursor:
        entities = doc.get("entities", [])
        if len(entities) < 2:
            continue

        # 提取有效实体（人、公司、项目）
        valid_entities = []
        for e in entities:
            etype = e.get("type", "")
            etext = e.get("text", "").strip()
            if etype in ["person", "company", "project"] and len(etext) >= 2:
                key = f"{etype}:{etext}"
                valid_entities.append(key)
                if key not in entity_info:
                    entity_info[key] = {"type": etype, "text": etext, "count": 0}
                entity_info[key]["count"] += 1

        # 构建共现对
        valid_entities = list(set(valid_entities))  # 去重
        for i in range(len(valid_entities)):
            for j in range(i + 1, len(valid_entities)):
                e1, e2 = sorted([valid_entities[i], valid_entities[j]])
                pair_key = f"{e1}||{e2}"
                cooccurrence[pair_key]["count"] += 1
                if len(cooccurrence[pair_key]["emails"]) < 5:  # 保存最多5个示例
                    cooccurrence[pair_key]["emails"].append({
                        "email_id": doc["email_id"],
                        "subject": doc.get("subject", "")[:50],
                        "date": doc.get("received_at").isoformat() if doc.get("received_at") else None
                    })

        processed += 1
        if processed % 10000 == 0:
            print(f"  已处理: {processed:,} 封邮件, 发现 {len(cooccurrence):,} 个实体对")

    print(f"\n处理完成!")
    print(f"  - 处理邮件数: {processed:,}")
    print(f"  - 唯一实体数: {len(entity_info):,}")
    print(f"  - 唯一实体对: {len(cooccurrence):,}")

    # 按共现次数排序
    sorted_pairs = sorted(
        cooccurrence.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    # 统计分布
    print("\n共现次数分布:")
    distribution = defaultdict(int)
    for _, data in sorted_pairs:
        count = data["count"]
        if count >= 100:
            distribution["100+"] += 1
        elif count >= 50:
            distribution["50-99"] += 1
        elif count >= 20:
            distribution["20-49"] += 1
        elif count >= 10:
            distribution["10-19"] += 1
        elif count >= 5:
            distribution["5-9"] += 1
        else:
            distribution["1-4"] += 1

    for k, v in sorted(distribution.items(), key=lambda x: -int(x[0].split("-")[0].replace("+", ""))):
        print(f"  {k} 次: {v:,} 对")

    # 显示 TOP 关系
    print("\n" + "=" * 60)
    print("TOP 30 最强关联实体对:")
    print("=" * 60)

    for pair_key, data in sorted_pairs[:30]:
        e1, e2 = pair_key.split("||")
        print(f"\n[{data['count']}次] {e1} <-> {e2}")
        print(f"  示例邮件: {data['emails'][0]['subject'] if data['emails'] else 'N/A'}")

    # 保存结果
    result = {
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "emails_processed": processed,
            "unique_entities": len(entity_info),
            "unique_pairs": len(cooccurrence),
            "distribution": dict(distribution)
        },
        "top_relationships": [
            {
                "entity1": pair_key.split("||")[0],
                "entity2": pair_key.split("||")[1],
                "cooccurrence_count": data["count"],
                "sample_emails": data["emails"]
            }
            for pair_key, data in sorted_pairs[:500]  # TOP 500
        ],
        "all_entities": [
            {"key": k, **v} for k, v in sorted(
                entity_info.items(),
                key=lambda x: -x[1]["count"]
            )[:1000]  # TOP 1000 实体
        ]
    }

    output_path = "/tmp/entity_cooccurrence_graph.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")

    return result


async def main():
    result = await analyze_entity_cooccurrence()

    print("\n" + "=" * 60)
    print("下一步: 使用 LLM 推理关系类型")
    print("=" * 60)
    print(f"""
只需要处理 {result['stats']['unique_pairs']:,} 个实体对
而不是 56,868 封邮件！

优化效果:
- 原方案: 56,868 封邮件 × LLM 处理 = ~13天
- 新方案: {result['stats']['unique_pairs']:,} 实体对 × 关系推理 = 估计 {result['stats']['unique_pairs'] // 60 // 60} 小时
    """)


if __name__ == "__main__":
    asyncio.run(main())
