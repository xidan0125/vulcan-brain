"""
Vulcan Brain V2 - Qwen-Agent 工具集
集成 MongoDB 记忆系统
"""
import json
import requests
from datetime import datetime
import pytz
from qwen_agent.tools.base import BaseTool, register_tool

# ============== 工具1: 时间获取 ==============
@register_tool('get_time')
class GetCurrentTime(BaseTool):
    description = '获取当前时间和日期'
    parameters = [{'name': 'timezone', 'type': 'string', 'description': '时区', 'required': False}]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        tz_name = params.get('timezone', 'Asia/Shanghai') if isinstance(params, dict) else 'Asia/Shanghai'
        try:
            tz = pytz.timezone(tz_name)
        except:
            tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        return f'当前时间: {now.strftime("%Y-%m-%d %H:%M:%S")} 星期{"一二三四五六日"[now.weekday()]} ({tz_name})'

# ============== 工具2: 联网搜索 ==============
@register_tool('searxng_search')
class WebSearch(BaseTool):
    description = '联网搜索最新信息'
    parameters = [{'name': 'query', 'type': 'string', 'description': '搜索关键词', 'required': True}]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        query = params.get('query', '') if isinstance(params, dict) else str(params)
        if not query:
            return '错误: 请提供搜索关键词'
        try:
            resp = requests.get('http://localhost:8080/search', params={'q': query, 'format': 'json'}, timeout=15)
            results = resp.json().get('results', [])[:5]
            if not results:
                return f'未找到「{query}」的结果'
            output = f'搜索「{query}」:\n\n'
            for i, r in enumerate(results, 1):
                output += f'{i}. **{r.get("title", "")}**\n   {r.get("content", "")[:150]}...\n   {r.get("url", "")}\n\n'
            return output
        except Exception as e:
            return f'搜索失败: {e}'

# ============== 工具3: 网页抓取 ==============
@register_tool('web_scrape')
class WebScraper(BaseTool):
    description = '抓取网页内容'
    parameters = [{'name': 'url', 'type': 'string', 'description': 'URL', 'required': True}]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        url = params.get('url', '') if isinstance(params, dict) else str(params)
        if not url:
            return '错误: 请提供URL'
        try:
            from bs4 import BeautifulSoup
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer']):
                tag.decompose()
            title = soup.title.string if soup.title else '无标题'
            main = soup.find('article') or soup.find('main') or soup.find('body')
            text = main.get_text('\n', strip=True) if main else ''
            return f'**{title}**\n\n{text[:3000]}...'
        except Exception as e:
            return f'抓取失败: {e}'

# ============== 工具4: 代码执行 ==============
@register_tool('python_exec')
class CodeInterpreter(BaseTool):
    description = '执行Python代码'
    parameters = [{'name': 'code', 'type': 'string', 'description': 'Python代码', 'required': True}]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        code = params.get('code', '') if isinstance(params, dict) else str(params)
        if not code:
            return '错误: 请提供代码'
        import io
        from contextlib import redirect_stdout, redirect_stderr
        safe_globals = {'__builtins__': {'print': print, 'len': len, 'range': range, 'str': str, 'int': int, 'float': float, 'list': list, 'dict': dict, 'sum': sum, 'max': max, 'min': min, 'abs': abs, 'round': round, 'sorted': sorted, 'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter, 'True': True, 'False': False, 'None': None}}
        try:
            import math
            safe_globals['math'] = math
        except: pass
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(code, safe_globals)
            out = stdout.getvalue()
            err = stderr.getvalue()
            return f'输出:\n{out}' + (f'\n警告:\n{err}' if err else '') if out or err else '执行完成，无输出'
        except Exception as e:
            return f'执行错误: {e}'

# ============== 工具5: 记忆系统 (MongoDB) ==============
@register_tool('memory')  
class MemoryTool(BaseTool):
    description = '存储/检索用户记忆(MongoDB)'
    parameters = [
        {'name': 'action', 'type': 'string', 'description': 'remember/recall/forget/list', 'required': True},
        {'name': 'key', 'type': 'string', 'description': '记忆键名', 'required': False},
        {'name': 'value', 'type': 'string', 'description': '记忆内容', 'required': False}
    ]
    
    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            params = json.loads(params) if params else {}
        action = params.get('action', 'list')
        key = params.get('key', '')
        value = params.get('value', '')
        
        try:
            from vulcan_libs.memory import remember, recall, forget, get_all_memories
            
            if action == 'remember':
                if not key or not value:
                    return '错误: remember需要key和value'
                return remember(key, value)
            elif action == 'recall':
                if not key:
                    return '错误: recall需要key'
                return recall(key)
            elif action == 'forget':
                if not key:
                    return '错误: forget需要key'
                return forget(key)
            elif action == 'list':
                return f'📚 用户记忆:\n{get_all_memories()}'
            else:
                return f'错误: 未知action「{action}」'
        except Exception as e:
            return f'记忆操作失败: {e}'

# ============== 创建Agent ==============
def create_vulcan_agent(system_prompt=None):
    from qwen_agent.agents import Assistant
    
    # 获取用户记忆
    memory_ctx = ''
    try:
        from vulcan_libs.memory import get_all_memories
        mem = get_all_memories()
        if mem and mem != '【暂无记忆】':
            memory_ctx = f'\n\n【用户记忆】\n{mem}'
    except: pass
    
    if not system_prompt:
        system_prompt = f'''你是Vulcan Brain，企业级AI助手。
工具: get_time, searxng_search, web_scrape, python_exec, memory
简洁回答，重要数据**加粗**。{memory_ctx}'''
    
    return Assistant(
        llm={'model': 'qwen3-thinking:latest', 'model_server': 'http://localhost:11434/v1', 'api_key': 'EMPTY',
             'generate_cfg': {'stop': ['</tool_call>', '<|im_end|>', 'Observation:']}},
        function_list=['get_time', 'searxng_search', 'web_scrape', 'python_exec', 'memory'],
        system_message=system_prompt
    )

if __name__ == '__main__':
    print('Vulcan Tools V2 (MongoDB) 已加载')
