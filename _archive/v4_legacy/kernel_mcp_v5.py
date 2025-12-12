# kernel_mcp_v5.py - Vulcan Brain MCP Kernel V5
"""
Vulcan Brain - MCP Code Execution Kernel V5.0

架构升级 (参考 Anthropic Code Execution with MCP):
1. 模块化工具: 工具变成可 import 的 Python 模块
2. 文件系统发现: Agent 浏览 mcp_tools/ 目录发现能力
3. 代码优先执行: Agent 写代码调用模块，而非预定义工具
4. 数据不进模型: 处理结果在沙箱完成，只返回精炼结果

Token 优化:
- 旧模式: ~20 个工具定义在 Context (~5000 tokens)
- 新模式: 只提供目录结构 (~500 tokens)，按需读取模块
- 预计减少 90% Context 占用
"""

import re
import os
import sys
import pytz
import traceback
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from io import StringIO

from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage
# VulcanStore 数据持久化
from vulcan_libs.store import store

# 导入三层记忆系统
from vulcan_libs.memory import get_all_memories
from vulcan_libs.alignment import load_constitution, get_relevant_lessons

# MCP 工具路径
MCP_TOOLS_PATH = os.path.expanduser('~/vulcan_brain_v2/mcp_tools')

# 代码块匹配 - 支持两种格式
CODE_BLOCK_REGEX = re.compile(r"```python(.*?)```", re.DOTALL)
# 裸代码匹配 - 检测以 from mcp_tools 开头的代码片段
BARE_CODE_REGEX = re.compile(r"(from mcp_tools\.[^\n]+\n(?:.*?print\([^\)]+\))?)", re.DOTALL)


