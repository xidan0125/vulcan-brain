#!/usr/bin/env python3
"""Qwen-Agent 测试 V3 - 修复参数解析"""

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
        # 关键修复：params可能是字符串，需要解析
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        tz_name = params.get('timezone', 'Asia/Shanghai') if isinstance(params, dict) else 'Asia/Shanghai'
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return f'当前时间: {now.strftime("%Y-%m-%d %H:%M:%S")} 星期{"一二三四五六日"[now.weekday()]}'

@register_tool('searxng')
class SearXNG(BaseTool):
    description = '联网搜索'
    parameters = [{'name': 'query', 'type': 'string', 'description': '搜索词', 'required': True}]
    
    def call(self, params, **kwargs) -> str:
        import requests
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        query = params.get('query', '') if isinstance(params, dict) else str(params)
        try:
            resp = requests.get('http://localhost:8080/search', params={'q': query, 'format': 'json'}, timeout=10)
            results = resp.json().get('results', [])[:3]
            if not results:
                return f'未找到{query}的结果'
            return '\n'.join([f'{i+1}. {r["title"]}: {r.get("content","")[:100]}' for i,r in enumerate(results)])
        except Exception as e:
            return f'搜索失败: {e}'

def test():
    llm_cfg = {'model': 'qwen3-thinking:latest', 'model_server': 'http://localhost:11434/v1', 'api_key': 'EMPTY'}
    agent = Assistant(llm=llm_cfg, function_list=['get_time', 'searxng'], system_message='简洁回答')
    
    print('测试: 现在几点？')
    for chunk in agent.run(messages=[{'role': 'user', 'content': '现在几点'}]):
        if isinstance(chunk, list) and chunk:
            c = chunk[-1].get('content', '')
            if c and not c.startswith('<think'):
                print(c)
        
if __name__ == '__main__':
    test()
