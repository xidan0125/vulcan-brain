"""
Soul Interceptor - LLM 调用拦截器

核心功能：
1. Pre-process: 注入宪法 + 人格到 prompt
2. Post-process: 检测违规输出
3. @with_soul 装饰器: 一行代码集成
"""

from functools import wraps
from typing import Optional, Callable, Any
import asyncio
import re

from core.soul.types import SoulContext, Genome, AuditResult
from core.soul.genome import GenomeManager, get_genome_manager
from core.soul.constitution import Constitution


class SoulInterceptor:
    """
    Soul 拦截器 - 所有 LLM 调用的守门人
    """

    def __init__(self):
        self.constitution = Constitution()
        self.genome_mgr = get_genome_manager()

        # 任务类型到宪法切片的映射
        self._task_rules_map = {
            "chat": ["communication_style", "core_values"],
            "code": ["code_implementation", "architecture_decisions", "core_values"],
            "search": ["search_guidelines", "core_values"],
            "email": ["communication_style", "core_values"],
            "general": ["core_values", "behavioral_guidelines"]
        }

    async def pre_process(self, prompt: str, context: SoulContext) -> str:
        """
        Pre-processing: 注入宪法 + 人格到 prompt

        Args:
            prompt: 原始 prompt
            context: Soul 上下文

        Returns:
            增强后的 prompt
        """
        # 1. 获取相关宪法规则（按任务类型切片，节省 token）
        rules = self._get_rules_for_task(context.task_type)

        # 2. 获取人格描述
        persona_desc = self.genome_mgr.describe(context.genome)
        response_hints = self.genome_mgr.get_response_hints(context.genome)

        # 3. 获取红线摘要
        red_lines = self.constitution.get_prohibited_actions()[:5]  # 只取前5条

        # 4. 组装 Soul Prompt
        soul_section = f"""
[Soul Protocol - Constitutional AI Layer]

## 用户人格特征
{persona_desc}

## 回复风格指导
{chr(10).join('- ' + h for h in response_hints) if response_hints else '- 保持专业中性'}

## 行为准则
{rules}

## 绝对红线（违反将被拦截）
{chr(10).join('❌ ' + r for r in red_lines)}

---

"""
        return soul_section + prompt

    def _get_rules_for_task(self, task_type: str) -> str:
        """
        根据任务类型获取相关规则（宪法切片）
        """
        categories = self._task_rules_map.get(task_type, self._task_rules_map["general"])

        rules_text = []
        for category in categories:
            rules = self.constitution.get_rules_by_category(category)
            if rules:
                rules_text.append(f"### {category}")
                rules_text.extend(f"- {r}" for r in rules[:3])  # 每类最多3条

        if not rules_text:
            # 回退到核心价值观
            for value in self.constitution.get_core_values()[:2]:
                rules_text.append(f"### {value['name']}")
                rules_text.extend(f"- {p}" for p in value.get('principles', [])[:2])

        return "\n".join(rules_text)

    def post_process(self, response: str, context: SoulContext) -> AuditResult:
        """
        Post-processing: 审计 LLM 输出

        Args:
            response: LLM 的原始输出
            context: Soul 上下文

        Returns:
            AuditResult
        """
        violations = []
        suggestions = []
        blocked = False

        # 1. 硬性检查（关键词匹配）
        hard_blocks = self._check_hard_blocks(response)
        if hard_blocks:
            violations.extend(hard_blocks)
            if context.strict_mode:
                blocked = True

        # 2. 软性检查（风格一致性等）
        soft_issues = self._check_soft_issues(response, context.genome)
        suggestions.extend(soft_issues)

        # 计算分数
        score = 1.0
        score -= len(violations) * 0.2
        score -= len(suggestions) * 0.05
        score = max(0, score)

        return AuditResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            blocked=blocked,
            original_response=response if blocked else None
        )

    def _check_hard_blocks(self, response: str) -> list:
        """
        硬性违规检查（必须拦截）
        """
        violations = []
        response_lower = response.lower()

        # 关键词检测
        block_patterns = [
            (r'简化版|临时方案|先这样', '检测到未经授权的简化方案'),
            (r'我不确定.*但我认为', '检测到不确定时的猜测'),
            (r'rm\s+-rf|drop\s+table|delete\s+from', '检测到危险操作'),
        ]

        for pattern, msg in block_patterns:
            if re.search(pattern, response_lower):
                violations.append(msg)

        return violations

    def _check_soft_issues(self, response: str, genome: Genome) -> list:
        """
        软性问题检查（建议改进）
        """
        issues = []

        # 检查响应长度与人格匹配
        if genome.control_style > 60 and len(response) < 100:
            issues.append("用户偏好结构化，但响应过于简短")

        if genome.strategic_drive < 40 and len(response) > 2000:
            issues.append("用户偏好简洁，但响应过于冗长")

        return issues

    def build_system_prompt(self, context: SoulContext) -> str:
        """
        构建完整的 System Prompt（不含用户输入）
        """
        persona_desc = self.genome_mgr.describe(context.genome)
        hints = self.genome_mgr.get_response_hints(context.genome)

        return f"""你是 Vulcan Brain AI 助手。

## 你的人格设定
{persona_desc}

## 回复风格
{chr(10).join('- ' + h for h in hints) if hints else '- 保持专业中性'}

## 核心原则
{self.constitution.to_system_prompt_section()}
"""


