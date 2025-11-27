"use client";

import { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Target, Star, Wrench, Moon, ChevronRight,
  Activity, AlertTriangle, CheckCircle2, Clock,
  TrendingUp, Mic, Send, Sparkles, ExternalLink
} from "lucide-react";

// ==================== Types ====================
interface Project {
  id: string;
  name: string;
  owner: string;
  ownerAvatar?: string;
  status: "on_track" | "at_risk" | "delayed" | "completed";
  priority: "strategic" | "maintenance" | "backlog";
  progress: number;
  daysOffset: number; // 正数=提前，负数=延期
  aiSummary: string;
  lastUpdate: string;
  commitTrend: number[]; // 火花线数据
}

interface SensorEvent {
  time: string;
  message: string;
  type: "info" | "warning" | "success";
}

// ==================== Mock Data ====================
const mockProjects: Project[] = [
  {
    id: "1",
    name: "Vulcan Brain V3",
    owner: "Tony",
    status: "on_track",
    priority: "strategic",
    progress: 78,
    daysOffset: 2,
    aiSummary: "本周进度良好。核心Agent模块已完成90%，正在进行API接口联调。预计周五完成第一阶段测试。",
    lastUpdate: "2 小时前",
    commitTrend: [3, 5, 4, 8, 6, 7, 9]
  },
  {
    id: "2",
    name: "飞书数据同步",
    owner: "Jason",
    status: "at_risk",
    priority: "strategic",
    progress: 45,
    daysOffset: -3,
    aiSummary: "主要卡点在飞书API权限审批。已提交申请，预计等待2-3天。建议并行准备Mock数据进行开发。",
    lastUpdate: "30 分钟前",
    commitTrend: [2, 3, 1, 2, 1, 0, 1]
  },
  {
    id: "3",
    name: "移动端适配",
    owner: "Tony",
    status: "delayed",
    priority: "maintenance",
    progress: 20,
    daysOffset: -7,
    aiSummary: "团队精力集中在V3主线。建议暂缓此项目，或外包UI部分。当前阻塞原因：设计稿未定稿。",
    lastUpdate: "1 天前",
    commitTrend: [1, 0, 0, 1, 0, 0, 0]
  },
  {
    id: "4",
    name: "知识库RAG优化",
    owner: "Jason",
    status: "completed",
    priority: "maintenance",
    progress: 100,
    daysOffset: 1,
    aiSummary: "已完成！检索准确率从65%提升至89%。已部署到生产环境。",
    lastUpdate: "3 天前",
    commitTrend: [5, 6, 8, 4, 2, 1, 0]
  }
];

const mockSensorEvents: SensorEvent[] = [
  { time: "10:45", message: "服务器 CPU > 80%，已自动扩容", type: "warning" },
  { time: "10:32", message: "Tony 提交了 3 个 commits", type: "info" },
  { time: "10:15", message: "飞书API测试通过", type: "success" },
  { time: "09:58", message: "Jason 更新了设计稿", type: "info" },
  { time: "09:30", message: "定时任务完成：数据备份", type: "success" },
];

// ==================== Components ====================

