import asyncio
import httpx
import re
import json

async def test():
    prompt = '''对以下事件去重，输出JSON:

数据:
- [GAIN] 样件确认 [1kg]: 北京研究院确认需求
- [GAIN] 开票通过 [294800元]: 开票申请通过
- [GAIN] 样件确认: 同一个北京研究院需求
- [RISK] 安全整改: 登高违规

输出JSON格式:
{"SALES": [{"tag":"样件","style":"GAIN","summary":"描述","key_number":"1kg"}], "GOVERNANCE": [], "DELIVERY": [], "OPERATIONS": []}'''

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post('http://localhost:8000/v1/chat/completions', json={
            'model': 'Qwen/Qwen3-VL-30B-A3B-Thinking-FP8',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 3000
        })
        content = r.json()['choices'][0]['message']['content']

        print(f"Total length: {len(content)}")

        # 移除 think 标签
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        print(f"After clean: {len(cleaned)}")
        print("=== Cleaned ===")
        print(cleaned)

        # 尝试提取 JSON
        start = cleaned.find('{')
        if start != -1:
            print(f"\nJSON starts at: {start}")
            # 找配对的 }
            depth = 0
            for i, c in enumerate(cleaned[start:], start):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = cleaned[start:i+1]
                        print(f"JSON length: {len(json_str)}")
                        try:
                            parsed = json.loads(json_str)
                            print("Parsed OK!")
                            print(json.dumps(parsed, ensure_ascii=False, indent=2))
                        except Exception as e:
                            print(f"Parse error: {e}")
                            print(f"JSON string: {json_str[:500]}")
                        break

asyncio.run(test())
