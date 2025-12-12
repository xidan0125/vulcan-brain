# vulcan_libs/tool_loader.py
"""
Vulcan Brain - 工具自动加载器 (Tool Auto-Loader)
从 mcp_tools/ 目录自动发现并注册工具

职责：
1. 扫描 mcp_tools/ 目录发现工具模块
2. 将函数包装为 LlamaIndex FunctionTool
3. 自动注册到 ToolRegistry
4. 支持 LOD (Load on Demand) 检索
"""

import os
import sys
import importlib
import inspect
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass

# 确保路径正确
sys.path.insert(0, '/home/xinyue/vulcan-brain')

from llama_index.core.tools import FunctionTool
from vulcan_libs.registry import ToolRegistry, ToolPackage, get_global_registry


# === 工具目录配置 ===
MCP_TOOLS_DIR = '/home/xinyue/vulcan-brain/mcp_tools'

# 核心工具包（常驻内存）
CORE_PACKAGES = {'core'}

# 包分类映射
CATEGORY_MAP = {
    'core': '核心工具 - 时间、基础功能',
    'knowledge': '知识工具 - RAG、文档搜索',
    'alignment': '对齐工具 - 反馈、洞察',
    'compute': '计算工具 - 代码执行、数据处理',
}


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    fn: Callable
    description: str
    module_path: str
    category: str


class ToolLoader:
    """
    工具自动加载器
    
    扫描 mcp_tools/ 目录，自动发现并注册工具
    """
    
    def __init__(self, tools_dir: str = MCP_TOOLS_DIR):
        self.tools_dir = tools_dir
        self.discovered_tools: Dict[str, List[ToolInfo]] = {}  # category -> tools
        self._loaded = False
    
    def discover(self) -> Dict[str, List[ToolInfo]]:
        """
        发现所有工具
        
        Returns:
            按类别分组的工具字典
        """
        print(f"🔍 [ToolLoader] 扫描工具目录: {self.tools_dir}")
        
        self.discovered_tools = {}
        
        for category in os.listdir(self.tools_dir):
            category_path = os.path.join(self.tools_dir, category)
            
            # 跳过非目录和特殊文件
            if not os.path.isdir(category_path) or category.startswith('_'):
                continue
            
            self.discovered_tools[category] = []
            
            # 扫描该类别下的所有 Python 文件
            for filename in os.listdir(category_path):
                if not filename.endswith('.py') or filename.startswith('_'):
                    continue
                
                module_name = filename[:-3]  # 去掉 .py
                module_path = f"mcp_tools.{category}.{module_name}"
                
                try:
                    tools = self._load_module_tools(module_path, category)
                    self.discovered_tools[category].extend(tools)
                except Exception as e:
                    print(f"⚠️  [ToolLoader] 加载模块失败 {module_path}: {e}")
        
        # 统计
        total = sum(len(tools) for tools in self.discovered_tools.values())
        print(f"✅ [ToolLoader] 发现 {total} 个工具:")
        for cat, tools in self.discovered_tools.items():
            print(f"   ├─ {cat}: {len(tools)} 个")
        
        self._loaded = True
        return self.discovered_tools
    
    def _load_module_tools(self, module_path: str, category: str) -> List[ToolInfo]:
        """加载单个模块的工具"""
        module = importlib.import_module(module_path)
        tools = []
        
        # 方式1: 从 __module_info__ 获取
        if hasattr(module, '__module_info__'):
            info = module.__module_info__
            for func_info in info.get('functions', []):
                func_name = func_info['name']
                if hasattr(module, func_name):
                    tools.append(ToolInfo(
                        name=func_name,
                        fn=getattr(module, func_name),
                        description=func_info.get('desc', f'{func_name} from {module_path}'),
                        module_path=module_path,
                        category=category
                    ))
        else:
            # 方式2: 自动发现公开函数
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith('_'):
                    continue
                # 只取该模块定义的函数
                if obj.__module__ == module.__name__:
                    doc = obj.__doc__ or f'{name} from {module_path}'
                    tools.append(ToolInfo(
                        name=name,
                        fn=obj,
                        description=doc.split('\n')[0],  # 取第一行
                        module_path=module_path,
                        category=category
                    ))
        
        return tools
    
    def register_to_registry(self, registry: Optional[ToolRegistry] = None) -> ToolRegistry:
        """
        将发现的工具注册到 ToolRegistry
        
        Args:
            registry: 注册表实例，如果为 None 则使用全局注册表
        
        Returns:
            注册表实例
        """
        if not self._loaded:
            self.discover()
        
        registry = registry or get_global_registry()
        
        print(f"📦 [ToolLoader] 注册工具到 ToolRegistry...")
        
        for category, tools in self.discovered_tools.items():
            if not tools:
                continue
            
            # 将 ToolInfo 转换为 LlamaIndex FunctionTool
            llama_tools = []
            for tool_info in tools:
                try:
                    llama_tool = FunctionTool.from_defaults(
                        fn=tool_info.fn,
                        name=tool_info.name,
                        description=tool_info.description
                    )
                    llama_tools.append(llama_tool)
                except Exception as e:
                    print(f"⚠️  [ToolLoader] 包装工具失败 {tool_info.name}: {e}")
            
            if llama_tools:
                # 创建工具包
                package = ToolPackage(
                    name=f"{category}_pkg",
                    description=CATEGORY_MAP.get(category, f'{category} 工具包'),
                    tools=llama_tools,
                    is_core=(category in CORE_PACKAGES),
                    category=category
                )
                registry.register(package)
        
        print(f"✅ [ToolLoader] 注册完成")
        print(registry.get_registry_summary())
        
        return registry
    
    def get_tool_by_name(self, name: str) -> Optional[Callable]:
        """按名称获取工具函数"""
        for tools in self.discovered_tools.values():
            for tool in tools:
                if tool.name == name:
                    return tool.fn
        return None
    
    def get_tools_by_category(self, category: str) -> List[ToolInfo]:
        """按类别获取工具"""
        return self.discovered_tools.get(category, [])


# === 便捷函数 ===

_loader_instance: Optional[ToolLoader] = None

def get_tool_loader() -> ToolLoader:
    """获取全局 ToolLoader 实例"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ToolLoader()
    return _loader_instance


def auto_load_and_register() -> ToolRegistry:
    """
    一键自动加载并注册所有工具
    
    Returns:
        已注册的 ToolRegistry
    """
    loader = get_tool_loader()
    return loader.register_to_registry()


# === CTO 执行器集成接口 ===

def get_sandbox_tools() -> Dict[str, Callable]:
    """
    获取 CTO 可用的沙盒工具
    
    Returns:
        工具名 -> 工具函数 的字典
    """
    loader = get_tool_loader()
    if not loader._loaded:
        loader.discover()
    
    sandbox_tools = {}
    
    # 只加载安全的工具到沙盒
    safe_categories = {'core', 'knowledge'}  # 可在沙盒中使用的类别
    
    for category, tools in loader.discovered_tools.items():
        if category in safe_categories:
            for tool in tools:
                sandbox_tools[tool.name] = tool.fn
    
    return sandbox_tools


# === 测试 ===
if __name__ == '__main__':
    print("=== Tool Loader 测试 ===\n")
    
    loader = ToolLoader()
    tools = loader.discover()
    
    print("\n--- 测试工具调用 ---")
    get_time = loader.get_tool_by_name('get_current_time')
    if get_time:
        print(f"当前时间: {get_time()}")
    
    print("\n--- 注册到 Registry ---")
    registry = loader.register_to_registry()
    
    print("\n✅ 测试完成")
