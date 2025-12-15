# Soul 模块重构方案 v1.0

> Generated: 2025-12-12
> Based on: Gemini Architect Consultation + Codebase Analysis

---

## 1. 现状分析

### 1.1 现有代码分布（需整合）

| 文件 | 功能 | 状态 |
|------|------|------|
| `boss_constitution.yaml` | 静态宪法配置 | ✅ 完整，需迁移 |
| `soul_api.py` | 校准问卷 API（情景题生成） | ⚠️ 需重构 |
| `auth_api.py` | Genesis 20问 API | ⚠️ 需提取 |
| `prediction_engine.py` | Genesis 数据消费 | ⚠️ 需对接 |
| `vulcan_libs/store.py` | `get_user_genesis()` 等 | ✅ 保留 |

### 1.2 现有数据结构

**MongoDB: user_genesis 集合**
```json
{
  "user_id": "tonysun",
  "current_genome": {
    "risk_appetite": 67,
    "time_horizon": 62,
    "strategic_drive": 67,
    "people_philosophy": 50,
    "control_style": 75,
    "ethical_boundary": 56
  },
  "initial_genome": {...},
  "questions_answered": 19,
  "version": "2.0"
}
```

---

## 2. 目标架构

### 2.1 模块结构

```
core/soul/
├── __init__.py           # SoulEngine 门面 + @with_soul 装饰器
├── types.py              # 数据结构定义
├── constitution.py       # 静态宪法加载与查询
├── genome.py             # 六维度人格管理（替代 personality.py）
├── interceptor.py        # LLM 调用拦截器（Pre/Post）
├── auditor.py            # 异步价值观审计
├── calibration/          # 校准子系统
│   ├── __init__.py
│   ├── engine.py         # EMA 算法核心
│   ├── generator.py      # LLM 情景题生成
│   └── question_store.py # 题库管理
├── prompts/
│   └── boss_constitution.yaml
└── api.py                # FastAPI 路由（合并现有 soul_api.py）
```

### 2.2 核心概念

| 概念 | 说明 | 数据源 |
|------|------|--------|
| **Constitution** | 静态宪法（红线、价值观） | YAML 文件 |
| **Genome** | 动态人格（六维度） | MongoDB |
| **Interceptor** | LLM 调用拦截 | 运行时 |
| **Calibration** | 持续校准系统 | 每日决策题 |

---

## 3. 详细设计

### 3.1 types.py - 数据结构

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class Dimension(Enum):
    RISK_APPETITE = "risk_appetite"
    TIME_HORIZON = "time_horizon"
    STRATEGIC_DRIVE = "strategic_drive"
    PEOPLE_PHILOSOPHY = "people_philosophy"
    CONTROL_STYLE = "control_style"
    ETHICAL_BOUNDARY = "ethical_boundary"

@dataclass
class Genome:
    """六维度人格基因"""
    risk_appetite: float      # 0-100, 50=中性
    time_horizon: float
    strategic_drive: float
    people_philosophy: float
    control_style: float
    ethical_boundary: float

    def to_dict(self) -> Dict[str, float]:
        return {d.value: getattr(self, d.value) for d in Dimension}

    @classmethod
    def from_dict(cls, data: Dict) -> "Genome":
        return cls(**{d.value: data.get(d.value, 50) for d in Dimension})

@dataclass
class SoulContext:
    """传递给 Interceptor 的上下文"""
    user_id: str
    genome: Genome
    task_type: str  # "chat", "code", "search", "email"
    strict_mode: bool = False

@dataclass
class AuditResult:
    """审计结果"""
    passed: bool
    violations: List[str]
    score: float  # 0-1
    suggestions: List[str]
```

### 3.2 genome.py - 人格管理

```python
from vulcan_libs.store import store
from core.soul.types import Genome, Dimension

