"use client";

import { X, Activity, Brain, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

interface InspectorProps {
  isOpen: boolean;
  onClose: () => void;
}

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

// Mock data for demo/external access
const MOCK_STATUS: SystemStatus = {
  gpu: { utilization: 45, temperature: 52, power_draw: 180 },
  vram: { used: 36864, total: 73728, percentage: 50 },
  performance: { tokens_per_second: 42.5, ttft: 0.234, latency: 0.0156, last_query: new Date().toISOString() },
  thinking_process: [
    "> Analyzing context...",
    "> Loading LOD tools...",
    "> Ready to execute"
  ],
  timestamp: new Date().toISOString()
};

export default function Inspector({ isOpen, onClose }: InspectorProps) {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const fetchSystemStatus = async () => {
      try {
        // Try localhost first (for internal access), then Tailscale IP
        const urls = [
          '/api/system/status'
        ];

        let success = false;
        for (const url of urls) {
          try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);
            const response = await fetch(url, {
              method: 'GET',
              headers: { 'Content-Type': 'application/json' },
              signal: controller.signal
            });
            clearTimeout(timeoutId);
            if (response.ok) {
              const data = await response.json();
              setSystemStatus(data);
              setIsLoading(false);
              setIsDemo(false);
              success = true;
              break;
            }
          } catch {
            continue;
          }
        }

        // Fallback to mock data for external/ngrok access
        if (!success) {
          setSystemStatus({
            ...MOCK_STATUS,
            gpu: {
              ...MOCK_STATUS.gpu,
              utilization: 40 + Math.random() * 20,
              temperature: 50 + Math.random() * 10
            },
            performance: {
              ...MOCK_STATUS.performance,
              tokens_per_second: 40 + Math.random() * 10,
              last_query: new Date().toISOString()
            },
            timestamp: new Date().toISOString()
          });
          setIsLoading(false);
          setIsDemo(true);
        }
      } catch (err: any) {
        // Use mock data on any error
        setSystemStatus(MOCK_STATUS);
        setIsLoading(false);
        setIsDemo(true);
      }
    };

    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 3000);
    return () => clearInterval(interval);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="w-96 bg-card border-l border-border flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">Inspector</h2>
          {isDemo && (
            <span className="px-1.5 py-0.5 text-[10px] bg-yellow-500/20 text-yellow-500 rounded">
              DEMO
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-accent rounded-md transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Loading State */}
        {isLoading && (
          <div className="text-center text-muted-foreground text-sm py-8">
            Loading system status...
          </div>
        )}

        {/* Data Display */}
        {systemStatus && !isLoading && (
          <>
            {/* System State */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <Activity className="w-4 h-4" />
                <span>SYSTEM STATE</span>
              </div>
              <div className="bg-background rounded-lg p-3 space-y-2 font-mono text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">GPU:</span>
                  <span className={cn(
                    systemStatus.gpu.utilization > 80 ? "text-emerald-500" :
                    systemStatus.gpu.utilization > 50 ? "text-yellow-500" : "text-blue-500"
                  )}>
                    {systemStatus.gpu.utilization.toFixed(0)}% ({systemStatus.gpu.temperature.toFixed(0)}°C)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Power:</span>
                  <span className="text-secondary">{systemStatus.gpu.power_draw}W</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">VRAM:</span>
                  <span className="text-primary">
                    {(systemStatus.vram.used / 1024).toFixed(1)}GB / {(systemStatus.vram.total / 1024).toFixed(1)}GB
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Tokens/s:</span>
                  <span className="text-secondary">
                    {systemStatus.performance.tokens_per_second.toFixed(1)}
                  </span>
                </div>
              </div>
            </div>

            {/* Thinking Process */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <Brain className="w-4 h-4" />
                <span>THINKING PROCESS</span>
              </div>
              <div className="bg-background rounded-lg p-3 font-mono text-xs text-muted-foreground">
                {systemStatus.thinking_process.length > 0 ? (
                  systemStatus.thinking_process.map((log, idx) => (
                    <p key={idx} className={cn(
                      idx === systemStatus.thinking_process.length - 1 ? "text-primary" : ""
                    )}>
                      {log}
                    </p>
                  ))
                ) : (
                  <p className="text-primary">&gt; Ready to execute</p>
                )}
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <Zap className="w-4 h-4" />
                <span>PERFORMANCE</span>
              </div>
              <div className="bg-background rounded-lg p-3 space-y-2 font-mono text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">TTFT:</span>
                  <span className="text-primary">
                    {systemStatus.performance.ttft.toFixed(3)}s
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Latency:</span>
                  <span className="text-foreground">
                    {systemStatus.performance.latency.toFixed(4)}s
                  </span>
                </div>
                {systemStatus.performance.last_query && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Last Query:</span>
                    <span className="text-emerald-500 text-[10px] truncate max-w-[150px]">
                      {new Date(systemStatus.performance.last_query).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Context Window */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-muted-foreground">
                CONTEXT WINDOW
              </div>
              <div className="bg-background rounded-lg p-3 font-mono text-xs text-muted-foreground">
                <p>Active Tools: 4 core</p>
                <p>VRAM Usage: {systemStatus.vram.percentage}%</p>
                <p className="text-primary mt-2">LOD Mode: Enabled</p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
