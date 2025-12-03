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
  ChevronRight,
} from "lucide-react";
import { useTranslation } from "@/i18n";

interface AgentCard {
  id: string;
  nameKey: string;
  codeKey: string;
  descriptionKey: string;
  icon: React.ComponentType<{ className?: string }>;
  statusKey: string;
  statusParams?: Record<string, string | number>;
  metrics: { labelKey: string; value: string }[];
  href: string;
  status: "active" | "beta" | "coming";
}

export default function Home() {
  const { t } = useTranslation();

  const agents: AgentCard[] = [
    {
      id: "financial",
      nameKey: "agents.financial.name",
      codeKey: "agents.financial.code",
      descriptionKey: "agents.financial.description",
      icon: TrendingUp,
      statusKey: "agents.financial.status",
      statusParams: { count: 3 },
      metrics: [
        { labelKey: "agents.metrics.queriesToday", value: "247" },
        { labelKey: "agents.metrics.alerts", value: "2" },
      ],
      href: "/agents/financial",
      status: "active",
    },
    {
      id: "hr",
      nameKey: "agents.hr.name",
      codeKey: "agents.hr.code",
      descriptionKey: "agents.hr.description",
      icon: Users,
      statusKey: "agents.hr.status",
      metrics: [
        { labelKey: "agents.metrics.profiles", value: "156" },
        { labelKey: "agents.metrics.riskScore", value: "Low" },
      ],
      href: "/agents/hr",
      status: "beta",
    },
    {
      id: "ghostwriter",
      nameKey: "agents.ghostwriter.name",
      codeKey: "agents.ghostwriter.code",
      descriptionKey: "agents.ghostwriter.description",
      icon: PenTool,
      statusKey: "agents.ghostwriter.status",
      statusParams: { count: 3 },
      metrics: [
        { labelKey: "agents.metrics.documents", value: "89" },
        { labelKey: "agents.metrics.accuracy", value: "94%" },
      ],
      href: "/agents/ghostwriter",
      status: "active",
    },
    {
      id: "watchdog",
      nameKey: "agents.watchdog.name",
      codeKey: "agents.watchdog.code",
      descriptionKey: "agents.watchdog.description",
      icon: Bell,
      statusKey: "agents.watchdog.status",
      statusParams: { count: 12 },
      metrics: [
        { labelKey: "agents.metrics.uptime", value: "99.9%" },
        { labelKey: "agents.metrics.latency", value: "23ms" },
      ],
      href: "/agents/watchdog",
      status: "coming",
    },
  ];

  const StatusIndicator = ({ status }: { status: AgentCard["status"] }) => {
    const config = {
      active: { color: "bg-emerald-500", labelKey: "common.online" },
      beta: { color: "bg-amber-500", labelKey: "common.beta" },
      coming: { color: "bg-zinc-500", labelKey: "common.offline" },
    };
    const { color, labelKey } = config[status];
    return (
      <div className="flex items-center gap-1.5">
        <div className={`w-1.5 h-1.5 rounded-full ${color} ${status === "active" ? "animate-pulse" : ""}`} />
        <span className="text-[10px] text-zinc-500 font-mono">{t(labelKey).toUpperCase()}</span>
      </div>
    );
  };

  return (
    <DashboardLayout>
      <div className="h-full overflow-y-auto p-4 md:p-6 bg-[#050505]">
        <div className="max-w-5xl mx-auto space-y-4 md:space-y-6">

          {/* Header */}
          <div className="flex items-center justify-between py-2 md:py-4">
            <div>
              <h1 className="text-lg md:text-xl font-medium text-zinc-200">{t("home.title")}</h1>
              <p className="text-[10px] md:text-xs text-zinc-600 font-mono mt-0.5">{t("home.subtitle")}</p>
            </div>
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-zinc-900/60 border border-white/10 rounded-md">
              <Activity className="w-3 h-3 text-emerald-500" />
              <span className="text-[10px] text-zinc-400 font-mono">{t("home.agentsOnline", { count: 4 })}</span>
            </div>
            {/* 移动端状态指示 */}
            <div className="md:hidden flex items-center gap-1.5">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-[10px] text-zinc-500 font-mono">{t("common.online").toUpperCase()}</span>
            </div>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3">
            {[
              { labelKey: "stats.gpu", value: "5090x2", color: "text-emerald-400" },
              { labelKey: "stats.model", value: "QWEN3", color: "text-blue-400" },
              { labelKey: "stats.vram", value: "48/72GB", color: "text-amber-400" },
              { labelKey: "stats.uptime", value: "99.97%", color: "text-purple-400" },
            ].map((stat, i) => (
              <div
                key={i}
                className="bg-zinc-900/40 border border-white/10 rounded-lg p-3"
              >
                <div className="text-[9px] md:text-[10px] text-zinc-600 font-mono mb-0.5">{t(stat.labelKey)}</div>
                <div className={`text-base md:text-lg font-mono font-medium ${stat.color}`}>{stat.value}</div>
              </div>
            ))}
          </div>

          {/* Separator */}
          <div className="flex items-center gap-3 py-1 md:py-2">
            <div className="h-px flex-1 bg-white/5" />
            <span className="text-[9px] md:text-[10px] font-mono text-zinc-600">{t("agents.title").toUpperCase()}</span>
            <div className="h-px flex-1 bg-white/5" />
          </div>

          {/* Agent Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
            {agents.map((agent) => {
              const Icon = agent.icon;
              return (
                <Link
                  key={agent.id}
                  href={agent.href}
                  className="group bg-zinc-900/40 border border-white/10 rounded-xl p-4 active:bg-zinc-800/50 md:hover:border-orange-500/30 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 md:w-10 md:h-10 bg-zinc-800/80 border border-white/10 rounded-xl flex items-center justify-center shrink-0">
                      <Icon className="w-5 h-5 md:w-4 md:h-4 text-zinc-400 group-active:text-orange-400 md:group-hover:text-orange-400 transition-colors" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <h2 className="text-sm font-medium text-zinc-200">{t(agent.nameKey)}</h2>
                        <StatusIndicator status={agent.status} />
                      </div>
                      <p className="text-[10px] text-zinc-600 font-mono mt-0.5 truncate">
                        {t(agent.statusKey, agent.statusParams)}
                      </p>
                      {/* 指标 */}
                      <div className="flex gap-4 mt-2">
                        {agent.metrics.map((m, idx) => (
                          <div key={idx} className="flex items-baseline gap-1">
                            <span className="text-sm font-mono font-medium text-zinc-300">{m.value}</span>
                            <span className="text-[9px] text-zinc-600">{t(m.labelKey)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-zinc-600 shrink-0 md:hidden" />
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-center gap-2 py-3 md:py-4">
            <div className="w-1 h-1 bg-emerald-500 rounded-full animate-pulse" />
            <span className="text-[9px] md:text-[10px] font-mono text-zinc-700">{t("home.operational").toUpperCase()}</span>
          </div>

        </div>
      </div>
    </DashboardLayout>
  );
}
