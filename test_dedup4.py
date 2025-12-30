import asyncio
import httpx
import json
import pymongo

async def test():
    # 加载真实数据
    mongo = pymongo.MongoClient("mongodb://localhost:27017")
    db = mongo.vulcan_brain
    doc = db.rongrong_filter_runs.find_one({"company": "shanghai", "date": "2025-12-26"})
    extraction = doc["extraction_results"]

    # 格式化数据 - 只取前10条
    lines = []
    for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
        items = extraction.get(cat, [])
        if items:
            lines.append(f"\n## {cat}")
            for item in items[:10]:
                tag = item.get("tag", "")
                style = item.get("style", "LOG")
                summary = item.get("summary", "")[:50]  # 截断
                lines.append(f"- [{style}] {tag}: {summary}")

    raw_data = "\n".join(lines)
    print(f"Data length: {len(raw_data)}")

    prompt = f'''去重并输出JSON:
{raw_data}

格式: {{"SALES": [{{"tag":"","style":"","summary":"","key_number":null}}]}}'''

    print(f"Prompt length: {len(prompt)}")

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post('http://localhost:8000/v1/chat/completions', json={
            'model': 'Qwen/Qwen3-VL-30B-A3B-Thinking-FP8',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 6000
        })
        data = r.json()
        print(f"\nResponse keys: {data.keys()}")

        if 'error' in data:
            print(f"Error: {data['error']}")
        elif 'choices' in data:
            content = data['choices'][0]['message']['content']
            print(f"Content length: {len(content)}")

            # 找 </think>
            think_end = content.find('</think>')
            if think_end > 0:
                after = content[think_end+8:].strip()
                print(f"After </think>: {len(after)} chars")
                print(after[:1000])
            else:
                print(f"No </think>, content: {content[:1000]}")
        else:
            print(f"Unexpected response: {data}")

asyncio.run(test())
