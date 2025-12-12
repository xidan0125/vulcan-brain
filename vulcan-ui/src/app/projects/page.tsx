"use client";

import { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Target, ChevronRight, ChevronDown,
  AlertTriangle, CheckCircle2, Clock, Plus,
  Send, Sparkles, ExternalLink, MessageCircle,
  HelpCircle, XCircle, TrendingUp, Bell,
  Search, X, User, Calendar, Trash2,
  Archive, RotateCcw, FolderArchive
} from "lucide-react";

// ==================== Types ====================
interface Task {
  id: string;
  project_id: string;
  title: string;
  assignee_feishu_id: string;
  assignee_name: string;
  status: "pending" | "in_progress" | "blocked" | "completed" | "at_risk";
  progress: number;
  deadline: string;
  priority: number;
  // 新的三层状态模型
  lifecycle_status: "pending" | "in_progress" | "completed";
  response_status: string[];  // 数组: ["accepted", "blocked"] 等
  response_at?: string;
  response_notes?: Array<{ status: string; note: string; at: string }>;
  notified_count?: number;
  last_notified_at?: string;
  // 兼容旧字段
  feedback_status?: string;
  feedback_note?: string;
}

interface Project {
  id: string;
  name: string;
  owner_name: string;
  status: string;
  progress: number;
  health_score: number;
  objective: string;
  created_at: string;
}

interface DashboardData {
  summary: {
    total_projects: number;
    total_tasks: number;
    on_track: number;
    at_risk: number;
  };
  task_stats: {
    pending: number;
    in_progress: number;
    blocked: number;
    completed: number;
  };
  overdue_tasks: Task[];
  blocked_tasks: Task[];
  recent_reports: any[];
  projects: Project[];
}

interface User {
  id: string;
  feishu_open_id: string;
  name: string;
  role: string;
}

// ==================== Health 计算函数 ====================
function calculateHealth(responseStatus: string[]): "healthy" | "at_risk" | "blocked" | "no_response" {
  if (!responseStatus || responseStatus.length === 0) {
    return "no_response";
  }

  // 优先级: blocked > at_risk > on_track > accepted > questioned
  if (responseStatus.includes("blocked")) return "blocked";
  if (responseStatus.includes("at_risk")) return "at_risk";
  if (responseStatus.includes("rejected")) return "blocked";
  if (responseStatus.includes("questioned")) return "at_risk";
  if (responseStatus.includes("on_track")) return "healthy";
  if (responseStatus.includes("accepted")) return "healthy";

  return "no_response";
}

// 获取任务的健康状态（兼容新旧字段）
function getTaskHealth(task: Task): "healthy" | "at_risk" | "blocked" | "no_response" {
  // 优先使用新字段
  if (task.response_status && task.response_status.length > 0) {
    return calculateHealth(task.response_status);
  }
  // 兼容旧字段
  if (task.feedback_status) {
    const map: Record<string, "healthy" | "at_risk" | "blocked" | "no_response"> = {
      "no_response": "no_response",
      "accepted": "healthy",
      "on_track": "healthy",
      "questioned": "at_risk",
      "at_risk": "at_risk",
      "blocked": "blocked",
      "rejected": "blocked"
    };
    return map[task.feedback_status] || "no_response";
  }
  return "no_response";
}

// 获取最新的备注
function getLatestNote(task: Task): string {
  if (task.response_notes && task.response_notes.length > 0) {
    return task.response_notes[task.response_notes.length - 1].note;
  }
  return task.feedback_note || "";
}

// ==================== API ====================
const API_BASE = "/api/pm";

async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch(`${API_BASE}/dashboard`);
  return res.json();
}

async function fetchTasks(): Promise<Task[]> {
  const res = await fetch(`${API_BASE}/tasks`);
  const data = await res.json();
  return data.tasks;
}

async function fetchUsers(): Promise<User[]> {
  const res = await fetch(`${API_BASE}/users`);
  const data = await res.json();
  return data.users;
}

async function createProject(data: any): Promise<any> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  return res.json();
}

async function createTask(data: any): Promise<any> {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  return res.json();
}

async function nudgeTask(taskId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/notify/progress`, {
    method: "POST"
  });
  return res.json();
}

async function deleteProject(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "DELETE"
  });
  return res.json();
}

async function deleteTask(taskId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
    method: "DELETE"
  });
  return res.json();
}

async function archiveProject(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/archive`, {
    method: "PUT"
  });
  return res.json();
}

async function restoreProject(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/restore`, {
    method: "PUT"
  });
  return res.json();
}

async function fetchArchivedProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects/archived`);
  const data = await res.json();
  return data.projects;
}

// ==================== Components ====================

