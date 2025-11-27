#!/usr/bin/env python3
"""
Vulcan Brain V2 - 核心工具集
基于Qwen-Agent + stop tokens修复
"""

import json
import requests
from datetime import datetime
import pytz
from qwen_agent.tools.base import BaseTool, register_tool

# ============== 工具1: 时间获取 ==============
@register_tool('get_time')
class GetCurrentTime(BaseTool):
    description = '获取当前时间和日期，支持不同时区'
    parameters = [
        {'name': 'timezone', 'type': 'string', 'description': '时区，如Asia/Shanghai, America/New_York', 'required': False}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        tz_name = params.get('timezone', 'Asia/Shanghai') if isinstance(params, dict) else 'Asia/Shanghai'
        try:
            tz = pytz.timezone(tz_name)
        except:
            tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        weekday = "一二三四五六日"[now.weekday()]
        return f'当前时间: {now.strftime("%Y-%m-%d %H:%M:%S")} 星期{weekday} ({tz_name})'

# ============== 工具2: 联网搜索 ==============
@register_tool('searxng_search')
class WebSearch(BaseTool):
    description = '联网搜索最新信息，包括新闻、价格、事件等'
    parameters = [
        {'name': 'query', 'type': 'string', 'description': '搜索关键词', 'required': True}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        query = params.get('query', '') if isinstance(params, dict) else str(params)
        
        if not query:
            return '错误: 请提供搜索关键词'
        
        try:
            resp = requests.get(
                'http://localhost:8080/search',
                params={'q': query, 'format': 'json'},
                timeout=15
            )
            data = resp.json()
            results = data.get('results', [])[:5]
            
            if not results:
                return f'未找到关于「{query}」的搜索结果'
            
            output = f'搜索「{query}」的结果:\n\n'
            for i, r in enumerate(results, 1):
                title = r.get('title', '无标题')
                content = r.get('content', '')[:150]
                url = r.get('url', '')
                output += f'{i}. **{title}**\n   {content}...\n   来源: {url}\n\n'
            return output
        except Exception as e:
            return f'搜索失败: {str(e)}'

# ============== 工具3: 代码解释器 ==============
@register_tool('python_exec')
class CodeInterpreter(BaseTool):
    description = '执行Python代码进行计算、数据分析、图表生成等'
    parameters = [
        {'name': 'code', 'type': 'string', 'description': 'Python代码', 'required': True}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        code = params.get('code', '') if isinstance(params, dict) else str(params)
        
        if not code:
            return '错误: 请提供要执行的代码'
        
        # 安全的代码执行环境
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        
        # 限制可用的模块
        safe_globals = {
            '__builtins__': {
                'print': print, 'len': len, 'range': range, 'str': str, 'int': int, 
                'float': float, 'list': list, 'dict': dict, 'sum': sum, 'max': max, 
                'min': min, 'abs': abs, 'round': round, 'sorted': sorted, 'enumerate': enumerate,
                'zip': zip, 'map': map, 'filter': filter, 'True': True, 'False': False, 'None': None
            }
        }
        
        # 导入常用安全模块
        try:
            import math
            safe_globals['math'] = math
        except: pass
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, safe_globals)
            
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            
            result = ''
            if output:
                result += f'输出:\n{output}'
            if errors:
                result += f'\n警告:\n{errors}'
            if not result:
                result = '代码执行完成，无输出'
            return result
        except Exception as e:
            return f'执行错误: {str(e)}'

# ============== 工具4: 记忆存储/检索 ==============
@register_tool('memory')  
class MemoryTool(BaseTool):
    description = '存储或检索重要信息到长期记忆'
    parameters = [
        {'name': 'action', 'type': 'string', 'description': 'save(保存) 或 search(搜索)', 'required': True},
        {'name': 'content', 'type': 'string', 'description': '要保存或搜索的内容', 'required': True},
        {'name': 'category', 'type': 'string', 'description': '分类标签', 'required': False}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        
        action = params.get('action', 'search')
        content = params.get('content', '')
        category = params.get('category', 'general')
        
        # 简单的内存存储（实际应用中连接MongoDB/Milvus）
        import os
        memory_file = os.path.expanduser('~/.vulcan_memory.json')
        
        try:
            if os.path.exists(memory_file):
                with open(memory_file, 'r') as f:
                    memories = json.load(f)
            else:
                memories = []
        except:
            memories = []
        
        if action == 'save':
            memories.append({
                'content': content,
                'category': category,
                'timestamp': datetime.now().isoformat()
            })
            with open(memory_file, 'w') as f:
                json.dump(memories[-100:], f, ensure_ascii=False)  # 保留最近100条
            return f'已保存到记忆: {content[:50]}...'
        
        elif action == 'search':
            # 简单关键词匹配
            matches = [m for m in memories if content.lower() in m['content'].lower()]
            if not matches:
                return f'未找到与「{content}」相关的记忆'
            
            output = f'找到 {len(matches)} 条相关记忆:\n\n'
            for i, m in enumerate(matches[-5:], 1):
                output += f'{i}. [{m[category]}] {m[content][:100]}...\n   时间: {m[timestamp]}\n\n'
            return output
        
        return '错误: action必须是save或search'

# ============== 工具5: 知识库RAG ==============
@register_tool('knowledge_base')
class KnowledgeBase(BaseTool):
    description = '查询内部知识库文档'
    parameters = [
        {'name': 'query', 'type': 'string', 'description': '查询内容', 'required': True}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        query = params.get('query', '') if isinstance(params, dict) else str(params)
        
        # 简单演示：实际应用中连接Milvus向量库
        # 这里返回一个模拟结果
        return f'知识库查询「{query}」: 当前知识库为空，请先导入文档。'


# ============== 创建Agent ==============
def create_vulcan_agent(system_prompt=None):
    from qwen_agent.agents import Assistant
    
    if not system_prompt:
        system_prompt = '''你是Vulcan Brain，一个企业级智能助手。
你可以使用以下工具:
- get_time: 获取当前时间
- web_search: 联网搜索信息
- run_code: 执行Python代码
- memory: 保存/搜索记忆
- knowledge_base: 查询知识库

请简洁回答，重要数据用**加粗**。'''
    
    llm_cfg = {
        'model': 'qwen3-thinking:latest', 
        'model_server': 'http://localhost:11434/v1', 
        'api_key': 'EMPTY',
        'generate_cfg': {
            'stop': ['</tool_call>', '<|im_end|>', 'Observation:'],
        }
    }
    
    return Assistant(
        llm=llm_cfg, 
        function_list=['get_time', 'searxng_search', 'web_scrape', 'python_exec', 'memory', 'knowledge_base'], 
        system_message=system_prompt
    )


if __name__ == '__main__':
    print('Vulcan Tools V1 已加载')
    print('可用工具: get_time, web_search, run_code, memory, knowledge_base')

# ============== 工具6: 网页抓取 ==============
@register_tool('web_scrape')
class WebScraper(BaseTool):
    description = '抓取指定URL的网页内容，用于深入阅读搜索结果'
    parameters = [
        {'name': 'url', 'type': 'string', 'description': '要抓取的网页URL', 'required': True}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        url = params.get('url', '') if isinstance(params, dict) else str(params)
        
        if not url:
            return '错误: 请提供URL'
        
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return '错误: 需要安装 beautifulsoup4: pip install beautifulsoup4'
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 移除script和style
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # 获取标题
            title = soup.title.string if soup.title else '无标题'
            
            # 获取正文
            # 尝试找article或main标签
            main_content = soup.find('article') or soup.find('main') or soup.find('body')
            
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
            
            # 清理空行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines[:100])  # 限制100行
            
            return f'**{title}**\n\n{text[:3000]}...'
        except Exception as e:
            return f'抓取失败: {str(e)}'
