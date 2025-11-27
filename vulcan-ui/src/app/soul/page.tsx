"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import DashboardLayout from "@/components/layout/DashboardLayout";
import TwinDashboard from "@/components/soul/TwinDashboard";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Soul 页面 - 数字孪生仪表盘
 */
export default function SoulPage() {
  const [isLoading, setIsLoading] = useState(true);
  const { user, isAuthenticated, loading, genesisCompleted } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    if (!genesisCompleted) {
      router.push('/calibration');
      return;
    }

    setIsLoading(false);
  }, [isAuthenticated, loading, genesisCompleted, router]);

  // 认证加载中
  if (loading) {
    return (
      <div className="h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border border-red-500/50 border-t-red-500 rounded-md animate-spin mx-auto mb-4" />
          <p className="text-zinc-600 text-xs font-mono tracking-wider">VERIFYING...</p>
        </div>
      </div>
    );
  }

  // 数据加载中
  if (isLoading || !user) {
    return (
      <div className="h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border border-red-500/50 border-t-red-500 rounded-md animate-spin mx-auto mb-4" />
          <p className="text-zinc-600 text-xs font-mono tracking-wider">LOADING TWIN DATA...</p>
        </div>
      </div>
    );
  }

  // 使用 DashboardLayout 包裹
  return (
    <DashboardLayout>
      <TwinDashboard userId={user.user_id} />
    </DashboardLayout>
  );
}
