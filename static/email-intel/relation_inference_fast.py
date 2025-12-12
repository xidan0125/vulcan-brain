"""
关系类型推理 - 快速版 (纯规则，无LLM)
L1规则处理60%，剩余40%默认colleague
"""

import json
from datetime import datetime

GRAPH_FILE = "/home/xinyue/vulcan-brain/static/email-intel/smart_graph_v5.json"
OUTPUT_FILE = "/home/xinyue/vulcan-brain/static/email-intel/graph_with_relations.json"

def heuristic_inference(t1: str, t2: str) -> str:
    # person + company -> works_at
    if (t1 == 'person' and t2 == 'company') or (t1 == 'company' and t2 == 'person'):
        return "works_at"
    # company + company -> business_partner
    if t1 == 'company' and t2 == 'company':
        return "business_partner"
    # person + project -> works_on
    if (t1 == 'person' and t2 == 'project') or (t1 == 'project' and t2 == 'person'):
        return "works_on"
    # company + project -> owns
    if (t1 == 'company' and t2 == 'project') or (t1 == 'project' and t2 == 'company'):
        return "owns"
    # person + person -> colleague (default)
    return "colleague"

def main():
    print("=" * 60)
    print("关系类型推理 - 快速版 (纯规则)")
    print("=" * 60)
    
    with open(GRAPH_FILE, "r") as f:
        data = json.load(f)
    
    relationships = data["top_relationships"]
    print(f"\n总共 {len(relationships)} 条关系")
    
    type_counts = {}
    for rel in relationships:
        t1, t2 = rel["entity1_type"], rel["entity2_type"]
        relation = heuristic_inference(t1, t2)
        rel["relation_type"] = relation
        type_counts[relation] = type_counts.get(relation, 0) + 1
    
    output = {
        "generated_at": datetime.now().isoformat(),
        "version": "fast_v1",
        "stats": data["stats"],
        "inference_stats": {
            "total": len(relationships),
            "method": "rule_based_only",
            "type_distribution": type_counts
        },
        "top_entities": data["top_entities"],
        "relationships": relationships
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("关系类型分布")
    print("=" * 60)
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = c * 100 / len(relationships)
        print(f"  {t}: {c} ({pct:.1f}%)")
    
    print(f"\n✅ 已保存: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
