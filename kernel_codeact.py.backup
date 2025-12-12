# kernel_codeact.py - V4 (LOD: Level-of-Detail Dynamic Tool Loading)
"""
Vulcan Brain - CodeAct 内核 V4.0 - LOD 架构

重大升级：
1. 动态工具加载：根据用户查询按需加载扩展工具
2. 核心工具常驻：基础工具（时间、记忆）永远在上下文中
3. 上下文优化：从"带着所有行李旅行"到"按需取用军械库"

架构演进：
- V1: 原生 while 循环 (废弃 LlamaIndex Agent)
- V2: Tool 封装 (利用 LlamaIndex Tool 结构)
- V3: Soul Injection (宪法 + 对齐记忆)
- V4: LOD (动态工具加载，减少 Context Window 压力)
"""

import re
import pytz
from datetime import datetime
import traceback
import asyncio
from typing import List, Dict, Any, Callable, Optional
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage
from llama_index.core.tools import BaseTool

# 导入三层记忆系统
# from vulcan_libs.memory import get_all_memories  # DISABLED
from vulcan_libs.alignment import load_constitution, get_relevant_lessons

# 导入 LOD 组件
from vulcan_libs.registry import ToolRegistry
from vulcan_libs.tool_retriever import ToolRetriever

# 匹配 Markdown 代码块

class OptimizedStreamingThinkFilter:
    """
    工业级流式过滤器 - 架构师设计
    
    核心机制：
    1. 实时处理每个chunk（不等待完整响应）
    2. 状态机跟踪是否在think块内
    3. 缓冲区处理跨chunk的标签边界
    4. 只输出确认的可见内容（增量）
    """
    
    def __init__(self):
        self.buffer = ""
        self.inside_think = False
        
    def process_chunk(self, chunk: str):
        """
        处理单个chunk，返回可以立即输出的内容
        
        Args:
            chunk: LLM输出的原始chunk
            
        Returns:
            list[str]: 可以立即输出的内容片段
        """
        self.buffer += chunk
        outputs = []
        
        # 循环处理buffer中的完整标签
        while True:
            if self.inside_think:
                # 在think块内，查找结束标签
                close_idx = self.buffer.find('</think>')
                if close_idx == -1:
                    # 没有结束标签，丢弃当前buffer（think块内容）
                    self.buffer = ""
                    break
                else:
                    # 找到结束标签，跳过并继续
                    self.buffer = self.buffer[close_idx + 8:]
                    self.inside_think = False
            else:
                # 在可见区域，查找开始标签
                open_idx = self.buffer.find('<think>')
                if open_idx == -1:
                    # 没有开始标签，检查安全输出长度
                    safe_len = self._find_safe_output_length(self.buffer)
                    if safe_len > 0:
                        outputs.append(self.buffer[:safe_len])
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    # 找到开始标签
                    if open_idx > 0:
                        outputs.append(self.buffer[:open_idx])
                    self.buffer = self.buffer[open_idx + 7:]
                    self.inside_think = True
        
        return outputs
    
    def _find_safe_output_length(self, text: str) -> int:
        """
        找到可以安全输出的长度
        保留可能是<think>或</think>开头的部分
        """
        if not text:
            return 0
        
        # 检查末尾是否可能是标签的开始
        for i in range(min(8, len(text)), 0, -1):
            suffix = text[-i:]
            if '<think>'.startswith(suffix) or '</think>'.startswith(suffix):
                return len(text) - i
        
        return len(text)
    
    def flush(self) -> str:
        """流结束时输出剩余buffer"""
        if self.buffer and not self.inside_think:
            result = self.buffer
            self.buffer = ""
            return result
        return ""


CODE_BLOCK_REGEX = re.compile(r"""```python(.*?)```""", re.DOTALL)


