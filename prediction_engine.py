# prediction_engine.py - Vulcan Brain 预测引擎 (异步版)
"""
基于 In-Context Learning 的用户决策预测引擎
使用统一的 VulcanStore 进行数据库访问

核心逻辑:
1. 构建 Persona (画像): Genesis 20问 + 历史决策
2. 组装 Prompt 发给 LLM
3. 生成预测并解析结果

数据优先级:
- 最高: Genesis 20问答案 (先天基因)
- 次高: 最近的 alignment_memory (对齐修正)
- 基础: 历史 soul_interactions (后天习惯)
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional

from vulcan_libs.store import store
from config import LLM_API_URL, LLM_PREDICTION_MODEL as LLM_MODEL

# LLM 配置


async def predict_user_choice(question_id: str, user_id: str) -> Dict:
    """
    预测用户对某道题的选择

    Args:
        question_id: 题目 ID
        user_id: 用户 ID

    Returns:
        {
            "option_id": "C",
            "confidence": 0.85,
            "reasoning": "基于您的现金流优先原则..."
        }
    """
    # 1. 获取题目
    question = await store.get_sandbox_question_by_id(question_id)
    if not question:
        return {"option_id": "A", "confidence": 0.5, "reasoning": "题目不存在"}

    # 2. 构建用户画像 Context
    context = await _build_user_context(user_id)

    # 3. 构建 Prompt
    prompt = _build_prediction_prompt(question, context)

    # 4. 调用 LLM
    try:
        prediction = await _call_llm_for_prediction(prompt, question.get("options", []))
        return prediction
    except Exception as e:
        # 如果 LLM 调用失败，使用启发式规则
        return _fallback_prediction(question, context)


async def _build_user_context(user_id: str) -> Dict:
    """
    构建用户上下文

    包含:
    - Genesis 20问答案 (先天基因)
    - 最近20条决策记录 (后天习惯)
    - 维度统计
    """
    context = {
        "genesis_traits": [],
        "recent_decisions": [],
        "dimension_summary": {}
    }

    # 1. Genesis 数据 (最高优先级)
    genesis = await store.get_user_genesis(user_id)
    if genesis:
        context["genesis_traits"] = genesis.get("key_traits", [])
        context["dimension_summary"] = genesis.get("dimensions", {})

    # 2. 最近决策 (Few-Shot 样本)
    recent = await store.get_soul_interactions_by_type(user_id, interaction_type="sandbox", limit=20)

    for r in recent:
        # 获取对应题目
        target_id = r.get("target_id")
        if target_id:
            q = await store.get_sandbox_question_by_id(str(target_id))
            if q:
                # 找到用户选择的选项文本
                user_choice_text = ""
                for opt in q.get("options", []):
                    if opt.get("id") == r.get("user_choice"):
                        user_choice_text = opt.get("text", "")
                        break

                context["recent_decisions"].append({
                    "scenario": q.get("scenario", "")[:100],
                    "category": q.get("category", ""),
                    "user_choice": user_choice_text,
                    "was_predicted_correctly": r.get("is_match", False)
                })

    return context


def _build_prediction_prompt(question: Dict, context: Dict) -> str:
    """
    构建预测 Prompt

    融合 Genesis + 历史决策
    """
    prompt_parts = []

    # System 角色
    prompt_parts.append("你是一个决策风格分析师，需要预测用户在给定场景下最可能的选择。")
    prompt_parts.append("")

    # Genesis 特征 (先天基因)
    if context.get("genesis_traits"):
        prompt_parts.append("【用户核心特征 (来自初始校准)】")
        for trait in context["genesis_traits"][:5]:
            prompt_parts.append(f"- {trait}")
        prompt_parts.append("")

    # 维度总结
    if context.get("dimension_summary"):
        prompt_parts.append("【用户决策维度】")
        dims = context["dimension_summary"]
        if dims.get("risk_appetite", 0.5) > 0.6:
            prompt_parts.append("- 风险偏好: 偏激进")
        elif dims.get("risk_appetite", 0.5) < 0.4:
            prompt_parts.append("- 风险偏好: 偏保守")

        if dims.get("social_tendency", 0.5) > 0.6:
            prompt_parts.append("- 人际决策: 重视情感")
        elif dims.get("social_tendency", 0.5) < 0.4:
            prompt_parts.append("- 人际决策: 结果导向")
        prompt_parts.append("")

    # 历史决策样本 (Few-Shot)
    if context.get("recent_decisions"):
        prompt_parts.append("【近期决策样本】")
        for dec in context["recent_decisions"][:5]:
            prompt_parts.append(f"- 场景: {dec['scenario'][:50]}... → 选择: {dec['user_choice']}")
        prompt_parts.append("")

    # 当前题目
    prompt_parts.append("【当前题目】")
    prompt_parts.append(f"场景: {question.get('scenario', '')}")
    prompt_parts.append("")
    prompt_parts.append("选项:")
    for opt in question.get("options", []):
        prompt_parts.append(f"  {opt.get('id', '')}. {opt.get('text', '')}")

    prompt_parts.append("")
    prompt_parts.append("请预测用户最可能选择哪个选项。只需回答选项字母(A/B/C/D)和简短理由。")
    prompt_parts.append("格式: [选项] 理由")

    return "\n".join(prompt_parts)


async def _call_llm_for_prediction(prompt: str, options: List[Dict]) -> Dict:
    """
    调用 LLM 进行预测
    """
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LLM_API_URL,
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 100
                    }
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    text = result.get("response", "A")
                    return _parse_llm_response(text, options)
                else:
                    return {"option_id": "A", "confidence": 0.5, "reasoning": "LLM 调用失败"}
    except Exception as e:
        return {"option_id": "A", "confidence": 0.5, "reasoning": f"连接错误: {str(e)}"}


def _parse_llm_response(text: str, options: List[Dict]) -> Dict:
    """
    解析 LLM 响应

    预期格式: "[A] 因为用户偏好..."
    """
    text = text.strip()

    # 提取选项
    option_id = "A"
    valid_options = [opt.get("id", "") for opt in options]

    for opt in valid_options:
        if opt in text[:10]:  # 在开头找选项
            option_id = opt
            break

    # 提取理由
    reasoning = text
    if "]" in text:
        reasoning = text.split("]", 1)[-1].strip()
    elif "." in text[:5]:
        reasoning = text.split(".", 1)[-1].strip()

    return {
        "option_id": option_id,
        "confidence": 0.75,  # 默认置信度
        "reasoning": reasoning[:100] if reasoning else "基于历史决策模式"
    }


def _fallback_prediction(question: Dict, context: Dict) -> Dict:
    """
    启发式回退预测

    当 LLM 不可用时，基于简单规则预测
    """
    options = question.get("options", [])
    if not options:
        return {"option_id": "A", "confidence": 0.5, "reasoning": "无选项"}

    category = question.get("category", "")
    dims = context.get("dimension_summary", {})

    # 基于维度和类别的简单规则
    if category == "RISK_DECISION":
        if dims.get("risk_appetite", 0.5) > 0.6:
            return {"option_id": options[0].get("id", "A"), "confidence": 0.6, "reasoning": "基于您的风险偏好"}
        else:
            idx = min(2, len(options) - 1)
            return {"option_id": options[idx].get("id", "C"), "confidence": 0.6, "reasoning": "基于您的稳健风格"}

    elif category == "HR_DECISION":
        if dims.get("social_tendency", 0.5) > 0.6:
            idx = min(1, len(options) - 1)
            return {"option_id": options[idx].get("id", "B"), "confidence": 0.6, "reasoning": "基于您对团队的重视"}
        else:
            idx = min(2, len(options) - 1)
            return {"option_id": options[idx].get("id", "C"), "confidence": 0.6, "reasoning": "基于您的效率优先原则"}

    # 默认选 B (通常是中庸选项)
    idx = min(1, len(options) - 1)
    return {"option_id": options[idx].get("id", "B"), "confidence": 0.5, "reasoning": "综合分析"}


# ==================== 校准期逻辑 ====================

async def get_calibration_status(user_id: str) -> Dict:
    """
    获取校准状态

    前 7 天为校准期，预测准确率低是正常的
    """
    interactions_count = await store.count_soul_interactions(user_id)

    if interactions_count < 7:
        return {
            "in_calibration": True,
            "calibration_progress": interactions_count / 7.0,
            "message": f"正在构建初始模型... ({interactions_count}/7)"
        }
    else:
        # 计算最近准确率
        recent = await store.get_soul_interactions_with_match(user_id, limit=20)

        if recent:
            accuracy = sum(1 for r in recent if r.get("is_match")) / len(recent)
        else:
            accuracy = 0.5

        return {
            "in_calibration": False,
            "calibration_progress": 1.0,
            "accuracy": accuracy,
            "message": f"模型准确率: {accuracy*100:.1f}%"
        }
