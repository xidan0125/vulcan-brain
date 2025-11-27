#!/usr/bin/env python3
"""
Qwen-Agent 核心工具测试脚本 V2
直接使用Qwen-Agent内置工具
"""

import asyncio
from datetime import datetime
import pytz
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

# ============ 自定义工具: 时间感知 (内置没有) ============
@register_tool('get_time')
class GetCurrentTime(BaseTool):
    description = '获取当前时间、日期、星期。当用户询问"现在几点"、"今天星期几"、"今天日期"时使用。'
    parameters = [{'name': 'timezone', 'type': 'string', 'description': '时区，默认Asia/Shanghai', 'required': False}]
    
    def call(self, params: dict, **kwargs) -> str:
        tz_name = params.get('timezone', 'Asia/Shanghai')
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        weekday_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        return f"""当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
星期: {weekday_cn[now.weekday()]}
时区: {tz_name}"""

# ============ 自定义工具: SearXNG搜索 (覆盖默认web_search) ============
@register_tool('searxng_search')
class SearXNGSearch(BaseTool):
    description = '联网搜索实时信息。当需要查询最新新闻、实时数据、当前价格、天气等信息时使用。'
    parameters = [
        {'name': 'query', 'type': 'string', 'description': '搜索关键词', 'required': True},
    ]
    
    def call(self, params: dict, **kwargs) -> str:
        import requests
        query = params.get('query', '')
        
        try:
            resp = requests.get(
                'http://localhost:8080/search',
                params={'q': query, 'format': 'json', 'categories': 'general'},
                timeout=15
            )
            data = resp.json()
            results = data.get('results', [])[:5]
            
            if not results:
                return f'未找到关于 "{query}" 的搜索结果'
            
            output = f'搜索结果 ({query}):\n'
            for i, r in enumerate(results, 1):
                output += f'{i}. {r.get("title", "No title")}\n   {r.get("content", "")[:150]}\n\n'
            return output
        except Exception as e:
            return f'搜索失败: {str(e)}'

# ============ 自定义工具: 记忆 ============
@register_tool('remember')
class RememberInfo(BaseTool):
    description = '记住用户告诉你的重要信息。'
    parameters = [
        {'name': 'key', 'type': 'string', 'description': '类别', 'required': True},
        {'name': 'value', 'type': 'string', 'description': '内容', 'required': True}
    ]
    
    def call(self, params: dict, **kwargs) -> str:
        return f'已记住: {params.get("key")} = {params.get("value")}'


# ============ 主测试函数 ============
def test_qwen_agent():
    print('=' * 60)
    print('Qwen-Agent 核心工具测试')
    print('=' * 60)
    
    # 配置LLM - 使用Ollama
    llm_cfg = {
        'model': 'qwen3-thinking:latest',
        'model_server': 'http://localhost:11434/v1',
        'api_key': 'EMPTY',
    }
    
    # 工具列表: 内置 + 自定义
    # code_interpreter 是Qwen-Agent内置的
    tools = [
        'get_time',           # 自定义: 时间感知
        'searxng_search',     # 自定义: 联网搜索  
        'code_interpreter',   # 内置: 代码解释器
        'remember',           # 自定义: 记忆
    ]
    
    agent = Assistant(
        llm=llm_cfg,
        function_list=tools,
        system_message='你是Vulcan Brain智能助手。可以使用工具帮助用户。回答要简洁。'
    )
    
    # 测试用例
    test_cases = [
        '现在几点了？',
        '搜索一下今天比特币的价格',
        '用Python计算斐波那契数列前10项',
    ]
    
    for i, query in enumerate(test_cases, 1):
        print(f'\n{"="*60}')
        print(f'测试 {i}: {query}')
        print('='*60)
        try:
            response = agent.run(messages=[{'role': 'user', 'content': query}])
            for chunk in response:
                if hasattr(chunk, 'get'):
                    content = chunk.get('content', '')
                    if content:
                        print(content)
                else:
                    print(chunk)
        except Exception as e:
            print(f'错误: {type(e).__name__}: {e}')

if __name__ == '__main__':
    test_qwen_agent()
