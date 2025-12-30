import asyncio
import httpx
import re
import json

async def test():
    prompt = '''对以下事件去重，输出JSON:

数据:
- [GAIN] 样件确认 [1kg]: 北京研究院确认需求
- [GAIN] 开票通过 [294800元]: 开票申请通过

输出JSON格式:
{"SALES": [{"tag":"样件","style":"GAIN","summary":"描述","key_number":"1kg"}]}'''

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post('http://localhost:8000/v1/chat/completions', json={
            'model': 'Qwen/Qwen3-VL-30B-A3B-Thinking-FP8',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 3000
        })
        content = r.json()['choices'][0]['message']['content']

        print(f"Total length: {len(content)}")

        # 检查 think 标签
        think_start = content.find('<think>')
        think_end = content.find('</think>')
        print(f"<think> at: {think_start}")
        print(f"</think> at: {think_end}")

        # 显示 think 结束后的内容
        if think_end > 0:
            after_think = content[think_end+8:]
            print(f"\n=== After </think> ({len(after_think)} chars) ===")
            print(after_think)
        else:
            # 没有 </think>，找 JSON
            print("\nNo </think> found, looking for JSON...")
            # 找最后一个 { 开始的 JSON
            last_brace = content.rfind('{')
            if last_brace > 0:
                print(f"Last {{ at: {last_brace}")
                print(f"Content from there: {content[last_brace:last_brace+500]}")

asyncio.run(test())
