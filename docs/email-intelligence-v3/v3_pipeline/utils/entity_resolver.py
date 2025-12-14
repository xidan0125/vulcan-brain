#!/usr/bin/env python3
"""
Entity Resolver - V2 Knowledge Inheritance
架构决策：Option A+ (只读继承)

利用 V2 沉淀的 LLM 聚类结果，不回写 MongoDB
"""
import json
import os
from pathlib import Path
from typing import Tuple, Dict, Optional

# Import the ported normalizer
from .name_normalizer import NameNormalizer

_normalizer = NameNormalizer()


class EntityResolver:
    """
    实体解析器 - 三级解析策略
    
    1. V2 知识库查找 (LLM 聚类结果)
    2. 规则归一化 (Name Normalizer)
    3. 兜底返回归一化名称
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.mapping: Dict[str, str] = {}
        self.reverse_mapping: Dict[str, list] = {}  # canonical -> [aliases]
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "entity_aliases.json"
        
        self._load_config(config_path)
    
    def _load_config(self, path):
        """加载 V2 沉淀的知识库"""
        if not os.path.exists(path):
            print(f"⚠️ Warning: V2 entity dictionary not found at {path}")
            return
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理 V2 的结构: {"dictionary": {alias: canonical}, "clusters": [...]}
        if "dictionary" in data:
            raw_dict = data["dictionary"]
            for alias, canonical in raw_dict.items():
                # 归一化 alias 作为 key
                norm_alias = self._normalize(alias)
                self.mapping[norm_alias] = canonical
                
                # 构建反向映射
                if canonical not in self.reverse_mapping:
                    self.reverse_mapping[canonical] = []
                self.reverse_mapping[canonical].append(alias)
        
        print(f"📖 Loaded V2 knowledge: {len(self.mapping)} alias mappings, {len(self.reverse_mapping)} canonical entities")
    
    def _normalize(self, name: str) -> str:
        """使用 V2 的 NameNormalizer 进行基础归一化"""
        if not name:
            return ""
        result = _normalizer.normalize(name)
        return result.normalized.upper()
    
    def resolve(self, raw_name: str) -> Tuple[str, str]:
        """
        解析实体名称
        
        Returns:
            (resolved_name, match_type)
            match_type: "V2_MATCH" | "NORMALIZED" | "EMPTY"
        """
        if not raw_name or not raw_name.strip():
            return "", "EMPTY"
        
        # Step 1: 基础归一化
        norm_name = self._normalize(raw_name)
        
        # Step 2: 查 V2 知识库
        if norm_name in self.mapping:
            canonical = self.mapping[norm_name]
            return canonical, "V2_MATCH"
        
        # Step 3: 直接用归一化后的名称
        if norm_name in self.reverse_mapping:
            # 本身就是 canonical
            return raw_name, "CANONICAL"
        
        return norm_name, "NORMALIZED"
    
    def get_aliases(self, canonical: str) -> list:
        """获取某个 canonical 的所有别名"""
        return self.reverse_mapping.get(canonical, [])
    
    def stats(self) -> dict:
        """返回统计信息"""
        return {
            "total_mappings": len(self.mapping),
            "total_canonicals": len(self.reverse_mapping),
            "top_canonicals": sorted(
                [(k, len(v)) for k, v in self.reverse_mapping.items()],
                key=lambda x: -x[1]
            )[:10]
        }


# Singleton instance
_resolver: Optional[EntityResolver] = None

def get_resolver() -> EntityResolver:
    """获取全局 EntityResolver 实例"""
    global _resolver
    if _resolver is None:
        _resolver = EntityResolver()
    return _resolver


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 Entity Resolver Test")
    print("=" * 60)
    
    resolver = EntityResolver()
    
    test_names = [
        "Space X",
        "SpaceX",
        "Microsoft",
        "Microsoft Corporation",
        "DHL Express Singapore Pte",
        "DHL EXPRESS (SINGAPORE) PTE",
        "Unknown Company XYZ",
    ]
    
    print("\n📊 Resolution Results:")
    for name in test_names:
        resolved, match_type = resolver.resolve(name)
        print(f"  {name:35} -> {resolved:30} [{match_type}]")
    
    print("\n📈 Stats:")
    stats = resolver.stats()
    print(f"  Total mappings: {stats['total_mappings']}")
    print(f"  Total canonicals: {stats['total_canonicals']}")
