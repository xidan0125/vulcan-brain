# bicameral_graph.py - V6.1 SingleBrain Architecture
"""
Vulcan Brain V6.1 - SingleBrain 架构

核心改进：
1. 双通道输出: <thinking> 深度推理 + <action_json> 结构化决策
2. CEO 推理能力释放，不再被 JSON 格式压制
3. Synth 支持多维分析框架

状态图：
User → decision_node → router → direct_answer → END
                            └→ need_code → cto_node → synth_node → END
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import HumanMessage, AIMessage

import httpx

# V6.1 类型定义
from vulcan_libs.bicameral_types import (
    GraphState, CEOAction, CTOTask, CTOResult, SynthResult,
    AnalysisDimension, DualChannelParser, parse_brain_output, parse_synth_result
)

# 工具
from vulcan_libs.ceo_soul import get_ceo_soul
from vulcan_libs.cto_executor import get_cto_executor, TaskSpec, ExecutionResult

# Agent 专业提示词
from agent_prompts import get_agent_prompt, AGENT_PROMPTS

# ============ 配置 ============

POSTGRES_URI = "postgresql://admin:vulcan%402025@localhost:5432/vulcan_brain"

THINKING_MODEL = {
    "base_url": "http://localhost:11434",
    "model": "qwen3:30b-a3b",
    "timeout": 120.0
}

logger = logging.getLogger("bicameral_v61")


# ============ V6.1 双通道格式说明 ============

DUAL_CHANNEL_FORMAT = """
---

## ① 内部推理（不向用户展示）

用以下格式输出内部推理：

<thinking>
在这里进行详细推理，包括但不限于：
- 背景理解与问题拆解
- 多维度比较与分析框架
- 因果链与逻辑推演
- 数据对照与关键指标
- 商业逻辑与战略判断
- 风险识别与不确定性
- 决策理由与权衡
</thinking>

⚠️ 注意：
- thinking 区域内容不会被用户看到
- 在 action_json 部分 **不要** 重复推理内容
- 思考尽可能详细、有层次、有洞察

---

## ② 决策 JSON（必须严格符合格式）

<action_json>
{
  "action": "direct_answer" 或 "need_code",
  "content": "直接回答内容（action=direct_answer时必填）",
  "task": "任务描述（action=need_code时必填）",
  "task_type": "search" | "compute" | "analysis" | "mixed",
  "constraints": ["约束1", "约束2"],
  "expected_output": "期望输出格式",
  "reasoning": "简短决策理由（可选）"
}
</action_json>

---

## 决策规则

### 选择 "direct_answer" 当：
- 简单问答、闲聊、常识问题
- 基于你已有知识可以回答的问题
- 不需要最新数据或实时信息
- 时间日期问题（使用环境感知信息）

### 选择 "need_code" 当：
- 需要搜索最新信息（财报、新闻、价格）
- 需要数学计算或数据分析
- 需要调用外部工具
- 需要处理用户上传的数据

---

## 重要原则

1. **深度思考优先**：在 <thinking> 区域充分展开推理，不要压缩思维链
2. **结构化洞察**：分析问题时使用多维框架（财务/战略/技术/市场/风险）
3. **观点鲜明**：给出明确的判断和结论，不要模棱两可
4. **数据支撑**：引用具体数据和事实支撑论点
5. **格式严格**：JSON 必须合法，不能有多余字符
"""


def build_system_prompt(agent_type: str = None) -> str:
    """
    构建系统提示词 = Agent专业提示词 + V6.1双通道格式

    Args:
        agent_type: 可选的 Agent 类型 (financial, hr, ghostwriter, watchdog)

    Returns:
        组合后的系统提示词
    """
    # 获取 Agent 专业提示词
    if agent_type and agent_type in AGENT_PROMPTS:
        agent_prompt = get_agent_prompt(agent_type)
        base_prompt = f"""{agent_prompt}

---