// 健康状态徽章（基于 response_status 数组）
function HealthBadge({ task }: { task: Task }) {
  const health = getTaskHealth(task);
  const note = getLatestNote(task);
  const responseStatus = task.response_status || [];

  const config: Record<string, { color: string; bg: string; icon: any; text: string }> = {
    no_response: { color: "text-zinc-400", bg: "bg-zinc-700", icon: Clock, text: "待回复" },
    healthy: { color: "text-emerald-400", bg: "bg-emerald-500/20", icon: CheckCircle2, text: "正常" },
    at_risk: { color: "text-amber-400", bg: "bg-amber-500/20", icon: AlertTriangle, text: "有风险" },
    blocked: { color: "text-red-400", bg: "bg-red-500/20", icon: XCircle, text: "阻塞" },
  };

  const c = config[health];
  const Icon = c.icon;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {/* 主状态 */}
      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${c.bg} ${c.color}`}>
        <Icon className="w-3 h-3" />
        {c.text}
      </span>

      {/* 备注 */}
      {note && health !== "no_response" && (
        <span className="text-[10px] text-zinc-500 truncate max-w-[100px]" title={note}>
          {note.length > 15 ? note.slice(0, 15) + "..." : note}
        </span>
      )}
    </div>
  );
}

// 任务健康度概览（基于实际任务反馈状态计算）
function TaskHealthOverview({ tasks }: { tasks: Task[] }) {
  // 按任务反馈状态统计
  const blocked = tasks.filter(t => getTaskHealth(t) === "blocked").length;
  const atRisk = tasks.filter(t => getTaskHealth(t) === "at_risk").length;
  const healthy = tasks.filter(t => getTaskHealth(t) === "healthy").length;
  const noResponse = tasks.filter(t => getTaskHealth(t) === "no_response").length;
  const total = tasks.length;

  // 计算健康百分比（排除未响应的）
  const respondedTasks = total - noResponse;
  const healthyPercent = respondedTasks > 0 ? Math.round((healthy / respondedTasks) * 100) : 0;

  // 整体状态判断
  let overallStatus = "正常";
  let statusColor = "text-emerald-400";
  if (blocked > 0) {
    overallStatus = "有阻塞";
    statusColor = "text-red-400";
  } else if (atRisk > 0) {
    overallStatus = "有风险";
    statusColor = "text-amber-400";
  } else if (noResponse === total) {
    overallStatus = "待响应";
    statusColor = "text-zinc-400";
  }

  return (
    <div className="mb-6">
      {/* 核心指标 */}
      <div className="flex items-center justify-between mb-3">
        <span className={`text-lg font-bold ${statusColor}`}>{overallStatus}</span>
        <span className="text-xs text-zinc-500">{total}个任务</span>
      </div>

      {/* 状态分布（全部显示，数字要对得上） */}
      <div className="flex flex-wrap gap-2 mb-3">
        {blocked > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-red-500/10 border border-red-500/30 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs text-red-400 font-medium">{blocked} 阻塞</span>
          </div>
        )}
        {atRisk > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-xs text-amber-400 font-medium">{atRisk} 风险</span>
          </div>
        )}
        {healthy > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-xs text-emerald-400">{healthy} 正常</span>
          </div>
        )}
        {noResponse > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-zinc-700/50 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-zinc-500" />
            <span className="text-xs text-zinc-400">{noResponse} 待回复</span>
          </div>
        )}
      </div>

      {/* 健康度进度条 */}
      <div className="h-2 rounded-full overflow-hidden bg-zinc-800 flex">
        {healthy > 0 && <div className="bg-emerald-500 transition-all" style={{ width: `${(healthy / total) * 100}%` }} />}
        {atRisk > 0 && <div className="bg-amber-500 transition-all" style={{ width: `${(atRisk / total) * 100}%` }} />}
        {blocked > 0 && <div className="bg-red-500 transition-all" style={{ width: `${(blocked / total) * 100}%` }} />}
        {noResponse > 0 && <div className="bg-zinc-600 transition-all" style={{ width: `${(noResponse / total) * 100}%` }} />}
      </div>
    </div>
  );
}

// 任务状态图标
function TaskStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed": return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    case "in_progress": return <Clock className="w-4 h-4 text-blue-400" />;
    case "blocked": return <AlertTriangle className="w-4 h-4 text-red-400" />;
    case "at_risk": return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    default: return <Clock className="w-4 h-4 text-zinc-500" />;
  }
}

// 项目卡片
function ProjectCard({ project, tasks, expanded, onToggle, onAddTask, onDeleteProject, onDeleteTask, onArchiveProject }: {
  project: Project;
  tasks: Task[];
  expanded: boolean;
  onToggle: () => void;
  onAddTask: (projectId: string) => void;
  onDeleteProject: (projectId: string) => void;
  onDeleteTask: (taskId: string) => void;
  onArchiveProject: (projectId: string) => void;
}) {
  const projectTasks = tasks.filter(t => t.project_id === project.id);
  const completedCount = projectTasks.filter(t => t.status === "completed" || t.lifecycle_status === "completed").length;
  const progress = projectTasks.length > 0 ? Math.round((completedCount / projectTasks.length) * 100) : 0;

  // 计算项目健康状态
  const blockedCount = projectTasks.filter(t => getTaskHealth(t) === "blocked").length;
  const atRiskCount = projectTasks.filter(t => getTaskHealth(t) === "at_risk").length;
  const noResponseCount = projectTasks.filter(t => getTaskHealth(t) === "no_response").length;

  // 获取参与人员列表（去重）
  const assignees = [...new Set(projectTasks.map(t => t.assignee_name).filter(Boolean))];

  // 确定项目健康状态和边框颜色
  let healthBorder = "border-zinc-800";
  let healthIndicator = null;
  if (blockedCount > 0) {
    healthBorder = "border-red-500/50";
    healthIndicator = <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" title={`${blockedCount}个阻塞`} />;
  } else if (atRiskCount > 0) {
    healthBorder = "border-amber-500/50";
    healthIndicator = <span className="w-2 h-2 rounded-full bg-amber-500" title={`${atRiskCount}个风险`} />;
  } else if (noResponseCount > 0 && projectTasks.length > 0) {
    healthIndicator = <span className="w-2 h-2 rounded-full bg-zinc-500" title={`${noResponseCount}个未响应`} />;
  } else if (projectTasks.length > 0) {
    healthIndicator = <span className="w-2 h-2 rounded-full bg-emerald-500" title="进展顺利" />;
  }

  return (
    <div className={`bg-zinc-900/50 rounded-xl border ${healthBorder} overflow-hidden transition-colors`}>
      <div onClick={onToggle} className="p-4 cursor-pointer hover:bg-zinc-800/50 transition-colors">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {expanded ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
            <div>
              <div className="flex items-center gap-2">
                {healthIndicator}
                <h3 className="font-medium text-white">{project.name}</h3>
              </div>
              <p className="text-xs text-zinc-500 mt-0.5">
                {assignees.length > 0 ? assignees.slice(0, 3).join(", ") : "暂无成员"}
                {assignees.length > 3 && ` +${assignees.length - 3}`}
                {" · "}
                {completedCount}/{projectTasks.length}完成
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-medium text-white">{progress}%</div>
            <div className="w-20 h-1.5 bg-zinc-800 rounded-full mt-1">
              <div
                className={`h-full rounded-full ${
                  blockedCount > 0 ? "bg-red-500" :
                  atRiskCount > 0 ? "bg-amber-500" :
                  "bg-gradient-to-r from-emerald-500 to-emerald-400"
                }`}
                style={{ width: `${Math.max(progress, 2)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-zinc-800">
          {projectTasks.map(task => (
            <div key={task.id} className="px-4 py-3 hover:bg-zinc-800/30 border-b border-zinc-800/50 group">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <TaskStatusIcon status={task.lifecycle_status || task.status} />
                  <div>
                    <div className="text-sm text-zinc-300">{task.title}</div>
                    <div className="text-xs text-zinc-500">{task.assignee_name}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-xs text-zinc-400">{task.deadline?.split("T")[0]}</div>
                  {/* 删除任务按钮 - hover 时显示 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`确定删除任务「${task.title}」？`)) {
                        onDeleteTask(task.id);
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-red-400 transition-all"
                    title="删除任务"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              {/* 健康状态徽章 */}
              <div className="mt-2 ml-7">
                <HealthBadge task={task} />
              </div>
            </div>
          ))}
          {/* 底部操作栏 */}
          <div className="flex items-center justify-between px-4 py-2 bg-zinc-800/30">
            <button
              onClick={(e) => { e.stopPropagation(); onAddTask(project.id); }}
              className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-blue-400 transition-colors"
            >
              <Plus className="w-4 h-4" />
              添加任务
            </button>
            <div className="flex items-center gap-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`确定归档项目「${project.name}」？\n归档后可在历史项目中查看和恢复。`)) {
                    onArchiveProject(project.id);
                  }
                }}
                className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-blue-400 transition-colors"
              >
                <Archive className="w-4 h-4" />
                归档
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`确定删除项目「${project.name}」？\n这将永久删除该项目及所有任务！`)) {
                    onDeleteProject(project.id);
                  }
                }}
                className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-red-400 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// 今日奏折（基于 health 分组）