class GenomeManager:
    """
    管理用户的六维度人格基因
    数据源: MongoDB user_genesis.current_genome
    """

    async def get(self, user_id: str) -> Genome:
        """获取用户当前人格"""
        data = await store.get_user_genesis(user_id)
        if data and "current_genome" in data:
            return Genome.from_dict(data["current_genome"])
        return Genome.from_dict({})  # 返回中性默认值

    async def update(self, user_id: str, genome: Genome):
        """更新用户人格（校准后调用）"""
        await store.db.user_genesis.update_one(
            {"user_id": user_id},
            {"$set": {"current_genome": genome.to_dict()}},
            upsert=True
        )

    def describe(self, genome: Genome) -> str:
        """将数值转为自然语言描述（给 LLM 看）"""
        descriptions = []

        if genome.risk_appetite > 60:
            descriptions.append("决策风格偏激进，愿意承担高风险")
        elif genome.risk_appetite < 40:
            descriptions.append("决策风格偏保守，倾向规避风险")

        if genome.time_horizon > 60:
            descriptions.append("注重长期价值，愿意延迟满足")
        elif genome.time_horizon < 40:
            descriptions.append("关注短期收益，追求快速回报")

        if genome.control_style > 60:
            descriptions.append("喜欢结构化方案，偏好秩序和流程")
        elif genome.control_style < 40:
            descriptions.append("适应不确定性，灵活应变")

        if genome.strategic_drive > 60:
            descriptions.append("深度谋划型，重视战略规划")
        elif genome.strategic_drive < 40:
            descriptions.append("直觉行动型，快速迭代")

        if genome.people_philosophy > 60:
            descriptions.append("协作共生，重视团队")
        elif genome.people_philosophy < 40:
            descriptions.append("独狼领袖，独立决策")

        if genome.ethical_boundary > 60:
            descriptions.append("原则坚守，不走捷径")
        elif genome.ethical_boundary < 40:
            descriptions.append("灰度决策，灵活变通")

        return "；".join(descriptions) if descriptions else "人格均衡，无明显偏好"
```

### 3.3 interceptor.py - LLM 拦截器

```python
from functools import wraps
from core.soul.constitution import Constitution
from core.soul.genome import GenomeManager
from core.soul.types import SoulContext

class SoulInterceptor:
    def __init__(self):
        self.constitution = Constitution()
        self.genome_mgr = GenomeManager()

    async def pre_process(self, prompt: str, context: SoulContext) -> str:
        """
        Pre-processing: 注入宪法 + 人格到 prompt
        """
        # 1. 获取相关宪法规则（按任务类型切片，节省 token）
        rules = self.constitution.get_rules_for_task(context.task_type)

        # 2. 获取人格描述
        persona = self.genome_mgr.describe(context.genome)

        # 3. 组装 System Prompt
        soul_prompt = f"""
[Soul Protocol - Constitutional AI Layer]

## 你的人格特征
{persona}

## 核心行为准则
{rules}

## 绝对红线
{self.constitution.get_red_lines_summary()}

---
[User Request]
{prompt}
"""
        return soul_prompt

    def post_process(self, response: str, context: SoulContext) -> str:
        """
        Post-processing: 快速违规检测
        """
        # 同步检测明显违规（关键词）
        if self.constitution.check_hard_blocks(response):
            return "[Soul Block] 响应包含禁止内容，已拦截。"

        return response


# === 装饰器：一行代码集成 Soul ===

