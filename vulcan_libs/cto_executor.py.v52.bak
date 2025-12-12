# vulcan_libs/cto_executor.py
"""
Vulcan Brain - CTO 执行器模块 V5.2
整合: SGLangClient + sandbox + ToolRegistry + ToolRetriever + 自我修复循环

新增 V5.2 特性:
- 动态工具加载 (LOD) - 根据任务语义检索相关工具
- 工具函数注入沙盒执行环境
"""

import re
import traceback
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

# 导入组件
from vulcan_libs.sglang_client import SGLangClient

# 安全沙盒
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
from mcp_tools.compute.sandbox import execute_code, execute_code_safe


@dataclass
class TaskSpec:
    """任务规范 - CEO 传递给 CTO 的工单"""
    task_id: str
    objective: str          # 目标描述（一句话）
    context: str            # 必要背景（精简）
    constraints: List[str]  # 约束条件
    expected_output: str    # 期望输出格式
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TaskSpec':
        return cls(
            task_id=data.get('task_id', 'task_001'),
            objective=data.get('objective', ''),
            context=data.get('context', ''),
            constraints=data.get('constraints', []),
            expected_output=data.get('expected_output', '')
        )
    
    def to_prompt(self) -> str:
        """转换为 CTO 可理解的 Prompt"""
        constraints_str = '\n'.join(f"- {c}" for c in self.constraints) if self.constraints else "无特殊约束"
        return f"""## 任务工单 [{self.task_id}]

**目标**: {self.objective}

**背景**: {self.context}

**约束条件**:
{constraints_str}

**期望输出**: {self.expected_output}

## 重要要求
1. 代码必须是完整可执行的（不只是定义函数）
2. 必须在最后调用函数并用 print() 输出结果
3. 不要只定义函数，要实际运行它
4. 如果有可用工具函数，可以直接调用它们

请编写代码完成上述任务。
"""


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    code: str
    error: Optional[str] = None
    attempts: int = 1
    tools_used: Optional[List[str]] = None


