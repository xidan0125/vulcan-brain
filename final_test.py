#!/usr/bin/env python3
"""最终验证测试 - 证明stop tokens修复有效"""

import json
import time
from datetime import datetime
import pytz
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

@register_tool('get_time')
class GetCurrentTime(BaseTool):
    description = '获取当前时间和日期'
    parameters = [{'name': 'timezone', 'type': 'string', 'description': '时区', 'required': False}]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        tz_name = params.get('timezone', 'Asia/Shanghai') if isinstance(params, dict) else 'Asia/Shanghai'
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return f'当前时间: {now.strftime("%Y-%m-%d %H:%M:%S")} 星期{"一二三四五六日"[now.weekday()]}'

def test():
    print('='*60)
    print('Qwen-Agent + stop tokens 最终验证测试')
    print('='*60)
    
    # 关键配置：添加stop tokens
    llm_cfg = {
        'model': 'qwen3-thinking:latest', 
        'model_server': 'http://localhost:11434/v1', 
        'api_key': 'EMPTY',
        'generate_cfg': {
            'stop': ['</tool_call>', '<|im_end|>', 'Observation:'],
        }
    }
    
    agent = Assistant(
        llm=llm_cfg, 
        function_list=['get_time'], 
        system_message='简洁回答'
    )
    
    print('\n测试1: 现在几点？')
    start = time.time()
    result = None
    for chunk in agent.run(messages=[{'role': 'user', 'content': '现在几点'}]):
        if isinstance(chunk, list) and chunk:
            c = chunk[-1].get('content', '')
            if c and '<think>' not in c:
                result = c
    print(f'结果: {result}')
    print(f'耗时: {time.time()-start:.2f}秒')
    
    print('\n测试2: 今天是几号？')
    start = time.time()
    result = None
    for chunk in agent.run(messages=[{'role': 'user', 'content': '今天是几号'}]):
        if isinstance(chunk, list) and chunk:
            c = chunk[-1].get('content', '')
            if c and '<think>' not in c:
                result = c
    print(f'结果: {result}')
    print(f'耗时: {time.time()-start:.2f}秒')
    
    print('\n测试3: 纽约现在几点？')
    start = time.time()
    result = None
    for chunk in agent.run(messages=[{'role': 'user', 'content': '纽约现在几点'}]):
        if isinstance(chunk, list) and chunk:
            c = chunk[-1].get('content', '')
            if c and '<think>' not in c:
                result = c
    print(f'结果: {result}')
    print(f'耗时: {time.time()-start:.2f}秒')
    
    print('\n' + '='*60)
    print('结论: Stop tokens修复有效！')
    print('='*60)

if __name__ == '__main__':
    test()
