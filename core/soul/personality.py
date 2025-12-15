"""
Personality - 人格层

管理用户的个性化人格档案（六维度模型）
数据来源于 Soul 校准问卷
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field, asdict


@dataclass
class PersonalityDimension:
    """人格维度"""
    name: str
    value: float  # -1.0 到 1.0
    description: str
    positive_pole: str  # 正极描述
    negative_pole: str  # 负极描述
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


# 六维度定义
DIMENSION_DEFINITIONS = {
    "risk_appetite": {
        "description": "风险阈值",
        "positive_pole": "激进",
        "negative_pole": "保守"
    },
    "time_horizon": {
        "description": "时间视界",
        "positive_pole": "长期主义",
        "negative_pole": "短期收益"
    },
    "strategic_drive": {
        "description": "战略驱动",
        "positive_pole": "深度谋划",
        "negative_pole": "直觉行动"
    },
    "people_philosophy": {
        "description": "人际哲学",
        "positive_pole": "协作共生",
        "negative_pole": "独狼领袖"
    },
    "control_style": {
        "description": "控制风格",
        "positive_pole": "秩序建立",
        "negative_pole": "混沌适应"
    },
    "ethical_boundary": {
        "description": "伦理边界",
        "positive_pole": "原则坚守",
        "negative_pole": "灰度决策"
    }
}


class Personality:
    """
    用户人格档案管理器
    
    - 存储用户的六维度人格数据
    - 支持增量更新（从校准问卷）
    - 持久化到本地 JSON
    """
    
    STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "personalities"
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.dimensions: Dict[str, PersonalityDimension] = {}
        self._load_or_create()
    
    def _get_storage_path(self) -> Path:
        """获取用户人格存储路径"""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        return self.STORAGE_DIR / f"{self.user_id}.json"
    
    def _load_or_create(self):
        """加载现有档案或创建默认档案"""
        path = self._get_storage_path()
        
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for dim_name, dim_data in data.get('dimensions', {}).items():
                    self.dimensions[dim_name] = PersonalityDimension(**dim_data)
        else:
            # 创建默认人格（所有维度为中性 0.0）
            self._create_default()
    
    def _create_default(self):
        """创建默认人格档案"""
        for dim_name, definition in DIMENSION_DEFINITIONS.items():
            self.dimensions[dim_name] = PersonalityDimension(
                name=dim_name,
                value=0.0,
                description=definition['description'],
                positive_pole=definition['positive_pole'],
                negative_pole=definition['negative_pole']
            )
        self.save()
    
    def save(self):
        """保存人格档案"""
        data = {
            "user_id": self.user_id,
            "updated_at": datetime.now().isoformat(),
            "dimensions": {
                name: asdict(dim) for name, dim in self.dimensions.items()
            }
        }
        with open(self._get_storage_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ==================== 维度操作 ====================
    
    def get_dimension(self, name: str) -> Optional[PersonalityDimension]:
        """获取特定维度"""
        return self.dimensions.get(name)
    
    def update_dimension(self, name: str, value: float):
        """
        更新维度值
        
        Args:
            name: 维度名称
            value: 新值 (-1.0 到 1.0)
        """
        if name not in self.dimensions:
            raise ValueError(f"Unknown dimension: {name}")
        
        # 限制范围
        value = max(-1.0, min(1.0, value))
        
        self.dimensions[name].value = value
        self.dimensions[name].last_updated = datetime.now().isoformat()
        self.save()
    
    def apply_weights(self, weights: Dict[str, float]):
        """
        批量应用权重（来自校准问卷选项）
        
        Args:
            weights: {risk_appetite: 0.2, time_horizon: -0.1, ...}
        """
        for dim_name, delta in weights.items():
            if dim_name in self.dimensions:
                current = self.dimensions[dim_name].value
                new_value = max(-1.0, min(1.0, current + delta))
                self.dimensions[dim_name].value = new_value
                self.dimensions[dim_name].last_updated = datetime.now().isoformat()
        self.save()
    
    # ==================== 档案查询 ====================
    
    def get_profile_summary(self) -> Dict:
        """获取人格档案摘要"""
        return {
            "user_id": self.user_id,
            "dimensions": {
                name: {
                    "value": dim.value,
                    "description": dim.description,
                    "tendency": self._get_tendency(dim)
                }
                for name, dim in self.dimensions.items()
            }
        }
    
    def _get_tendency(self, dim: PersonalityDimension) -> str:
        """根据值获取倾向描述"""
        if dim.value > 0.3:
            return dim.positive_pole
        elif dim.value < -0.3:
            return dim.negative_pole
        else:
            return "中性"
    
    def get_dominant_traits(self, threshold: float = 0.3) -> List[Dict]:
        """获取主导特质（偏离中性超过阈值的维度）"""
        traits = []
        for name, dim in self.dimensions.items():
            if abs(dim.value) > threshold:
                traits.append({
                    "dimension": name,
                    "value": dim.value,
                    "trait": dim.positive_pole if dim.value > 0 else dim.negative_pole
                })
        return sorted(traits, key=lambda x: abs(x['value']), reverse=True)
    
    # ==================== Prompt 生成 ====================
    
    def to_prompt_section(self) -> str:
        """
        将人格转换为 Prompt 片段
        用于注入到 System Prompt 中
        """
        dominant = self.get_dominant_traits()
        
        if not dominant:
            return "用户人格档案：暂未校准，使用默认中性人格。"
        
        lines = ["## 用户人格特征\n"]
        for trait in dominant:
            direction = "偏向" if abs(trait['value']) < 0.7 else "强烈"
            lines.append(f"- {DIMENSION_DEFINITIONS[trait['dimension']]['description']}: {direction} {trait['trait']}")
        
        return "\n".join(lines)
    
    def get_response_style_hints(self) -> List[str]:
        """根据人格生成回复风格提示"""
        hints = []
        
        # 风险偏好
        risk = self.dimensions.get('risk_appetite')
        if risk and risk.value > 0.3:
            hints.append("用户倾向激进决策，可以提供大胆建议")
        elif risk and risk.value < -0.3:
            hints.append("用户偏保守，建议强调风险和备选方案")
        
        # 时间视界
        time_h = self.dimensions.get('time_horizon')
        if time_h and time_h.value > 0.3:
            hints.append("用户注重长期价值，可以讨论长远规划")
        elif time_h and time_h.value < -0.3:
            hints.append("用户关注短期收益，强调即时成果")
        
        # 控制风格
        control = self.dimensions.get('control_style')
        if control and control.value > 0.3:
            hints.append("用户喜欢结构化方案，提供清晰步骤")
        elif control and control.value < -0.3:
            hints.append("用户适应不确定性，可以探索多种可能")
        
        return hints
