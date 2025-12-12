#!/usr/bin/env python3
"""测试添加stop tokens是否能解决无限思考问题"""

import json
from datetime import datetime
import pytz
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

@register_tool('get_time')
class GetCurrentTime(BaseTool):
    description = '获取当前时间'
    parameters = [{'name': 'timezone', 'type': 'string', 'description': '时区', 'required': False}]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        tz_name = params.get('timezone', 'Asia/Shanghai') if isinstance(params, dict) else 'Asia/Shanghai'
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return f'当前时间: {now.strftime("%Y-%m-%d %H:%M:%S")} 星期{"一二三四五六日"[now.weekday()]}'

@register_tool('searxng')
class SearXNG(BaseTool):
    description = '联网搜索信息'
    parameters = [{'name': 'query', 'type': 'string', 'description': '搜索关键词', 'required': True}]
    
    def call(self, params, **kwargs) -> str:
        import requests
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        query = params.get('query', '') if isinstance(params, dict) else str(params)
        try:
            resp = requests.get('http://localhost:8080/search', params={'q': query, 'format': 'json'}, timeout=10)
            results = resp.json().get('results', [])[:3]
            if not results:
                return f'未找到关于{query}的结果'
            return '\n'.join([f'{i+1}. {r["title"]}: {r.get("content","")[:100]}' for i,r in enumerate(results)])
        except Exception as e:
            return f'搜索失败: {e}'

def test_with_stop_tokens():
    print('='*60)
    print('测试: 添加stop tokens + </tool_call>作为停止符')
    print('='*60)
    
    llm_cfg = {
        'model': 'qwen3-thinking:latest', 
        'model_server': 'http://localhost:11434/v1', 
        'api_key': 'EMPTY',
        'generate_cfg': {
            # 关键修复：添加stop tokens
            'stop': ['</tool_call>', '<|im_end|>', 'Observation:'],
            'max_input_tokens': 6000,
        }
    }
    
    agent = Assistant(
        llm=llm_cfg, 
        function_list=['get_time', 'searxng'], 
        system_message='你是一个助手。简洁回答问题。'
    )
    
    # 测试搜索 - 这是之前卡住的场景
    print('\n测试: 搜索今日新闻')
    import time
    start = time.time()
    
    try:
        for i, chunk in enumerate(agent.run(messages=[{'role': 'user', 'content': '搜索一下今天的新闻'}])):
            elapsed = time.time() - start
            if elapsed > 30:
                print(f'\n超时30秒，终止')
                break
            if isinstance(chunk, list) and chunk:
                c = chunk[-1].get('content', '')
                if c:
                    # 只打印非思考内容
                    if '<think>' not in c:
                        print(f'[{elapsed:.1f}s] {c[:200]}')
                    else:
                        print(f'[{elapsed:.1f}s] (thinking中...长度:{len(c)})')
    except Exception as e:
        print(f'错误: {e}')
    
    print(f'\n总耗时: {time.time()-start:.1f}秒')

if __name__ == '__main__':
    test_with_stop_tokens()
