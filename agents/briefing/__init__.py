"""
Briefing Agent Package
紧急简报智能分析Agent
"""

from .agent import (
    BriefingAgent,
    get_agent,
    generate_briefing,
    chat_about_briefing,
    _briefing_cache,
)
from .prompts import (
    URGENCY_BRIEFING_PROMPT,
    CHAT_PROMPT,
)

__all__ = [
    # Agent
    'BriefingAgent',
    'get_agent',
    'generate_briefing',
    'chat_about_briefing',
    '_briefing_cache',
    # Prompts
    'URGENCY_BRIEFING_PROMPT',
    'CHAT_PROMPT',
]
