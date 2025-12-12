# vulcan_libs/bicameral_types.py
"""
Vulcan Brain V6.1 - SingleBrain 架构类型定义

核心变化：
1. 双通道输出: <thinking> 推理区 + <action_json> 决策区
2. CEO 推理能力释放，不再被 JSON 格式压制
3. Synth 支持多维分析框架
"""

import re
import json
from typing import Literal, List, Optional, Annotated, Tuple
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# ============ V6.1 双通道解析器 ============

class DualChannelParser:
    """
    双通道输出解析器
    
    解析格式:
    <thinking>
    ...深度推理...
    </thinking>
    
    <action_json>
    {...决策JSON...}
    </action_json>
    """
    
    THINKING_PATTERN = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)
    ACTION_JSON_PATTERN = re.compile(r'<action_json>(.*?)</action_json>', re.DOTALL)
    LEGACY_JSON_PATTERN = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
    
    @classmethod
    def parse(cls, raw_output: str) -> Tuple[Optional[str], Optional[dict]]:
        """解析双通道输出"""
        thinking = None
        action_dict = None
        
        # 1. 提取 thinking 区域
        thinking_match = cls.THINKING_PATTERN.search(raw_output)
        if thinking_match:
            thinking = thinking_match.group(1).strip()
        
        # 2. 提取 action_json 区域
        action_match = cls.ACTION_JSON_PATTERN.search(raw_output)
        if action_match:
            json_str = action_match.group(1).strip()
            try:
                action_dict = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"[Parser] action_json parse failed: {e}")
                action_dict = None
        
        # 3. 降级：尝试旧格式
        if action_dict is None:
            legacy_match = cls.LEGACY_JSON_PATTERN.search(raw_output)
            if legacy_match:
                try:
                    action_dict = json.loads(legacy_match.group(1).strip())
                except:
                    pass
            
            if action_dict is None:
                try:
                    clean = raw_output.strip()
                    if clean.startswith('{'):
                        action_dict = json.loads(clean)
                except:
                    pass
        
        return thinking, action_dict
    
    @classmethod
    def extract_final_content(cls, raw_output: str) -> str:
        """提取最终展示给用户的内容，剥离 thinking 区域"""
        content = cls.THINKING_PATTERN.sub('', raw_output)
        content = cls.ACTION_JSON_PATTERN.sub('', content)
        return content.strip()


# ============ CEO Action (V6.1) ============

class DelegationSpec(BaseModel):
    """委派任务规范"""
    objective: str = Field(..., description="核心目标")
    context: str = Field(default="", description="背景/上下文")
    constraints: List[str] = Field(default_factory=list, description="约束条件")
    expected_output: str = Field(default="执行结果", description="期望输出")
    task_type: Optional[Literal["search", "compute", "analysis", "mixed"]] = None
    priority: Optional[Literal["low", "normal", "high"]] = "normal"


class CEOAction(BaseModel):
    """CEO 决策输出 - V6.1 增强版"""
    action: Literal["direct_answer", "need_code"]
    
    # direct_answer 时使用
    content: Optional[str] = Field(default=None, description="直接回答内容")
    
    # need_code 时使用
    task: Optional[str] = Field(default=None, description="任务描述")
    task_type: Optional[Literal["search", "compute", "analysis", "mixed"]] = None
    constraints: List[str] = Field(default_factory=list, description="约束条件")
    expected_output: Optional[str] = None
    
    # 兼容旧字段
    answer: Optional[str] = None
    delegation: Optional[DelegationSpec] = None
    reasoning: Optional[str] = None
    
    def normalize(self) -> 'CEOAction':
        """标准化处理 - 兼容新旧格式"""
        if self.answer and not self.content:
            self.content = self.answer
        
        if self.delegation and not self.task:
            self.task = self.delegation.objective
            self.constraints = self.delegation.constraints
            self.expected_output = self.delegation.expected_output
            self.task_type = self.delegation.task_type
        
        return self


# ============ CTO Task & Result ============

