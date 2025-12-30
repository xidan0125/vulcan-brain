"""
Briefing Agent Core
紧急简报智能分析Agent - 从日报JSON生成按紧急度排序的统一简报
"""

import json
from typing import Dict, Optional, Any
from datetime import datetime

from vulcan_libs.ai_service import generate as ai_generate
from .prompts import URGENCY_BRIEFING_PROMPT, CHAT_PROMPT

# 缓存
_briefing_cache: Dict[str, Dict] = {}


class BriefingAgent:
    """
    紧急简报智能分析Agent

    功能:
    - generate(): 从日报生成紧急简报
    - chat(): 基于简报进行对话
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    async def generate(self, daily_report: Dict, today_date: str, force_refresh: bool = False) -> Dict:
        """
        生成紧急简报

        Args:
            daily_report: 日报数据
            today_date: 今天日期
            force_refresh: 强制刷新

        Returns:
            简报结果
        """
        report_date = daily_report.get("date", "unknown")
        cache_key = report_date

        # 检查缓存
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key].copy()
            cached["from_cache"] = True
            return cached

        # 构建 prompt
        slim_report = self._slim_report(daily_report)
        prompt = URGENCY_BRIEFING_PROMPT.format(
            daily_report_json=json.dumps(slim_report, ensure_ascii=False, indent=2),
            today_date=today_date
        )

        # 调用 AI Service
        try:
            content = await ai_generate(prompt, temperature=0.3, max_tokens=8000)
            result = self._parse_json_response(content)

            # 添加 email_index_map
            result["email_index_map"] = daily_report.get("email", {}).get("ai_analysis", {}).get("email_index_map", {})
            result["from_cache"] = False
            result["generated_at"] = datetime.now().isoformat()

            # 缓存
            self._cache[cache_key] = result.copy()

            return result

        except Exception as e:
            return {
                "error": str(e),
                "from_cache": False
            }

    async def chat(self, query: str, briefing: Dict) -> str:
        """
        基于简报进行对话

        Args:
            query: 用户问题
            briefing: 当前简报数据

        Returns:
            回答文本
        """
        briefing_context = json.dumps(briefing, ensure_ascii=False, indent=2)
        prompt = CHAT_PROMPT.format(
            briefing_context=briefing_context,
            query=query
        )

        try:
            content = await ai_generate(prompt, temperature=0.5, max_tokens=1000)
            return self._strip_thinking(content)
        except Exception as e:
            return f"回答失败: {str(e)}"

    def _slim_report(self, daily_report: Dict) -> Dict:
        """精简日报数据，减少 token"""
        return {
            "date": daily_report.get("date"),
            "email": {
                "ai_analysis": daily_report.get("email", {}).get("ai_analysis", {}),
                "vip_emails": daily_report.get("email", {}).get("vip_emails", [])[:5],
            },
            "chat": daily_report.get("chat", {}),
            "approval": daily_report.get("approval", {}),
            "projects": daily_report.get("projects", {}),
        }

    def _parse_json_response(self, content: str) -> Dict:
        """解析 LLM 返回的 JSON"""
        # 处理 thinking 模式
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()

        # 处理 markdown 代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"raw_response": content, "parse_error": True}

    def _strip_thinking(self, content: str) -> str:
        """移除 thinking 标签 (包括截断的情况)"""
        import re
        # 移除完整的 <think>...</think> 块
        content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.IGNORECASE)
        # 如果有未闭合的 <think> (被截断)，移除它及之后的内容
        if '<think>' in content.lower():
            content = re.split(r'<think>', content, flags=re.IGNORECASE)[0]
        return content.strip()


# 单例
_agent: Optional[BriefingAgent] = None


def get_agent() -> BriefingAgent:
    """获取 Agent 单例"""
    global _agent
    if _agent is None:
        _agent = BriefingAgent()
    return _agent


async def generate_briefing(daily_report: Dict, today_date: str, force_refresh: bool = False) -> Dict:
    """便捷函数: 生成简报"""
    return await get_agent().generate(daily_report, today_date, force_refresh)


async def chat_about_briefing(query: str, briefing: Dict) -> str:
    """便捷函数: 简报对话"""
    return await get_agent().chat(query, briefing)
