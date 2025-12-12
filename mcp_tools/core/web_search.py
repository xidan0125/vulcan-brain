# mcp_tools/core/web_search.py
"""
Web Search Tool - 联网搜索最新信息
使用 SearXNG 作为搜索后端
"""

import requests
from typing import Optional


def web_search(query: str, num_results: int = 5) -> str:
    """
    联网搜索最新信息

    Args:
        query: 搜索关键词
        num_results: 返回结果数量 (默认5)

    Returns:
        格式化的搜索结果

    Examples:
        >>> web_search("特斯拉2024年财报")
        >>> web_search("比特币今日价格")
    """
    if not query or not query.strip():
        return '错误: 请提供搜索关键词'

    try:
        resp = requests.get(
            'http://localhost:8080/search',
            params={'q': query, 'format': 'json'},
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get('results', [])[:num_results]

        if not results:
            return f'未找到关于「{query}」的搜索结果'

        output = f'搜索「{query}」的结果:\n\n'
        for i, r in enumerate(results, 1):
            title = r.get('title', '无标题')
            content = r.get('content', '')[:200]
            url = r.get('url', '')
            output += f'{i}. **{title}**\n   {content}...\n   来源: {url}\n\n'
        return output
    except requests.exceptions.ConnectionError:
        return '搜索服务不可用 (SearXNG 未启动)，请稍后重试'
    except requests.exceptions.Timeout:
        return '搜索超时，请稍后重试'
    except Exception as e:
        return f'搜索失败: {str(e)}'


# 导出
__all__ = ['web_search']
