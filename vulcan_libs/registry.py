# vulcan_libs/registry.py
"""
Vulcan Brain - 工具注册表 (Tool Registry)

职责：
1. 管理工具包 (ToolPackage) - 将相关工具组织成逻辑单元
2. 区分核心工具 (Core) 和扩展工具 (Extensions)
3. 为 ToolRetriever 提供元数据映射

设计原则：
- 工具包 = Agent 的"武器库"，每个包有明确的职责
- 核心包常驻内存（如 get_time, memory）
- 扩展包按需加载（如 RAG, 数据分析）
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from llama_index.core.tools import BaseTool


@dataclass
class ToolPackage:
    """工具包数据结构"""
    name: str                  # 包名，如 "rag_tools"
    description: str           # 包的宏观描述，用于 LOD-0 概览
    tools: List[BaseTool]      # 包含的具体工具列表
    is_core: bool = False      # 是否为核心包 (常驻内存)
    category: str = "general"  # 分类标签（可选，用于高级过滤）


class ToolRegistry:
    """工具注册表 - Vulcan 的"军械库管理系统"""
    
    def __init__(self):
        self.packages: Dict[str, ToolPackage] = {}
        self.all_tools_map: Dict[str, BaseTool] = {}  # 工具名 -> 工具实例
        self._stats = {"core_count": 0, "extension_count": 0}
    
    def register(self, package: ToolPackage):
        """
        注册工具包
        
        Args:
            package: ToolPackage 实例
        """
        print(f"📦 [Registry] 注册工具包: {package.name} ({len(package.tools)} tools, core={package.is_core})")
        
        self.packages[package.name] = package
        
        # 构建工具名 -> 工具实例的映射
        for tool in package.tools:
            tool_name = tool.metadata.name
            if tool_name in self.all_tools_map:
                print(f"⚠️  [Registry] 工具名冲突: {tool_name} (覆盖)")
            self.all_tools_map[tool_name] = tool
        
        # 更新统计
        if package.is_core:
            self._stats["core_count"] += len(package.tools)
        else:
            self._stats["extension_count"] += len(package.tools)
    
    def get_core_tools(self) -> List[BaseTool]:
        """
        获取所有核心工具（常驻工具）
        
        Returns:
            核心工具列表
        """
        tools = []
        for pkg in self.packages.values():
            if pkg.is_core:
                tools.extend(pkg.tools)
        return tools
    
    def get_package_tools(self, package_names: List[str]) -> List[BaseTool]:
        """
        获取指定工具包的所有工具
        
        Args:
            package_names: 包名列表，如 ["rag_pkg", "data_analysis_pkg"]
        
        Returns:
            工具列表
        """
        tools = []
        for name in package_names:
            if name in self.packages:
                tools.extend(self.packages[name].tools)
            else:
                print(f"⚠️  [Registry] 未找到工具包: {name}")
        return tools
    
    def get_all_packages(self) -> List[str]:
        """获取所有已注册的包名"""
        return list(self.packages.keys())
    
    def get_package_info(self, package_name: str) -> str:
        """
        获取工具包的详细信息（用于调试）
        
        Args:
            package_name: 包名
        
        Returns:
            格式化的包信息
        """
        if package_name not in self.packages:
            return f"❌ 未找到工具包: {package_name}"
        
        pkg = self.packages[package_name]
        lines = [
            f"📦 {pkg.name}",
            f"   描述: {pkg.description}",
            f"   类型: {核心包 if pkg.is_core else 扩展包}",
            f"   工具数: {len(pkg.tools)}",
            "   工具列表:"
        ]
        for tool in pkg.tools:
            lines.append(f"     - {tool.metadata.name}: {tool.metadata.description[:60]}...")
        
        return "\n".join(lines)
    
    def get_registry_summary(self) -> str:
        """
        获取注册表摘要（用于启动时显示）
        
        Returns:
            摘要信息
        """
        lines = [
            "🗂️  [Registry] 工具注册表摘要",
            f"   总包数: {len(self.packages)}",
            f"   核心工具: {self._stats['core_count']} 个",
            f"   扩展工具: {self._stats['extension_count']} 个",
            "   已注册的包:"
        ]
        
        for pkg_name, pkg in self.packages.items():
            status = "🔒 Core" if pkg.is_core else "🔓 Extension"
            lines.append(f"     - {status} {pkg_name} ({len(pkg.tools)} tools)")
        
        return "\n".join(lines)


# === 便捷函数接口 ===

_default_registry = None

def get_global_registry() -> ToolRegistry:
    """获取全局注册表实例（单例模式）"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
    return _default_registry


# === 测试代码 ===
if __name__ == "__main__":
    from llama_index.core.tools import FunctionTool
    
    print("=== Tool Registry 测试 ===\n")
    
    # 创建测试工具
    def dummy_func1():
        return "tool1"
    
    def dummy_func2():
        return "tool2"
    
    tool1 = FunctionTool.from_defaults(fn=dummy_func1, name="test_tool_1", description="测试工具1")
    tool2 = FunctionTool.from_defaults(fn=dummy_func2, name="test_tool_2", description="测试工具2")
    
    # 测试注册
    registry = ToolRegistry()
    
    core_pkg = ToolPackage(
        name="core",
        description="核心工具包",
        tools=[tool1],
        is_core=True
    )
    
    ext_pkg = ToolPackage(
        name="extensions",
        description="扩展工具包",
        tools=[tool2],
        is_core=False
    )
    
    registry.register(core_pkg)
    registry.register(ext_pkg)
    
    # 测试检索
    print("\n--- 测试核心工具检索 ---")
    core_tools = registry.get_core_tools()
    print(f"核心工具数: {len(core_tools)}")
    
    print("\n--- 测试包检索 ---")
    ext_tools = registry.get_package_tools(["extensions"])
    print(f"扩展工具数: {len(ext_tools)}")
    
    print("\n--- 注册表摘要 ---")
    print(registry.get_registry_summary())
    
    print("\n✅ 测试完成")
