"""
Vulcan Nexus - Intent Router
快速意图分类: 规则优先 + LLM Fallback
"""

import re
import httpx
from dataclasses import dataclass
from typing import Optional, Tuple, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """意图类型"""
    CHAT = "chat"              # 纯对话 → CPU, 无工具
    FEISHU = "feishu"          # 飞书操作 → CPU, 飞书工具
    DATA = "data"              # 数据查询 → GPU, 数据工具
    FINANCE = "finance"        # 财务相关 → GPU, 财务工具
    CODE = "code"              # 代码相关 → GPU, 代码工具
    WEB_SEARCH = "web_search"  # 联网搜索 → GPU + web_search工具


class ModelTier(str, Enum):
    """模型层级"""
    CPU = "cpu"     # llama-server 8002
    GPU = "gpu"     # vLLM 8000
    GEMINI = "gemini"


@dataclass
class RoutingDecision:
    """路由决策"""
    intent: Intent
    model_tier: ModelTier
    confidence: float  # 0-1
    reasoning: str     # 决策原因 (调试用)
    use_tools: bool = True
    agent_id: str = ""
    
    def __post_init__(self):
        """设置默认 agent_id"""
        if not self.agent_id:
            self.agent_id = f"{self.intent.value}_agent"


class IntentRouter:
    """
    快速意图路由器
    
    策略:
    1. 规则匹配 (0ms) - 关键词检测
    2. LLM 分类 (~300ms) - CPU 模型
    
    防止 Sticky Tool:
    - 当 intent=CHAT 时，use_tools=False
    """
    
    # === 规则配置 ===
    
    # 飞书关键词
    FEISHU_KEYWORDS = [
        "发飞书", "飞书消息", "发消息", "发给", "告诉", "通知",
        "群消息", "私聊", "@", "飞书群", "机器人消息",
        "日历", "日程", "会议", "审批"
    ]
    
    # 数据关键词
    DATA_KEYWORDS = [
        "数据", "统计", "报表", "查询数据", "SQL",
        "分析数据", "趋势", "图表", "指标", "KPI"
    ]
    
    # 财务关键词
    FINANCE_KEYWORDS = [
        "财务", "支出", "收入", "报销", "预算",
        "成本", "利润", "账单", "发票", "财报"
    ]
    
    # 代码关键词
    CODE_KEYWORDS = [
        "代码", "编程", "函数", "类", "API",
        "bug", "调试", "运行", "执行", "脚本"
    ]
    
    # 搜索关键词
    SEARCH_KEYWORDS = [
        "搜索", "查一下", "最新", "新闻", "今天",
        "实时", "联网", "网上"
    ]
    
    # 纯聊天关键词 (高优先级，直接返回 CHAT)
    CHAT_KEYWORDS = [
        "你好", "谢谢", "好的", "行", "嗯",
        "聊聊", "你觉得", "你认为", "怎么看"
    ]
    
    # LLM 分类 Prompt
    ROUTER_PROMPT = """任务: 分类用户意图。只输出类别名，不要解释。

类别:
- chat: 闲聊、问答、讨论、意见咨询
- feishu: 发送飞书消息、通知团队、日历日程
- data: 数据查询、统计分析、报表
- finance: 财务相关、报销、预算
- code: 代码编程、调试运行
- web_search: 需要联网搜索最新信息

用户输入: {input}
类别:"""

    def __init__(
        self,
        cpu_base_url: str = "http://localhost:8002",
        cpu_model: str = "qwen3-8b",
        enable_llm_fallback: bool = True
    ):
        self.cpu_base_url = cpu_base_url
        self.cpu_model = cpu_model
        self.enable_llm_fallback = enable_llm_fallback
    
    async def route(self, user_input: str, context: str = "") -> RoutingDecision:
        """
        路由决策
        
        Args:
            user_input: 用户输入
            context: 上下文 (可选)
            
        Returns:
            RoutingDecision
        """
        # Step 1: 规则匹配 (最快)
        rule_result = self._rule_match(user_input)
        if rule_result:
            return rule_result
        
        # Step 2: LLM 分类 (fallback)
        if self.enable_llm_fallback:
            try:
                return await self._llm_classify(user_input)
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")
        
        # Step 3: 默认 CHAT
        return RoutingDecision(
            intent=Intent.CHAT,
            model_tier=ModelTier.CPU,
            confidence=0.5,
            reasoning="default_fallback",
            use_tools=False
        )
    
    def _rule_match(self, text: str) -> Optional[RoutingDecision]:
        """规则匹配"""
        
        # 纯聊天检测 (高优先级)
        for kw in self.CHAT_KEYWORDS:
            if text.startswith(kw) or text == kw:
                return RoutingDecision(
                    intent=Intent.CHAT,
                    model_tier=ModelTier.CPU,
                    confidence=0.95,
                    reasoning=f"chat_keyword:{kw}",
                    use_tools=False
                )
        
        # 飞书检测
        for kw in self.FEISHU_KEYWORDS:
            if kw in text:
                return RoutingDecision(
                    intent=Intent.FEISHU,
                    model_tier=ModelTier.CPU,  # 飞书用 CPU，快
                    confidence=0.9,
                    reasoning=f"feishu_keyword:{kw}",
                    use_tools=True
                )
        
        # 数据检测
        for kw in self.DATA_KEYWORDS:
            if kw in text:
                return RoutingDecision(
                    intent=Intent.DATA,
                    model_tier=ModelTier.GPU,  # 数据分析用 GPU
                    confidence=0.85,
                    reasoning=f"data_keyword:{kw}",
                    use_tools=True
                )
        
        # 财务检测
        for kw in self.FINANCE_KEYWORDS:
            if kw in text:
                return RoutingDecision(
                    intent=Intent.FINANCE,
                    model_tier=ModelTier.GPU,
                    confidence=0.85,
                    reasoning=f"finance_keyword:{kw}",
                    use_tools=True
                )
        
        # 代码检测
        for kw in self.CODE_KEYWORDS:
            if kw in text:
                return RoutingDecision(
                    intent=Intent.CODE,
                    model_tier=ModelTier.GPU,
                    confidence=0.85,
                    reasoning=f"code_keyword:{kw}",
                    use_tools=True
                )
        
        # 搜索检测
        for kw in self.SEARCH_KEYWORDS:
            if kw in text:
                return RoutingDecision(
                    intent=Intent.DATA,
                    model_tier=ModelTier.CPU,
                    confidence=0.85,
                    reasoning=f"data_keyword:{kw}",
                    use_tools=True  # GPU + web_search 工具
                )
        
        return None
    
    async def _llm_classify(self, user_input: str) -> RoutingDecision:
        """使用 CPU LLM 分类"""
        
        prompt = self.ROUTER_PROMPT.format(input=user_input[:200])
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.cpu_base_url}/v1/completions",
                json={
                    "model": self.cpu_model,
                    "prompt": prompt,
                    "max_tokens": 10,
                    "temperature": 0.1,
                    "stop": ["\n", "。", ","]
                }
            )
            
            data = response.json()
            category = data["choices"][0]["text"].strip().lower()
        
        # 映射到 Intent
        mapping = {
            "chat": (Intent.CHAT, ModelTier.CPU, False),
            "feishu": (Intent.FEISHU, ModelTier.CPU, True),
            "data": (Intent.DATA, ModelTier.GPU, True),
            "finance": (Intent.FINANCE, ModelTier.GPU, True),
            "code": (Intent.CODE, ModelTier.GPU, True),
            "web_search": (Intent.DATA, ModelTier.CPU, True),
        }
        
        if category in mapping:
            intent, tier, use_tools = mapping[category]
            return RoutingDecision(
                intent=intent,
                model_tier=tier,
                confidence=0.8,
                reasoning=f"llm_classify:{category}",
                use_tools=use_tools
            )
        
        # 默认 CHAT
        return RoutingDecision(
            intent=Intent.CHAT,
            model_tier=ModelTier.CPU,
            confidence=0.5,
            reasoning=f"llm_unknown:{category}",
            use_tools=False
        )