# ==================== 装饰器 ====================

def with_soul(task_type: str = "general", strict: bool = False):
    """
    装饰器：为 LLM 调用注入 Soul

    Usage:
        @with_soul(task_type="code")
        async def call_llm(prompt: str, user_id: str = "default"):
            response = await some_llm_call(prompt)
            return response

    Args:
        task_type: 任务类型，用于宪法切片
        strict: 严格模式，违规时阻断响应
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # 提取参数
            prompt = kwargs.get("prompt")
            if prompt is None and args:
                prompt = args[0]

            user_id = kwargs.get("user_id", "default")

            # 获取 Soul 组件
            interceptor = SoulInterceptor()
            genome = await interceptor.genome_mgr.get(user_id)

            context = SoulContext(
                user_id=user_id,
                genome=genome,
                task_type=task_type,
                strict_mode=strict
            )

            # Pre-process: 注入 Soul
            enhanced_prompt = await interceptor.pre_process(prompt, context)

            # 替换参数
            if "prompt" in kwargs:
                kwargs["prompt"] = enhanced_prompt
            elif args:
                args = (enhanced_prompt,) + args[1:]

            # 执行原函数
            response = await func(*args, **kwargs)

            # Post-process: 审计
            audit_result = interceptor.post_process(response, context)

            # 如果被阻断，返回替代响应
            if audit_result.blocked:
                return f"[Soul Protocol] 响应已被拦截。违规: {', '.join(audit_result.violations)}"

            return response

        return wrapper
    return decorator


def with_soul_sync(task_type: str = "general", strict: bool = False):
    """
    同步版装饰器（用于非异步函数）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 在同步上下文中运行异步代码
            async def async_wrapper():
                prompt = kwargs.get("prompt")
                if prompt is None and args:
                    prompt = args[0]

                user_id = kwargs.get("user_id", "default")

                interceptor = SoulInterceptor()
                genome = await interceptor.genome_mgr.get(user_id)

                context = SoulContext(
                    user_id=user_id,
                    genome=genome,
                    task_type=task_type,
                    strict_mode=strict
                )

                enhanced_prompt = await interceptor.pre_process(prompt, context)

                if "prompt" in kwargs:
                    kwargs["prompt"] = enhanced_prompt
                elif args:
                    args_list = list(args)
                    args_list[0] = enhanced_prompt
                    return func(*args_list, **kwargs)

                return func(*args, **kwargs)

            # 尝试获取现有事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已在异步上下文中，创建任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, async_wrapper())
                        return future.result()
                else:
                    return loop.run_until_complete(async_wrapper())
            except RuntimeError:
                return asyncio.run(async_wrapper())

        return wrapper
    return decorator


# ==================== 便捷函数 ====================

async def inject_soul(prompt: str, user_id: str = "default",
                      task_type: str = "general") -> str:
    """
    便捷函数：手动注入 Soul（不使用装饰器时）

    Usage:
        enhanced = await inject_soul(prompt, user_id="tony")
        response = await llm.call(enhanced)
    """
    interceptor = SoulInterceptor()
    genome = await interceptor.genome_mgr.get(user_id)

    context = SoulContext(
        user_id=user_id,
        genome=genome,
        task_type=task_type
    )

    return await interceptor.pre_process(prompt, context)


async def audit_response(response: str, user_id: str = "default",
                         task_type: str = "general") -> AuditResult:
    """
    便捷函数：手动审计响应

    Usage:
        result = await audit_response(llm_response, user_id="tony")
        if not result.passed:
            print(result.violations)
    """
    interceptor = SoulInterceptor()
    genome = await interceptor.genome_mgr.get(user_id)

    context = SoulContext(
        user_id=user_id,
        genome=genome,
        task_type=task_type
    )

    return interceptor.post_process(response, context)
