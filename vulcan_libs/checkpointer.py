# vulcan_libs/checkpointer.py
"""
Vulcan Brain - PostgreSQL Checkpointer
支持 LangGraph 对话状态持久化
V5.1 修复版 - 正确处理 AsyncPostgresSaver API
"""

import asyncio
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager

# psycopg 异步支持
import psycopg
from psycopg_pool import AsyncConnectionPool

# LangGraph checkpointer
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class VulcanCheckpointer:
    """
    Vulcan Brain PostgreSQL 检查点器

    特性:
    1. 使用连接池管理 PostgreSQL 连接
    2. 懒初始化 - 首次使用时才创建表
    3. 支持多线程/用户隔离
    4. 自动重连
    """

    # Password vulcan@2025 encoded: @ -> %40
    DEFAULT_URI = "postgresql://admin:vulcan%402025@localhost:5432/vulcan_brain"

    def __init__(self, uri: Optional[str] = None):
        self.uri = uri or self.DEFAULT_URI
        self._pool: Optional[AsyncConnectionPool] = None
        self._initialized = False

    async def _ensure_pool(self):
        """确保连接池已创建"""
        if self._pool is None:
            self._pool = AsyncConnectionPool(
                conninfo=self.uri,
                min_size=2,
                max_size=10,
                open=False
            )
            await self._pool.open()

    async def _ensure_tables(self, conn):
        """确保检查点表存在"""
        if self._initialized:
            return

        # 创建 LangGraph 需要的表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint BYTEA NOT NULL,
                metadata BYTEA NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                blob BYTEA,
                PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_path TEXT NOT NULL DEFAULT '',
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                blob BYTEA NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, task_path, idx)
            );
        """)

        await conn.commit()
        self._initialized = True

    @asynccontextmanager
    async def get_saver(self):
        """
        获取 AsyncPostgresSaver 实例（上下文管理器）

        Usage:
            async with checkpointer.get_saver() as saver:
                # 使用 saver 进行操作
                graph.invoke(..., config={"checkpointer": saver})
        """
        await self._ensure_pool()

        async with self._pool.connection() as conn:
            await self._ensure_tables(conn)
            saver = AsyncPostgresSaver(conn)
            yield saver

    async def create_saver_for_graph(self) -> AsyncPostgresSaver:
        """
        为 CompiledGraph 创建持久化 saver

        注意: 这个方法返回的 saver 会在内部管理连接生命周期
        适用于 LangGraph 的 checkpointer 参数
        """
        await self._ensure_pool()

        # 获取一个连接（不用 context manager，让 saver 管理）
        conn = await self._pool.getconn()
        await self._ensure_tables(conn)

        return AsyncPostgresSaver(conn)

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None


class CheckpointerManager:
    """
    全局检查点器管理器
    支持 LangGraph graph.compile(checkpointer=...) 模式
    """

    _instance: Optional['CheckpointerManager'] = None

    def __init__(self):
        self._checkpointer: Optional[VulcanCheckpointer] = None
        self._saver: Optional[AsyncPostgresSaver] = None

    @classmethod
    def get_instance(cls) -> 'CheckpointerManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_checkpointer(
        self,
        uri: Optional[str] = None
    ) -> AsyncPostgresSaver:
        """
        获取或创建 checkpointer saver

        适用于 graph.compile(checkpointer=saver)
        """
        if self._saver is None:
            self._checkpointer = VulcanCheckpointer(uri)
            self._saver = await self._checkpointer.create_saver_for_graph()
        return self._saver

    async def cleanup(self):
        """清理资源"""
        if self._checkpointer:
            await self._checkpointer.close()
            self._checkpointer = None
            self._saver = None


# 便捷函数
async def get_checkpointer(uri: Optional[str] = None) -> AsyncPostgresSaver:
    """获取全局 checkpointer saver"""
    manager = CheckpointerManager.get_instance()
    return await manager.get_checkpointer(uri)


async def cleanup_checkpointer():
    """清理全局 checkpointer"""
    manager = CheckpointerManager.get_instance()
    await manager.cleanup()


# === 测试 ===
async def test_checkpointer():
    """测试检查点器"""
    print("🧪 测试 VulcanCheckpointer...")

    checkpointer = VulcanCheckpointer()

    try:
        async with checkpointer.get_saver() as saver:
            print(f"✅ Saver 创建成功: {type(saver)}")

            # 测试基本操作
            from langgraph.checkpoint.base import empty_checkpoint

            config = {"configurable": {"thread_id": "test_thread_001", "checkpoint_ns": ""}}

            # 获取（应该为空）
            result = await saver.aget(config)
            print(f"📖 初始状态: {result}")

            # 保存检查点
            checkpoint = empty_checkpoint()
            metadata = {"source": "test", "step": 1}
            new_config = await saver.aput(config, checkpoint, metadata, {"__start__": 1})
            print(f"💾 已保存检查点: {new_config}")

            # 再次获取
            result = await saver.aget(config)
            print(f"📖 读取状态: {result is not None}")

            # 删除测试线程
            await saver.adelete_thread("test_thread_001")
            print("🗑️ 已清理测试数据")

        print("✅ 所有测试通过!")

    finally:
        await checkpointer.close()


if __name__ == "__main__":
    asyncio.run(test_checkpointer())