// 健康电池组件
function HealthBattery({ projects }: { projects: Project[] }) {
  const onTrack = projects.filter(p => p.status === "on_track" || p.status === "completed").length;
  const atRisk = projects.filter(p => p.status === "at_risk").length;
  const delayed = projects.filter(p => p.status === "delayed").length;
  const total = projects.length;

  return (
    <div className="mb-6">
      <div className="text-sm text-zinc-400 mb-2">Health Status</div>
      <div className="flex h-3 rounded-full overflow-hidden bg-zinc-800">
        <div
          className="bg-emerald-500 transition-all"
          style={{ width: `${(onTrack / total) * 100}%` }}
        />
        <div
          className="bg-amber-500 transition-all"
          style={{ width: `${(atRisk / total) * 100}%` }}
        />
        <div
          className="bg-red-500 transition-all"
          style={{ width: `${(delayed / total) * 100}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-zinc-500 mt-2">
        <span>{total} Active</span>
        <span className="text-amber-400">{atRisk} Risk</span>
        <span className="text-red-400">{delayed} Critical</span>
      </div>
    </div>
  );
}

// 项目卡片组件 - Linear 风格
function ProjectCard({ project, onSelect }: { project: Project; onSelect: () => void }) {
  const statusConfig = {
    on_track: { color: "text-emerald-400", bg: "bg-emerald-500/10", label: "On Track" },
    at_risk: { color: "text-amber-400", bg: "bg-amber-500/10", label: "At Risk" },
    delayed: { color: "text-red-400", bg: "bg-red-500/10", label: "Delayed" },
    completed: { color: "text-blue-400", bg: "bg-blue-500/10", label: "Completed" }
  };

  const status = statusConfig[project.status];

  return (
    <div
      onClick={onSelect}
      className="group p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 hover:border-orange-500/50 transition-all cursor-pointer hover:shadow-lg hover:shadow-orange-500/5"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-red-500 flex items-center justify-center text-white text-sm font-bold">
            {project.owner[0]}
          </div>
          <div>
            <h3 className="font-medium text-white group-hover:text-orange-400 transition-colors">
              {project.name}
            </h3>
            <p className="text-xs text-zinc-500">{project.owner} · {project.lastUpdate}</p>
          </div>
        </div>
        <div className={`px-2 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>
          {project.daysOffset > 0 ? `+${project.daysOffset}d` : project.daysOffset === 0 ? "On Time" : `${project.daysOffset}d`}
        </div>
      </div>

      {/* AI Summary */}
      <p className="text-sm text-zinc-400 mb-4 line-clamp-2">
        {project.aiSummary}
      </p>

      {/* Progress & Sparkline */}
      <div className="flex items-center justify-between">
        <div className="flex-1 mr-4">
          <div className="flex justify-between text-xs text-zinc-500 mb-1">
            <span>Progress</span>
            <span>{project.progress}%</span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-orange-500 to-red-500 transition-all"
              style={{ width: `${project.progress}%` }}
            />
          </div>
        </div>

        {/* Mini Sparkline */}
        <div className="flex items-end gap-0.5 h-6">
          {project.commitTrend.map((v, i) => (
            <div
              key={i}
              className="w-1 bg-orange-500/60 rounded-full transition-all"
              style={{ height: `${(v / 10) * 100}%`, minHeight: "2px" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// Agent 参谋部 - 今日奏折
function DailyBriefing() {
  return (
    <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 border border-orange-500/20 rounded-xl p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-orange-400" />
        <span className="text-sm font-medium text-orange-400">今日奏折</span>
      </div>
      <p className="text-sm text-zinc-300 leading-relaxed">
        Boss，今天 <span className="text-amber-400 font-medium">飞书数据同步</span> 有延期风险，
        <span className="text-emerald-400 font-medium">Vulcan Brain V3</span> 进展顺利提前2天。
        建议您先关注飞书API权限问题。
      </p>
    </div>
  );
}

// 传感器实时流
function SensorStream({ events }: { events: SensorEvent[] }) {
  const typeStyles = {
    info: "text-zinc-400",
    warning: "text-amber-400",
    success: "text-emerald-400"
  };

  return (
    <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-zinc-400" />
        <span className="text-sm font-medium text-zinc-400">Live Sensor</span>
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
      </div>
      <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin">
        {events.map((event, i) => (
          <div key={i} className="flex gap-2 text-xs">
            <span className="text-zinc-600 font-mono">[{event.time}]</span>
            <span className={typeStyles[event.type]}>{event.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ==================== Main Page ====================
export default function ProjectsPage() {
  const [selectedPriority, setSelectedPriority] = useState<string | null>(null);
  const [voiceActive, setVoiceActive] = useState(false);
  const [command, setCommand] = useState("");

  const filteredProjects = selectedPriority
    ? mockProjects.filter(p => p.priority === selectedPriority)
    : mockProjects;

  const priorityConfig = [
    { key: "strategic", icon: Star, label: "Strategic", color: "text-amber-400" },
    { key: "maintenance", icon: Wrench, label: "Maintenance", color: "text-zinc-400" },
    { key: "backlog", icon: Moon, label: "Backlog", color: "text-zinc-600" }
  ];

  return (
    <DashboardLayout>
      <div className="h-full flex">
        {/* ========== Left: Radar Panel (20%) ========== */}
        <div className="w-[20%] border-r border-zinc-800 p-4 flex flex-col">
          <h1 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-400" />
            War Room
          </h1>
          <p className="text-xs text-zinc-500 mb-6">项目作战室</p>

          {/* Health Battery */}
          <HealthBattery projects={mockProjects} />

          {/* Priority Filter */}
          <div className="space-y-2">
            <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Priority</div>
            {priorityConfig.map(({ key, icon: Icon, label, color }) => {
              const count = mockProjects.filter(p => p.priority === key).length;
              const isActive = selectedPriority === key;

              return (
                <button
                  key={key}
                  onClick={() => setSelectedPriority(isActive ? null : key)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-all ${
                    isActive
                      ? "bg-orange-500/20 text-orange-400 border border-orange-500/30"
                      : "hover:bg-zinc-800 text-zinc-400"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Icon className={`w-4 h-4 ${color}`} />
                    <span className="text-sm">{label}</span>
                  </div>
                  <span className="text-xs bg-zinc-800 px-2 py-0.5 rounded-full">{count}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ========== Middle: Project Feed (50%) ========== */}
        <div className="w-[50%] p-6 overflow-y-auto">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm text-zinc-400 uppercase tracking-wider">
              {selectedPriority ? `${selectedPriority} Projects` : "All Projects"}
            </h2>
            <span className="text-xs text-zinc-600">{filteredProjects.length} items</span>
          </div>

          <div className="space-y-4">
            {filteredProjects.map(project => (
              <ProjectCard
                key={project.id}
                project={project}
                onSelect={() => console.log("Select project:", project.id)}
              />
            ))}
          </div>
        </div>

        {/* ========== Right: Agent Sidebar (30%) ========== */}
        <div className="w-[30%] border-l border-zinc-800 p-4 flex flex-col">
          {/* Daily Briefing */}
          <DailyBriefing />

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            <button className="px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 transition-all flex items-center gap-2">
              <AlertTriangle className="w-3 h-3 text-amber-400" />
              催促进度
            </button>
            <button className="px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 transition-all flex items-center gap-2">
              <ExternalLink className="w-3 h-3" />
              飞书群组
            </button>
          </div>

          {/* Sensor Stream */}
          <SensorStream events={mockSensorEvents} />

          {/* Voice Command */}
          <div className="mt-auto pt-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setVoiceActive(!voiceActive)}
                className={`p-3 rounded-full transition-all ${
                  voiceActive
                    ? "bg-red-500 text-white animate-pulse"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
              >
                <Mic className="w-4 h-4" />
              </button>
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="问问 Vulcan..."
                  className="w-full px-4 py-2 bg-zinc-800/50 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500/50"
                />
                <button className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-zinc-500 hover:text-orange-400 transition-colors">
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