class VulcanCodeActKernel:
    """Vulcan Brain CodeAct 内核 - V4 LOD 架构"""
    
    def __init__(
        self, 
        model: str,
        registry: ToolRegistry,
        retriever: Optional[ToolRetriever] = None,
        enable_lod: bool = True
    ):
        """
        初始化内核
        
        Args:
            model: 模型名称，如 "qwen3-30b-thinking"
            registry: 工具注册表
            retriever: 工具检索引擎（如果为 None 则禁用 LOD）
            enable_lod: 是否启用动态工具加载（默认 True）
        """
        # 1. LLM 初始化
        self.llm = Ollama(
            model=model,
            temperature=0.1,
            request_timeout=120.0,
            context_window=8192,
            additional_kwargs={"num_gpu": -1, "stop": ["<|im_end|>", "<|endoftext|>", "User:", "Observation:"]}
        )
        
        # 2. LOD 组件
        self.registry = registry
        self.retriever = retriever
        self.enable_lod = enable_lod and retriever is not None
        
        # 3. 初始状态：只加载核心工具
        self.active_tools: List[BaseTool] = self.registry.get_core_tools()
        self.execution_env: Dict[str, Callable] = self._build_execution_env(self.active_tools)
        
        # 4. [灵魂注入] 加载三层记忆
        self.constitution = load_constitution()          # 宪法（价值观）
        self.alignment_lessons = get_relevant_lessons()  # 历史教训
        self.user_memories = ""  # DISABLED for stability          # 用户记忆
        
        # 5. 构建基础 System Prompt（不包含工具描述）
        self.base_system_prompt = self._build_base_prompt()
        
        # 6. 首次构建完整 Prompt（只包含核心工具）
        self.system_prompt = self._build_full_prompt()
        
        # 7. 调试模式
        self._debug_mode = False
        
        print(f"🚀 [Vulcan Kernel V4] 初始化完成")
        print(f"   ├─ 模型: {model}")
        print(f"   ├─ LOD 模式: {'启用' if self.enable_lod else '禁用'}")
        print(f"   ├─ 核心工具: {len(self.active_tools)} 个")
        print(f"   └─ 初始 Context: ~{len(self.system_prompt.split())} words")
    
    def _build_execution_env(self, tools: List[BaseTool]) -> Dict[str, Callable]:
        """构建代码执行环境（工具函数注入 + 模块访问）"""
        import tools as tools_module

        env = {
            '__builtins__': __builtins__,
            'tools': tools_module,  # 允许 from tools import xxx
            'print': print,
            'json': __import__('json'),
        }
        # 直接注入工具函数（可直接调用 web_search(query)）
        for tool in tools:
            func_name = tool.metadata.name
            env[func_name] = tool.fn
        return env

    def _get_perception_context(self):
        """
        [感知层] 获取当前物理世界的快照
        这是架构修正：把'查时间'从工具层提升到感知层
        """
        tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz)

        return f"""【环境感知 - 实时更新】
- 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
- 星期: {now.strftime('%A')}
- 时区: Asia/Shanghai
- 系统状态: 在线 (Dual RTX 5090 Ready)
"""

    def _build_base_prompt(self) -> str:
        """构建基础 Prompt（灵魂层 + 指令 + 环境感知，不含工具描述）"""
        # [混合感知架构] 动态注入当前时间
        perception = self._get_perception_context()

        return f"""你是 Vulcan Brain - 一个有原则、有记忆、有灵魂的 AI 助手。

{perception}

{self.constitution}

{self.alignment_lessons}

【用户长期记忆】
{self.user_memories}

【工作流程】
1. **感知优先**：对于时间、日期等基础问题，直接利用【环境感知】中的信息回答，**不要**写代码调用工具。
2. **工具使用**：如果系统加载了相关工具，请编写 Python 代码使用它们。
3. **纯聊天模式**：如果没有加载工具或问题是观点性/闲聊类的，直接回答即可，不要强行写代码。
5. **复杂计算**：对于数据分析、逻辑推演，必须编写 Python 代码 (```python ... ```) 来解决。
6. 我会执行代码，并将 print() 输出返回给你。
7. 你根据输出，给出最终答案。

【核心原则】
- 遇到问题直接上报，不擅自创建简化版
- 代码优于文字：Show, don't tell
- 简洁胜于复杂：100 行优于 1000 行
- 必须使用 print() 输出关键结果
- 当用户让你"记住"某事时，调用 remember_info()
- 当 Boss 纠正你时，调用 record_boss_feedback()
"""
    
    def _build_full_prompt(self) -> str:
        """构建完整 Prompt（基础 + 当前激活的工具描述）"""
        # 生成工具描述
        tool_docs = []
        for tool in self.active_tools:
            tool_docs.append(
                f"- {tool.metadata.name}{tool.metadata.fn_schema_str}: {tool.metadata.description}"
            )
        
        tools_context = "\n".join(tool_docs) if tool_docs else "  (当前无可用工具)"
        
        # 拼接完整 Prompt
        return f"""{self.base_system_prompt}

【当前可用工具库】
{tools_context}

开始执行任务。
"""
    
    def _update_context(self, user_query: str):
        """
        [LOD 核心] 根据用户查询动态更新工具上下文
        
        Args:
            user_query: 用户查询
        """
        if not self.enable_lod:
            return  # LOD 未启用，跳过
        
        print(f"\n🔍 [LOD] 正在检索相关工具...")
        
        # 1. 检索相关扩展包
        relevant_packages = self.retriever.retrieve_package_names(user_query, debug=True)
        
        # 2. 获取工具实例（核心 + 检索到的扩展）
        core_tools = self.registry.get_core_tools()
        extension_tools = self.registry.get_package_tools(relevant_packages)
        
        # 3. 更新激活工具列表
        self.active_tools = core_tools + extension_tools
        
        # 4. 更新执行环境
        self.execution_env = self._build_execution_env(self.active_tools)
        
        # 5. 重新生成 System Prompt
        self.system_prompt = self._build_full_prompt()
        
        # 6. 日志
        print(f"🔋 [Context] 已加载工具包:")
        print(f"   ├─ 核心工具: {len(core_tools)} 个")
        print(f"   ├─ 扩展工具: {len(extension_tools)} 个 (来自 {relevant_packages})")
        print(f"   └─ 当前 Context: ~{len(self.system_prompt.split())} words")
    
    async def run(self, user_query: str):
        """执行用户任务（带 LOD 动态加载）"""
        print(f"\n🚀 [Vulcan] 启动任务: {user_query}")
        
        # ========== [LOD 核心逻辑] ==========
        # 在对话开始前，根据查询动态加载工具
        self._update_context(user_query)
        # ===================================
        
        history = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user_query)
        ]
        
        step = 0
        MAX_STEPS = 10
        
        while step < MAX_STEPS:
            step += 1
            print(f"🔄 [Step {step}] 生成中...")
            
            # 1. 调用模型
            response = await self.llm.achat(history)
            content = response.message.content
            
            # 2. 记录模型回复
            history.append(response.message)
            
            # 3. 提取代码
            code_match = CODE_BLOCK_REGEX.search(content)
            
            if code_match:
                code = code_match.group(1).strip()
                print(f"💻 [Code Detected]\n{code}")
                
                # 4. 执行代码
                output = self._execute_code(code)
                print(f"✅ [Execution Result]\n{output}")
                
                # 5. 反馈结果
                history.append(ChatMessage(
                    role="user",
                    content=f"Execution Output:\n{output}"
                ))
            else:
                # 6. 没有代码 -> 结束
                print("🏁 [Finish] 任务完成")
                
                # 清洗输出（移除 <think> 标签）
                final_answer = content
                if "</think>" in content:
                    final_answer = content.split("</think>")[-1].strip()
                
                return final_answer
        
        return "Error: Maximum steps reached."
    
    async def run_stream(self, user_query: str):
        """
        V-Final 真流式内核（混合感知架构）
        特性：
        1. 使用 astream_chat 实现毫秒级 TTFT
        2. 动态刷新时间感知（每次查询都是最新时间）
        3. 实时缓冲输出以进行 CodeAct 匹配
        4. 协议严格对齐 app.py
        """
        print(f"\n🚀 [Vulcan] 启动流式任务: {user_query}")

        # [混合感知] 刷新System Prompt（确保时间是最新的）
        self.base_system_prompt = self._build_base_prompt()

        # LOD 动态加载工具（保留原有逻辑）
        if hasattr(self, "_update_context"):
            self._update_context(user_query)
        else:
            # 如果没有LOD，至少要确保system_prompt是最新的
            self.system_prompt = self._build_full_prompt()

        # 初始化历史
        history = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user_query)
        ]

        step = 0
        MAX_STEPS = 5  # 防止死循环

        while step < MAX_STEPS:
            step += 1
            print(f"🔄 [Step {step}] 生成中...")

            # --- 1. 真流式调用 LLM（工业级过滤） ---
            response_gen = await self.llm.astream_chat(history)

            full_content = ""
            prev_content = ""  # 用于计算delta增量
            filter = OptimizedStreamingThinkFilter()  # 创建过滤器实例

            async for chunk in response_gen:
                current_content = chunk.message.content  # LLM返回的是累积内容
                
                # [防御性检查] 处理异常回退情况
                if len(current_content) >= len(prev_content):
                    delta = current_content[len(prev_content):]  # 计算增量
                else:
                    delta = ""  # 异常情况：内容回退，跳过
                
                prev_content = current_content
                
                full_content += delta  # 累加增量
                
                # 实时过滤处理（输入增量）
                filtered_outputs = filter.process_chunk(delta)
                
                # 立即输出过滤后的内容
                for output in filtered_outputs:
                    yield {
                        "type": "token",
                        "content": output,
                        "is_thinking": False
                    }
            
            # 流式结束，输出剩余buffer
            final_output = filter.flush()
            if final_output:
                yield {
                    "type": "token",
                    "content": final_output,
                    "is_thinking": False
                }
            
            # 将完整回复加入历史
            history.append(ChatMessage(role="assistant", content=full_content))

            # --- 2. CodeAct 解析与执行 ---
            code_match = CODE_BLOCK_REGEX.search(full_content)

            if code_match:
                code = code_match.group(1).strip()
                print(f"💻 [Code Detected] 长度: {len(code)}")

                # ✅ 发送 'code' 事件（让前端显示正在执行的代码）
                yield {
                    "type": "code",
                    "content": code
                }

                # 执行代码
                output = self._execute_code(code)
                print(f"✅ [Execution] {output[:50]}...")

                # ✅ 发送 'tool_output' 事件（工具执行结果）
                yield {
                    "type": "tool_output",
                    "content": output
                }

                # 喂回历史
                history.append(ChatMessage(
                    role="user",
                    content=f"Execution Output:\n{output}"
                ))

                # 循环继续
                continue

            else:
                # --- 3. 结束条件 ---
                print("🏁 [Finish] 任务完成")
                return

        yield {"type": "error", "content": "Error: Maximum steps reached."}

    def _execute_code(self, code: str) -> str:
        """代码执行器（捕获 stdout）"""
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                exec(code, self.execution_env)
            return f.getvalue().strip() or "[Code executed successfully, no output printed]"
        except Exception:
            return traceback.format_exc()
    
    def get_system_prompt(self) -> str:
        """获取完整 System Prompt（用于调试）"""
        return self.system_prompt
    
    def get_active_tools_info(self) -> str:
        """获取当前激活工具的信息（用于调试）"""
        lines = [f"当前激活工具 ({len(self.active_tools)} 个):"]
        for tool in self.active_tools:
            lines.append(f"  - {tool.metadata.name}: {tool.metadata.description[:60]}...")
        return "\n".join(lines)
