import json
from datetime import datetime
import pytz
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

@register_tool('get_time')
class GetTime(BaseTool):
    description = '获取当前时间'
    parameters = []
    def call(self, params, **kwargs) -> str:
        now = datetime.now(pytz.timezone('Asia/Shanghai'))
        return f'当前: {now.strftime("%Y-%m-%d %H:%M:%S")} 星期{"一二三四五六日"[now.weekday()]}'

@register_tool('search')
class Search(BaseTool):
    description = '联网搜索'
    parameters = [{'name': 'q', 'type': 'string', 'description': '关键词', 'required': True}]
    def call(self, params, **kwargs) -> str:
        import requests
        if isinstance(params, str): params = json.loads(params) if params else {}
        q = params.get('q', '')
        try:
            r = requests.get('http://localhost:8080/search', params={'q': q, 'format': 'json'}, timeout=10)
            res = r.json().get('results', [])[:3]
            return '\n'.join([f'{i+1}. {x["title"]}' for i,x in enumerate(res)]) or '无结果'
        except Exception as e: return f'错误: {e}'

# 关键: 使用 /no_think 禁用深度思考
llm = {'model': 'qwen3-thinking:latest', 'model_server': 'http://localhost:11434/v1', 'api_key': 'EMPTY'}
agent = Assistant(llm=llm, function_list=['get_time', 'search'], 
    system_message='/no_think\n你是助手，简洁回答。')

print('=== 测试1: 时间 ===')
for c in agent.run(messages=[{'role': 'user', 'content': '/no_think 现在几点'}]):
    if isinstance(c, list) and c:
        txt = c[-1].get('content', '')
        if txt and not txt.startswith('<think'): print(txt[-200:] if len(txt)>200 else txt)
print('\n=== 测试2: 搜索 ===')
for c in agent.run(messages=[{'role': 'user', 'content': '/no_think 搜比特币价格'}]):
    if isinstance(c, list) and c:
        txt = c[-1].get('content', '')
        if txt and not txt.startswith('<think'): print(txt[-200:] if len(txt)>200 else txt)
