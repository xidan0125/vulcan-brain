#!/usr/bin/env python3
"""
AI语义聚类 V2 - 小批量 + 大token限制
"""
import json
import requests

VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

with open('/tmp/entity_roster.json', 'r') as f:
    roster = json.load(f)
entities = roster['entities']


def call_llm(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8000,  # 增大
        "temperature": 0.1
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    return content


def cluster_batch(batch: list) -> list:
    """小批量聚类"""
    numbered = "\n".join([f"{i+1}. {e['name']}" for i, e in enumerate(batch)])

    prompt = f"""找出下列实体中**同一实体的不同写法**，返回JSON。

规则：
- 缩写：VSG = Vulcan Shield Global
- 拼写错误：Sheild = Shield
- 格式：Barry.Claypool = Barry Claypool
- 后缀：Pte. Ltd. = Pte

实体：
{numbered}

输出格式：
[{{"canonical": "标准名", "aliases": [编号]}}]

只返回JSON，只输出有多个变体的组。"""

    response = call_llm(prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())
    except Exception as e:
        print(f"  解析失败: {e}")
        print(f"  返回内容: {response[:300]}")
        return []


# 先测试一个小批次
print("="*60)
print("🧪 测试小批量聚类 (前30个)")
print("="*60)

test_batch = entities[:30]
for i, e in enumerate(test_batch, 1):
    print(f"{i:2d}. {e['name']}")

print("\n调用LLM...")
result = cluster_batch(test_batch)

print(f"\n找到 {len(result)} 个聚类组:")
for c in result:
    canonical = c.get('canonical', '')
    aliases = c.get('aliases', [])
    alias_names = []
    for idx in aliases:
        if isinstance(idx, int) and 1 <= idx <= len(test_batch):
            alias_names.append(test_batch[idx-1]['name'])
    print(f"  ✅ {canonical}")
    print(f"     别名: {alias_names}")