## V6.1 双通道输出格式

作为 Vulcan Brain 的专业 Agent，你需要使用双通道输出格式来展示你的推理过程和决策。
{DUAL_CHANNEL_FORMAT}

开始执行任务。"""
    else:
        # 通用提示词
        base_prompt = f"""你是 Vulcan Brain 的「统一大脑」（SingleBrain），负责理解用户意图、进行深度推理，并决定是否需要调用 CodeTool。

你的输出分为两部分：
{DUAL_CHANNEL_FORMAT}

开始执行任务。"""

    return base_prompt


# ============ V6.1 SingleBrain System Prompt (保留兼容) ============

SINGLEBRAIN_SYSTEM_PROMPT = """你是 Vulcan Brain 的「统一大脑」（SingleBrain），负责理解用户意图、进行深度推理，并决定是否需要调用 CodeTool。

你的输出分为两部分：

---

## ① 内部推理（不向用户展示）

用以下格式输出内部推理：

<thinking>
在这里进行详细推理，包括但不限于：
- 背景理解与问题拆解
- 多维度比较与分析框架
- 因果链与逻辑推演
- 数据对照与关键指标
- 商业逻辑与战略判断
- 风险识别与不确定性
- 决策理由与权衡
</thinking>

⚠️ 注意：
- thinking 区域内容不会被用户看到
- 在 action_json 部分 **不要** 重复推理内容
- 思考尽可能详细、有层次、有洞察

---

## ② 决策 JSON（必须严格符合格式）

<action_json>
{
  "action": "direct_answer" 或 "need_code",
  "content": "直接回答内容（action=direct_answer时必填）",
  "task": "任务描述（action=need_code时必填）",
  "task_type": "search" | "compute" | "analysis" | "mixed",
  "constraints": ["约束1", "约束2"],
  "expected_output": "期望输出格式",
  "reasoning": "简短决策理由（可选）"
}
</action_json>

---

## 决策规则

### 选择 "direct_answer" 当：
- 简单问答、闲聊、常识问题
- 基于你已有知识可以回答的问题
- 不需要最新数据或实时信息
- 时间日期问题（使用环境感知信息）

### 选择 "need_code" 当：
- 需要搜索最新信息（财报、新闻、价格）
- 需要数学计算或数据分析
- 需要调用外部工具
- 需要处理用户上传的数据

---

## 重要原则

1. **深度思考优先**：在 <thinking> 区域充分展开推理，不要压缩思维链
2. **结构化洞察**：分析问题时使用多维框架（财务/战略/技术/市场/风险）
3. **观点鲜明**：给出明确的判断和结论，不要模棱两可
4. **数据支撑**：引用具体数据和事实支撑论点
5. **格式严格**：JSON 必须合法，不能有多余字符

开始执行任务。
"""


# ============ Decision Node (V6.1 SingleBrain) ============

async def decision_node(state: GraphState) -> Dict[str, Any]:
    """
    V6.1 SingleBrain 决策节点

    - 支持双通道输出
    - 释放 CEO 推理能力
    - 支持 Agent 专业提示词
    """
    user_input = state.get("user_input", "")
    agent_type = state.get("agent_type", None)  # 获取 Agent 类型

    if not user_input:
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            user_input = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    agent_label = f"[{agent_type}]" if agent_type else "[通用]"
    print(f"\n🧠 [SingleBrain V6.1] {agent_label} 分析: {user_input[:80]}...")

    # 获取环境感知
    soul = get_ceo_soul()
    perception = soul.get_perception_context()

    # 构建系统提示词 = Agent专业提示词 + V6.1双通道格式
    base_prompt = build_system_prompt(agent_type)
    system_prompt = f"""{perception}