function DailyBriefing({ tasks }: { tasks: Task[] }) {
  const noResponse = tasks.filter(t => getTaskHealth(t) === "no_response").length;
  const atRisk = tasks.filter(t => getTaskHealth(t) === "at_risk").length;
  const blocked = tasks.filter(t => getTaskHealth(t) === "blocked").length;

  const hasIssues = noResponse > 0 || atRisk > 0 || blocked > 0;

  return (
    <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 border border-orange-500/20 rounded-xl p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-orange-400" />
        <span className="text-sm font-medium text-orange-400">今日奏折</span>
      </div>
      {hasIssues ? (
        <p className="text-sm text-zinc-300 leading-relaxed">
          Boss，当前有
          {noResponse > 0 && <span className="text-zinc-400"> {noResponse}个未响应</span>}
          {atRisk > 0 && <span className="text-amber-400">，{atRisk}个有风险</span>}
          {blocked > 0 && <span className="text-red-400">，{blocked}个阻塞</span>}
          。建议优先处理。
        </p>
      ) : (
        <p className="text-sm text-zinc-300">所有任务运转正常！</p>
      )}
    </div>
  );
}

// 反馈中心面板（基于 health 分组）
function FeedbackCenter({ tasks, onNudge }: { tasks: Task[]; onNudge: (taskId: string) => void }) {
  // 按 health 分组
  const noResponse = tasks.filter(t => getTaskHealth(t) === "no_response");
  const atRisk = tasks.filter(t => getTaskHealth(t) === "at_risk");
  const blocked = tasks.filter(t => getTaskHealth(t) === "blocked");

  return (
    <div className="space-y-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wider">反馈中心</div>

      {/* 阻塞 - 最高优先级 */}
      {blocked.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm font-medium text-red-400">阻塞告警 ({blocked.length})</span>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {blocked.map(t => (
              <div key={t.id} className="text-xs">
                <div className="text-zinc-300">{t.title} - {t.assignee_name}</div>
                {getLatestNote(t) && (
                  <div className="text-red-400/80 mt-1 pl-2 border-l-2 border-red-500/30">
                    {getLatestNote(t)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 有风险 */}
      {atRisk.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-medium text-amber-400">需关注 ({atRisk.length})</span>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {atRisk.map(t => (
              <div key={t.id} className="text-xs">
                <div className="text-zinc-300">{t.title} - {t.assignee_name}</div>
                {getLatestNote(t) && (
                  <div className="text-amber-400/80 mt-1 pl-2 border-l-2 border-amber-500/30">
                    "{getLatestNote(t)}"
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 未响应 */}
      {noResponse.length > 0 && (
        <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-medium text-zinc-300">未响应 ({noResponse.length})</span>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {noResponse.map(t => (
              <div key={t.id} className="flex items-center justify-between text-xs">
                <div className="text-zinc-400 truncate flex-1">
                  {t.title} - {t.assignee_name}
                </div>
                <button
                  onClick={() => onNudge(t.id)}
                  className="ml-2 px-2 py-1 bg-zinc-700 hover:bg-zinc-600 rounded text-zinc-300 flex items-center gap-1"
                >
                  <Bell className="w-3 h-3" />
                  催
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {noResponse.length === 0 && atRisk.length === 0 && blocked.length === 0 && (
        <div className="text-center py-4 text-zinc-500 text-sm">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500/50" />
          全部正常，无待处理项
        </div>
      )}
    </div>
  );
}

// 团队负载面板（按问题优先排序）
function TeamLoadPanel({ tasks }: { tasks: Task[] }) {
  // 按任务执行人分组（从任务中提取，不依赖users列表）
  const assigneeMap = new Map<string, { name: string; tasks: Task[] }>();

  tasks.forEach(t => {
    if (!t.assignee_name) return;
    const key = t.assignee_feishu_id || t.assignee_name;
    if (!assigneeMap.has(key)) {
      assigneeMap.set(key, { name: t.assignee_name, tasks: [] });
    }
    assigneeMap.get(key)!.tasks.push(t);
  });

  // 转换为数组并按问题数量排序（有问题的排前面）
  const teamMembers = Array.from(assigneeMap.values())
    .map(({ name, tasks: userTasks }) => {
      const blocked = userTasks.filter(t => getTaskHealth(t) === "blocked").length;
      const atRisk = userTasks.filter(t => getTaskHealth(t) === "at_risk").length;
      const noResponse = userTasks.filter(t => getTaskHealth(t) === "no_response").length;
      const healthy = userTasks.filter(t => getTaskHealth(t) === "healthy").length;
      const total = userTasks.length;
      const problemScore = blocked * 100 + atRisk * 10 + noResponse; // 用于排序

      return { name, total, blocked, atRisk, noResponse, healthy, problemScore };
    })
    .sort((a, b) => b.problemScore - a.problemScore); // 问题多的排前面

  if (teamMembers.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">团队负载</div>
      {teamMembers.map(member => {
        // 确定成员状态颜色
        const hasIssue = member.blocked > 0 || member.atRisk > 0;
        const borderClass = member.blocked > 0 ? "border-l-red-500" :
                           member.atRisk > 0 ? "border-l-amber-500" :
                           "border-l-zinc-700";

        return (
          <div key={member.name} className={`flex items-center gap-2 py-1.5 pl-2 border-l-2 ${borderClass}`}>
            {/* 名字 */}
            <span className={`text-sm flex-1 ${hasIssue ? "text-white font-medium" : "text-zinc-400"}`}>
              {member.name}
            </span>

            {/* 状态指示 */}
            <div className="flex items-center gap-1">
              {member.blocked > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] bg-red-500/20 text-red-400 rounded">
                  {member.blocked}阻塞
                </span>
              )}
              {member.atRisk > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] bg-amber-500/20 text-amber-400 rounded">
                  {member.atRisk}风险
                </span>
              )}
              {!hasIssue && member.healthy > 0 && (
                <span className="text-[10px] text-emerald-400">{member.healthy}正常</span>
              )}
              {member.noResponse > 0 && (
                <span className="text-[10px] text-zinc-500">{member.noResponse}待回复</span>
              )}
            </div>

            {/* 任务数 */}
            <span className="text-[10px] text-zinc-600 w-8 text-right">{member.total}个</span>
          </div>
        );
      })}
    </div>
  );
}

// 历史项目面板（归档项目）
function ArchivedProjectsPanel({ onRestore }: { onRestore: (projectId: string) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const loadArchived = async () => {
    if (!expanded) {
      setExpanded(true);
      setLoading(true);
      try {
        const data = await fetchArchivedProjects();
        setProjects(data);
      } catch (e) {
        console.error("Failed to load archived projects:", e);
      } finally {
        setLoading(false);
      }
    } else {
      setExpanded(false);
    }
  };

  return (
    <div className="mt-4 pt-4 border-t border-zinc-800">
      <button
        onClick={loadArchived}
        className="flex items-center justify-between w-full text-left hover:bg-zinc-800/30 rounded-lg px-2 py-1.5 transition-colors"
      >
        <div className="flex items-center gap-2 text-zinc-500">
          <FolderArchive className="w-4 h-4" />
          <span className="text-xs">历史项目</span>
        </div>
        <ChevronRight className={`w-4 h-4 text-zinc-600 transition-transform ${expanded ? "rotate-90" : ""}`} />
      </button>

      {expanded && (
        <div className="mt-2 space-y-1">
          {loading ? (
            <div className="text-xs text-zinc-600 px-2">加载中...</div>
          ) : projects.length === 0 ? (
            <div className="text-xs text-zinc-600 px-2">暂无归档项目</div>
          ) : (
            projects.map(p => (
              <div key={p.id} className="flex items-center justify-between px-2 py-1.5 bg-zinc-800/30 rounded">
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-400 truncate">{p.name}</div>
                  <div className="text-[10px] text-zinc-600">{p.owner_name}</div>
                </div>
                <button
                  onClick={() => {
                    if (confirm(`确定恢复项目「${p.name}」？`)) {
                      onRestore(p.id);
                      setProjects(projects.filter(proj => proj.id !== p.id));
                    }
                  }}
                  className="ml-2 p-1 text-zinc-500 hover:text-emerald-400 transition-colors"
                  title="恢复项目"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// 快捷统计
function QuickStats({ data }: { data: DashboardData }) {
  const { task_stats } = data;
  return (
    <div className="grid grid-cols-2 gap-2 mb-4">
      <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
        <div className="text-2xl font-bold text-white">{task_stats.in_progress}</div>
        <div className="text-xs text-zinc-500">进行中</div>
      </div>
      <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
        <div className="text-2xl font-bold text-emerald-400">{task_stats.completed}</div>
        <div className="text-xs text-zinc-500">已完成</div>
      </div>
      <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
        <div className="text-2xl font-bold text-amber-400">{task_stats.pending}</div>
        <div className="text-xs text-zinc-500">待开始</div>
      </div>
      <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
        <div className="text-2xl font-bold text-red-400">{task_stats.blocked}</div>
        <div className="text-xs text-zinc-500">阻塞</div>
      </div>
    </div>
  );
}

// ==================== 可复用组件：人员选择器 ====================
function UserSelector({ users, selected, onSelect, placeholder = "选择负责人" }: {
  users: User[];
  selected: User | null;
  onSelect: (user: User | null) => void;
  placeholder?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = users.filter(u =>
    u.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="relative">
      {/* 选中状态显示 */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-left flex items-center gap-2 hover:border-zinc-600 transition-colors"
      >
        {selected ? (
          <>
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center text-xs text-white font-medium">
              {selected.name[0]}
            </div>
            <span className="text-white flex-1">{selected.name}</span>
            <button
              onClick={(e) => { e.stopPropagation(); onSelect(null); }}
              className="text-zinc-500 hover:text-zinc-300"
            >
              <X className="w-4 h-4" />
            </button>
          </>
        ) : (
          <>
            <User className="w-4 h-4 text-zinc-500" />
            <span className="text-zinc-500 flex-1">{placeholder}</span>
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          </>
        )}
      </button>

      {/* 下拉列表 */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-50 overflow-hidden">
          {/* 搜索框 */}
          <div className="p-2 border-b border-zinc-700">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="搜索成员..."
                className="w-full pl-8 pr-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500"
                autoFocus
              />
            </div>
          </div>
          {/* 用户列表 */}
          <div className="max-h-48 overflow-y-auto">
            {filtered.length > 0 ? (
              filtered.map(user => (
                <button
                  key={user.id}
                  onClick={() => { onSelect(user); setIsOpen(false); setSearch(""); }}
                  className="w-full px-3 py-2 flex items-center gap-2 hover:bg-zinc-700/50 transition-colors text-left"
                >
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-xs text-white font-medium">
                    {user.name[0]}
                  </div>
                  <span className="text-sm text-zinc-200">{user.name}</span>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-center text-sm text-zinc-500">
                没有找到匹配的成员
              </div>
            )}
          </div>
        </div>
      )}

      {/* 点击外部关闭 */}
      {isOpen && (
        <div className="fixed inset-0 z-40" onClick={() => { setIsOpen(false); setSearch(""); }} />
      )}
    </div>
  );
}

// ==================== 任务行（用于创建面板） ====================
interface TaskDraft {
  id: string;
  title: string;
  assignee: User | null;
  deadline: string;
}

function TaskRow({ task, users, onChange, onRemove }: {
  task: TaskDraft;
  users: User[];
  onChange: (task: TaskDraft) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-start gap-2 p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50 group">
      <div className="flex-1 space-y-2">
        {/* 任务标题 */}
        <input
          type="text"
          value={task.title}
          onChange={e => onChange({ ...task, title: e.target.value })}
          placeholder="任务名称"
          className="w-full px-2 py-1 bg-transparent border-b border-zinc-700 text-white text-sm focus:outline-none focus:border-orange-500 placeholder:text-zinc-500"
        />
        {/* 负责人和截止日期 */}
        <div className="flex gap-2">
          <div className="flex-1">
            <UserSelector
              users={users}
              selected={task.assignee}
              onSelect={user => onChange({ ...task, assignee: user })}
              placeholder="指派给..."
            />
          </div>
          <div className="relative">
            <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
            <input
              type="date"
              value={task.deadline}
              onChange={e => onChange({ ...task, deadline: e.target.value })}
              className="pl-8 pr-2 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white w-36"
            />
          </div>
        </div>
      </div>
      {/* 删除按钮 */}
      <button
        onClick={onRemove}
        className="p-1 text-zinc-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}

// ==================== 草稿缓存 Key ====================
const DRAFT_KEY = "vulcan_project_draft";

interface ProjectDraft {
  projectName: string;
  projectObjective: string;
  ownerFeishuId: string | null;
  tasks: Array<{ id: string; title: string; assigneeFeishuId: string | null; deadline: string }>;
  savedAt: number;
}

function saveDraft(draft: ProjectDraft) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch (e) {
    console.warn("Failed to save draft:", e);
  }
}

function loadDraft(): ProjectDraft | null {
  try {
    const data = localStorage.getItem(DRAFT_KEY);
    if (!data) return null;
    const draft = JSON.parse(data) as ProjectDraft;
    // 24小时过期
    if (Date.now() - draft.savedAt > 24 * 60 * 60 * 1000) {
      localStorage.removeItem(DRAFT_KEY);
      return null;
    }
    return draft;
  } catch (e) {
    return null;
  }
}

function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch (e) {}
}

// ==================== 综合管理面板（已有项目 + 新建项目） ====================
function CreatePanel({ users, projects, existingTasks, onClose, onSubmitProject, onSubmitTask }: {
  users: User[];
  projects: Project[];
  existingTasks: Task[];
  onClose: () => void;
  onSubmitProject: (projectData: any, tasksData: any[]) => void;
  onSubmitTask: (taskData: any) => void;
}) {
  const [activeTab, setActiveTab] = useState<"existing" | "new">("existing");

  // 新项目表单 - 从草稿恢复
  const [projectName, setProjectName] = useState("");
  const [projectObjective, setProjectObjective] = useState("");
  const [projectOwner, setProjectOwner] = useState<User | null>(null);
  const [newTasks, setNewTasks] = useState<TaskDraft[]>([
    { id: "1", title: "", assignee: null, deadline: "" }
  ]);
  const [draftRestored, setDraftRestored] = useState(false);

  // 给已有项目添加任务
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [quickTask, setQuickTask] = useState<TaskDraft>({ id: "quick", title: "", assignee: null, deadline: "" });
  const [projectSearch, setProjectSearch] = useState("");

  // 初始化时恢复草稿
  useEffect(() => {
    const draft = loadDraft();
    if (draft && !draftRestored) {
      // 恢复基本信息
      setProjectName(draft.projectName || "");
      setProjectObjective(draft.projectObjective || "");

      // 恢复负责人（通过 feishu_id 匹配）
      if (draft.ownerFeishuId) {
        const owner = users.find(u => u.feishu_open_id === draft.ownerFeishuId);
        if (owner) setProjectOwner(owner);
      }

      // 恢复任务列表
      if (draft.tasks && draft.tasks.length > 0) {
        const restoredTasks = draft.tasks.map(t => ({
          id: t.id,
          title: t.title,
          assignee: t.assigneeFeishuId ? users.find(u => u.feishu_open_id === t.assigneeFeishuId) || null : null,
          deadline: t.deadline
        }));
        setNewTasks(restoredTasks);
      }

      setDraftRestored(true);
      // 如果有草稿内容，自动切到新建项目 Tab
      if (draft.projectName || draft.tasks?.some(t => t.title)) {
        setActiveTab("new");
      }
    }
  }, [users, draftRestored]);

  // 自动保存草稿（防抖）
  useEffect(() => {
    const timer = setTimeout(() => {
      // 只在有内容时保存
      const hasContent = projectName.trim() || projectObjective.trim() || projectOwner || newTasks.some(t => t.title.trim());
      if (hasContent) {
        saveDraft({
          projectName,
          projectObjective,
          ownerFeishuId: projectOwner?.feishu_open_id || null,
          tasks: newTasks.map(t => ({
            id: t.id,
            title: t.title,
            assigneeFeishuId: t.assignee?.feishu_open_id || null,
            deadline: t.deadline
          })),
          savedAt: Date.now()
        });
      }
    }, 500); // 500ms 防抖
    return () => clearTimeout(timer);
  }, [projectName, projectObjective, projectOwner, newTasks]);

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(projectSearch.toLowerCase())
  );

  const addNewTask = () => {
    setNewTasks([...newTasks, { id: Date.now().toString(), title: "", assignee: null, deadline: "" }]);
  };

  const updateNewTask = (id: string, updated: TaskDraft) => {
    setNewTasks(newTasks.map(t => t.id === id ? updated : t));
  };

  const removeNewTask = (id: string) => {
    if (newTasks.length > 1) {
      setNewTasks(newTasks.filter(t => t.id !== id));
    }
  };

  const handleSubmitNewProject = () => {
    if (!projectName.trim()) {
      alert("请输入项目名称");
      return;
    }
    if (!projectOwner) {
      alert("请选择项目负责人");
      return;
    }
    const validTasks = newTasks.filter(t => t.title.trim() && t.assignee);
    if (validTasks.length === 0) {
      alert("请至少添加一个完整的任务（标题+负责人）");
      return;
    }

    const projectData = {
      name: projectName,
      objective: projectObjective,
      owner_id: projectOwner.feishu_open_id,
      owner_name: projectOwner.name
    };
    const tasksData = validTasks.map(t => ({
      title: t.title,
      assignee_feishu_id: t.assignee!.feishu_open_id,
      assignee_name: t.assignee!.name,
      deadline: t.deadline ? t.deadline + "T18:00:00" : undefined
    }));

    clearDraft(); // 提交成功前清除草稿
    onSubmitProject(projectData, tasksData);
  };

  const handleSubmitQuickTask = () => {
    if (!selectedProject) {
      alert("请选择项目");
      return;
    }
    if (!quickTask.title.trim()) {
      alert("请输入任务名称");
      return;
    }
    if (!quickTask.assignee) {
      alert("请选择负责人");
      return;
    }

    onSubmitTask({
      project_id: selectedProject.id,
      title: quickTask.title,
      assignee_feishu_id: quickTask.assignee.feishu_open_id,
      assignee_name: quickTask.assignee.name,
      deadline: quickTask.deadline ? quickTask.deadline + "T18:00:00" : undefined
    });
  };

  // 获取项目的任务数量
  const getProjectTaskCount = (projectId: string) => {
    return existingTasks.filter(t => t.project_id === projectId).length;
  };

  return (
    <>
      {/* 遮罩 */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* 侧边面板 */}
      <div className="fixed right-0 top-0 bottom-0 w-[520px] bg-zinc-900 border-l border-zinc-800 z-50 flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* 头部 */}
        <div className="p-4 border-b border-zinc-800">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-white">任务管理</h2>
            <button onClick={onClose} className="p-1 text-zinc-500 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
          {/* Tab 切换 */}
          <div className="flex gap-1 p-1 bg-zinc-800 rounded-lg">
            <button
              onClick={() => setActiveTab("existing")}
              className={`flex-1 px-3 py-1.5 text-sm rounded-md transition-colors ${
                activeTab === "existing"
                  ? "bg-zinc-700 text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              已有项目
            </button>
            <button
              onClick={() => setActiveTab("new")}
              className={`flex-1 px-3 py-1.5 text-sm rounded-md transition-colors ${
                activeTab === "new"
                  ? "bg-zinc-700 text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              新建项目
            </button>
          </div>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === "existing" ? (
            /* ===== 已有项目 Tab ===== */
            <div className="p-4 space-y-4">
              {/* 项目搜索 */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <input
                  type="text"
                  value={projectSearch}
                  onChange={e => setProjectSearch(e.target.value)}
                  placeholder="搜索项目..."
                  className="w-full pl-9 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500 text-sm"
                />
              </div>

              {/* 项目列表 */}
              <div className="space-y-2">
                {filteredProjects.map(project => (
                  <div
                    key={project.id}
                    onClick={() => setSelectedProject(project)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      selectedProject?.id === project.id
                        ? "bg-orange-500/10 border-orange-500/50"
                        : "bg-zinc-800/50 border-zinc-700 hover:border-zinc-600"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-white font-medium">{project.name}</span>
                      <span className="text-xs text-zinc-500">{getProjectTaskCount(project.id)} 个任务</span>
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">负责人: {project.owner_name}</div>
                  </div>
                ))}
                {filteredProjects.length === 0 && (
                  <div className="text-center py-8 text-zinc-500 text-sm">
                    {projectSearch ? "没有匹配的项目" : "暂无项目"}
                  </div>
                )}
              </div>

              {/* 选中项目后显示添加任务表单 */}
              {selectedProject && (
                <div className="mt-4 pt-4 border-t border-zinc-700 space-y-3">
                  <div className="flex items-center gap-2 text-sm text-orange-400">
                    <Target className="w-4 h-4" />
                    为「{selectedProject.name}」添加任务
                  </div>
                  <div>
                    <input
                      type="text"
                      value={quickTask.title}
                      onChange={e => setQuickTask({ ...quickTask, title: e.target.value })}
                      placeholder="任务名称..."
                      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500 text-sm"
                    />
                  </div>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <UserSelector
                        users={users}
                        selected={quickTask.assignee}
                        onSelect={(u) => setQuickTask({ ...quickTask, assignee: u })}
                        placeholder="负责人"
                      />
                    </div>
                    <div className="w-32">
                      <div className="relative">
                        <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500 pointer-events-none" />
                        <input
                          type="date"
                          value={quickTask.deadline}
                          onChange={e => setQuickTask({ ...quickTask, deadline: e.target.value })}
                          className="w-full pl-7 pr-2 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-xs focus:outline-none focus:border-orange-500"
                        />
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={handleSubmitQuickTask}
                    className="w-full py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors text-sm font-medium"
                  >
                    添加任务
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* ===== 新建项目 Tab ===== */
            <div className="p-4 space-y-6">
              {/* 项目信息 */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">项目名称 *</label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={e => setProjectName(e.target.value)}
                    placeholder="输入项目名称..."
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">项目目标</label>
                  <input
                    type="text"
                    value={projectObjective}
                    onChange={e => setProjectObjective(e.target.value)}
                    placeholder="简述项目目标..."
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">项目负责人 *</label>
                  <UserSelector
                    users={users}
                    selected={projectOwner}
                    onSelect={setProjectOwner}
                    placeholder="选择项目负责人..."
                  />
                </div>
              </div>

              {/* 分隔线 */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-zinc-800" />
                <span className="text-xs text-zinc-500 uppercase tracking-wider">任务列表</span>
                <div className="flex-1 h-px bg-zinc-800" />
              </div>

              {/* 任务列表 */}
              <div className="space-y-3">
                {newTasks.map(task => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    users={users}
                    onChange={updated => updateNewTask(task.id, updated)}
                    onRemove={() => removeNewTask(task.id)}
                  />
                ))}

                {/* 添加任务按钮 */}
                <button
                  onClick={addNewTask}
                  className="w-full py-2 border border-dashed border-zinc-700 rounded-lg text-sm text-zinc-500 hover:text-orange-400 hover:border-orange-500/50 transition-colors flex items-center justify-center gap-1"
                >
                  <Plus className="w-4 h-4" />
                  添加任务
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 底部按钮 - 只在新建项目 Tab 显示 */}
        {activeTab === "new" && (
          <div className="p-4 border-t border-zinc-800 flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2.5 bg-zinc-800 text-zinc-400 rounded-lg hover:bg-zinc-700 transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSubmitNewProject}
              className="flex-1 px-4 py-2.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors font-medium"
            >
              创建项目
            </button>
          </div>
        )}
      </div>
    </>
  );
}

// ==================== 单独添加任务的面板（在项目内） ====================
function AddTaskPanel({ projectId, projectName, users, onClose, onSubmit }: {
  projectId: string;
  projectName: string;
  users: User[];
  onClose: () => void;
  onSubmit: (taskData: any) => void;
}) {
  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState<User | null>(null);
  const [deadline, setDeadline] = useState("");

  const handleSubmit = () => {
    if (!title.trim()) {
      alert("请输入任务名称");
      return;
    }
    if (!assignee) {
      alert("请选择负责人");
      return;
    }

    onSubmit({
      project_id: projectId,
      title,
      assignee_feishu_id: assignee.id,
      assignee_name: assignee.name,
      deadline: deadline ? deadline + "T18:00:00" : undefined
    });
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-[400px] bg-zinc-900 border-l border-zinc-800 z-50 flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-white">添加任务</h2>
            <p className="text-xs text-zinc-500 mt-0.5">{projectName}</p>
          </div>
          <button onClick={onClose} className="p-1 text-zinc-500 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 p-4 space-y-4">
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">任务名称 *</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="输入任务名称..."
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">负责人 *</label>
            <UserSelector users={users} selected={assignee} onSelect={setAssignee} />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">截止日期</label>
            <input
              type="date"
              value={deadline}
              onChange={e => setDeadline(e.target.value)}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
            />
          </div>
        </div>

        <div className="p-4 border-t border-zinc-800 flex gap-3">
          <button onClick={onClose} className="flex-1 px-4 py-2.5 bg-zinc-800 text-zinc-400 rounded-lg hover:bg-zinc-700">
            取消
          </button>
          <button onClick={handleSubmit} className="flex-1 px-4 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 font-medium">
            添加
          </button>
        </div>
      </div>
    </>
  );
}

// ==================== Main Page ====================
export default function ProjectsPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [addTaskTo, setAddTaskTo] = useState<{ projectId: string; projectName: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [dashData, tasksData, usersData] = await Promise.all([
        fetchDashboard(),
        fetchTasks(),
        fetchUsers()
      ]);
      setDashboard(dashData);
      setTasks(tasksData);
      setUsers(usersData);
    } catch (e) {
      console.error("Failed to load data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const toggleProject = (id: string) => {
    const next = new Set(expandedProjects);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpandedProjects(next);
  };

  // 创建项目+任务（一起创建）
  const handleCreateProjectWithTasks = async (projectData: any, tasksData: any[]) => {
    try {
      // 1. 先创建项目
      const result = await createProject(projectData);
      const project = result?.project;
      if (!project?.id) {
        alert("创建项目失败");
        return;
      }
      // 2. 批量创建任务
      for (const taskData of tasksData) {
        await createTask({ ...taskData, project_id: project.id });
      }
      setShowCreatePanel(false);
      loadData();
    } catch (e) {
      console.error("Create failed:", e);
      alert("创建失败");
    }
  };

  // 单独添加任务（在项目内）
  const handleAddSingleTask = async (taskData: any) => {
    try {
      await createTask(taskData);
      setAddTaskTo(null);
      loadData();
    } catch (e) {
      console.error("Add task failed:", e);
      alert("添加任务失败");
    }
  };

  const handleAddTask = (projectId: string) => {
    const project = dashboard?.projects.find(p => p.id === projectId);
    setAddTaskTo({ projectId, projectName: project?.name || "" });
  };

  const handleNudge = async (taskId: string) => {
    const result = await nudgeTask(taskId);
    if (result.success) {
      alert("催促已发送！");
      loadData();
    }
  };

  // 删除项目
  const handleDeleteProject = async (projectId: string) => {
    try {
      const result = await deleteProject(projectId);
      if (result.success) {
        loadData();
      } else {
        alert("删除项目失败");
      }
    } catch (e) {
      console.error("Delete project failed:", e);
      alert("删除项目失败");
    }
  };

  // 删除任务
  const handleDeleteTask = async (taskId: string) => {
    try {
      const result = await deleteTask(taskId);
      if (result.success) {
        loadData();
      } else {
        alert("删除任务失败");
      }
    } catch (e) {
      console.error("Delete task failed:", e);
      alert("删除任务失败");
    }
  };

  // 归档项目
  const handleArchiveProject = async (projectId: string) => {
    try {
      const result = await archiveProject(projectId);
      if (result.success) {
        loadData();
      } else {
        alert("归档项目失败");
      }
    } catch (e) {
      console.error("Archive project failed:", e);
      alert("归档项目失败");
    }
  };

  // 恢复归档项目
  const handleRestoreProject = async (projectId: string) => {
    try {
      const result = await restoreProject(projectId);
      if (result.success) {
        loadData();
      } else {
        alert("恢复项目失败");
      }
    } catch (e) {
      console.error("Restore project failed:", e);
      alert("恢复项目失败");
    }
  };

  if (loading || !dashboard) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full">
          <div className="text-zinc-500">加载中...</div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      {/* ===== 移动端布局 ===== */}
      <div className="md:hidden h-full flex flex-col bg-[#050505]">
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-orange-400" />
              War Room
            </h1>
            <p className="text-xs text-zinc-500">项目作战室</p>
          </div>
          <button onClick={() => setShowCreatePanel(true)} className="px-3 py-2 bg-orange-500/20 border border-orange-500/30 rounded-lg text-xs text-orange-400 flex items-center gap-1">
            <Plus className="w-4 h-4" />
            新项目
          </button>
        </div>

        <div className="flex justify-around p-3 bg-zinc-900/50 border-b border-zinc-800">
          <div className="text-center">
            <div className="text-lg font-bold text-white">{dashboard.task_stats.in_progress}</div>
            <div className="text-[10px] text-zinc-500">进行中</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-emerald-400">{dashboard.task_stats.completed}</div>
            <div className="text-[10px] text-zinc-500">已完成</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-amber-400">{dashboard.task_stats.pending}</div>
            <div className="text-[10px] text-zinc-500">待开始</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-red-400">{dashboard.task_stats.blocked}</div>
            <div className="text-[10px] text-zinc-500">阻塞</div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {dashboard.projects.map(project => (
            <ProjectCard
              key={project.id}
              project={project}
              tasks={tasks}
              expanded={expandedProjects.has(project.id)}
              onToggle={() => toggleProject(project.id)}
              onAddTask={handleAddTask}
              onDeleteProject={handleDeleteProject}
              onDeleteTask={handleDeleteTask}
              onArchiveProject={handleArchiveProject}
            />
          ))}
        </div>
      </div>

      {/* ===== 桌面端布局 ===== */}
      <div className="hidden md:flex h-full">
        {/* Left: Radar Panel (20%) */}
        <div className="w-[20%] border-r border-zinc-800 p-4 flex flex-col overflow-y-auto">
          <h1 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-400" />
            War Room
          </h1>
          <p className="text-xs text-zinc-500 mb-4">项目作战室</p>

          {/* 任务健康度概览 - 基于实际反馈状态 */}
          <TaskHealthOverview tasks={tasks} />

          {/* 团队负载 - 按问题优先排序 */}
          <TeamLoadPanel tasks={tasks} />

          {/* 历史项目 */}
          <ArchivedProjectsPanel onRestore={handleRestoreProject} />
        </div>

        {/* Middle: Project Feed (50%) */}
        <div className="w-[50%] p-6 overflow-y-auto">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm text-zinc-400 uppercase tracking-wider">
              所有项目 ({dashboard.projects.length})
            </h2>
          </div>

          <div className="space-y-4">
            {dashboard.projects.map(project => (
              <ProjectCard
                key={project.id}
                project={project}
                tasks={tasks}
                expanded={expandedProjects.has(project.id)}
                onToggle={() => toggleProject(project.id)}
                onAddTask={handleAddTask}
                onDeleteProject={handleDeleteProject}
                onDeleteTask={handleDeleteTask}
                onArchiveProject={handleArchiveProject}
              />
            ))}
          </div>
        </div>

        {/* Right: Agent Sidebar (30%) */}
        <div className="w-[30%] border-l border-zinc-800 p-4 flex flex-col overflow-y-auto">
          <button
            onClick={() => setShowCreatePanel(true)}
            className="w-full mb-4 px-3 py-2 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/30 rounded-lg text-sm text-orange-400 transition-all flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            新项目
          </button>

          <DailyBriefing tasks={tasks} />

          <FeedbackCenter tasks={tasks} onNudge={handleNudge} />

          <div className="grid grid-cols-2 gap-2 mt-auto pt-4">
            <button className="px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 transition-all flex items-center gap-2">
              <Send className="w-3 h-3" />
              批量催促
            </button>
            <button className="px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 transition-all flex items-center gap-2">
              <ExternalLink className="w-3 h-3" />
              飞书群
            </button>
          </div>
        </div>
      </div>

      {/* 综合管理面板（已有项目 + 新建项目） */}
      {showCreatePanel && dashboard && (
        <CreatePanel
          users={users}
          projects={dashboard.projects}
          existingTasks={tasks}
          onClose={() => setShowCreatePanel(false)}
          onSubmitProject={handleCreateProjectWithTasks}
          onSubmitTask={handleAddSingleTask}
        />
      )}

      {/* 单独添加任务面板 */}
      {addTaskTo && (
        <AddTaskPanel
          projectId={addTaskTo.projectId}
          projectName={addTaskTo.projectName}
          users={users}
          onClose={() => setAddTaskTo(null)}
          onSubmit={handleAddSingleTask}
        />
      )}
    </DashboardLayout>
  );
}
