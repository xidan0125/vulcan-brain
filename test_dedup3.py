import asyncio
import httpx
import re
import json
import pymongo

async def test():
    # 加载真实数据
    mongo = pymongo.MongoClient("mongodb://localhost:27017")
    db = mongo.vulcan_brain
    doc = db.rongrong_filter_runs.find_one({"company": "shanghai", "date": "2025-12-26"})
    extraction = doc["extraction_results"]

    # 格式化数据
    lines = []
    for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
        items = extraction.get(cat, [])
        if items:
            lines.append(f"\n## {cat}")
            for item in items[:15]:  # 只取前15条
                tag = item.get("tag", "")
                style = item.get("style", "LOG")
                summary = item.get("summary", "")
                lines.append(f"- [{style}] {tag}: {summary}")

    raw_data = "\n".join(lines)
    print(f"Data length: {len(raw_data)}")

    prompt = f'''对以下事件去重，输出JSON:

{raw_data}

输出JSON格式:
{{"SALES": [{{"tag":"","style":"","summary":"","key_number":null}}], "GOVERNANCE": [], "DELIVERY": [], "OPERATIONS": []}}'''

    print(f"Prompt length: {len(prompt)}")

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post('http://localhost:8000/v1/chat/completions', json={
            'model': 'Qwen/Qwen3-VL-30B-A3B-Thinking-FP8',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 8000
        })
        content = r.json()['choices'][0]['message']['content']

        print(f"\nResponse length: {len(content)}")

        # 检查 think 标签
        think_start = content.find('<think>')
        think_end = content.find('</think>')
        print(f"<think> at: {think_start}")
        print(f"</think> at: {think_end}")

        if think_end > 0:
            after_think = content[think_end+8:].strip()
            print(f"\n=== After </think> ({len(after_think)} chars) ===")
            print(after_think[:2000])

            # 尝试解析
            try:
                parsed = json.loads(after_think)
                print("\nJSON parsed OK!")
                for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS"]:
                    print(f"  {cat}: {len(parsed.get(cat, []))} items")
            except Exception as e:
                print(f"\nJSON parse error: {e}")
        else:
            print("\nNo </think>, showing last 500 chars:")
            print(content[-500:])

asyncio.run(test())