{base_prompt}"""
    
    async with httpx.AsyncClient(timeout=THINKING_MODEL["timeout"]) as client:
        try:
            resp = await client.post(
                f"{THINKING_MODEL['base_url']}/api/chat",
                json={
                    "model": THINKING_MODEL["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
            )
            data = resp.json()
            raw_output = data.get("message", {}).get("content", "")
            
        except Exception as e:
            print(f"❌ [SingleBrain] 调用失败: {e}")
            return {
                "brain_action": CEOAction(
                    action="direct_answer",
                    content=f"抱歉，系统出现错误: {e}"
                ).model_dump(),
                "ceo_action": CEOAction(
                    action="direct_answer",
                    content=f"抱歉，系统出现错误: {e}"
                ).model_dump(),
                "final_answer": f"系统错误: {e}"
            }
    
    # V6.1 双通道解析
    thinking, action = parse_brain_output(raw_output)
    
    if thinking:
        print(f"💭 [Thinking] {thinking[:200]}...")
    print(f"✓ [Decision] action={action.action}")
    
    return {
        "user_input": user_input,
        "thinking": thinking or "",
        "brain_action": action.model_dump(),
        "ceo_action": action.model_dump()  # 兼容旧字段
    }


# ============ Router ============

def router_decision(state: GraphState) -> Literal["direct_answer", "need_code"]:
    """路由决策"""
    brain_action = state.get("brain_action") or state.get("ceo_action", {})
    action = brain_action.get("action", "direct_answer")
    return action


# ============ Direct Answer Node ============

def direct_answer_node(state: GraphState) -> Dict[str, Any]:
    """直接回答节点"""
    brain_action = state.get("brain_action") or state.get("ceo_action", {})
    content = brain_action.get("content") or brain_action.get("answer", "")
    
    # 如果有 thinking，可以用来丰富回答
    thinking = state.get("thinking", "")
    
    print(f"💬 [Direct] 回答: {content[:100]}...")
    
    return {
        "final_answer": content,
        "messages": [AIMessage(content=content)]
    }


# ============ CTO Node (Code Execution) ============

async def cto_node(state: GraphState) -> Dict[str, Any]:
    """CTO 节点 - 代码执行"""
    brain_action = state.get("brain_action") or state.get("ceo_action", {})
    
    # 提取任务信息
    task_desc = brain_action.get("task") or ""
    if not task_desc:
        # 兼容旧格式
        delegation = brain_action.get("delegation", {})
        task_desc = delegation.get("objective", "") if delegation else ""
    
    if not task_desc:
        return {
            "cto_result": CTOResult(
                success=False,
                error="没有任务描述"
            ).model_dump()
        }
    
    print(f"\n⚙️ [CTO] 执行: {task_desc[:80]}...")
    
    # 构建 TaskSpec
    task = TaskSpec(
        task_id=f"task_{datetime.now().strftime('%H%M%S')}",
        objective=task_desc,
        context=brain_action.get("context", ""),
        constraints=brain_action.get("constraints", []),
        expected_output=brain_action.get("expected_output", "执行结果")
    )
    
    # 执行
    executor = get_cto_executor()
    result: ExecutionResult = await executor.execute(task)
    
    cto_result = CTOResult(
        success=result.success,
        result=result.output if result.success else None,
        error=result.error if not result.success else None,
        code=result.code,
        tools_used=result.tools_used if hasattr(result, 'tools_used') else []
    )
    
    if result.success:
        print(f"✅ [CTO] 成功: {result.output[:100]}...")
    else:
        print(f"❌ [CTO] 失败: {result.error}")
    
    return {
        "cto_task": task.__dict__,
        "cto_result": cto_result.model_dump()
    }


# ============ Synth Node (V6.1 多维分析) ============

SYNTH_SYSTEM_PROMPT_V61 = """你是分析综合模块。根据用户问题和执行结果，输出深度分析。

你的输出必须是一个 JSON，格式如下：

