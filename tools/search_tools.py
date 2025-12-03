# tools/search_tools.py
"""联网搜索工具 - 基于 SearXNG"""
import requests
from llama_index.core.tools import FunctionTool

def searxng_search(query: str) -> str:
    """
    联网搜索最新信息，包括新闻、股票、事件等实时数据。
    参数 query: 搜索关键词
    """
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
            content = r.get('content', '')[:200]
            url = r.get('url', '')
            output += f'{i}. **{title}**\n   {content}\n   来源: {url}\n\n'
        return output
    except Exception as e:
        return f'搜索失败: {str(e)}'

# 创建 LlamaIndex 工具对象
web_search_tool = FunctionTool.from_defaults(
    fn=searxng_search,
    name="web_search",
    description="联网搜索最新信息。当用户问实时新闻、股价、天气、最新事件时使用。"
)
