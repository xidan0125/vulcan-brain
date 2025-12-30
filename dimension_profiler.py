"""
维度分析器 - 预计算各事件类型各维度的信息价值
用于帮助Agent选择有意义的分析维度
"""
import json
import math
from pathlib import Path
import kuzu

DB_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"
OUTPUT_PATH = "/home/xinyue/vulcan-brain/dimension_stats.json"

def get_connection():
    db = kuzu.Database(DB_PATH)
    return kuzu.Connection(db)

def calculate_entropy(distribution: dict) -> float:
    """计算香农熵(归一化)"""
    total = sum(distribution.values())
    if total == 0:
        return 0.0
    
    probabilities = [v/total for v in distribution.values()]
    
    # 香农熵
    entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
    
    # 归一化 (消除类别数量偏差)
    num_classes = len(distribution)
    if num_classes <= 1:
        return 0.0
    
    max_entropy = math.log2(num_classes)
    normalized = entropy / max_entropy
    
    return round(normalized, 3)

def calculate_score(distribution: dict) -> dict:
    """计算维度得分，含业务规则惩罚"""
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
        reason = f"{top_value}占{max_ratio*100:.1f}%，几乎无差异"
    
    # 惩罚2: 类别太多(>20)，图表会乱
    if len(distribution) > 20:
        score *= 0.7
        if not reason:
            reason = f"类别过多({len(distribution)}个)"
    
    # 惩罚3: 类别太少(<3)
    if len(distribution) < 3:
        score *= 0.5
        if not reason:
            reason = f"类别太少({len(distribution)}个)"
    
    useful = score > 0.3
    
    return {
        "entropy": entropy,
        "score": round(score, 3),
        "cardinality": len(distribution),
        "total": total,
        "useful": useful,
        "reason": reason,
        "top3": dict(sorted(distribution.items(), key=lambda x: -x[1])[:3])
    }

def profile_dimension(conn, event_type: str, dimension: str) -> dict:
    """分析单个维度的分布"""
    cypher = f"""
    MATCH (e:BusinessEvent)
    WHERE e.event_type = '{event_type}'
    RETURN e.{dimension} as value, count(*) as cnt
    """
    try:
        result = conn.execute(cypher)
        distribution = {}
        while result.has_next():
            row = result.get_next()
            value = str(row[0]) if row[0] else "(空)"
            distribution[value] = row[1]
        return calculate_score(distribution)
    except Exception as e:
        return {"error": str(e), "useful": False}

def profile_all():
    """分析所有事件类型的所有维度"""
    conn = get_connection()
    
    event_types = ["Payment", "Order", "Quotation", "Shipment", "Contract"]
    dimensions = ["status", "counterparty", "counterparty_role", "currency"]
    
    result = {}
    
    for event_type in event_types:
        print(f"分析 {event_type}...")
        result[event_type] = {}
        
        for dim in dimensions:
            stats = profile_dimension(conn, event_type, dim)
            result[event_type][dim] = stats
            
            # 打印结果
            status = "✅" if stats.get("useful") else "❌"
            score = stats.get("score", 0)
            reason = stats.get("reason", "")
            print(f"  {dim}: {status} score={score:.2f} {reason}")
    
    # 保存结果
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到 {OUTPUT_PATH}")
    return result

if __name__ == "__main__":
    profile_all()
