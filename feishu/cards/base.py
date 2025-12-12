"""
飞书卡片基类
提供统一的卡片构建接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseCard(ABC):
    """
    飞书卡片基类

    所有卡片继承此类，实现 build_content() 和 build_actions() 方法
    """

    def __init__(
        self,
        title: str,
        color: str = "blue",
        icon: str = ""
    ):
        """
        初始化卡片

        Args:
            title: 卡片标题
            color: 标题栏颜色 (blue/green/orange/red/purple/grey)
            icon: 标题前的图标 emoji
        """
        self.title = f"{icon} {title}" if icon else title
        self.color = color

    @abstractmethod
    def build_content(self) -> List[Dict[str, Any]]:
        """
        构建卡片内容区域

        Returns:
            飞书卡片元素列表
        """
        pass

    def build_actions(self) -> List[Dict[str, Any]]:
        """
        构建操作按钮区域 (可选)

        Returns:
            按钮元素列表，默认为空
        """
        return []

    def build_footer(self) -> Optional[Dict[str, Any]]:
        """
        构建底部区域 (可选)

        Returns:
            底部元素，默认为 None
        """
        return None

    def build(self) -> Dict[str, Any]:
        """
        构建完整的飞书卡片

        Returns:
            飞书卡片 JSON 结构
        """
        elements = self.build_content()

        actions = self.build_actions()
        if actions:
            elements.append({"tag": "hr"})
            elements.append({"tag": "action", "actions": actions})

        footer = self.build_footer()
        if footer:
            elements.append(footer)

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": self.title},
                "template": self.color,
            },
            "elements": elements,
        }


# ==================== 辅助函数 ====================

def markdown_text(content: str) -> Dict[str, Any]:
    """创建 Markdown 文本元素"""
    return {
        "tag": "div",
        "text": {"tag": "lark_md", "content": content}
    }


def plain_text(content: str) -> Dict[str, Any]:
    """创建纯文本元素"""
    return {
        "tag": "div",
        "text": {"tag": "plain_text", "content": content}
    }


def button(
    text: str,
    action: str,
    value: Dict[str, Any] = None,
    button_type: str = "default",
    url: str = None
) -> Dict[str, Any]:
    """
    创建按钮元素

    Args:
        text: 按钮文字
        action: 动作类型 (用于回调识别)
        value: 回调时携带的数据
        button_type: 按钮样式 (default/primary/danger)
        url: 跳转链接 (可选)

    Returns:
        按钮元素
    """
    btn = {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": button_type,
    }

    if url:
        btn["url"] = url
    else:
        btn["value"] = {"action": action, **(value or {})}

    return btn


def button_primary(text: str, action: str, value: Dict = None) -> Dict:
    """主要按钮 (蓝色)"""
    return button(text, action, value, "primary")


def button_danger(text: str, action: str, value: Dict = None) -> Dict:
    """危险按钮 (红色)"""
    return button(text, action, value, "danger")


def button_link(text: str, url: str) -> Dict:
    """链接按钮"""
    return button(text, "", url=url)


def select_static(
    placeholder: str,
    options: List[Dict[str, str]],
    name: str
) -> Dict[str, Any]:
    """
    创建下拉选择框

    Args:
        placeholder: 占位文字
        options: 选项列表 [{"text": "显示文字", "value": "值"}, ...]
        name: 表单字段名

    Returns:
        下拉选择框元素
    """
    return {
        "tag": "select_static",
        "placeholder": {"tag": "plain_text", "content": placeholder},
        "options": [
            {"text": {"tag": "plain_text", "content": opt["text"]}, "value": opt["value"]}
            for opt in options
        ],
        "value": {"key": name}
    }


def input_field(name: str, placeholder: str, default: str = "") -> Dict[str, Any]:
    """
    创建输入框

    Args:
        name: 表单字段名
        placeholder: 占位文字
        default: 默认值

    Returns:
        输入框元素
    """
    field = {
        "tag": "input",
        "name": name,
        "placeholder": {"tag": "plain_text", "content": placeholder},
    }
    if default:
        field["default_value"] = default
    return field


def divider() -> Dict[str, Any]:
    """水平分割线"""
    return {"tag": "hr"}


def note(text: str) -> Dict[str, Any]:
    """备注文字 (灰色小字)"""
    return {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": text}]
    }
