"use client";

import Link from "next/link";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  TrendingUp,
  Users,
  PenTool,
  Bell,
  ArrowRight,
  Activity,
} from "lucide-react";

interface AgentCard {
  id: string;
  name: string;
  code: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  statusText: string;
  metrics: { label: string; value: string }[];
  href: string;
  status: "active" | "beta" | "coming";
}

const agents: AgentCard[] = [
  {
    id: "financial",
    name: "财务投资",
    code: "AGENT.FINANCE",
    description: "直连ERP/数据库，自动生成SQL查询，实时财务分析与智能预警",
    icon: TrendingUp,
    statusText: "Ready | 3 connections",
    metrics: [
      { label: "Queries Today", value: "247" },
      { label: "Alerts", value: "2" },
    ],
    href: "/agents/financial",
    status: "active",
  },
  {
    id: "hr",
    name: "HR管理",
    code: "AGENT.HR",
    description: "员工画像、离职预测、邮件敏感词监控，守护团队稳定的智能助手",
    icon: Users,
    statusText: "Beta | Limited access",
    metrics: [
      { label: "Profiles", value: "156" },
      { label: "Risk Score", value: "Low" },
    ],
    href: "/agents/hr",
    status: "beta",
  },
  {
    id: "ghostwriter",
    name: "替身写作",
    code: "AGENT.GHOST",
    description: "学习您的写作风格，完美模拟老板口吻生成公文、演讲稿、邮件",
    icon: PenTool,
    statusText: "Ready | 3 styles loaded",
    metrics: [
      { label: "Documents", value: "89" },
      { label: "Accuracy", value: "94%" },
    ],
    href: "/agents/ghostwriter",
    status: "active",
  },
  {
    id: "watchdog",
    name: "业务雷达",
    code: "AGENT.RADAR",
    description: "7x24小时监控业务指标，自动发现异常并通过多渠道预警",
    icon: Bell,
    statusText: "Monitoring 12 streams...",
    metrics: [
      { label: "Uptime", value: "99.9%" },
      { label: "Latency", value: "23ms" },
    ],
    href: "/agents/watchdog",
    status: "coming",
  },
];

const StatusIndicator = ({ status }: { status: AgentCard["status"] }) => {
  const config = {
    active: { color: "bg-emerald-500", label: "ONLINE" },
    beta: { color: "bg-amber-500", label: "BETA" },
    coming: { color: "bg-zinc-500", label: "OFFLINE" },
  };
  const { color, label } = config[status];
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-1.5 h-1.5 rounded-sm ${color} ${status === 'active' ? 'animate-pulse' : ''}`} />
      <span className="text-[10px] text-zinc-500 font-mono tracking-wider">{label}</span>
    </div>
  );
};

export default function Home() {
  return (
    <DashboardLayout>
      <div className="h-full overflow-y-auto p-6 bg-[#050505]">
        <div className="max-w-5xl mx-auto space-y-6">

          {/* Header - 更简洁的标题 */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h1 className="text-xl font-medium text-zinc-200 tracking-wide">Command Center</h1>
              <p className="text-xs text-zinc-600 font-mono mt-1">VULCAN BRAIN v3.0 // ALL SYSTEMS NOMINAL</p>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900/60 border border-white/10 rounded-md">
              <Activity className="w-3 h-3 text-emerald-500" />
              <span className="text-[10px] text-zinc-400 font-mono">4 AGENTS DEPLOYED</span>
            </div>
          </div>

          {/* Stats Bar - 精密数据面板 */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "GPU", value: "5090x2", color: "text-emerald-400" },
              { label: "MODEL", value: "QWEN3-TK", color: "text-blue-400" },
              { label: "VRAM", value: "48/72GB", color: "text-amber-400" },
              { label: "UPTIME", value: "99.97%", color: "text-purple-400" },
            ].map((stat, i) => (
              <div
                key={i}
                className="bg-zinc-900/40 backdrop-blur-sm border border-white/10 rounded-md p-3"
              >
                <div className="text-[10px] text-zinc-600 font-mono tracking-wider mb-1">{stat.label}</div>
                <div className={`text-lg font-mono font-medium ${stat.color}`}>{stat.value}</div>
              </div>
            ))}
          </div>

          {/* Separator */}
          <div className="flex items-center gap-3 py-2">
            <div className="h-px flex-1 bg-white/5" />
            <span className="text-[10px] font-mono text-zinc-600 tracking-widest">AGENT PORTALS</span>
            <div className="h-px flex-1 bg-white/5" />
          </div>

          {/* Agent Cards Grid - 实时微型终端风格 */}
          <div className="grid grid-cols-2 gap-4">
            {agents.map((agent) => {
              const Icon = agent.icon;
              return (
                <Link
                  key={agent.id}
                  href={agent.href}
                  className="group bg-zinc-900/40 backdrop-blur-sm border border-white/10 rounded-md p-5 hover:border-orange-500/30 hover:bg-zinc-900/60 transition-all duration-200"
                >
                  {/* Header Row */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 bg-zinc-800/80 border border-white/10 rounded-md flex items-center justify-center">
                        <Icon className="w-4 h-4 text-zinc-400 group-hover:text-orange-400 transition-colors" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h2 className="text-sm font-medium text-zinc-200">{agent.name}</h2>
                          <ArrowRight className="w-3 h-3 text-zinc-600 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 group-hover:text-orange-400 transition-all" />
                        </div>
                        <p className="text-[10px] text-zinc-600 font-mono">{agent.code}</p>
                      </div>
                    </div>
                    <StatusIndicator status={agent.status} />
                  </div>

                  {/* Status Line - 模拟终端输出 */}
                  <div className="bg-zinc-950/50 border border-white/5 rounded px-3 py-2 mb-4">
                    <p className="text-[11px] text-zinc-500 font-mono">
                      <span className="text-zinc-600">&gt;</span> {agent.statusText}
                    </p>
                  </div>

                  {/* Metrics Row */}
                  <div className="flex gap-4">
                    {agent.metrics.map((metric, idx) => (
                      <div key={idx} className="flex-1">
                        <div className="text-[9px] text-zinc-600 font-mono tracking-wider mb-0.5">{metric.label}</div>
                        <div className="text-sm text-zinc-300 font-mono font-medium">{metric.value}</div>
                      </div>
                    ))}
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Footer Status */}
          <div className="flex items-center justify-center gap-2 py-4 text-zinc-700">
            <div className="w-1 h-1 bg-emerald-500 rounded-sm animate-pulse" />
            <span className="text-[10px] font-mono tracking-wider">SYSTEM OPERATIONAL</span>
          </div>

        </div>
      </div>
    </DashboardLayout>
  );
}
