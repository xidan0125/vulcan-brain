# kernel_bicameral_v5.py - V5.0 "Bicameral Mind" Architecture
"""
Vulcan Brain - 双脑内核 V5.0 "Bicameral Mind"

架构革命：
1. CEO (Qwen3-Thinking via Ollama) - 战略决策脑
   - 深度推理 (<think> 块)
   - 任务规划与分解
   - 上下文理解与记忆调用

2. CTO (Qwen2.5-Coder via SGLang) - 技术执行脑
   - 代码生成 (结构化输出)
   - 工具调用 (JSON Schema 约束)
   - 高速推理 (AWQ + FP8 KV Cache)

协作模式：
- 简单查询: CEO 直接回答
- 编程任务: CEO 分析 → CTO 编码 → CEO 总结
- 复杂任务: CEO 拆解 → CTO 逐步执行 → CEO 整合

性能指标：
- CEO: Qwen3-32B (FP16) @ ~50 tok/s
- CTO: Qwen2.5-Coder-32B-AWQ @ ~150 tok/s (结构化)
"""

import re
import pytz
import json
import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional, AsyncGenerator, Tuple

from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage
from llama_index.core.tools import BaseTool

# V5 双脑客户端
from vulcan_libs.sglang_client import get_sglang_client

# 导入灵魂层
from vulcan_libs.alignment import load_constitution, get_relevant_lessons

# 导入 LOD 组件
from vulcan_libs.registry import ToolRegistry
from vulcan_libs.tool_retriever import ToolRetriever

# 代码块匹配
CODE_BLOCK_REGEX = re.compile(r"```python\n(.*?)\n```", re.DOTALL)


class BicameralStreamFilter:
    """双脑流式过滤器 - 支持 CEO 思考 + CTO 代码分流"""

    def __init__(self):
        self.buffer = ""
        self.inside_think = False

    def process_chunk(self, chunk: str) -> List[Tuple[str, str]]:
        """处理 chunk，返回 [(type, content), ...]"""
        self.buffer += chunk
        outputs = []

        while True:
            if self.inside_think:
                close_idx = self.buffer.find('</think>')
                if close_idx == -1:
                    safe_len = max(0, len(self.buffer) - 8)
                    if safe_len > 0:
                        outputs.append(('thinking', self.buffer[:safe_len]))
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    if close_idx > 0:
                        outputs.append(('thinking', self.buffer[:close_idx]))
                    self.buffer = self.buffer[close_idx + 8:]
                    self.inside_think = False
            else:
                open_idx = self.buffer.find('<think>')
                if open_idx == -1:
                    safe_len = max(0, len(self.buffer) - 7)
                    if safe_len > 0:
                        outputs.append(('token', self.buffer[:safe_len]))
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    if open_idx > 0:
                        outputs.append(('token', self.buffer[:open_idx]))
                    self.buffer = self.buffer[open_idx + 7:]
                    self.inside_think = True

        return outputs

    def flush(self) -> List[Tuple[str, str]]:
        """刷新缓冲区"""
        if self.buffer:
            typ = 'thinking' if self.inside_think else 'token'
            result = [(typ, self.buffer)]
            self.buffer = ""
            return result
        return []


