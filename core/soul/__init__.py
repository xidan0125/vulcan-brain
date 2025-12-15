"""
Vulcan Brain - Soul Module (一级核心模块)

Soul 是 AI 的"人格层"，决定了：
- WHO: AI 是谁（人格、身份）
- WHAT: 能做什么、不能做什么（红线）
- HOW: 怎么说话（风格、语气）
- WHY: 为什么这样做（价值观）

核心组件：
- Constitution: 静态宪法（红线、价值观）
- Genome: 动态人格（六维度）
- Interceptor: LLM 调用拦截器
- Calibration: 持续校准系统

使用方式：

    # 方式1: 装饰器（推荐）
    from core.soul import with_soul

    @with_soul(task_type="code")
    async def call_llm(prompt: str, user_id: str):
        ...

    # 方式2: 手动注入
    from core.soul import inject_soul, audit_response

    enhanced = await inject_soul(prompt, user_id="tony")
    response = await llm.call(enhanced)
    result = await audit_response(response, user_id="tony")

    # 方式3: 直接使用组件
    from core.soul import SoulEngine

    soul = SoulEngine(user_id="tony")
    genome = await soul.get_genome()
    system_prompt = soul.build_system_prompt()
"""

__version__ = "2.0.0"

# 核心类型
from core.soul.types import (
    Dimension,
    Genome,
    SoulContext,
    AuditResult,
    CalibrationQuestion,
    CalibrationAnswer,
    DIMENSION_META
)

# 宪法
from core.soul.constitution import Constitution

# 人格管理
from core.soul.genome import (
    GenomeManager,
    get_genome_manager
)

# 拦截器
from core.soul.interceptor import (
    SoulInterceptor,
    with_soul,
    with_soul_sync,
    inject_soul,
    audit_response
)

# 校准引擎
from core.soul.calibration.engine import (
    CalibrationEngine,
    AdaptiveCalibrationEngine,
    get_calibration_engine
)

__all__ = [
    # 版本
    "__version__",

    # 类型
    "Dimension",
    "Genome",
    "SoulContext",
    "AuditResult",
    "CalibrationQuestion",
    "CalibrationAnswer",
    "DIMENSION_META",

    # 宪法
    "Constitution",

    # 人格
    "GenomeManager",
    "get_genome_manager",

    # 拦截器
    "SoulInterceptor",
    "with_soul",
    "with_soul_sync",
    "inject_soul",
    "audit_response",

    # 校准
    "CalibrationEngine",
    "AdaptiveCalibrationEngine",
    "get_calibration_engine",

    # 门面
    "SoulEngine",
    "get_soul"
]


class SoulEngine:
    """
    Soul 统一门面

    提供简洁的 API 访问所有 Soul 功能
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._constitution = None
        self._genome_mgr = None
        self._interceptor = None
        self._calibration = None

    @property
    def constitution(self) -> Constitution:
        if self._constitution is None:
            self._constitution = Constitution()
        return self._constitution

    @property
    def genome_manager(self) -> GenomeManager:
        if self._genome_mgr is None:
            self._genome_mgr = get_genome_manager()
        return self._genome_mgr

    @property
    def interceptor(self) -> SoulInterceptor:
        if self._interceptor is None:
            self._interceptor = SoulInterceptor()
        return self._interceptor

    @property
    def calibration(self) -> CalibrationEngine:
        if self._calibration is None:
            self._calibration = get_calibration_engine()
        return self._calibration

    async def get_genome(self) -> Genome:
        """获取用户当前人格"""
        return await self.genome_manager.get(self.user_id)

    async def update_genome(self, genome: Genome):
        """更新用户人格"""
        await self.genome_manager.update(self.user_id, genome)

    def describe_genome(self, genome: Genome) -> str:
        """描述人格特征"""
        return self.genome_manager.describe(genome)

    async def inject(self, prompt: str, task_type: str = "general") -> str:
        """注入 Soul 到 prompt"""
        genome = await self.get_genome()
        context = SoulContext(
            user_id=self.user_id,
            genome=genome,
            task_type=task_type
        )
        return await self.interceptor.pre_process(prompt, context)

    async def audit(self, response: str, task_type: str = "general") -> AuditResult:
        """审计 LLM 响应"""
        genome = await self.get_genome()
        context = SoulContext(
            user_id=self.user_id,
            genome=genome,
            task_type=task_type
        )
        return self.interceptor.post_process(response, context)

    def build_system_prompt(self, task_type: str = "general") -> str:
        """构建系统提示词"""
        # 同步版本，使用默认人格
        genome = Genome()  # 需要异步获取时使用 get_genome()
        context = SoulContext(
            user_id=self.user_id,
            genome=genome,
            task_type=task_type
        )
        return self.interceptor.build_system_prompt(context)

    def get_red_lines(self) -> list:
        """获取禁止行为列表"""
        return self.constitution.get_prohibited_actions()


# 全局单例
_soul_instances = {}


def get_soul(user_id: str = "default") -> SoulEngine:
    """获取 Soul 实例（单例模式，按用户缓存）"""
    if user_id not in _soul_instances:
        _soul_instances[user_id] = SoulEngine(user_id)
    return _soul_instances[user_id]