def with_soul(task_type: str = "general"):
    """
    装饰器：为 LLM 调用注入 Soul

    Usage:
        @with_soul(task_type="code")
        async def call_llm(prompt: str, user_id: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 提取参数
            prompt = kwargs.get("prompt") or args[0]
            user_id = kwargs.get("user_id", "default")

            # 获取 Soul 实例
            interceptor = SoulInterceptor()
            genome = await interceptor.genome_mgr.get(user_id)
            context = SoulContext(user_id=user_id, genome=genome, task_type=task_type)

            # Pre-process
            enhanced_prompt = await interceptor.pre_process(prompt, context)

            # 替换参数
            if "prompt" in kwargs:
                kwargs["prompt"] = enhanced_prompt
            else:
                args = (enhanced_prompt,) + args[1:]

            # 执行原函数
            response = await func(*args, **kwargs)

            # Post-process
            return interceptor.post_process(response, context)

        return wrapper
    return decorator
```

### 3.4 calibration/engine.py - EMA 校准算法

```python
from typing import Dict
from core.soul.types import Genome, Dimension

class CalibrationEngine:
    """
    指数移动平均（EMA）校准算法

    公式: P_new = P_old * (1-α) + W_choice * α
    α (学习率): 0.15 - 新题目对总人格的影响程度
    """

    def __init__(self, learning_rate: float = 0.15):
        self.alpha = learning_rate

    def calibrate(self, current: Genome, option_weights: Dict[str, float]) -> Genome:
        """
        根据用户选择更新人格

        Args:
            current: 当前人格
            option_weights: 选项权重，如 {"risk_appetite": 10, "time_horizon": -5}

        Returns:
            更新后的人格
        """
        new_values = {}

        for dim in Dimension:
            current_val = getattr(current, dim.value)
            weight = option_weights.get(dim.value, 0)

            # EMA 公式: 旧值权重 (1-α) + 新值权重 α
            # weight 范围是 -30 到 +30，作为增量
            target = current_val + weight
            new_val = current_val * (1 - self.alpha) + target * self.alpha

            # 边界钳制 (0-100)
            new_values[dim.value] = max(0, min(100, new_val))

        return Genome(**new_values)
```

---

## 4. 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                        Soul System                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Constitution │    │    Genome    │    │  Calibration │      │
│  │    (YAML)    │    │  (MongoDB)   │    │   (每日题)    │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └─────────┬─────────┴─────────┬─────────┘               │
│                   │                   │                         │
│                   ▼                   ▼                         │
│            ┌─────────────────────────────┐                      │
│            │       Interceptor           │                      │
│            │  ┌─────────┐ ┌─────────┐   │                      │
│            │  │   Pre   │ │  Post   │   │                      │
│            │  │ Process │ │ Process │   │                      │
│            │  └────┬────┘ └────┬────┘   │                      │
│            └───────┼───────────┼────────┘                      │
│                    │           │                                │
└────────────────────┼───────────┼────────────────────────────────┘
                     │           │
                     ▼           ▼
              ┌─────────────────────────┐
              │    LLM Calls Layer      │
              │  (kernel_codeact.py)    │
              │  (sglang)               │
              └─────────────────────────┘
```

---

## 5. 集成方案

### 5.1 与现有 LLM 调用集成

**kernel_codeact.py:**
```python
from core.soul import with_soul

@with_soul(task_type="code_act")
async def run_codeact(prompt: str, user_id: str):
    # 原有逻辑不变
    ...
```

**sglang 调用封装:**
```python
@with_soul(task_type="coding")
async def call_sglang_coder(prompt: str, user_id: str):
    ...
```

### 5.2 与现有 API 整合

**保留:**
- `GET /api/soul/profile` - 获取用户人格
- `POST /api/soul/calibrate` - 提交校准答案

**迁移到 core/soul/api.py:**
- 从 `soul_api.py` 迁移情景题生成
- 从 `auth_api.py` 提取 Genesis 相关

---

## 6. 实施步骤

### Phase 1: 基础模块 (今天)
1. ✅ 创建 `core/soul/__init__.py`
2. ✅ 创建 `core/soul/constitution.py`
3. ⏳ 创建 `core/soul/types.py`
4. ⏳ 创建 `core/soul/genome.py`
5. ⏳ 迁移 `boss_constitution.yaml` 到 `prompts/`

### Phase 2: 拦截器
1. 创建 `core/soul/interceptor.py`
2. 实现 `@with_soul` 装饰器
3. 在 `kernel_codeact.py` 集成测试

### Phase 3: 校准系统
1. 创建 `calibration/engine.py` (EMA)
2. 迁移 `soul_api.py` 的题目生成逻辑
3. 实现异步题库

### Phase 4: 清理
1. 废弃旧 `soul_api.py`
2. 整合 `prediction_engine.py` 的 Genesis 消费
3. 文档更新

---

## 7. 风险与 Trade-offs

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Token 成本增加 | 每次调用多 ~200 token | 宪法切片，按任务类型只注入相关规则 |
| 延迟增加 | Pre-process 增加 ~10ms | 缓存常用配置，异步审计 |
| 人格突变 | 一道极端题改变太多 | EMA 平滑，α=0.15 |
| 宪法冲突人格 | 宪法说极简，人格说详细 | 明确优先级：Constitution > Genome |

---

## 8. 验收标准

- [ ] `@with_soul` 装饰器正常工作
- [ ] Tony 的人格（67/62/67/50/75/56）正确注入到 LLM
- [ ] 每日校准题能更新 current_genome
- [ ] 禁止行为被正确拦截
- [ ] Token 增量 < 300/调用
