#!/usr/bin/env python3
"""
AI语义聚类 - 用LLM识别同义实体

策略：
1. 按频次排序，分批处理（每批100个）
2. 让LLM找出同义词组
3. 输出 {alias: canonical} 映射字典
"""
import json
import requests
from pathlib import Path

# vLLM配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# 加载名册
with open('/tmp/entity_roster.json', 'r') as f:
    roster = json.load(f)

entities = roster['entities']
print(f"总共 {len(entities)} 个实体待聚类")


def call_llm(prompt: str) -> str:
    """调用vLLM"""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.1
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]

    # 处理thinking标签
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()

    return content


def parse_clusters(response: str) -> list:
    """解析LLM返回的聚类结果"""
    try:
        # 尝试提取JSON
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        data = json.loads(response.strip())

        # 兼容不同返回格式
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'clusters' in data:
            return data['clusters']
        else:
            return []
    except:
        return []


def cluster_batch(batch: list, batch_num: int) -> list:
    """对一批实体进行聚类"""
    # 构建编号列表
    numbered = "\n".join([f"{i+1}. {e['name']} ({e['count']}次)" for i, e in enumerate(batch)])

    prompt = f"""你是B2B企业数据专家。下面是一组实体名称列表（含出现频次）。

请找出**指代同一实体**的项目并分组。注意识别：
- 缩写（如 VSG = Vulcan Shield Global）
- 拼写错误（如 Vulcan Sheild = Vulcan Shield）
- 格式变体（如 Barry.Claypool = Barry Claypool）
- 名字顺序（如 Fong Sheng Kai = Sheng Kai Fong）
- 公司后缀（如 Pte. Ltd. = Pte = Ltd）

**重要：只合并确定是同一实体的，不确定就不要合并！**

实体列表：
{numbered}

请返回JSON格式：
[
  {{"canonical": "标准名称", "aliases": [编号列表]}},
  ...
]

只返回JSON，不要解释。只输出有多个变体的组（单独的实体不用输出）。"""

    print(f"\n=== Batch {batch_num}: {len(batch)} 个实体 ===")

    response = call_llm(prompt)
    clusters = parse_clusters(response)

    if clusters:
        print(f"找到 {len(clusters)} 个聚类组")
        for c in clusters[:3]:  # 显示前3个
            print(f"  - {c.get('canonical', 'N/A')}: {len(c.get('aliases', []))} 个别名")
    else:
        print("未找到聚类或解析失败")
        print(f"原始返回: {response[:200]}...")

    return clusters


def build_dictionary(all_clusters: list, entities: list) -> dict:
    """从聚类结果构建 alias -> canonical 字典"""
    dictionary = {}

    for cluster in all_clusters:
        canonical = cluster.get('canonical', '')
        aliases = cluster.get('aliases', [])

        if not canonical or not aliases:
            continue

        for alias_idx in aliases:
            try:
                # alias可能是编号或名称
                if isinstance(alias_idx, int):
                    idx = alias_idx - 1  # 编号从1开始
                    if 0 <= idx < len(entities):
                        alias_name = entities[idx]['name']
                        if alias_name != canonical:
                            dictionary[alias_name] = canonical
                elif isinstance(alias_idx, str):
                    if alias_idx != canonical:
                        dictionary[alias_idx] = canonical
            except:
                pass

    return dictionary


def main():
    print("="*60)
    print("🧠 AI语义聚类")
    print("="*60)

    # 先处理前500个高频实体（最重要的）
    # 完整处理8216个需要太久，先验证逻辑
    top_n = 500
    target_entities = entities[:top_n]

    print(f"\n处理前 {top_n} 个高频实体...")

    all_clusters = []
    batch_size = 100

    for i in range(0, len(target_entities), batch_size):
        batch = target_entities[i:i+batch_size]
        batch_num = i // batch_size + 1

        clusters = cluster_batch(batch, batch_num)

        # 转换编号为实际名称
        for c in clusters:
            resolved_aliases = []
            for alias_idx in c.get('aliases', []):
                try:
                    if isinstance(alias_idx, int):
                        idx = i + alias_idx - 1  # 全局索引
                        if 0 <= idx < len(entities):
                            resolved_aliases.append(entities[idx]['name'])
                    elif isinstance(alias_idx, str):
                        resolved_aliases.append(alias_idx)
                except:
                    pass
            c['aliases'] = resolved_aliases
            all_clusters.append(c)

    print(f"\n总共 {len(all_clusters)} 个聚类组")

    # 构建字典
    # 注意：这里用原始entities列表构建
    dictionary = {}
    for c in all_clusters:
        canonical = c.get('canonical', '')
        for alias in c.get('aliases', []):
            if alias and alias != canonical:
                dictionary[alias] = canonical

    print(f"生成 {len(dictionary)} 条映射")

    # 保存字典
    output = {
        'clusters': all_clusters,
        'dictionary': dictionary,
        'stats': {
            'total_entities': len(target_entities),
            'clusters_found': len(all_clusters),
            'mappings': len(dictionary)
        }
    }

    with open('/tmp/entity_dictionary.json', 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到 /tmp/entity_dictionary.json")

    # 显示关键映射
    print("\n=== 关键映射检查 ===")
    key_tests = ['VSG', 'Barry', 'vulcanshield', 'Space X', 'Sheng Kai']
    for key in key_tests:
        if key in dictionary:
            print(f"  ✅ '{key}' -> '{dictionary[key]}'")
        else:
            # 尝试不区分大小写
            found = False
            for k, v in dictionary.items():
                if k.lower() == key.lower():
                    print(f"  ✅ '{k}' -> '{v}'")
                    found = True
                    break
            if not found:
                print(f"  ❓ '{key}' 未找到映射")


if __name__ == '__main__':
    main()