def _is_code_line(line: str) -> bool:
    """判断一行是否是 Python 代码"""
    stripped = line.strip()
    if not stripped:
        return True  # 空行可以保留

    # 明确的代码模式
    code_patterns = [
        stripped.startswith('from '),
        stripped.startswith('import '),
        stripped.startswith('print('),
        stripped.startswith('print '),
        stripped.startswith('#'),  # 注释
        stripped.startswith('def '),
        stripped.startswith('class '),
        stripped.startswith('if '),
        stripped.startswith('else:'),
        stripped.startswith('elif '),
        stripped.startswith('for '),
        stripped.startswith('while '),
        stripped.startswith('try:'),
        stripped.startswith('except'),
        stripped.startswith('with '),
        stripped.startswith('return '),
        stripped.startswith('raise '),
        '=' in stripped,  # 赋值
        stripped.endswith(')'),  # 函数调用
        stripped.endswith(':'),  # 块语句
        re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\(', stripped),  # 函数调用开头
    ]

    return any(code_patterns)


def _is_natural_language(line: str) -> bool:
    """判断是否是自然语言（非代码）"""
    stripped = line.strip()
    if not stripped:
        return False

    # 中文字符占比超过 50% 认为是自然语言
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', stripped))
    if chinese_chars > len(stripped) * 0.3:
        return True

    # 特定的非代码标记
    non_code_markers = ['✅', '❌', '⚠️', '📝', '🔍', '💡', '根据', '注意', '说明', '提示']
    for marker in non_code_markers:
        if marker in stripped:
            return True

    return False


def extract_code(content: str) -> Optional[str]:
    """
    从响应中提取代码
    优先检测 ```python``` 代码块，其次检测裸代码
    """
    # 1. 优先检测代码块
    match = CODE_BLOCK_REGEX.search(content)
    if match:
        return match.group(1).strip()

    # 2. 检测裸代码（以 from mcp_tools 开头）
    if 'from mcp_tools' in content:
        lines = content.split('\n')
        code_lines = []
        in_code = False

        for line in lines:
            stripped = line.strip()

            # 检测代码开始
            if stripped.startswith('from mcp_tools') or stripped.startswith('import mcp_tools'):
                in_code = True

            if in_code:
                # 遇到自然语言，代码块结束
                if _is_natural_language(stripped):
                    break

                # 空行保留（可能是代码中的空行）
                if not stripped:
                    if code_lines:  # 只有已收集代码后才保留空行
                        code_lines.append('')
                    continue

                # 检查是否像代码
                if _is_code_line(stripped):
                    code_lines.append(stripped)
                else:
                    # 不太确定是不是代码，但不是明显的自然语言
                    # 如果看起来像函数调用或表达式，保留
                    if re.match(r'^[a-zA-Z_]', stripped) and '(' in stripped:
                        code_lines.append(stripped)
                    elif code_lines:  # 已有代码后遇到不确定的行，结束
                        break

        # 清理尾部空行
        while code_lines and not code_lines[-1]:
            code_lines.pop()

        if code_lines:
            return '\n'.join(code_lines)

    return None


class MCPToolDiscovery:
    """
    MCP 工具发现系统

    让 Agent 通过浏览文件系统发现可用工具
    """

    def __init__(self, tools_path: str = MCP_TOOLS_PATH):
        self.tools_path = tools_path

    def get_directory_structure(self) -> str:
        """获取工具目录结构（给 Agent 看的）"""
        lines = ['mcp_tools/']

        for category in sorted(os.listdir(self.tools_path)):
            cat_path = os.path.join(self.tools_path, category)
            if os.path.isdir(cat_path) and not category.startswith('_'):
                lines.append(f'├── {category}/')

                for file in sorted(os.listdir(cat_path)):
                    if file.endswith('.py') and not file.startswith('_'):
                        lines.append(f'│   ├── {file}')

        return '\n'.join(lines)

    def get_module_info(self, category: str, module_name: str) -> str:
        """获取指定模块的接口信息"""
        module_path = os.path.join(self.tools_path, category, f'{module_name}.py')

        if not os.path.exists(module_path):
            return f'模块不存在: {category}/{module_name}.py'

        with open(module_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取 docstring 和 __module_info__
        lines = []

        # 提取模块 docstring
        if content.startswith('"""') or content.startswith("'''"):
            quote = '"""' if content.startswith('"""') else "'''"
            end = content.find(quote, 3)
            if end > 0:
                docstring = content[3:end].strip()
                lines.append(f'# {category}/{module_name}.py')
                lines.append(docstring)

        # 提取 __module_info__
        if '__module_info__' in content:
            match = re.search(r'__module_info__\s*=\s*(\{[^}]+\})', content, re.DOTALL)
            if match:
                lines.append('\n可用函数:')
                try:
                    info = eval(match.group(1))
                    for func in info.get('functions', []):
                        params = ', '.join(func.get('params', []))
                        lines.append(f"  - {func['name']}({params}): {func['desc']}")
                except:
                    pass

        return '\n'.join(lines)

    def list_categories(self) -> List[str]:
        """列出所有工具类别"""
        return [d for d in os.listdir(self.tools_path)
                if os.path.isdir(os.path.join(self.tools_path, d))
                and not d.startswith('_')]


class MCPCodeExecutor:
    """
    MCP 代码执行器

    执行 Agent 生成的代码，自动注入 mcp_tools 模块
    """

    def __init__(self, tools_path: str = MCP_TOOLS_PATH):
        self.tools_path = tools_path
        self._setup_import_path()

    def _setup_import_path(self):
        """设置 Python 导入路径"""
        parent_path = os.path.dirname(self.tools_path)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)

    def execute(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        执行代码

        代码可以直接 import mcp_tools 中的模块:
        ```python
        from mcp_tools.core import get_current_time
        print(get_current_time())
        ```
        """
        # 安全检查
        forbidden = ['os.system', 'subprocess', 'eval(', 'exec(', 'shutil', 'socket']
        for pattern in forbidden:
            if pattern in code.lower():
                return {
                    'success': False,
                    'output': '',
                    'error': f'禁止的操作: {pattern}'
                }

        # 捕获 stdout
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()

        result = None
        error = None

        try:
            # 准备执行环境
            exec_globals = {
                '__builtins__': __builtins__,
                '__name__': '__main__',
            }
            exec_locals = {}

            # 编译执行
            compiled = compile(code, '<mcp_sandbox>', 'exec')
            exec(compiled, exec_globals, exec_locals)

            # 获取 result 变量
            for var in ['result', 'output', 'data', 'answer']:
                if var in exec_locals:
                    result = exec_locals[var]
                    break

        except Exception as e:
            error = f'{type(e).__name__}: {str(e)}\n{traceback.format_exc()}'
        finally:
            sys.stdout = old_stdout

        stdout_content = captured.getvalue()

        return {
            'success': error is None,
            'output': stdout_content[:10000],
            'result': result,
            'error': error
        }


class OptimizedStreamingThinkFilter:
    """流式过滤器 - 过滤 <think> 标签"""

    def __init__(self):
        self.buffer = ""
        self.inside_think = False

    def process_chunk(self, chunk: str):
        self.buffer += chunk
        outputs = []

        while True:
            if self.inside_think:
                close_idx = self.buffer.find('</think>')
                if close_idx == -1:
                    self.buffer = ""
                    break
                else:
                    self.buffer = self.buffer[close_idx + 8:]
                    self.inside_think = False
            else:
                open_idx = self.buffer.find('<think>')
                if open_idx == -1:
                    safe_len = self._find_safe_output_length(self.buffer)
                    if safe_len > 0:
                        outputs.append(self.buffer[:safe_len])
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    if open_idx > 0:
                        outputs.append(self.buffer[:open_idx])
                    self.buffer = self.buffer[open_idx + 7:]
                    self.inside_think = True

        return outputs

    def _find_safe_output_length(self, text: str) -> int:
        if not text:
            return 0
        for i in range(min(8, len(text)), 0, -1):
            suffix = text[-i:]
            if '<think>'.startswith(suffix) or '</think>'.startswith(suffix):
                return len(text) - i
        return len(text)

    def flush(self) -> str:
        if self.buffer and not self.inside_think:
            result = self.buffer
            self.buffer = ""
            return result
        return ""


class VulcanMCPKernel:
    """
    Vulcan Brain MCP Kernel V5

    核心变化:
    1. 不再预加载工具定义到 Context
    2. 提供目录结构，让 Agent 自己浏览发现
    3. Agent 写代码 import 并调用模块
    4. 数据处理在沙箱完成，不占用 Context
    """

    def __init__(self, model: str):
        # 1. LLM 初始化
        self.llm = Ollama(
            model=model,
            temperature=0.1,
            request_timeout=120.0,
            context_window=8192,
            additional_kwargs={
                "num_gpu": -1,
                "stop": ["<|im_end|>", "<|endoftext|>", "User:", "Observation:"]
            }
        )

        # 2. MCP 组件
        self.discovery = MCPToolDiscovery()
        self.executor = MCPCodeExecutor()

        # 3. 三层记忆
        self.constitution = load_constitution()
        self.alignment_lessons = get_relevant_lessons()
        self.user_memories = get_all_memories()

        # 4. 构建 System Prompt
        self.system_prompt = self._build_system_prompt()

        # 5. VulcanStore 集成
        self.store = store
        self.current_session_id = None

        print(f"🚀 [Vulcan MCP Kernel V5] 初始化完成")
        print(f"   ├─ 模型: {model}")
        print(f"   ├─ 工具目录: {MCP_TOOLS_PATH}")
        print(f"   └─ System Prompt: ~{len(self.system_prompt.split())} words")

    def _get_perception_context(self) -> str:
        """获取环境感知"""
        tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz)
        return f"""【环境感知】
- 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
- 星期: {now.strftime('%A')}
- 时区: Asia/Shanghai
"""

    def _build_system_prompt(self) -> str:
        """构建 System Prompt（MCP 模式）"""
        perception = self._get_perception_context()
        tools_structure = self.discovery.get_directory_structure()

        return f"""你是 Vulcan Brain - 一个有原则、有记忆、有灵魂的 AI 助手。

{perception}

{self.constitution}

{self.alignment_lessons}

【用户长期记忆】
{self.user_memories}

【工具系统 - MCP 模式】
你可以通过编写 Python 代码来使用工具。工具以 Python 模块形式组织：

{tools_structure}

**使用方法:**
1. 直接 import 需要的模块
2. 调用函数处理数据
3. 用 print() 输出结果

**示例 - 获取时间:**
```python
from mcp_tools.core.time import get_datetime_info
info = get_datetime_info()
print(f"现在是 {{info['datetime']}}，{{info['weekday_cn']}}")
```

**示例 - 记忆管理:**
```python
from mcp_tools.core.memory import remember, recall
remember("Boss 喜欢简洁的汇报")
print(recall("Boss"))
```

**示例 - 知识库搜索:**
```python
from mcp_tools.knowledge.rag import search_knowledge
result = search_knowledge("项目进度")
print(result)
```

**示例 - 执行计算:**
```python
from mcp_tools.compute.sandbox import execute_code_safe
result = execute_code_safe("print(sum(range(100)))")
print(result)
```

【工作流程】
1. **感知优先**: 简单问题（如时间）直接用环境感知信息回答
2. **代码执行**: 需要工具时，写 Python 代码 import 并调用模块
3. **纯聊天**: 观点类/闲聊类问题直接回答，不强行写代码
4. 我会执行你的代码，并将 print() 输出返回给你
5. 你根据输出给出最终答案

【核心原则】
- 代码优于文字：Show, don't tell
- 简洁胜于复杂
- 必须使用 print() 输出关键结果

开始执行任务。
"""

    async def run_stream(self, user_query: str, user_id: str = "xinyueyu", session_id: str = None):
        """流式执行"""
        print(f"\n🚀 [Vulcan MCP] 启动任务: {user_query}")

        # 会话持久化 - 创建或使用已有会话
        if session_id is None:
            session_id = await self.store.create_session(user_id, provider="vulcan", title=user_query[:50])
        self.current_session_id = session_id
        # 保存用户消息
        await self.store.add_message(session_id, "user", user_query, provider="vulcan")


        # 刷新 System Prompt（更新时间感知）
        self.system_prompt = self._build_system_prompt()

        history = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user_query)
        ]

        step = 0
        MAX_STEPS = 5

        while step < MAX_STEPS:
            step += 1
            print(f"🔄 [Step {step}] 生成中...")

            # 流式调用 LLM
            response_gen = await self.llm.astream_chat(history)

            full_content = ""
            prev_content = ""
            filter = OptimizedStreamingThinkFilter()

            async for chunk in response_gen:
                current_content = chunk.message.content

                if len(current_content) >= len(prev_content):
                    delta = current_content[len(prev_content):]
                else:
                    delta = ""

                prev_content = current_content
                full_content += delta

                filtered_outputs = filter.process_chunk(delta)
                for output in filtered_outputs:
                    yield {
                        "type": "token",
                        "content": output,
                        "is_thinking": False
                    }

            final_output = filter.flush()
            if final_output:
                yield {
                    "type": "token",
                    "content": final_output,
                    "is_thinking": False
                }

            history.append(ChatMessage(role="assistant", content=full_content))

            # 检测代码块（支持 ```python``` 和裸代码）
            code = extract_code(full_content)

            if code:
                print(f"💻 [Code Detected] 长度: {len(code)}")

                # 执行代码
                exec_result = self.executor.execute(code)

                if exec_result['success']:
                    output = exec_result['output']
                    if exec_result['result'] is not None:
                        output += f"\n[Result]: {exec_result['result']}"
                else:
                    output = f"[Error]: {exec_result['error']}"

                print(f"✅ [Execution] {output[:100]}...")

                yield {
                    "type": "tool_output",
                    "content": output
                }

                history.append(ChatMessage(
                    role="user",
                    content=f"Execution Output:\n{output}"
                ))

                continue
            else:
                print("🏁 [Finish] 任务完成")
                # 保存 assistant 响应到数据库
                await self.store.add_message(session_id, "assistant", full_content, provider="vulcan")
                return

        yield {"type": "error", "content": "Error: Maximum steps reached."}

    async def run(self, user_query: str) -> str:
        """非流式执行（收集完整响应）"""
        full_response = ""
        async for event in self.run_stream(user_query):
            if event.get("type") == "token":
                full_response += event.get("content", "")
        return full_response

    def get_system_prompt(self) -> str:
        """获取完整 System Prompt（调试用）"""
        return self.system_prompt


# === 测试 ===
if __name__ == "__main__":
    import asyncio
    from config import LLM_MODEL_NAME

    async def test():
        kernel = VulcanMCPKernel(model=LLM_MODEL_NAME)

        print("\n=== 测试 1: 时间查询 ===")
        async for event in kernel.run_stream("现在几点了？"):
            if event["type"] == "token":
                print(event["content"], end="", flush=True)

        print("\n\n=== 测试 2: 记忆 ===")
        async for event in kernel.run_stream("帮我记住：我明天有重要会议"):
            if event["type"] == "token":
                print(event["content"], end="", flush=True)

        print("\n\n=== 测试完成 ===")

    asyncio.run(test())