class CTOTask(BaseModel):
    """CTO 任务输入"""
    task_id: str = ""
    objective: str
    context: str = ""
    constraints: List[str] = Field(default_factory=list)
    expected_output: str = "执行结果"
    task_type: Optional[str] = None
    
    def to_prompt(self) -> str:
        constraints_str = '\n'.join(f"- {c}" for c in self.constraints) if self.constraints else "无特殊约束"
        return f"""## 任务工单 [{self.task_id}]

**目标**: {self.objective}

**背景**: {self.context}

**约束条件**:
{constraints_str}

**期望输出**: {self.expected_output}
"""


class CTOResult(BaseModel):
    """CTO 执行结果"""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    code: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    execution_time_ms: Optional[float] = None


# ============ Synth Result (V6.1 多维分析) ============

class AnalysisDimension(BaseModel):
    """单维度分析"""
    dimension: str
    findings: List[str] = Field(default_factory=list)
    assessment: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0, le=10)


class SynthResult(BaseModel):
    """综合分析结果 - V6.1 多维框架"""
    core_facts: List[str] = Field(default_factory=list)
    analysis: str = ""
    conclusion: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    
    dimensions: List[AnalysisDimension] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)
    
    def to_answer(self) -> str:
        parts = []
        
        if self.conclusion:
            parts.append(f"**结论**: {self.conclusion}")
        
        if self.key_insights:
            insights = '\n'.join(f"- {i}" for i in self.key_insights)
            parts.append(f"\n**关键洞察**:\n{insights}")
        
        if self.core_facts:
            facts = '\n'.join(f"- {f}" for f in self.core_facts)
            parts.append(f"\n**关键数据**:\n{facts}")
        
        if self.dimensions:
            dims_text = []
            for d in self.dimensions:
                score_str = f" ({d.score}/10)" if d.score else ""
                dims_text.append(f"**{d.dimension}**{score_str}: {d.assessment or ''}")
            parts.append(f"\n**多维评估**:\n" + '\n'.join(dims_text))
        
        if self.analysis:
            parts.append(f"\n**分析**: {self.analysis}")
        
        if self.risks:
            risks_str = '\n'.join(f"⚠️ {r}" for r in self.risks)
            parts.append(f"\n**风险提示**:\n{risks_str}")
        
        if self.recommendations:
            recs = '\n'.join(f"→ {r}" for r in self.recommendations)
            parts.append(f"\n**建议**:\n{recs}")
        
        return '\n'.join(parts)
    
    def to_compact_answer(self) -> str:
        parts = [self.conclusion]
        if self.key_insights:
            parts.append('\n'.join(f"• {i}" for i in self.key_insights[:3]))
        return '\n\n'.join(parts)


# ============ Graph State (V6.1) ============

class GraphState(TypedDict, total=False):
    """LangGraph 状态 - V6.1"""
    run_id: str
    user_input: str
    messages: Annotated[List[BaseMessage], add_messages]
    agent_type: str  # Agent 类型 (financial, hr, ghostwriter, watchdog)

    thinking: str
    brain_action: dict
    ceo_action: dict

    cto_task: dict
    cto_result: dict
    synth_result: dict

    final_answer: str

    thread_id: str
    created_at: str
    retry_count: int
    last_error: str
    complexity_score: float


# ============ 辅助函数 ============

def parse_brain_output(raw_output: str) -> Tuple[Optional[str], CEOAction]:
    """解析 SingleBrain 输出"""
    thinking, action_dict = DualChannelParser.parse(raw_output)
    
    if action_dict is None:
        clean_content = DualChannelParser.extract_final_content(raw_output)
        return thinking, CEOAction(
            action="direct_answer",
            content=clean_content or raw_output
        )
    
    try:
        action = CEOAction.model_validate(action_dict).normalize()
        return thinking, action
    except Exception as e:
        print(f"[Parser] CEOAction validation failed: {e}")
        return thinking, CEOAction(
            action="direct_answer",
            content=action_dict.get('content') or action_dict.get('answer') or str(action_dict)
        )


def parse_ceo_action(json_str: str) -> CEOAction:
    """兼容旧接口"""
    _, action = parse_brain_output(json_str)
    return action


def parse_synth_result(json_str: str) -> SynthResult:
    """解析 Synth JSON 输出"""
    try:
        return SynthResult.model_validate_json(json_str)
    except:
        try:
            data = json.loads(json_str)
            return SynthResult.model_validate(data)
        except:
            return SynthResult(conclusion=json_str)