class VulcanBicameralKernel:
    """
    V5.0 双脑内核 - CEO (思考) + CTO (执行)

    核心创新:
    1. 任务路由: 根据查询类型选择单脑或双脑模式
    2. 结构化代码: CTO 使用 JSON Schema 生成规范代码
    3. 并行推理: 可异步调度两个脑
    """

    def __init__(
        self,
        ceo_model: str = "qwen3:30b-a3b",
        cto_base_url: str = "http://localhost:30000",
        cto_model: str = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
        enable_lod: bool = True
    ):
        # ========== CEO (Ollama) ==========
        self.ceo = Ollama(
            model=ceo_model,
            base_url="http://localhost:11434",
            request_timeout=120.0
        )
        self.ceo_model = ceo_model

        # ========== CTO (SGLang) ==========
        self.cto = get_sglang_client(
            base_url=cto_base_url,
            model=cto_model
        )
        self.cto_model = cto_model

        # ========== 灵魂层 (共享) ==========
        self.constitution = load_constitution() or ""
        self.alignment_lessons = get_relevant_lessons() or ""
        self.user_memories = ""  # 可后续注入

        # ========== LOD 工具系统 ==========
        self.enable_lod = enable_lod
        self.registry = ToolRegistry()
        self.retriever = ToolRetriever(self.registry)

        # 初始化工具
        self.active_tools: List[BaseTool] = []
        self.execution_env: Dict[str, Any] = {}

        # 构建 Prompt
        self.ceo_system_prompt = self._build_ceo_prompt()

        print(f"🧠 [V5.0] Bicameral Mind 初始化完成")
        print(f"   ├─ CEO: {ceo_model} (Ollama)")
        print(f"   └─ CTO: {cto_model} (SGLang)")

    def _get_perception_context(self) -> str:
        """感知层 - 实时环境状态"""
        tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz)

        return f"""【环境感知 - 实时更新】
- 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
- 星期: {now.strftime('%A')}
- 时区: Asia/Shanghai
- 系统状态: 在线 (Dual RTX 5090 | Bicameral V5.0)
- CEO 状态: {self.ceo_model} @ Ollama
- CTO 状态: {self.cto_model} @ SGLang
"""

    def _build_ceo_prompt(self) -> str:
        """构建 CEO 系统提示词"""
        perception = self._get_perception_context()

        return f"""你是 Vulcan Brain CEO - 战略决策脑，负责理解、规划和总结。

{perception}

{self.constitution}

{self.alignment_lessons}

【用户长期记忆】
{self.user_memories}

【双脑协作模式】
你是 CEO (Chief Executive Officer)，负责：
1. 深度理解用户意图
2. 规划任务执行步骤
3. 决定是否需要调用 CTO (代码执行脑)
4. 整合执行结果，给出最终回答

【工作流程】
1. **分析查询**：理解用户真正需要什么
2. **路由决策**：
   - 知识问答/闲聊 → 直接回答 (单脑模式)
   - 需要代码/工具 → 编写代码，我会转交 CTO 执行 (双脑模式)
3. **代码规范**：如需代码，使用 ```python ... ``` 包裹
4. **结果整合**：根据 CTO 执行结果，给出最终答案

【核心原则】
- 思考时使用 <think>...</think> 包裹
- 遇到问题直接上报，不擅自简化
- 简洁胜于复杂
- 代码必须使用 print() 输出关键结果
"""

    def _build_full_ceo_prompt(self) -> str:
        """完整 CEO Prompt (含工具描述)"""
        tool_docs = []
        for tool in self.active_tools:
            tool_docs.append(
                f"- {tool.metadata.name}{tool.metadata.fn_schema_str}: {tool.metadata.description}"
            )

        tools_context = "\n".join(tool_docs) if tool_docs else "  (当前无可用工具)"

        return f"""{self.ceo_system_prompt}

【当前可用工具库】
{tools_context}

开始执行任务。
"""

    def _build_execution_env(self, tools: List[BaseTool]) -> Dict[str, Callable]:
        """构建代码执行环境"""
        import tools as tools_module

        env = {
            '__builtins__': __builtins__,
            'tools': tools_module,
            'print': print,
            'json': __import__('json'),
            'datetime': datetime,
            'asyncio': asyncio,
        }

        for tool in tools:
            func_name = tool.metadata.name
            env[func_name] = tool.fn

        return env

    def _execute_code(self, code: str) -> str:
        """执行代码并捕获输出"""
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        try:
            exec(code, self.execution_env)
            output = buffer.getvalue()
            return output if output else "(No output)"
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout

    def _update_context(self, user_query: str):
        """LOD 动态工具加载"""
        if not self.enable_lod:
            return

        print(f"\n🔍 [LOD] 正在检索相关工具...")

        relevant_packages = self.retriever.retrieve_package_names(user_query, debug=True)

        core_tools = self.registry.get_core_tools()
        extension_tools = self.registry.get_package_tools(relevant_packages)

        self.active_tools = core_tools + extension_tools
        self.execution_env = self._build_execution_env(self.active_tools)

        print(f"🔋 [Context] 已加载工具包:")
        print(f"   ├─ 核心工具: {len(core_tools)} 个")
        print(f"   └─ 扩展工具: {len(extension_tools)} 个")

    def _classify_query(self, query: str) -> str:
        """快速分类查询类型"""
        query_lower = query.lower()

        # 编程关键词
        code_keywords = ['代码', '编程', '写一个', '实现', 'python', 'code',
                        'function', '函数', '脚本', '程序', 'api', '接口',
                        '爬虫', '数据处理', '计算', '分析']

        # 工具关键词
        tool_keywords = ['搜索', '查询', '发送', '获取', '下载', '上传',
                        '邮件', '日历', '天气', '股票', '新闻']

        if any(kw in query_lower for kw in code_keywords):
            return 'code'
        if any(kw in query_lower for kw in tool_keywords):
            return 'tool'

        return 'chat'

    async def _cto_generate_code(
        self,
        task: str,
        context: Optional[str] = None
    ) -> str:
        """
        [CTO 专用] 高速结构化代码生成
        利用 SGLang 的 constrained decoding
        """
        code = await self.cto.generate_code(
            task=task,
            language="python",
            context=context
        )
        return code

    async def run(self, user_query: str) -> str:
        """同步执行 (兼容旧接口)"""
        print(f"\n🚀 [V5.0] 启动双脑任务: {user_query}")

        # LOD 加载工具
        self._update_context(user_query)

        # 构建完整 Prompt
        system_prompt = self._build_full_ceo_prompt()

        history = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_query)
        ]

        step = 0
        MAX_STEPS = 10

        while step < MAX_STEPS:
            step += 1
            print(f"🔄 [CEO Step {step}] 思考中...")

            # CEO 分析
            response = await self.ceo.achat(history)
            content = response.message.content
            history.append(response.message)

            # 提取代码
            code_match = CODE_BLOCK_REGEX.search(content)

            if code_match:
                code = code_match.group(1).strip()
                print(f"💻 [CTO Execute]\n{code}")

                # 执行代码
                output = self._execute_code(code)
                print(f"✅ [Result]\n{output}")

                history.append(ChatMessage(
                    role="user",
                    content=f"执行结果:\n{output}"
                ))
            else:
                # 无代码 -> 结束
                print("🏁 [Finish] 双脑任务完成")

                final_answer = content
                if "</think>" in content:
                    final_answer = content.split("</think>")[-1].strip()

                return final_answer

        return "Error: Maximum steps reached."

    async def run_stream(self, user_query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        V5.0 流式双脑执行

        协议:
        - {"type": "thinking", "content": "..."} - CEO 思考过程
        - {"type": "token", "content": "..."} - 可见输出
        - {"type": "code", "content": "..."} - CTO 代码
        - {"type": "execution", "content": "..."} - 执行结果
        - {"type": "done"} - 完成
        """
        print(f"\n🚀 [V5.0] 启动流式双脑任务: {user_query}")

        # 刷新 Prompt (确保时间最新)
        self.ceo_system_prompt = self._build_ceo_prompt()
        self._update_context(user_query)
        system_prompt = self._build_full_ceo_prompt()

        history = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_query)
        ]

        step = 0
        MAX_STEPS = 10
        filter = BicameralStreamFilter()

        while step < MAX_STEPS:
            step += 1
            yield {"type": "step", "content": f"[CEO Step {step}]"}

            # CEO 流式生成
            full_response = ""

            async for chunk in await self.ceo.astream_chat(history):
                delta = chunk.delta or ""
                full_response += delta

                # 分流输出
                outputs = filter.process_chunk(delta)
                for typ, content in outputs:
                    yield {"type": typ, "content": content}

            # 刷新缓冲区
            for typ, content in filter.flush():
                yield {"type": typ, "content": content}

            # 记录完整响应
            history.append(ChatMessage(role="assistant", content=full_response))

            # 提取代码
            code_match = CODE_BLOCK_REGEX.search(full_response)

            if code_match:
                code = code_match.group(1).strip()
                yield {"type": "code", "content": code}

                # 执行
                output = self._execute_code(code)
                yield {"type": "execution", "content": output}

                history.append(ChatMessage(
                    role="user",
                    content=f"执行结果:\n{output}"
                ))
            else:
                # 完成
                yield {"type": "done"}
                return

        yield {"type": "error", "content": "Maximum steps reached"}

    async def check_health(self) -> Dict[str, Any]:
        """健康检查 - 双脑状态"""
        ceo_ok = False
        cto_ok = False

        # CEO 检查
        try:
            test = await self.ceo.acomplete("Hi")
            ceo_ok = bool(test.text)
        except Exception as e:
            print(f"CEO health check failed: {e}")

        # CTO 检查
        try:
            cto_ok = await self.cto.health_check()
        except Exception as e:
            print(f"CTO health check failed: {e}")

        return {
            "ceo": {"model": self.ceo_model, "healthy": ceo_ok},
            "cto": {"model": self.cto_model, "healthy": cto_ok},
            "bicameral_ready": ceo_ok and cto_ok
        }


# ============ 工厂函数 ============

_kernel_instance: Optional[VulcanBicameralKernel] = None

def get_bicameral_kernel(
    ceo_model: str = "qwen3:30b-a3b",
    cto_base_url: str = "http://localhost:30000",
    cto_model: str = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
) -> VulcanBicameralKernel:
    """获取双脑内核单例"""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = VulcanBicameralKernel(
            ceo_model=ceo_model,
            cto_base_url=cto_base_url,
            cto_model=cto_model
        )
    return _kernel_instance


# ============ 测试入口 ============

async def test_bicameral():
    """快速测试"""
    kernel = get_bicameral_kernel()

    # 健康检查
    health = await kernel.check_health()
    print(f"\n🏥 健康状态: {json.dumps(health, indent=2)}")

    if not health["bicameral_ready"]:
        print("⚠️ 双脑未就绪，跳过测试")
        return

    # 简单测试
    test_queries = [
        "现在几点了？",
        "写一个 Python 函数计算斐波那契数列前10项",
    ]

    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"测试: {query}")
        print('='*50)
        result = await kernel.run(query)
        print(f"\n结果: {result[:500]}...")


if __name__ == "__main__":
    asyncio.run(test_bicameral())
