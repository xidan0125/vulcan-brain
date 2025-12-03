"use client";

import DashboardLayout from "@/components/layout/DashboardLayout";
import { Activity, Brain, Zap, Server, Cpu, HardDrive, AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface GPUInfo {
  utilization: number;
  temperature: number;
  power_draw: number;
}

interface VRAMInfo {
  used: number;
  total: number;
  percentage: number;
}

interface PerformanceInfo {
  tokens_per_second: number;
  ttft: number;
  latency: number;
  last_query: string;
}

interface SystemStatus {
  gpu: GPUInfo;
  vram: VRAMInfo;
  performance: PerformanceInfo;
  thinking_process: string[];
  timestamp: string;
}

export default function SystemStatusPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchSystemStatus = async () => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("vulcan_token") : null;
      const response = await fetch("/api/system/status", {
        method: "GET",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
      });

      if (!response.ok) {
        throw new Error(`API 返回 ${response.status}`);
      }

      const data = await response.json();
      setSystemStatus(data);
      setError(null);
      setLastUpdate(new Date());
    } catch (err: any) {
      setError(err.message || "无法连接后端 API");
      setSystemStatus(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <DashboardLayout>
      <div className="h-full overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Server className="w-5 h-5 text-orange-500" />
                <h1 className="text-2xl font-semibold text-zinc-100">System Status</h1>
              </div>
              <p className="text-sm text-zinc-500">
                Vulcan Brain 硬件监控与性能指标
              </p>
            </div>
            <button
              onClick={fetchSystemStatus}
              className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-md text-xs text-zinc-400 transition-colors"
            >
              <RefreshCw className={cn("w-3 h-3", isLoading && "animate-spin")} />
              刷新
            </button>
          </div>

          {/* Error State */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5" />
                <div>
                  <h3 className="text-sm font-semibold text-red-500 mb-1">后端 API 不可用</h3>
                  <p className="text-xs text-zinc-400 mb-2">错误: {error}</p>
                  <p className="text-xs text-zinc-500">
                    请检查: <code className="px-1.5 py-0.5 bg-zinc-800 rounded">GET /api/system/status</code>
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Loading State */}
          {isLoading && !error && (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <div className="w-8 h-8 border border-orange-500/50 border-t-orange-500 rounded-md animate-spin mx-auto mb-4" />
                <p className="text-zinc-600 text-xs font-mono">LOADING...</p>
              </div>
            </div>
          )}

          {/* Data Display */}
          {systemStatus && !error && (
            <>
              {/* Stats Grid */}
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Cpu className="w-4 h-4 text-emerald-500" />
                    <span className="text-xs text-zinc-500 font-mono">GPU UTIL</span>
                  </div>
                  <div className="text-2xl font-bold text-emerald-500">
                    {systemStatus.gpu.utilization.toFixed(0)}%
                  </div>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-4 h-4 text-orange-500" />
                    <span className="text-xs text-zinc-500 font-mono">TEMPERATURE</span>
                  </div>
                  <div className="text-2xl font-bold text-orange-500">
                    {systemStatus.gpu.temperature.toFixed(0)}°C
                  </div>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <HardDrive className="w-4 h-4 text-blue-500" />
                    <span className="text-xs text-zinc-500 font-mono">VRAM</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-500">
                    {(systemStatus.vram.used / 1024).toFixed(1)}GB
                  </div>
                  <div className="text-xs text-zinc-600 mt-1">
                    / {(systemStatus.vram.total / 1024).toFixed(1)}GB
                  </div>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <span className="text-xs text-zinc-500 font-mono">TOKENS/S</span>
                  </div>
                  <div className="text-2xl font-bold text-yellow-500">
                    {systemStatus.performance.tokens_per_second.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* Detailed Panels */}
              <div className="grid grid-cols-2 gap-6">
                {/* GPU Details */}
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Cpu className="w-4 h-4 text-emerald-500" />
                    <h3 className="text-sm font-semibold text-zinc-300">GPU Details</h3>
                  </div>
                  <div className="space-y-3 font-mono text-sm">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Utilization</span>
                      <span className="text-emerald-500">{systemStatus.gpu.utilization.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Temperature</span>
                      <span className="text-orange-500">{systemStatus.gpu.temperature.toFixed(0)}°C</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Power Draw</span>
                      <span className="text-zinc-300">{systemStatus.gpu.power_draw}W</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">VRAM Used</span>
                      <span className="text-blue-500">{systemStatus.vram.percentage}%</span>
                    </div>
                  </div>
                </div>

                {/* Performance Metrics */}
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <h3 className="text-sm font-semibold text-zinc-300">Performance</h3>
                  </div>
                  <div className="space-y-3 font-mono text-sm">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Tokens/Second</span>
                      <span className="text-yellow-500">{systemStatus.performance.tokens_per_second.toFixed(1)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">TTFT</span>
                      <span className="text-zinc-300">{systemStatus.performance.ttft.toFixed(3)}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Latency</span>
                      <span className="text-zinc-300">{systemStatus.performance.latency.toFixed(4)}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Last Query</span>
                      <span className="text-emerald-500 text-xs">
                        {systemStatus.performance.last_query 
                          ? new Date(systemStatus.performance.last_query).toLocaleTimeString()
                          : "N/A"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Thinking Process Log */}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Brain className="w-4 h-4 text-purple-500" />
                  <h3 className="text-sm font-semibold text-zinc-300">System Log</h3>
                </div>
                <div className="bg-black/30 rounded-lg p-4 font-mono text-xs space-y-1">
                  {systemStatus.thinking_process && systemStatus.thinking_process.length > 0 ? (
                    systemStatus.thinking_process.map((log, idx) => (
                      <p key={idx} className={cn(
                        idx === systemStatus.thinking_process.length - 1
                          ? "text-emerald-500"
                          : "text-zinc-500"
                      )}>
                        {log}
                      </p>
                    ))
                  ) : (
                    <p className="text-zinc-500">&gt; System ready</p>
                  )}
                </div>
              </div>

              {/* Footer Info */}
              <div className="flex justify-between items-center text-xs text-zinc-600">
                <span>
                  数据每 3 秒自动刷新 | API: <code className="px-1 py-0.5 bg-zinc-800 rounded">/api/system/status</code>
                </span>
                {lastUpdate && (
                  <span>最后更新: {lastUpdate.toLocaleTimeString()}</span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
