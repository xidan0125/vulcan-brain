"""
Vulcan Brain - 工具定义 (OpenAI Function Calling 格式)
"""

from typing import List, Dict, Any, Callable
import json

# ==================== 工具执行器 ====================

import sys
import os
sys.path.insert(0, os.path.expanduser('~/vulcan-brain'))

from tools.search_tools import searxng_search
from tools.memory_tools import remember_info, recall_info, forget_info


# ==================== 工具 Schema 定义 ====================

TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索最新信息。当用户询问实时新闻、股价、天气、最新事件、或任何需要最新数据的问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，应该简洁明确"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "记住重要信息到长期记忆。当用户说'记住xxx'、'我叫xxx'、'我喜欢xxx'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "记忆键，如 user_name, favorite_color, project_name"
                    },
                    "value": {
                        "type": "string",
                        "description": "要记住的内容"
                    }
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "回忆之前记住的信息。当用户问'你还记得xxx吗'、'我之前说过什么'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要回忆的记忆键"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": "忘记某条记忆。当用户说'忘了xxx'、'删除xxx'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要删除的记忆键"
                    }
                },
                "required": ["key"]
            }
        }
    }
]


# ==================== 工具执行映射 ====================

TOOL_EXECUTORS: Dict[str, Callable] = {
    "web_search": lambda args: searxng_search(args.get("query", "")),
    "remember": lambda args: remember_info(args.get("key", ""), args.get("value", "")),
    "recall": lambda args: recall_info(args.get("key", "")),
    "forget": lambda args: forget_info(args.get("key", "")),
}


def execute_tool(name: str, arguments: str) -> str:
    if name not in TOOL_EXECUTORS:
        return f"错误: 未知工具 '{name}'"

    try:
        args = json.loads(arguments) if arguments else {}
        result = TOOL_EXECUTORS[name](args)
        return str(result)
    except json.JSONDecodeError as e:
        return f"错误: 参数解析失败 - {e}"
    except Exception as e:
        return f"错误: 工具执行失败 - {e}"


def get_tool_names() -> List[str]:
    return list(TOOL_EXECUTORS.keys())


def get_tool_description(name: str) -> str:
    for tool in TOOL_DEFINITIONS:
        if tool["function"]["name"] == name:
            return tool["function"]["description"]
    return "未知工具"
