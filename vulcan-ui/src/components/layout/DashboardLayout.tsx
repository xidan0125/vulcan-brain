"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "./Sidebar";
import { Settings } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

// 系统状态呼吸灯组件
function SystemBreathingLight() {
  const [status, setStatus] = useState<"normal" | "warning" | "error">("normal");

  // 可以从 API 获取实际系统状态
  useEffect(() => {
    // TODO: 从 /api/system/status 获取真实状态
    // 暂时模拟正常状态
    setStatus("normal");
  }, []);

  const statusColors = {
    normal: "bg-emerald-500 shadow-emerald-500/50",
    warning: "bg-amber-500 shadow-amber-500/50",
    error: "bg-rose-500 shadow-rose-500/50"
  };

  return (
    <Link
      href="/settings/system"
      className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-white/5 transition-colors group"
      title="系统状态 - 点击查看详情"
    >
      <div className={`
        w-2 h-2 rounded-full animate-pulse shadow-lg
        ${statusColors[status]}
      `} />
      <span className="text-xs text-zinc-500 font-mono group-hover:text-zinc-400 transition-colors">
        SYS
      </span>
    </Link>
  );
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const { isAuthenticated, loading, genesisCompleted, checkingCalibration } = useAuth();
  const router = useRouter();

  // 全局保护：未登录 → /login
  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login');
    }
  }, [loading, isAuthenticated, router]);

  // 全局保护：未校准 → /calibration
  useEffect(() => {
    if (!loading && !checkingCalibration && isAuthenticated && !genesisCompleted) {
      router.push('/calibration');
    }
  }, [loading, checkingCalibration, isAuthenticated, genesisCompleted, router]);

  // 认证加载中
  if (loading || checkingCalibration) {
    return (
      <div className="h-screen w-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border border-orange-500/50 border-t-orange-500 rounded-md animate-spin mx-auto mb-4" />
          <p className="text-zinc-600 text-xs font-mono tracking-wider">INITIALIZING...</p>
        </div>
      </div>
    );
  }

  // 未登录（等待跳转）
  if (!isAuthenticated) {
    return (
      <div className="h-screen w-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border border-orange-500/50 border-t-orange-500 rounded-md animate-spin mx-auto mb-4" />
          <p className="text-zinc-600 text-xs font-mono tracking-wider">REDIRECTING...</p>
        </div>
      </div>
    );
  }

  // 未校准（等待跳转）
  if (!genesisCompleted) {
    return (
      <div className="h-screen w-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border border-orange-500/50 border-t-orange-500 rounded-md animate-spin mx-auto mb-4" />
          <p className="text-zinc-600 text-xs font-mono tracking-wider">CALIBRATION REQUIRED</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen bg-[#050505] overflow-hidden">
      {/* Left Sidebar */}
      <Sidebar />

      {/* Main Content Area - 现在占据全部剩余空间 */}
      <div className="flex-1 flex flex-col relative">
        {/* Top Bar - 更精简的设计 */}
        <div className="h-12 border-b border-white/10 flex items-center justify-between px-6 bg-zinc-900/40 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-medium text-zinc-300 tracking-wide">
              VULCAN OPERATIONS CENTER
            </h1>
          </div>

          {/* 右侧：系统呼吸灯 + 设置入口 */}
          <div className="flex items-center gap-2">
            <SystemBreathingLight />
            <Link
              href="/settings"
              className="p-2 hover:bg-white/5 rounded-md transition-colors text-zinc-500 hover:text-zinc-300"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Main Stage - 全宽显示 */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
