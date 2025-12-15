# tools/memory_tools.py
"""
Vulcan Brain - Memory Tools v3 (记忆工具)

工具调用方式：Qwen3 调用 remember 时存入 pending，前端显示确认卡片
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.memory_service import get_memory_service

# 当前用户ID和会话ID（由上层注入）
_current_user_id = "default_user"
_current_session_id = "default_session"


def set_context(user_id: str, session_id: str = None):
    """设置当前用户和会话上下文"""
    global _current_user_id, _current_session_id
    _current_user_id = user_id
    if session_id:
        _current_session_id = session_id


def _run_async(coro):
    """运行异步函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有事件循环中，创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def remember_info(key: str, value: str, category: str = "fact") -> str:
    """
    记住重要信息 - 存入待确认，等用户确认后才正式保存
    
    Args:
        key: 记忆键（如 name, role, preference）
        value: 要记住的内容
        category: 分类 (identity/preference/fact)
    
    Returns:
        JSON 格式的 pending 信息，前端据此显示确认卡片
    """
    async def _add_pending():
        svc = get_memory_service()
        pending = await svc.add_pending(
            user_id=_current_user_id,
            session_id=_current_session_id,
            key=key,
            value=value,
            category=category,
            confidence=0.95,  # 工具调用置信度高
            context=f"Tool call: remember({key}, {value})"
        )
        return pending
    
    try:
        pending = _run_async(_add_pending())
        # 返回 JSON，前端解析后显示确认卡片
        result = {
            "type": "pending_memory",
            "pending_id": pending.get("id") or pending.get("_id"),
            "key": key,
            "value": value,
            "category": category,
            "message": f"已添加待确认记忆: {key} = {value}"
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"type": "error", "message": f"记忆保存失败: {e}"}, ensure_ascii=False)


def recall_info(key: str = None) -> str:
    """
    回忆之前记住的信息（已确认的记忆）
    
    Args:
        key: 记忆键，不指定则返回所有
    """
    async def _recall():
        svc = get_memory_service()
        memories = await svc.recall(_current_user_id, key)
        return memories
    
    try:
        memories = _run_async(_recall())
        if not memories:
            if key:
                return f"没有找到关于 '{key}' 的记忆"
            return "暂无任何记忆"
        
        if key and memories:
            return f"{key}: {memories[0]['value']}"
        
        lines = ["已记住的信息:"]
        for m in memories:
            lines.append(f"  - {m['key']}: {m['value']}")
        return "\n".join(lines)
    except Exception as e:
        return f"回忆失败: {e}"


def forget_info(key: str) -> str:
    """
    忘记某条信息（删除已确认的记忆）
    
    Args:
        key: 要删除的记忆键
    """
    async def _forget():
        svc = get_memory_service()
        return await svc.forget(_current_user_id, key)
    
    try:
        success = _run_async(_forget())
        if success:
            return f"已删除记忆: {key}"
        return f"没有找到记忆: {key}"
    except Exception as e:
        return f"删除失败: {e}"


# 导出
__all__ = ['remember_info', 'recall_info', 'forget_info', 'set_context']
