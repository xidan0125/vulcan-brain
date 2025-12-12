"""
关系类型推理 V3 - 架构师优化方案
L1: 规则层 - 90%关系直接定性
L2: 批量层 - 剩余10%打包推理
"""

import asyncio
import json
import os
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
os.chdir('/home/xinyue/vulcan-brain')
from dotenv import load_dotenv
load_dotenv('/home/xinyue/vulcan-brain/.env')

import httpx
from datetime import datetime

OLLAMA_HOST = os.getenv("LLM_BASE_URL", "http://localhost:11434")
MODEL = "qwen3:30b-a3b"
GRAPH_FILE = "/home/xinyue/vulcan-brain/static/email-intel/smart_graph_v4.json"
OUTPUT_FILE = "/home/xinyue/vulcan-brain/static/email-intel/graph_with_relations.json"


# ===== L1: 规则引擎 =====
def heuristic_inference(t1: str, t2: str) -> str:
    """基于实体类型的规则推断 - 毫秒级"""
    
    # 人 + 公司 -> works_at
    if (t1 == 'person' and t2 == 'company') or (t1 == 'company' and t2 == 'person'):
        return "works_at"
    
    # 公司 + 公司 -> business_partner
    if t1 == 'company' and t2 == 'company':
        return "business_partner"
    
    # 人 + 项目 -> works_on
    if (t1 == 'person' and t2 == 'project') or (t1 == 'project' and t2 == 'person'):
        return "works_on"
    
    # 公司 + 项目 -> owns
    if (t1 == 'company' and t2 == 'project') or (t1 == 'project' and t2 == 'company'):
        return "owns"
    
    # 人 + 人 -> 需要 LLM
    return None


# ===== L2: 批量LLM推理 =====
async def batch_llm_inference(pairs: list, client: httpx.AsyncClient) -> dict:
    """一次发送多对关系给LLM，返回JSON"""
    
    prompt = "分析以下人员关系，每对输出一个关系类型。\n"
    prompt += "可选类型: colleague(同事), supervisor(上级), subordinate(下级), contact(联系人)\n\n"
    
    for i, p in enumerate(pairs):
        prompt += f"{i}. {p['e1']} 和 {p['e2']} - 共现 {p['count']} 次\n"
    
    prompt += "\n只输出JSON格式，如: {\"0\":\"colleague\",\"1\":\"contact\"}\n/no_think"
    
    try:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 500}
            },
            timeout=180.0
        )
        data = resp.json()
        # qwen3是thinking model，内容可能在thinking字段
        result = data.get("response", "") or data.get("thinking", "")
        
        # 尝试解析JSON
        import re
        json_match = re.search(r'\{[^{}]+\}', result)
        if json_match:
            return json.loads(json_match.group())
        return {}
    except Exception as e:
        print(f"  Batch error: {e}")
        return {}


async def main():
    print("=" * 60)
    print("关系类型推理 V3 - 规则+批量优化")
    print("=" * 60)
    
    # 加载数据
    with open(GRAPH_FILE, "r") as f:
        data = json.load(f)
    
    relationships = data["top_relationships"]
    print(f"\n总共 {len(relationships)} 条关系")
    
    # L1: 规则过滤
    rule_results = []
    llm_pending = []
    
    for i, rel in enumerate(relationships):
        t1, t2 = rel["entity1_type"], rel["entity2_type"]
        relation = heuristic_inference(t1, t2)
        
        if relation:
            rel["relation_type"] = relation
            rule_results.append(rel)
        else:
            llm_pending.append({
                "idx": i,
                "e1": rel["entity1"],
                "e2": rel["entity2"],
                "count": rel["count"],
                "rel": rel
            })
    
    print(f"✅ 规则处理: {len(rule_results)} 条")
    print(f"⏳ 待LLM推理: {len(llm_pending)} 条 (person-person)")
    
    # L2: 批量LLM推理
    BATCH_SIZE = 10
    semaphore = asyncio.Semaphore(2)  # 限制并发
    
    async with httpx.AsyncClient() as client:
        batches = [llm_pending[i:i+BATCH_SIZE] for i in range(0, len(llm_pending), BATCH_SIZE)]
        
        for batch_idx, batch in enumerate(batches):
            async with semaphore:
                print(f"  Batch {batch_idx+1}/{len(batches)}...", end=" ", flush=True)
                results = await batch_llm_inference(batch, client)
                
                # 回填结果
                for i, item in enumerate(batch):
                    rel_type = results.get(str(i), "colleague")  # 默认同事
                    item["rel"]["relation_type"] = rel_type
                
                print(f"done ({len(results)} results)")
    
    # 合并并保存
    all_rels = relationships  # 原数据已就地更新
    
    output = {
        "generated_at": datetime.now().isoformat(),
        "stats": data["stats"],
        "stats_inference": {
            "total": len(all_rels),
            "rule_based": len(rule_results),
            "llm_inferred": len(llm_pending)
        },
        "top_entities": data["top_entities"],
        "relationships": all_rels
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 统计
    print("\n" + "=" * 60)
    print("关系类型分布")
    print("=" * 60)
    
    type_counts = {}
    for r in all_rels:
        t = r.get("relation_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    
    print(f"\n✅ 已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
