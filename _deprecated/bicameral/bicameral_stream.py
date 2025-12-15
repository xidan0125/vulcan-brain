# vulcan_libs/bicameral_stream.py
"""
Vulcan Brain - Bicameral 流式输出处理器
V5.1 SSE 流式输出接口
"""

import json
import time
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional

from vulcan_libs.bicameral_graph import BicameralRunner
from vulcan_libs.stream_filter import OptimizedStreamingThinkFilter


class BicameralStreamHandler:
    """
    Bicameral 流式输出处理器

    特性:
    1. SSE 格式输出
    2. 节点状态追踪 (CEO/CTO/Synthesizer)
    3. 思考过程分离 (<think> 标签)
    4. 性能指标收集
    """

    def __init__(self, runner: Optional[BicameralRunner] = None):
        self.runner = runner or BicameralRunner()
        self._filter = OptimizedStreamingThinkFilter()

    async def stream_sse(
        self,
        user_message: str,
        thread_id: str = "default",
        max_steps: int = 10,
        agent_type: str = None  # Agent 类型
    ) -> AsyncGenerator[str, None]:
        """
        生成 SSE 流式输出

        事件类型:
        - node_start: 节点开始执行
        - node_end: 节点执行完成
        - token: 文本 token (可能是思考或输出)
        - thinking: 思考过程
        - code: 代码块
        - tool_output: 工具执行输出
        - error: 错误信息
        - done: 完成
        """
        start_time = time.time()
        first_token_time = None
        token_count = 0
        current_node = None

        try:
            # 发送开始事件
            yield self._sse_event("stream_start", {
                "thread_id": thread_id,
                "agent_type": agent_type,
                "timestamp": datetime.now().isoformat()
            })

            # 消费 Bicameral Graph 的流式输出 (传递 agent_type)
            async for event in self.runner.run_stream(user_message, thread_id, max_steps, agent_type):
                evt_type = event.get("type")

                if evt_type == "node_start":
                    node_name = event.get("node", "")
                    current_node = node_name

                    # 发送节点开始事件
                    node_info = self._get_node_info(node_name)
                    yield self._sse_event("node_start", {
                        "node": node_name,
                        "label": node_info["label"],
                        "icon": node_info["icon"]
                    })

                elif evt_type == "node_end":
                    node_name = event.get("node", "")
                    output = event.get("output", {})

                    # 发送节点结束事件
                    yield self._sse_event("node_end", {
                        "node": node_name,
                        "success": True,
                        "duration_ms": int((time.time() - start_time) * 1000)
                    })

                elif evt_type == "token":
                    content = event.get("content", "")
                    if not content:
                        continue

                    # 记录首 token 时间
                    if first_token_time is None:
                        first_token_time = time.time()

                    token_count += len(content)

                    # 使用 StreamFilter 处理 <think> 标签
                    self._filter.reset()
                    for (output_type, output_content) in self._filter.process_chunk(content):
                        if output_type == "thinking":
                            yield self._sse_event("thinking", {
                                "content": output_content,
                                "node": current_node
                            })
                        else:
                            yield self._sse_event("token", {
                                "content": output_content,
                                "node": current_node
                            })

                    # Flush 剩余
                    for (output_type, output_content) in self._filter.flush():
                        if output_type == "thinking":
                            yield self._sse_event("thinking", {
                                "content": output_content,
                                "node": current_node
                            })
                        else:
                            yield self._sse_event("token", {
                                "content": output_content,
                                "node": current_node
                            })

            # 计算性能指标
            end_time = time.time()
            total_time = end_time - start_time
            ttft = (first_token_time - start_time) if first_token_time else 0
            tps = token_count / total_time if total_time > 0 else 0

            # 发送完成事件
            yield self._sse_event("done", {
                "thread_id": thread_id,
                "metrics": {
                    "total_time_ms": int(total_time * 1000),
                    "ttft_ms": int(ttft * 1000),
                    "token_count": token_count,
                    "tokens_per_second": round(tps, 2)
                }
            })

        except Exception as e:
            # 发送错误事件
            yield self._sse_event("error", {
                "message": str(e),
                "node": current_node
            })
            yield self._sse_event("done", {
                "thread_id": thread_id,
                "error": True
            })

    def _sse_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """格式化 SSE 事件 - 在 data 中包含 type 以兼容前端解析"""
        # 前端只解析 "data: " 行，需要在 JSON 中包含 type
        data_with_type = {"type": event_type, **data}
        return f"data: {json.dumps(data_with_type, ensure_ascii=False)}\n\n"

    def _get_node_info(self, node_name: str) -> Dict[str, str]:
        """获取节点显示信息"""
        node_map = {
            "ceo": {"label": "🧠 CEO 分析", "icon": "brain"},
            "cto": {"label": "⚙️ CTO 执行", "icon": "code"},
            "synthesizer": {"label": "🎯 综合答案", "icon": "target"},
            "LangGraph": {"label": "🔄 流程控制", "icon": "workflow"},
        }
        return node_map.get(node_name, {"label": node_name, "icon": "circle"})


# 全局处理器实例
_handler_cache = None

def get_bicameral_stream_handler() -> BicameralStreamHandler:
    """获取流式处理器实例（单例）"""
    global _handler_cache
    if _handler_cache is None:
        _handler_cache = BicameralStreamHandler()
    return _handler_cache


# === 测试 ===
async def test_stream():
    """测试流式输出"""
    handler = BicameralStreamHandler()

    print("🧪 测试 Bicameral 流式输出...")
    print("=" * 60)

    async for event in handler.stream_sse("今天星期几？", thread_id="stream_test"):
        print(event.strip())

    print("=" * 60)
    print("✅ 测试完成")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_stream())
