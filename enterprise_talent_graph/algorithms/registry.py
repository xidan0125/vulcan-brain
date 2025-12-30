"""
算法注册表 - 自动发现和管理算法

使用方式:
    from algorithms.registry import AlgorithmRegistry
    
    registry = AlgorithmRegistry()
    registry.auto_discover()
    
    # 获取所有算法
    all_algos = registry.get_all()
    
    # 按层级获取
    layer1_algos = registry.get_by_layer("layer1_network")
    
    # 获取单个算法
    centrality = registry.get("degree_centrality")
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type
import logging

from .base import BaseAlgorithm

logger = logging.getLogger(__name__)


class AlgorithmRegistry:
    """算法注册表"""
    
    def __init__(self):
        self._algorithms: Dict[str, Type[BaseAlgorithm]] = {}
        self._by_layer: Dict[str, List[str]] = {}
    
    def register(self, algorithm_class: Type[BaseAlgorithm]) -> None:
        """注册算法"""
        name = algorithm_class.name
        layer = algorithm_class.layer
        
        if name in self._algorithms:
            logger.warning(f"Algorithm {name} already registered, overwriting")
        
        self._algorithms[name] = algorithm_class
        
        if layer not in self._by_layer:
            self._by_layer[layer] = []
        if name not in self._by_layer[layer]:
            self._by_layer[layer].append(name)
        
        logger.debug(f"Registered algorithm: {name} (layer: {layer})")
    
    def get(self, name: str, config: Optional[Dict] = None) -> Optional[BaseAlgorithm]:
        """获取算法实例"""
        if name not in self._algorithms:
            logger.error(f"Algorithm not found: {name}")
            return None
        return self._algorithms[name](config)
    
    def get_class(self, name: str) -> Optional[Type[BaseAlgorithm]]:
        """获取算法类"""
        return self._algorithms.get(name)
    
    def get_all(self) -> Dict[str, Type[BaseAlgorithm]]:
        """获取所有算法"""
        return self._algorithms.copy()
    
    def get_by_layer(self, layer: str) -> List[Type[BaseAlgorithm]]:
        """按层级获取算法"""
        names = self._by_layer.get(layer, [])
        return [self._algorithms[n] for n in names]
    
    def list_layers(self) -> List[str]:
        """列出所有层级"""
        return list(self._by_layer.keys())
    
    def list_algorithms(self) -> List[Dict]:
        """列出所有算法信息"""
        result = []
        for name, cls in self._algorithms.items():
            result.append({
                "name": name,
                "layer": cls.layer,
                "description": cls.description,
                "class": cls.__name__
            })
        return result
    
    def auto_discover(self, package_path: Optional[str] = None) -> int:
        """
        自动发现并注册算法
        
        扫描 algorithms 目录下的所有 Python 文件，
        找到继承 BaseAlgorithm 的类并注册。
        
        Returns:
            int: 注册的算法数量
        """
        if package_path is None:
            package_path = str(Path(__file__).parent)
        
        count = 0
        layers = ["layer1_network", "layer2_semantics", "layer3_functions", 
                  "layer4_external", "risk"]
        
        for layer in layers:
            layer_path = Path(package_path) / layer
            if not layer_path.exists():
                continue
            
            for py_file in layer_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                
                module_name = f"enterprise_talent_graph.algorithms.{layer}.{py_file.stem}"
                try:
                    module = importlib.import_module(module_name)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseAlgorithm) and 
                            attr is not BaseAlgorithm and
                            hasattr(attr, "name") and 
                            attr.name != "base"):
                            self.register(attr)
                            count += 1
                            
                except Exception as e:
                    logger.error(f"Failed to load module {module_name}: {e}")
        
        logger.info(f"Auto-discovered {count} algorithms")
        return count


# 全局注册表实例
_registry = None

def get_registry() -> AlgorithmRegistry:
    """获取全局注册表"""
    global _registry
    if _registry is None:
        _registry = AlgorithmRegistry()
    return _registry
