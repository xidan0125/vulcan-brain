"""
Vulcan Brain - Web Search Tool
使用 SearXNG 进行联网搜索

v2: 重写为新架构
"""

import requests
from typing import Optional, List
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool


class WebSearchInput(BaseModel):
    """Web搜索参数"""
    query: str = Field(
        ...,
        description="搜索关键词，应该简洁明确"
    )
    max_results: int = Field(
        default=5,
        description="返回结果数量 (默认5条)",
        ge=1,
        le=20
    )


@register_tool
class WebSearchTool(BaseTool):
    """
    联网搜索工具
    
    当用户询问实时新闻、股价、天气、最新事件、或任何需要最新数据的问题时使用。
    基于 SearXNG 元搜索引擎，聚合多个搜索源的结果。
    
    示例:
    - {"query": "比特币今日价格"}
    - {"query": "OpenAI 最新新闻", "max_results": 10}
    """
    
    name = "web_search"
    description = "联网搜索最新信息。当用户问实时新闻、股价、天气、最新事件、或任何需要当前数据的问题时使用。"
    args_schema = WebSearchInput
    domain = ToolDomain.EXTERNAL
    is_destructive = False
    is_idempotent = True
    
    # SearXNG 配置
    SEARXNG_URL = "http://localhost:8080/search"
    TIMEOUT = 15
    
    def run(self, params: WebSearchInput, context: ToolContext) -> ToolResult:
        """执行搜索"""
        query = params.query
        max_results = params.max_results
        
        if not query or not query.strip():
            return ToolResult.fail("请提供搜索关键词")
        
        try:
            resp = requests.get(
                self.SEARXNG_URL,
                params={"q": query, "format": "json"},
                timeout=self.TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get("results", [])[:max_results]
            
            if not results:
                return ToolResult.ok({
                    "query": query,
                    "count": 0,
                    "results": [],
                    "message": f"未找到关于「{query}」的搜索结果"
                })
            
            # 格式化结果
            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append({
                    "rank": i,
                    "title": r.get("title", "无标题"),
                    "content": r.get("content", "")[:300],  # 截断长内容
                    "url": r.get("url", "")
                })
            
            # 生成可读文本
            output_lines = [f"搜索「{query}」的结果:\n"]
            for r in formatted:
                output_lines.append(f"{r['rank']}. **{r['title']}**")
                if r['content']:
                    output_lines.append(f"   {r['content']}")
                output_lines.append(f"   来源: {r['url']}\n")
            
            return ToolResult.ok({
                "query": query,
                "count": len(formatted),
                "results": formatted,
                "text": "\n".join(output_lines)
            })
            
        except requests.Timeout:
            return ToolResult.fail(f"搜索超时 ({self.TIMEOUT}秒)，请稍后重试")
        except requests.RequestException as e:
            return ToolResult.fail(f"搜索请求失败: {e}")
        except Exception as e:
            return ToolResult.fail(f"搜索失败: {e}")
