"""
Vulcan Brain - 统一记忆系统 (Unified Memory System)

重构版本：
- 使用 VulcanStore 作为唯一存储后端
- 支持用户绑定 (user_id)
- 同时提供同步和异步接口
- 兼容旧 API (remember, recall, forget, get_all_memories)
"""
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
from vulcan_libs.store import store

# =====================================================
# 异步接口 (推荐在 API 中使用)
# =====================================================

class VulcanMemoryV2:
    """统一记忆管理器 - 基于 VulcanStore"""
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.store = store
    
    async def remember_async(self, key: str, value: str, category: str = "general") -> str:
        """异步记忆存储"""
        content = f"{key}: {value}"
        await self.store.add_memory(
            user_id=self.user_id,
            content=content,
            category=category
        )
        return f"✅ 已记住: {key} = {value}"
    
    async def recall_async(self, key: Optional[str] = None, limit: int = 20) -> str:
        """异步记忆检索"""
        memories = await self.store.get_memories(self.user_id, limit)
        
        if not memories:
            if key:
                return f"❌ 没有「{key}」的记忆"
            return "【暂无记忆】"
        
        # 如果指定了 key，过滤匹配的
        if key:
            for mem in memories:
                content = mem.get("content", "")
                if content.startswith(f"{key}:"):
                    return content.split(":", 1)[1].strip()
            return f"❌ 没有「{key}」的记忆"
        
        # 返回所有记忆
        lines = []
        for mem in memories:
            content = mem.get("content", str(mem))
            lines.append(f"- {content}")
        return "\n".join(lines)
    
    async def forget_async(self, key: str) -> str:
        """异步删除记忆"""
        memories = await self.store.get_memories(self.user_id, limit=100)
        deleted = 0
        
        for mem in memories:
            content = mem.get("content", "")
            if key.lower() in content.lower():
                mem_id = mem.get("_id")
                if mem_id:
                    if await self.store.delete_memory(mem_id, self.user_id):
                        deleted += 1
        
        if deleted > 0:
            return f"✅ 已删除 {deleted} 条相关记忆"
        return f"❌ 没找到与「{key}」相关的记忆"
    
    async def get_all_async(self) -> str:
        """异步获取所有记忆"""
        return await self.recall_async(key=None, limit=50)
    
    async def search_async(self, query: str, limit: int = 5) -> List[Dict]:
        """异步搜索记忆"""
        return await self.store.search_memories(self.user_id, query, limit)
    
    # =====================================================
    # 同步接口 (兼容旧代码 / Kernel 使用)
    # =====================================================
    
    def remember(self, key: str, value: str, category: str = "general") -> str:
        """同步记忆存储"""
        return _run_sync(self.remember_async(key, value, category))
    
    def recall(self, key: Optional[str] = None) -> str:
        """同步记忆检索"""
        return _run_sync(self.recall_async(key))
    
    def forget(self, key: str) -> str:
        """同步删除记忆"""
        return _run_sync(self.forget_async(key))
    
    def get_all_memories(self) -> str:
        """同步获取所有记忆"""
        return _run_sync(self.get_all_async())
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """同步搜索"""
        return _run_sync(self.search_async(query, limit))


# =====================================================
# 工具函数
# =====================================================

def _run_sync(coro):
    """在同步上下文中运行协程 - 兼容已运行的事件循环"""
    import nest_asyncio
    nest_asyncio.apply()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


# =====================================================
# 便捷函数接口 (全局默认实例)
# =====================================================

_default_user_id = "default"
_managers: Dict[str, VulcanMemoryV2] = {}

def get_manager(user_id: str = None) -> VulcanMemoryV2:
    """获取指定用户的记忆管理器"""
    uid = user_id or _default_user_id
    if uid not in _managers:
        _managers[uid] = VulcanMemoryV2(uid)
    return _managers[uid]

def set_default_user(user_id: str):
    """设置默认用户 ID"""
    global _default_user_id
    _default_user_id = user_id

# 兼容旧 API
def remember(key: str, value: str, category: str = "general") -> str:
    return get_manager().remember(key, value, category)

def recall(key: str = None) -> str:
    return get_manager().recall(key)

def forget(key: str) -> str:
    return get_manager().forget(key)

def get_all_memories() -> str:
    return get_manager().get_all_memories()

# 兼容旧代码的别名
EpisodicMemoryManager = VulcanMemoryV2


# =====================================================
# 测试代码
# =====================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=== Memory System V2 测试 ===")
        
        m = VulcanMemoryV2("test_user")
        
        # 测试记忆
        print(await m.remember_async("name", "张三"))
        print(await m.remember_async("job", "AI工程师"))
        
        # 测试检索
        print(f"回忆 name: {await m.recall_async('name')}")
        print(f"所有记忆:\n{await m.get_all_async()}")
        
        # 测试删除
        print(await m.forget_async("name"))
        print(f"删除后: {await m.recall_async('name')}")
        
        print("\n✅ 测试完成")
    
    asyncio.run(test())
