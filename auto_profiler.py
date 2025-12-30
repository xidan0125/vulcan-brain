"""
自动维度分析器 - 自动发现所有字段并计算信息价值
"""
import json
import math
import kuzu
from collections import defaultdict

DB_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"
OUTPUT_PATH = "/home/xinyue/vulcan-brain/dimension_stats.json"

def get_connection():
    db = kuzu.Database(DB_PATH, read_only=True)
    return kuzu.Connection(db)

def calculate_entropy(distribution: dict) -> float:
    """计算归一化香农熵"""
    total = sum(distribution.values())
    if total == 0 or len(distribution) <= 1:
        return 0.0

    probabilities = [v/total for v in distribution.values()]
    entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
    max_entropy = math.log2(len(distribution))

    return round(entropy / max_entropy, 3) if max_entropy > 0 else 0

def calculate_score(distribution: dict, field_type: str = "categorical") -> dict:
    """计算维度得分"""
    total = sum(distribution.values())
    if total == 0:
        return {"entropy": 0, "score": 0, "useful": False, "reason": "无数据"}

    entropy = calculate_entropy(distribution)
    score = entropy
    reason = None

    # 惩罚1: 某类占比超95%
    max_ratio = max(distribution.values()) / total
    if max_ratio > 0.95:
        score *= 0.1
        top_value = max(distribution, key=distribution.get)
        reason = f"{top_value}占{max_ratio*100:.1f}%"

    # 惩罚2: 类别太多(>30)
    if len(distribution) > 30:
        score *= 0.6
        if not reason:
            reason = f"类别过多({len(distribution)}个)"

    # 惩罚3: 类别太少(<3)
    if len(distribution) < 3:
        score *= 0.5
        if not reason:
            reason = f"类别太少({len(distribution)}个)"

    return {
        "entropy": entropy,
        "score": round(score, 3),
        "cardinality": len(distribution),
        "total": total,
        "useful": score > 0.3,
        "reason": reason,
        "top3": dict(sorted(distribution.items(), key=lambda x: -x[1])[:3])
    }

def bucket_numeric(values: list) -> dict:
    """将数值分桶"""
    if not values:
        return {}

    buckets = {"<1K": 0, "1K-10K": 0, "10K-100K": 0, "100K-1M": 0, ">1M": 0}
    for v in values:
        if v < 1000:
            buckets["<1K"] += 1
        elif v < 10000:
            buckets["1K-10K"] += 1
        elif v < 100000:
            buckets["10K-100K"] += 1
        elif v < 1000000:
            buckets["100K-1M"] += 1
        else:
            buckets[">1M"] += 1

    # 移除空桶
    return {k: v for k, v in buckets.items() if v > 0}

def auto_discover_fields(conn) -> dict:
    """自动发现所有字段及其类型"""
    result = conn.execute('MATCH (e:BusinessEvent) RETURN e LIMIT 100')

    field_types = {}
    field_samples = defaultdict(list)

    while result.has_next():
        row = result.get_next()[0]
        for k, v in row.items():
            if k.startswith('_'):
                continue

            # 推断类型
            if k not in field_types:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    field_types[k] = "numeric"
                elif isinstance(v, str):
                    field_types[k] = "categorical"
                else:
                    field_types[k] = "other"

            field_samples[k].append(v)

    return field_types

def profile_field(conn, event_type: str, field: str, field_type: str) -> dict:
    """分析单个字段"""

    if field_type == "numeric":
        # 数值型：获取非零值并分桶
        cypher = f"""
        MATCH (e:BusinessEvent)
        WHERE e.event_type = '{event_type}' AND e.{field} > 0
        RETURN e.{field}
        """
        try:
            result = conn.execute(cypher)
            values = []
            while result.has_next():
                values.append(result.get_next()[0])

            if not values:
                return {"useful": False, "reason": "无有效数据", "score": 0}

            buckets = bucket_numeric(values)
            stats = calculate_score(buckets, "numeric")
            stats["type"] = "numeric"
            stats["non_zero_count"] = len(values)
            return stats
        except Exception as e:
            return {"error": str(e), "useful": False}

    else:
        # 分类型：统计分布
        cypher = f"""
        MATCH (e:BusinessEvent)
        WHERE e.event_type = '{event_type}'
        RETURN e.{field} as value, count(*) as cnt
        """
        try:
            result = conn.execute(cypher)
            distribution = {}
            while result.has_next():
                row = result.get_next()
                value = str(row[0]) if row[0] else "(空)"
                distribution[value] = row[1]

            stats = calculate_score(distribution, "categorical")
            stats["type"] = "categorical"
            return stats
        except Exception as e:
            return {"error": str(e), "useful": False}

def profile_all():
    """自动发现并分析所有字段"""
    conn = get_connection()

    # 1. 自动发现字段
    print("🔍 自动发现字段...")
    field_types = auto_discover_fields(conn)
    print(f"   发现 {len(field_types)} 个字段:")
    for f, t in field_types.items():
        print(f"     {f}: {t}")

    # 排除不适合分析的字段
    skip_fields = {'id', 'created_at', 'summary'}  # ID、时间戳、长文本
    analyze_fields = {k: v for k, v in field_types.items() if k not in skip_fields}

    print(f"\n📊 分析 {len(analyze_fields)} 个字段...")

    # 2. 获取所有事件类型
    result = conn.execute("""
    MATCH (e:BusinessEvent)
    WHERE e.event_type IN ['Payment', 'Order', 'Quotation', 'Shipment', 'Contract']
    RETURN DISTINCT e.event_type
    """)
    event_types = []
    while result.has_next():
        event_types.append(result.get_next()[0])

    # 3. 分析每个事件类型的每个字段
    all_stats = {}

    for event_type in event_types:
        print(f"\n{'='*50}")
        print(f"📦 {event_type}")
        print('='*50)

        all_stats[event_type] = {}

        for field, ftype in analyze_fields.items():
            stats = profile_field(conn, event_type, field, ftype)
            all_stats[event_type][field] = stats

            status = "✅" if stats.get("useful") else "❌"
            score = stats.get("score", 0)
            reason = stats.get("reason", "")
            ftype_icon = "🔢" if ftype == "numeric" else "📝"
            print(f"  {ftype_icon} {field}: {status} score={score:.2f} {reason or ''}")

    # 4. 生成推荐摘要
    print(f"\n{'='*50}")
    print("📋 推荐维度摘要")
    print('='*50)

    summary = {}
    for event_type in event_types:
        useful = [(f, s) for f, s in all_stats[event_type].items()
                  if s.get("useful") and not s.get("error")]
        useful.sort(key=lambda x: -x[1].get("score", 0))

        summary[event_type] = {
            "recommended": [f for f, s in useful[:3]],
            "avoid": [f for f, s in all_stats[event_type].items()
                     if not s.get("useful") and not s.get("error")]
        }
        print(f"\n{event_type}:")
        print(f"  ✅ 推荐: {', '.join(summary[event_type]['recommended']) or '无'}")
        print(f"  ❌ 避免: {', '.join(summary[event_type]['avoid'][:3]) or '无'}")

    # 5. 保存完整结果
    output = {
        "field_types": field_types,
        "stats": all_stats,
        "summary": summary
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 结果已保存到 {OUTPUT_PATH}")
    return output

if __name__ == "__main__":
    profile_all()
