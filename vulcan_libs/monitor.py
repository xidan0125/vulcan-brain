# vulcan_libs/monitor.py
"""
Vulcan Brain - 算力探针 (Compute Monitor)

职责：
1. 实时读取 NVIDIA GPU 状态（Load, VRAM, Temperature）
2. 提供轻量级 JSON API（非阻塞）
3. 支持多 GPU 环境（自动检测所有可用 GPU）

设计原则：
- 非阻塞：使用缓存机制，避免频繁调用 nvidia-smi
- 轻量级：返回精简的 JSON 数据
- 容错性：GPU 不可用时返回 mock 数据
"""

import subprocess
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import threading


@dataclass
class GPUStats:
    """单个 GPU 的状态数据"""
    gpu_id: int
    name: str
    utilization: int          # GPU 使用率 (%)
    memory_used: int          # 已用显存 (MB)
    memory_total: int         # 总显存 (MB)
    memory_percent: float     # 显存使用率 (%)
    temperature: int          # 温度 (°C)
    power_draw: int           # 功耗 (W)
    power_limit: int          # 功耗限制 (W)


class GPUMonitor:
    """GPU 算力监控器"""
    
    def __init__(self, cache_duration: float = 1.0):
        """
        初始化监控器
        
        Args:
            cache_duration: 缓存有效期（秒），避免频繁调用 nvidia-smi
        """
        self.cache_duration = cache_duration
        self._cache: Optional[List[GPUStats]] = None
        self._last_update: float = 0
        self._lock = threading.Lock()
        self._gpu_available = self._check_gpu_availability()
    
    def _check_gpu_availability(self) -> bool:
        """检查 GPU 是否可用"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=count", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _query_nvidia_smi(self) -> List[GPUStats]:
        """
        调用 nvidia-smi 获取 GPU 状态
        
        Returns:
            GPU 状态列表
        """
        if not self._gpu_available:
            return self._get_mock_data()
        
        try:
            # nvidia-smi 查询命令
            query = [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
                "--format=csv,noheader,nounits"
            ]
            
            result = subprocess.run(
                query,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return self._get_mock_data()
            
            # 解析输出
            gpu_stats = []
            for line in result.stdout.strip().split(n):
                if not line.strip():
                    continue
                
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 8:
                    continue
                
                try:
                    memory_used = int(parts[3])
                    memory_total = int(parts[4])
                    memory_percent = (memory_used / memory_total * 100) if memory_total > 0 else 0
                    
                    stat = GPUStats(
                        gpu_id=int(parts[0]),
                        name=parts[1],
                        utilization=int(parts[2]),
                        memory_used=memory_used,
                        memory_total=memory_total,
                        memory_percent=round(memory_percent, 1),
                        temperature=int(parts[5]),
                        power_draw=int(float(parts[6])),
                        power_limit=int(float(parts[7]))
                    )
                    gpu_stats.append(stat)
                except (ValueError, IndexError) as e:
                    print(f"⚠️  [Monitor] 解析 GPU 数据失败: {e}")
                    continue
            
            return gpu_stats if gpu_stats else self._get_mock_data()
        
        except Exception as e:
            print(f"⚠️  [Monitor] nvidia-smi 调用失败: {e}")
            return self._get_mock_data()
    
    def _get_mock_data(self) -> List[GPUStats]:
        """返回 Mock 数据（开发环境或 GPU 不可用时）"""
        return [
            GPUStats(
                gpu_id=0,
                name="RTX 5090 (Mock)",
                utilization=42,
                memory_used=24576,
                memory_total=49152,
                memory_percent=50.0,
                temperature=65,
                power_draw=350,
                power_limit=450
            ),
            GPUStats(
                gpu_id=1,
                name="RTX 5090 (Mock)",
                utilization=38,
                memory_used=20480,
                memory_total=49152,
                memory_percent=41.7,
                temperature=62,
                power_draw=320,
                power_limit=450
            )
        ]
    
    def get_stats(self, force_refresh: bool = False) -> List[GPUStats]:
        """
        获取 GPU 状态（带缓存）
        
        Args:
            force_refresh: 强制刷新缓存
        
        Returns:
            GPU 状态列表
        """
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否有效
            if not force_refresh and self._cache is not None:
                if current_time - self._last_update < self.cache_duration:
                    return self._cache
            
            # 刷新数据
            self._cache = self._query_nvidia_smi()
            self._last_update = current_time
            
            return self._cache
    
    def get_stats_json(self, force_refresh: bool = False) -> str:
        """
        获取 GPU 状态的 JSON 表示
        
        Args:
            force_refresh: 强制刷新缓存
        
        Returns:
            JSON 字符串
        """
        stats = self.get_stats(force_refresh)
        data = {
            "timestamp": time.time(),
            "gpu_count": len(stats),
            "gpus": [asdict(stat) for stat in stats]
        }
        return json.dumps(data, indent=2)
    
    def get_summary(self) -> str:
        """
        获取人类可读的摘要
        
        Returns:
            摘要文本
        """
        stats = self.get_stats()
        
        lines = [f"🖥️  GPU 状态 ({len(stats)} 个 GPU)"]
        
        for stat in stats:
            lines.append(
                f"  GPU {stat.gpu_id} ({stat.name}): "
                f"Load={stat.utilization}% | "
                f"VRAM={stat.memory_used}/{stat.memory_total}MB ({stat.memory_percent}%) | "
                f"Temp={stat.temperature}°C | "
                f"Power={stat.power_draw}/{stat.power_limit}W"
            )
        
        return "\n".join(lines)


# === 全局单例 ===

_global_monitor: Optional[GPUMonitor] = None

def get_monitor() -> GPUMonitor:
    """获取全局监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = GPUMonitor(cache_duration=1.0)
    return _global_monitor


