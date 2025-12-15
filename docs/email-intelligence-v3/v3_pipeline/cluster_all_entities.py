#!/usr/bin/env python3
"""
AI语义聚类 - 完整版
处理所有高频实体，生成同义词字典
"""
import json
import requests
import time

VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

with open('/tmp/entity_roster.json', 'r') as f:
    roster = json.load(f)
entities = roster['entities']
print(f"总共 {len(entities)} 个实体")


def call_llm(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 6000,
        "temperature": 0.1
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return content


def cluster_batch(batch_entities: list, start_idx: int) -> list:
    """聚类一批实体"""
    numbered = "\n".join([f"{i+1}. {e['name']}" for i, e in enumerate(batch_entities)])

    prompt = f"""找出下列实体中同一实体的不同写法：

{numbered}

返回JSON: [{{"canonical": "标准名", "aliases": [编号列表]}}]
只输出有多个变体的组。不要解释，直接输出JSON。"""

    response = call_llm(prompt)

    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        else:
            json_str = response

        result = json.loads(json_str.strip())

        # 转换编号为全局索引和实际名称
        clusters = []
        for c in result:
            canonical = c.get("canonical", "")
            aliases = c.get("aliases", [])
            alias_names = []
            for idx in aliases:
                if isinstance(idx, int) and 1 <= idx <= len(batch_entities):
                    alias_names.append(batch_entities[idx-1]['name'])
            if canonical and alias_names:
                clusters.append({
                    "canonical": canonical,
                    "aliases": alias_names
                })
        return clusters
    except Exception as e:
        print(f"    解析失败: {e}")
        return []


def main():
    print("="*60)
    print("🧠 AI语义聚类 - 完整版")
    print("="*60)

    # 处理前1000个高频实体（覆盖最重要的）
    top_n = 1000
    target = entities[:top_n]
    batch_size = 30  # 小批量更稳定

    all_clusters = []

    for i in range(0, len(target), batch_size):
        batch = target[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(target) + batch_size - 1) // batch_size

        print(f"\n[{batch_num}/{total_batches}] 处理第 {i+1}-{i+len(batch)} 个实体...")

        clusters = cluster_batch(batch, i)

        if clusters:
            print(f"    找到 {len(clusters)} 个聚类组")
            for c in clusters:
                print(f"      - {c['canonical']}: {len(c['aliases'])} 个")
            all_clusters.extend(clusters)
        else:
            print(f"    无聚类")

        # 稍微等待，避免过载
        time.sleep(0.5)

    # 构建字典
    print("\n" + "="*60)
    print("📖 构建同义词字典")
    print("="*60)

    dictionary = {}
    for c in all_clusters:
        canonical = c['canonical']
        for alias in c['aliases']:
            if alias != canonical:
                dictionary[alias] = canonical

    print(f"总聚类组: {len(all_clusters)}")
    print(f"总映射条目: {len(dictionary)}")

    # 保存
    output = {
        "clusters": all_clusters,
        "dictionary": dictionary,
        "stats": {
            "processed": top_n,
            "clusters": len(all_clusters),
            "mappings": len(dictionary)
        }
    }

    with open('/tmp/entity_dictionary.json', 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到 /tmp/entity_dictionary.json")

    # 显示关键映射
    print("\n=== 关键映射验证 ===")
    tests = [
        ("VSG", "Vulcan"),
        ("Barry", "Claypool"),
        ("vulcanshield", "Vulcan"),
        ("Space X", "SpaceX"),
        ("Sheng Kai", "Fong"),
        ("Microsoft Teams", "Microsoft"),
    ]
    for alias, should_contain in tests:
        if alias in dictionary:
            canonical = dictionary[alias]
            status = "✅" if should_contain.lower() in canonical.lower() else "⚠️"
            print(f"  {status} '{alias}' -> '{canonical}'")
        else:
            print(f"  ❌ '{alias}' 无映射")

    # 显示所有Vulcan相关映射
    print("\n=== Vulcan相关映射 ===")
    vulcan_mappings = {k: v for k, v in dictionary.items() if 'vulcan' in k.lower() or 'vsg' in k.lower() or 'vulcan' in v.lower()}
    for k, v in list(vulcan_mappings.items())[:20]:
        print(f"  '{k}' -> '{v}'")


if __name__ == '__main__':
    main()