class CTOExecutor:
    """
    CTO 执行器 V5.2 - 代码生成 + 执行 + 自我修复 + LOD
    
    特性:
    1. 使用 SGLangClient 生成代码（结构化解码）
    2. 使用安全沙盒执行代码
    3. 失败时自动修复（最多3次）
    4. 支持 LOD (Load on Demand) 动态工具加载
    """
    
    CODE_BLOCK_REGEX = re.compile(r"```python(.*?)```", re.DOTALL)
    MAX_REPAIR_ATTEMPTS = 3
    
    def __init__(
        self,
        sglang_client: Optional[SGLangClient] = None,
        enable_lod: bool = True
    ):
        # SGLang 代码生成器
        self.sglang = sglang_client or SGLangClient()
        
        # LOD 相关
        self.enable_lod = enable_lod
        self._registry = None
        self._retriever = None
        self._tool_loader = None
        
        # 基础执行环境
        self.base_env = {
            '__builtins__': __builtins__,
            'print': print,
        }
    
    def _lazy_init_lod(self):
        """懒加载 LOD 组件（避免启动时加载）"""
        if self._registry is not None:
            return
        
        try:
            from vulcan_libs.tool_loader import auto_load_and_register, get_tool_loader
            from vulcan_libs.registry import get_global_registry
            from vulcan_libs.tool_retriever import ToolRetriever
            
            print("📦 [CTO] 初始化 LOD 系统...")
            
            # 自动加载并注册工具
            self._registry = auto_load_and_register()
            self._tool_loader = get_tool_loader()
            
            # 创建检索器
            self._retriever = ToolRetriever(self._registry)
            
            print("✅ [CTO] LOD 系统就绪")
        except Exception as e:
            print(f"⚠️  [CTO] LOD 初始化失败: {e}")
            self.enable_lod = False
    
    def _get_relevant_tools(self, task: TaskSpec) -> Dict[str, Callable]:
        """
        根据任务获取相关工具
        
        Args:
            task: 任务规范
            
        Returns:
            工具名 -> 工具函数 的字典
        """
        if not self.enable_lod:
            return {}
        
        self._lazy_init_lod()
        
        if not self._retriever or not self._registry:
            return {}
        
        # 使用语义检索找到相关工具包
        relevant_packages = self._retriever.retrieve_package_names(
            task.objective, 
            debug=True
        )
        
        # 获取工具函数
        tools = {}
        
        # 总是加载核心工具
        core_tools = self._registry.get_core_tools()
        for tool in core_tools:
            tools[tool.metadata.name] = tool.fn
        
        # 加载检索到的扩展工具
        if relevant_packages:
            ext_tools = self._registry.get_package_tools(relevant_packages)
            for tool in ext_tools:
                tools[tool.metadata.name] = tool.fn
        
        if tools:
            print(f"🔧 [CTO] 已加载 {len(tools)} 个工具: {list(tools.keys())}")
        
        return tools
    
    async def execute(self, task: TaskSpec) -> ExecutionResult:
        """
        执行任务（带自我修复和 LOD）
        
        Args:
            task: 任务规范
            
        Returns:
            ExecutionResult
        """
        # 获取相关工具
        tools = self._get_relevant_tools(task) if self.enable_lod else {}
        tool_names = list(tools.keys())
        
        # 构建提示（包含可用工具信息）
        prompt = task.to_prompt()
        if tools:
            # V5.2.1: 添加详细的工具签名，避免返回值类型错误
            tool_docs = {
                'web_search': 'web_search(query: str) -> str  # 搜索网络，返回文本结果',
                'run_python': 'run_python(code: str) -> str  # 执行Python代码',
                'remember': 'remember(content: str) -> str  # 保存记忆',
                'recall': 'recall(query: str) -> str  # 检索记忆',
                'get_current_time': 'get_current_time() -> str  # 获取当前时间',
                'get_current_date': 'get_current_date() -> str  # 获取当前日期',
            }
            tool_list = '\n'.join(tool_docs.get(name, f"{name}()") for name in tool_names)
            prompt += f"""

## 可用工具函数（已导入，可直接调用）
{tool_list}

注意: 所有工具函数返回的都是字符串(str)，不是字典！

正确用法：
```python
result = web_search("特斯拉2024年财报")
print(result)  # 直接输出搜索结果
```

错误用法：
- result['key'] ❌ (返回的是字符串不是字典)
- print("未找到") ❌ (不要自己判断，让调用方处理)

你的职责是**执行任务并返回原始数据**，分析工作由上层完成。

**代码风格要求**：
- 写最简单的代码，不要定义函数
- 直接调用工具，直接 print 结果
- 不要用 def，不要用 class，不要过度工程化

示例（正确 - 简单直接）：
```python
result = web_search("特斯拉2024年财报")
print(result)
```

示例（错误 - 过度复杂）：
```python
def fetch_data(query):
    return web_search(query + "财报")
    
result = fetch_data("特斯拉")  # 不要这样！
print(result)
```
"""
        
        last_error = None
        last_code = ""
        
        for attempt in range(1, self.MAX_REPAIR_ATTEMPTS + 1):
            print(f"🔧 [CTO] 尝试 {attempt}/{self.MAX_REPAIR_ATTEMPTS}")
            
            # 1. 生成代码
            if attempt == 1:
                code = await self._generate_code(prompt)
            else:
                # 修复模式：带上错误信息
                repair_prompt = f"""{prompt}

## 上次尝试失败
代码:
```python
{last_code}
```

错误:
{last_error}

请修复代码并重试。
"""
                code = await self._generate_code(repair_prompt)
            
            if not code:
                last_error = "代码生成失败：未能提取有效代码"
                continue
            
            last_code = code
            print(f"💻 [CTO] 生成代码:\n{code[:200]}...")
            
            # 2. 构建执行环境（注入工具）
            exec_env = {**self.base_env, **tools}
            
            # 3. 执行代码（使用安全沙盒）
            result = execute_code(code, timeout=30, extra_globals=exec_env)
            
            if result['success']:
                output = result['output'] or str(result.get('result', ''))
                print(f"✅ [CTO] 执行成功: {output[:100]}...")
                return ExecutionResult(
                    success=True,
                    output=output,
                    code=code,
                    attempts=attempt,
                    tools_used=tool_names if tools else None
                )
            else:
                last_error = result['error']
                print(f"❌ [CTO] 执行失败: {last_error}")
        
        # 所有尝试都失败
        return ExecutionResult(
            success=False,
            output="",
            code=last_code,
            error=f"经过 {self.MAX_REPAIR_ATTEMPTS} 次尝试仍然失败: {last_error}",
            attempts=self.MAX_REPAIR_ATTEMPTS,
            tools_used=tool_names if tools else None
        )
    
    async def _generate_code(self, prompt: str) -> Optional[str]:
        """使用 SGLang 生成代码"""
        try:
            # 检查 SGLang 健康状态
            if not await self.sglang.health_check():
                print("⚠️ [CTO] SGLang 不可用，尝试降级到 Ollama")
                return await self._generate_code_fallback(prompt)
            
            # 调用 SGLang 生成
            response = await self.sglang.generate_code(
                task=prompt,
                language="python"
            )
            
            # 提取代码块
            match = self.CODE_BLOCK_REGEX.search(response)
            if match:
                return match.group(1).strip()
            
            # 没有代码块，可能整个响应就是代码
            if 'def ' in response or 'print(' in response or 'import ' in response:
                return response.strip()
            
            return None
            
        except Exception as e:
            print(f"⚠️ [CTO] SGLang 调用失败: {e}")
            return await self._generate_code_fallback(prompt)
    
    async def _generate_code_fallback(self, prompt: str) -> Optional[str]:
        """降级到 Ollama 生成代码"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "qwen3:30b-a3b",
                        "messages": [
                            {"role": "system", "content": "你是一个代码生成专家。只输出 Python 代码，用 ```python ``` 包裹。"},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    }
                )
                data = resp.json()
                content = data.get('message', {}).get('content', '')
                
                match = self.CODE_BLOCK_REGEX.search(content)
                if match:
                    return match.group(1).strip()
                return None
        except Exception as e:
            print(f"❌ [CTO] Ollama fallback 也失败: {e}")
            return None


# 便捷函数
_executor_cache = None

def get_cto_executor(enable_lod: bool = True) -> CTOExecutor:
    """获取 CTO 执行器实例（单例）"""
    global _executor_cache
    if _executor_cache is None:
        _executor_cache = CTOExecutor(enable_lod=enable_lod)
    return _executor_cache