# === 便捷函数 ===

def get_gpu_stats_json() -> str:
    """获取 GPU 状态 JSON（用于 API）"""
    return get_monitor().get_stats_json()


def get_gpu_summary() -> str:
    """获取 GPU 状态摘要（用于日志）"""
    return get_monitor().get_summary()


# === 测试代码 ===
if __name__ == "__main__":
    print("=== Vulcan GPU Monitor 测试 ===\n")
    
    monitor = GPUMonitor()
    
    # 测试 1: 获取状态
    print("--- 测试 1: 获取 GPU 状态 ---")
    stats = monitor.get_stats()
    print(f"检测到 {len(stats)} 个 GPU\n")
    
    for stat in stats:
        print(f"GPU {stat.gpu_id}: {stat.name}")
        print(f"  利用率: {stat.utilization}%")
        print(f"  显存: {stat.memory_used}/{stat.memory_total} MB ({stat.memory_percent}%)")
        print(f"  温度: {stat.temperature}°C")
        print(f"  功耗: {stat.power_draw}/{stat.power_limit} W")
        print()
    
    # 测试 2: JSON 输出
    print("--- 测试 2: JSON 输出 ---")
    json_data = monitor.get_stats_json()
    print(json_data)
    
    # 测试 3: 摘要
    print("\n--- 测试 3: 摘要 ---")
    print(monitor.get_summary())
    
    # 测试 4: 缓存机制
    print("\n--- 测试 4: 缓存机制 ---")
    import time
    start = time.time()
    monitor.get_stats()  # 第一次调用，查询 nvidia-smi
    t1 = time.time() - start
    
    start = time.time()
    monitor.get_stats()  # 第二次调用，使用缓存
    t2 = time.time() - start
    
    print(f"首次查询: {t1*1000:.2f}ms")
    print(f"缓存查询: {t2*1000:.2f}ms")
    print(f"加速比: {t1/t2:.1f}x")
    
    print("\n✅ 测试完成")