{
  "conclusion": "核心结论（1-2句话，明确观点）",
  "key_insights": ["关键洞察1", "关键洞察2", "关键洞察3"],
  "core_facts": ["关键数据1", "关键数据2"],
  "dimensions": [
    {"dimension": "财务", "assessment": "评估", "score": 8.5},
    {"dimension": "战略", "assessment": "评估", "score": 7.0}
  ],
  "analysis": "深度分析（2-3段）",
  "risks": ["风险提示1", "风险提示2"],
  "recommendations": ["建议1", "建议2"],
  "confidence": 0.85
}

要求：
1. **conclusion**: 直接回答用户问题，观点明确
2. **key_insights**: 3-5 个深度洞察，不是事实堆砌
3. **dimensions**: 多维度评估（根据问题选择：财务/战略/技术/市场/风险）
4. **analysis**: 有深度的分析，展示思维链
5. **confidence**: 0.0-1.0 的置信度

不要输出 JSON 以外的内容。
"""


async def synth_node(state: GraphState) -> Dict[str, Any]:
    """Synth 节点 - V6.1 多维综合分析"""
    user_input = state.get("user_input", "")
    cto_result = state.get("cto_result", {})
    thinking = state.get("thinking", "")
    
    print(f"\n🎯 [Synth V6.1] 多维综合分析...")
    
    if not cto_result.get("success"):
        error = cto_result.get("error", "未知错误")
        return {
            "final_answer": f"执行失败: {error}",
            "messages": [AIMessage(content=f"执行失败: {error}")]
        }
    
    result_text = cto_result.get("result", "")
    
    # 构建综合分析请求
    content = f"""用户问题: {user_input}

执行结果:
{result_text}

