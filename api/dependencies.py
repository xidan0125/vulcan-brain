"""
Vulcan Brain API - 全局依赖
存放被多个 router 共享的依赖：Kernel 实例、GPU 状态等
"""
from typing import Optional, Dict, Any
from config import LLM_MODEL_NAME

# === GPU 监控 ===
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False
    print('[WARNING] GPU monitoring not available, using mock data')

# === Kernel 实例（单例）===
_kernel_instance = None

def get_kernel():
    """
    获取或初始化 Kernel 实例（单例模式）
    延迟导入避免循环依赖
    """
    global _kernel_instance
    
    if _kernel_instance is None:
        print('[INFO] 初始化 Vulcan Kernel...')
        
        try:
            from kernel_codeact import VulcanCodeActKernel
        except ImportError:
            print('[ERROR] kernel_codeact not available')
            return None
        
        from vulcan_libs.registry import ToolRegistry, ToolPackage
        from vulcan_libs.tool_retriever import ToolRetriever
        from tools.function_tools import get_time_tool
        from tools.memory_tools import remember_tool, recall_tool, forget_tool
        from tools.rag_tools import add_document_tool, search_knowledge_tool
        from tools.alignment_tools import record_boss_feedback_tool, get_alignment_summary_tool
        from tools.boss_insight_tool import save_boss_insight_tool
        from tools.search_tools import web_search_tool
        from tools.code_executor import create_code_execution_tool
        
        # 创建工具注册表
        registry = ToolRegistry()
        
        # 核心包（常驻内存）
        registry.register(ToolPackage(
            name='core_tools',
            description='核心基础工具：时间查询、联网搜索、记忆管理',
            tools=[get_time_tool, web_search_tool, remember_tool, recall_tool, forget_tool],
            is_core=True,
            category='foundation'
        ))
        
        # RAG 扩展包
        registry.register(ToolPackage(
            name='rag_pkg',
            description='知识库检索能力：文档添加、语义搜索',
            tools=[add_document_tool, search_knowledge_tool],
            is_core=False,
            category='knowledge'
        ))
        
        # 对齐扩展包
        registry.register(ToolPackage(
            name='alignment_pkg',
            description='价值观对齐工具：记录 Boss 反馈、保存洞察',
            tools=[record_boss_feedback_tool, get_alignment_summary_tool, save_boss_insight_tool],
            is_core=False,
            category='alignment'
        ))
        
        # 代码执行扩展包
        registry.register(ToolPackage(
            name='code_execution_pkg',
            description='代码执行沙箱：执行 Python 代码进行数据处理、计算、筛选和批量操作',
            tools=[create_code_execution_tool()],
            is_core=False,
            category='computation'
        ))
        
        # 创建检索器
        retriever = ToolRetriever(registry, top_k=3)
        
        # 创建内核
        _kernel_instance = VulcanCodeActKernel(
            model=LLM_MODEL_NAME,
            registry=registry,
            retriever=retriever,
            enable_lod=True
        )
        
        print('[INFO] Vulcan Kernel 初始化完成')
    
    return _kernel_instance


def get_gpu_stats() -> Dict[str, Any]:
    """获取 GPU 统计信息"""
    if not GPU_AVAILABLE:
        return {
            'utilization': 85,
            'temperature': 68,
            'power_draw': 380
        }
    
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        power = pynvml.nvmlDeviceGetPowerUsage(handle) // 1000
        
        return {
            'utilization': util.gpu,
            'temperature': temp,
            'power_draw': power
        }
    except Exception as e:
        print(f'[ERROR] GPU stats failed: {e}')
        return {'utilization': 0, 'temperature': 0, 'power_draw': 0}


def get_vram_stats() -> Dict[str, Any]:
    """获取 VRAM 统计信息"""
    if not GPU_AVAILABLE:
        return {
            'used': 18432,
            'total': 24576,
            'percentage': 75
        }
    
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        return {
            'used': mem_info.used // (1024**2),
            'total': mem_info.total // (1024**2),
            'percentage': int((mem_info.used / mem_info.total) * 100)
        }
    except Exception as e:
        print(f'[ERROR] VRAM stats failed: {e}')
        return {'used': 0, 'total': 0, 'percentage': 0}


# === 性能指标（全局状态）===
performance_metrics = {
    'tokens_per_second': 0.0,
    'ttft': 0.0,
    'latency': 0.0,
    'last_query_time': None
}

# === 思考日志 ===
thinking_logs: list = []


def update_performance(tokens_per_sec: float, ttft: float, latency: float):
    """更新性能指标"""
    from datetime import datetime
    performance_metrics['tokens_per_second'] = tokens_per_sec
    performance_metrics['ttft'] = ttft
    performance_metrics['latency'] = latency
    performance_metrics['last_query_time'] = datetime.now().isoformat()


def add_thinking_log(log: dict):
    """添加思考日志"""
    thinking_logs.append(log)
    # 只保留最近 50 条
    if len(thinking_logs) > 50:
        thinking_logs.pop(0)
