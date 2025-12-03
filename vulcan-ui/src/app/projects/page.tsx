"use client";

import { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Target, Star, Wrench, Moon, ChevronRight, ChevronDown,
  Activity, AlertTriangle, CheckCircle2, Clock, Plus,
  TrendingUp, Mic, Send, Sparkles, ExternalLink, Users,
  Calendar, BarChart3
} from "lucide-react";

// ==================== Types ====================
interface Task {
  id: string;
  project_id: string;
  title: string;
  assignee_id: string;
  assignee_name: string;
  status: "pending" | "in_progress" | "blocked" | "completed";
  progress: number;
  deadline: string;
  priority: number;
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
  task_count?: number;
  completed_count?: number;
  at_risk_count?: number;
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
  name: string;
  role: string;
}

// ==================== API ====================
const API_BASE = "/api/pm";

async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch(`${API_BASE}/dashboard`);
  return res.json();
}

async function fetchTasks(projectId?: string): Promise<Task[]> {
  const url = projectId ? `${API_BASE}/tasks?project_id=${projectId}` : `${API_BASE}/tasks`;
  const res = await fetch(url);
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

// ==================== Components ====================

// 健康电池
function HealthBattery({ data }: { data: DashboardData }) {
  const { on_track, at_risk, total_projects } = data.summary;
  const delayed = total_projects - on_track - at_risk;

  return (
    <div className="mb-6">
      <div className="text-sm text-zinc-400 mb-2">项目健康度</div>
      <div className="flex h-3 rounded-full overflow-hidden bg-zinc-800">
        <div className="bg-emerald-500" style={{ width: `${(on_track / Math.max(total_projects, 1)) * 100}%` }} />
        <div className="bg-amber-500" style={{ width: `${(at_risk / Math.max(total_projects, 1)) * 100}%` }} />
        <div className="bg-red-500" style={{ width: `${(delayed / Math.max(total_projects, 1)) * 100}%` }} />
      </div>
      <div className="flex justify-between text-xs text-zinc-500 mt-2">
        <span className="text-emerald-400">{on_track} 正常</span>
        <span className="text-amber-400">{at_risk} 风险</span>
        <span className="text-red-400">{delayed} 延期</span>
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
    default: return <Clock className="w-4 h-4 text-zinc-500" />;
  }
}

// 项目卡片(含任务列表)
function ProjectCard({ project, tasks, expanded, onToggle }: {
  project: Project;
  tasks: Task[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const projectTasks = tasks.filter(t => t.project_id === project.id);
  const completedCount = projectTasks.filter(t => t.status === "completed").length;
  const progress = projectTasks.length > 0 ? Math.round((completedCount / projectTasks.length) * 100) : 0;

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
      {/* 项目头部 */}
      <div
        onClick={onToggle}
        className="p-4 cursor-pointer hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {expanded ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
            <div>
              <h3 className="font-medium text-white">{project.name}</h3>
              <p className="text-xs text-zinc-500">{project.owner_name} · {projectTasks.length}个任务</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-medium text-white">{progress}%</div>
            <div className="w-20 h-1.5 bg-zinc-800 rounded-full mt-1">
              <div className="h-full bg-gradient-to-r from-orange-500 to-red-500 rounded-full" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* 任务列表 */}
      {expanded && projectTasks.length > 0 && (
        <div className="border-t border-zinc-800">
          {projectTasks.map(task => (
            <div key={task.id} className="px-4 py-3 flex items-center justify-between hover:bg-zinc-800/30 border-b border-zinc-800/50 last:border-0">
              <div className="flex items-center gap-3">
                <TaskStatusIcon status={task.status} />
                <div>
                  <div className="text-sm text-zinc-300">{task.title}</div>
                  <div className="text-xs text-zinc-500">{task.assignee_name}</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-zinc-400">{task.deadline?.split("T")[0]}</div>
                <div className="text-xs text-zinc-500">{task.progress}%</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// 今日奏折
function DailyBriefing({ data }: { data: DashboardData }) {
  const { overdue_tasks, blocked_tasks } = data;
  const hasIssues = overdue_tasks.length > 0 || blocked_tasks.length > 0;

  return (
    <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 border border-orange-500/20 rounded-xl p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-orange-400" />
        <span className="text-sm font-medium text-orange-400">今日奏折</span>
      </div>
      {hasIssues ? (
        <p className="text-sm text-zinc-300 leading-relaxed">
          Boss，当前有 <span className="text-red-400 font-medium">{overdue_tasks.length}个逾期任务</span>
          {blocked_tasks.length > 0 && <>，<span className="text-amber-400 font-medium">{blocked_tasks.length}个阻塞</span></>}。
          建议优先处理。
        </p>
      ) : (
        <p className="text-sm text-zinc-300">所有项目运转正常，继续保持！</p>
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

// 创建弹窗
function CreateModal({ type, users, projects, onClose, onSubmit }: {
  type: "project" | "task";
  users: User[];
  projects: Project[];
  onClose: () => void;
  onSubmit: (data: any) => void;
}) {
  const [formData, setFormData] = useState<any>({});

  const handleSubmit = () => {
    onSubmit(formData);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 rounded-xl p-6 w-96 border border-zinc-700" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-white mb-4">
          {type === "project" ? "新建项目" : "新建任务"}
        </h3>

        {type === "project" ? (
          <div className="space-y-4">
            <input
              type="text"
              placeholder="项目名称"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => setFormData({ ...formData, name: e.target.value })}
            />
            <input
              type="text"
              placeholder="项目目标"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => setFormData({ ...formData, objective: e.target.value })}
            />
            <select
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => {
                const user = users.find(u => u.id === e.target.value);
                setFormData({ ...formData, owner_id: e.target.value, owner_name: user?.name });
              }}
            >
              <option value="">选择负责人</option>
              {users.filter(u => u.role !== "member").map(u => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>
        ) : (
          <div className="space-y-4">
            <select
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => setFormData({ ...formData, project_id: e.target.value })}
            >
              <option value="">选择项目</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="任务标题"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => setFormData({ ...formData, title: e.target.value })}
            />
            <select
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => {
                const user = users.find(u => u.id === e.target.value);
                setFormData({ ...formData, assignee_id: e.target.value, assignee_name: user?.name });
              }}
            >
              <option value="">选择负责人</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
            <input
              type="date"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
              onChange={e => setFormData({ ...formData, deadline: e.target.value + "T18:00:00" })}
            />
          </div>
        )}

        <div className="flex gap-2 mt-6">
          <button onClick={onClose} className="flex-1 px-4 py-2 bg-zinc-800 text-zinc-400 rounded-lg hover:bg-zinc-700">
            取消
          </button>
          <button onClick={handleSubmit} className="flex-1 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600">
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

// ==================== Main Page ====================
export default function ProjectsPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [createModal, setCreateModal] = useState<"project" | "task" | null>(null);
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

  const handleCreate = async (data: any) => {
    if (createModal === "project") {
      await createProject(data);
    } else {
      await createTask(data);
    }
    loadData();
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
        {/* 顶部标题+操作 */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-orange-400" />
              War Room
            </h1>
            <p className="text-xs text-zinc-500">项目作战室</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setCreateModal("project")}
              className="px-3 py-2 bg-orange-500/20 border border-orange-500/30 rounded-lg text-xs text-orange-400"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={() => setCreateModal("task")}
              className="px-3 py-2 bg-blue-500/20 border border-blue-500/30 rounded-lg text-xs text-blue-400"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 简化统计条 */}
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

        {/* 项目列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {dashboard.projects.map(project => (
            <ProjectCard
              key={project.id}
              project={project}
              tasks={tasks}
              expanded={expandedProjects.has(project.id)}
              onToggle={() => toggleProject(project.id)}
            />
          ))}
        </div>
      </div>

      {/* ===== 桌面端布局 (原样) ===== */}
      <div className="hidden md:flex h-full">
        {/* Left: Radar Panel (20%) */}
        <div className="w-[20%] border-r border-zinc-800 p-4 flex flex-col">
          <h1 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-400" />
            War Room
          </h1>
          <p className="text-xs text-zinc-500 mb-6">项目作战室</p>

          <HealthBattery data={dashboard} />

          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">任务统计</div>
          <QuickStats data={dashboard} />

          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2 mt-4">团队</div>
          <div className="space-y-2">
            {users.filter(u => u.role === "member").map(u => {
              const userTasks = tasks.filter(t => t.assignee_id === u.id);
              return (
                <div key={u.id} className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">{u.name}</span>
                  <span className="text-xs text-zinc-600">{userTasks.length}任务</span>
                </div>
              );
            })}
          </div>
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
              />
            ))}
          </div>
        </div>

        {/* Right: Agent Sidebar (30%) */}
        <div className="w-[30%] border-l border-zinc-800 p-4 flex flex-col">
          <div className="grid grid-cols-2 gap-2 mb-4">
            <button
              onClick={() => setCreateModal("project")}
              className="px-3 py-2 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/30 rounded-lg text-sm text-orange-400 transition-all flex items-center justify-center gap-2"
            >
              <Plus className="w-4 h-4" />
              新项目
            </button>
            <button
              onClick={() => setCreateModal("task")}
              className="px-3 py-2 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 rounded-lg text-sm text-blue-400 transition-all flex items-center justify-center gap-2"
            >
              <Plus className="w-4 h-4" />
              新任务
            </button>
          </div>

          <DailyBriefing data={dashboard} />

          {dashboard.overdue_tasks.length > 0 && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 mb-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <span className="text-sm font-medium text-red-400">逾期任务 ({dashboard.overdue_tasks.length})</span>
              </div>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {dashboard.overdue_tasks.slice(0, 5).map(t => (
                  <div key={t.id} className="text-xs text-zinc-400">
                    {t.title} - {t.assignee_name}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 mt-auto">
            <button className="px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 transition-all flex items-center gap-2">
              <Send className="w-3 h-3" />
              催进度
            </button>
            <button className="px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 transition-all flex items-center gap-2">
              <ExternalLink className="w-3 h-3" />
              飞书群
            </button>
          </div>
        </div>
      </div>

      {createModal && (
        <CreateModal
          type={createModal}
          users={users}
          projects={dashboard.projects}
          onClose={() => setCreateModal(null)}
          onSubmit={handleCreate}
        />
      )}
    </DashboardLayout>
  );
}