# === 工具作用域管理 ===

def get_tools_for_intent(intent: Intent) -> List[str]:
    """
    根据意图返回可用工具列表
    
    关键: 物理隔离，防止 Sticky Tool
    注意: CHAT 意图包含记忆工具，让 AI 可以记住用户信息
    """
    tools_by_intent = {
        Intent.CHAT: [],  # 纯聊天不给工具，记忆由后端自动提取
        
        Intent.FEISHU: [
            "feishu_send_message",
            "feishu_search_user",
            "feishu_create_chat",
            "feishu_get_chat_history",
            "feishu_list_chats",
            "feishu_add_chat_members",
            "feishu_list_chat_members",
            "feishu_list_departments",
            "feishu_create_calendar_event",
            "feishu_list_calendar_events",
            "feishu_create_task",
            "feishu_list_tasks",
            "feishu_complete_task",
            "feishu_list_approval_definitions",
            "feishu_list_approvals",
            "feishu_get_approval_detail",
            "feishu_approve",
            "feishu_reject",
            "remember",
            "recall",
        ],
        
        Intent.DATA: [
            "recall",
            "remember",
        ],
        
        Intent.FINANCE: [
            "recall",
        ],
        
        Intent.CODE: [
        ],
        
        Intent.WEB_SEARCH: [
            "web_search",
        ],
    }
    
    return tools_by_intent.get(intent, [])


# === 测试 ===

async def test_router():
    """测试路由器"""
    router = IntentRouter()
    
    test_cases = [
        "你好",
        "发消息给 xinyue",
        "查一下昨天的销售数据",
        "帮我看下这段代码有什么问题",
        "最近有什么科技新闻",
        "今天的预算执行情况怎么样",
    ]
    
    for case in test_cases:
        decision = await router.route(case)
        print(f"Input: {case}")
        print(f"  → Intent: {decision.intent.value}, Model: {decision.model_tier.value}")
        print(f"  → Tools: {decision.use_tools}, Reason: {decision.reasoning}")
        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_router())
