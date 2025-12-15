"""
Constitution - 宪法层

加载和管理 boss_constitution.yaml 中定义的核心价值观、行为准则和红线
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional


class Constitution:
    """
    宪法管理器
    
    负责：
    - 加载静态宪法配置
    - 提供价值观查询接口
    - 验证行为是否违规
    """
    
    # 默认宪法路径
    DEFAULT_PATH = Path(__file__).parent / "prompts" / "boss_constitution.yaml"
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_PATH
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载宪法配置文件"""
        if not self.config_path.exists():
            # 回退到项目根目录的配置
            fallback_path = Path(__file__).parent.parent.parent / "boss_constitution.yaml"
            if fallback_path.exists():
                self.config_path = fallback_path
            else:
                raise FileNotFoundError(f"Constitution not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def reload(self):
        """热重载配置"""
        self._config = self._load_config()
    
    # ==================== 价值观查询 ====================
    
    def get_core_values(self) -> List[Dict]:
        """获取核心价值观列表"""
        return self._config.get('core_values', [])
    
    def get_value_by_name(self, name: str) -> Optional[Dict]:
        """按名称获取特定价值观"""
        for value in self.get_core_values():
            if name.lower() in value.get('name', '').lower():
                return value
        return None
    
    def get_principles(self, value_name: str) -> List[str]:
        """获取特定价值观的原则列表"""
        value = self.get_value_by_name(value_name)
        return value.get('principles', []) if value else []
    
    # ==================== 行为准则 ====================
    
    def get_behavioral_guidelines(self) -> List[Dict]:
        """获取行为准则"""
        return self._config.get('behavioral_guidelines', [])
    
    def get_rules_by_category(self, category: str) -> List[str]:
        """按类别获取规则"""
        for guideline in self.get_behavioral_guidelines():
            if category.lower() in guideline.get('category', '').lower():
                return guideline.get('rules', [])
        return []
    
    # ==================== 红线/禁止行为 ====================
    
    def get_prohibited_actions(self) -> List[str]:
        """获取禁止行为列表（红线）"""
        return self._config.get('prohibited_actions', [])
    
    def is_prohibited(self, action_description: str) -> bool:
        """
        检查行为是否被禁止
        
        简单实现：关键词匹配
        高级实现：可以用 LLM 做语义匹配
        """
        action_lower = action_description.lower()
        prohibited = self.get_prohibited_actions()
        
        # 关键词列表
        red_flags = [
            '简化版', '临时方案', '隐藏错误', '掩盖', '确定性答案',
            '敏感信息', 'rm -rf', '编造', '虚构', '臆造'
        ]
        
        for flag in red_flags:
            if flag in action_lower:
                return True
        
        return False
    
    # ==================== 搜索规范 ====================
    
    def get_search_guidelines(self) -> Dict:
        """获取搜索工具使用规范"""
        return self._config.get('search_guidelines', {})
    
    # ==================== 对话风格 ====================
    
    def get_communication_style(self) -> Dict:
        """获取对话风格配置"""
        return self._config.get('communication_style', {})
    
    def get_tone(self) -> str:
        """获取语气风格"""
        return self.get_communication_style().get('tone', '专业、简洁、友好')
    
    # ==================== 自我改进 ====================
    
    def get_reflection_triggers(self) -> List[str]:
        """获取触发反思的场景"""
        improvement = self._config.get('self_improvement', {})
        return improvement.get('reflection_triggers', [])
    
    def get_learning_protocol(self) -> List[str]:
        """获取学习协议"""
        improvement = self._config.get('self_improvement', {})
        return improvement.get('learning_protocol', [])
    
    # ==================== 格式化输出 ====================
    
    def to_system_prompt_section(self) -> str:
        """
        将宪法转换为 System Prompt 片段
        用于注入到 LLM 的系统提示中
        """
        lines = []
        lines.append("## 核心价值观 (Core Values)\n")
        
        for value in self.get_core_values():
            lines.append(f"### {value['name']}")
            lines.append(f"{value.get('description', '')}\n")
            for principle in value.get('principles', []):
                lines.append(f"- {principle}")
            lines.append("")
        
        lines.append("## 禁止行为 (Red Lines)\n")
        for action in self.get_prohibited_actions():
            lines.append(f"❌ {action}")
        
        lines.append("\n## 对话风格\n")
        style = self.get_communication_style()
        lines.append(f"语气: {style.get('tone', '')}")
        lines.append(f"Emoji: {style.get('emoji_usage', '')}")
        
        return "\n".join(lines)
    
    # ==================== 元信息 ====================
    
    @property
    def version(self) -> str:
        return self._config.get('version', '0.0.0')
    
    @property
    def last_updated(self) -> str:
        return self._config.get('last_updated', 'unknown')