前序推理（参考）:
{thinking[:500] if thinking else "无"}
"""
    
    async with httpx.AsyncClient(timeout=THINKING_MODEL["timeout"]) as client:
        try:
            resp = await client.post(
                f"{THINKING_MODEL['base_url']}/api/chat",
                json={
                    "model": THINKING_MODEL["model"],
                    "messages": [
                        {"role": "system", "content": SYNTH_SYSTEM_PROMPT_V61},
                        {"role": "user", "content": content}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.2}
                }
            )
            data = resp.json()
            raw_json = data.get("message", {}).get("content", "{}")
            
            synth = parse_synth_result(raw_json)
            answer = synth.to_answer()
            
            print(f"✓ [Synth] 完成，置信度: {synth.confidence}")
            
            return {
                "synth_result": synth.model_dump(),
                "final_answer": answer,
                "messages": [AIMessage(content=answer)]
            }
            
        except Exception as e:
            print(f"⚠️ [Synth] 解析失败: {e}，降级返回原始结果")
            return {
                "final_answer": result_text,
                "messages": [AIMessage(content=result_text)]
            }


# ============ 构建状态图 ============

def create_singlebrain_graph() -> StateGraph:
    """创建 V6.1 SingleBrain 状态图"""
    graph = StateGraph(GraphState)
    
    # 节点
    graph.add_node("decision", decision_node)
    graph.add_node("direct_answer", direct_answer_node)
    graph.add_node("cto", cto_node)
    graph.add_node("synth", synth_node)
    
    # 入口
    graph.add_edge(START, "decision")
    
    # 决策分支
    graph.add_conditional_edges(
        "decision",
        router_decision,
        {
            "direct_answer": "direct_answer",
            "need_code": "cto"
        }
    )
    
    # 路径
    graph.add_edge("direct_answer", END)
    graph.add_edge("cto", "synth")
    graph.add_edge("synth", END)
    
    return graph


# ============ Runner ============

class BicameralRunner:
    """V6.1 SingleBrain 运行器"""
    
    def __init__(self, db_uri: str = POSTGRES_URI):
        self.db_uri = db_uri
        self._workflow = None
    
    def _get_workflow(self):
        if self._workflow is None:
            self._workflow = create_singlebrain_graph()
        return self._workflow
    
    async def run(
        self,
        user_message: str,
        thread_id: str = "default",
        agent_type: str = None  # Agent 类型
    ) -> str:
        """同步执行"""
        workflow = self._get_workflow()

        async with AsyncPostgresSaver.from_conn_string(self.db_uri) as checkpointer:
            app = workflow.compile(checkpointer=checkpointer)

            initial_state = {
                "user_input": user_message,
                "messages": [HumanMessage(content=user_message)],
                "agent_type": agent_type,  # 传递 Agent 类型
                "thinking": "",
                "brain_action": {},
                "ceo_action": {},
                "cto_task": {},
                "cto_result": {},
                "synth_result": {},
                "final_answer": "",
                "thread_id": thread_id,
                "created_at": datetime.now().isoformat(),
                "retry_count": 0,
                "last_error": ""
            }

            config = {"configurable": {"thread_id": thread_id}}
            final_state = await app.ainvoke(initial_state, config)
            return final_state.get("final_answer", "No answer")

    async def run_stream(
        self,
        user_message: str,
        thread_id: str = "default",
        max_steps: int = 10,  # 兼容旧接口
        agent_type: str = None  # Agent 类型
    ):
        """流式执行 - V6.1 兼容版"""
        workflow = self._get_workflow()

        async with AsyncPostgresSaver.from_conn_string(self.db_uri) as checkpointer:
            app = workflow.compile(checkpointer=checkpointer)

            initial_state = {
                "user_input": user_message,
                "messages": [HumanMessage(content=user_message)],
                "agent_type": agent_type,  # 传递 Agent 类型
                "thinking": "",
                "brain_action": {},
                "ceo_action": {},
                "cto_task": {},
                "cto_result": {},
                "synth_result": {},
                "final_answer": "",
                "thread_id": thread_id,
                "created_at": datetime.now().isoformat(),
                "retry_count": 0,
                "last_error": ""
            }

            config = {"configurable": {"thread_id": thread_id}}
            emitted = set()

            async for event in app.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event")

                if event_type == "on_chain_start":
                    node = event.get("name", "")
                    # 映射节点名称到前端期望的名称
                    node_label = {
                        "decision": "ceo",
                        "direct_answer": "synthesizer",
                        "cto": "cto",
                        "synth": "synthesizer"
                    }.get(node, node)
                    yield {"type": "node_start", "node": node_label}

                elif event_type == "on_chain_end":
                    node = event.get("name", "")
                    output = event.get("data", {}).get("output", {})

                    node_label = {
                        "decision": "ceo",
                        "direct_answer": "synthesizer",
                        "cto": "cto",
                        "synth": "synthesizer"
                    }.get(node, node)

                    # 输出 thinking (用 <think> 标签包裹以兼容 stream_filter)
                    if isinstance(output, dict):
                        thinking = output.get("thinking", "")
                        if thinking and thinking not in emitted:
                            emitted.add(thinking)
                            # 用 <think> 标签包裹，让 stream_filter 处理
                            yield {"type": "token", "content": f"<think>{thinking}</think>"}

                        # 输出最终答案
                        answer = output.get("final_answer", "")
                        if answer and answer not in emitted:
                            emitted.add(answer)
                            yield {"type": "token", "content": answer}

                    yield {"type": "node_end", "node": node_label}


# ============ 便捷函数 ============

_runner_cache = None

def get_bicameral_runner() -> BicameralRunner:
    """获取运行器实例（单例）"""
    global _runner_cache
    if _runner_cache is None:
        _runner_cache = BicameralRunner()
    return _runner_cache


# ============ 测试 ============

async def test_v61():
    """V6.1 测试"""
    runner = BicameralRunner()
    
    test_cases = [
        "现在几点了？",
        "2024年特斯拉和比亚迪的营收对比如何？谁更有前景？",
    ]
    
    for query in test_cases:
        print("\n" + "="*60)
        print(f"测试: {query}")
        print("="*60)
        result = await runner.run(query)
        print(f"\n结果:\n{result}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_v61())
