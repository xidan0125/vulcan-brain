import json
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

@register_tool('search')
class Search(BaseTool):
    description = '联网搜索最新信息，如新闻、价格、天气等'
    parameters = [{'name': 'query', 'type': 'string', 'description': '搜索词', 'required': True}]
    
    def call(self, params, **kwargs) -> str:
        import requests
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        query = params.get('query', '')
        try:
            resp = requests.get('http://localhost:8080/search', params={'q': query, 'format': 'json'}, timeout=10)
            results = resp.json().get('results', [])[:3]
            return '\n'.join([f'{i+1}. {r["title"]}' for i,r in enumerate(results)]) or '无结果'
        except Exception as e:
            return f'错误: {e}'

llm = {'model': 'qwen3-thinking:latest', 'model_server': 'http://localhost:11434/v1', 'api_key': 'EMPTY'}
agent = Assistant(llm=llm, function_list=['search'], system_message='用中文简洁回答')

print('搜索测试: BTC价格')
for chunk in agent.run(messages=[{'role': 'user', 'content': '搜一下比特币今天价格'}]):
    if isinstance(chunk, list) and chunk:
        c = chunk[-1].get('content', '')
        if c and '</think>' in c:
            print(c.split('</think>')[-1].strip())
