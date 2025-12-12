"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  FolderKanban,
  ArrowLeft,
  Target,
  AlertTriangle,
  Users,
  Eye,
  Bell,
  GitBranch,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.vsg-brain.com";

interface Milestone {
  title: string;
  project: string;
  due_date: string;
  status: string;
  risk_level: "low" | "medium" | "high";
}

interface LeftoverIssue {
  issue: string;
  project: string;
  owner: string;
  blocked_reason: string;
  suggested_action: string;
}

interface ResourceAllocation {
  person: string;
  projects: string[];
  task_count: number;
  workload: "low" | "medium" | "high";
  overloaded: boolean;
}

interface ProjectAttention {
  project: string;
  reason: string;
  risk_factors: string[];
  priority: "low" | "medium" | "high";
}

interface WorkloadWarning {
  person: string;
  warning: string;
  task_count: number;
  deadline_pressure: string;
}

interface CrossDeptRisk {
  risk: string;
  involved_projects: string[];
  involved_people: string[];
  mitigation: string;
}

interface ProjectAnalysis {
  milestones: Milestone[];
  leftover_issues: LeftoverIssue[];
  resource_allocation: ResourceAllocation[];
  projects_needing_attention: ProjectAttention[];
  workload_warnings: WorkloadWarning[];
  cross_department_risks: CrossDeptRisk[];
  summary: string;
}

interface ProjectSummary {
  date: string;
  generated_at: string;
  stats: {
    total_projects: number;
    total_tasks: number;
    completed_tasks: number;
    blocked_tasks: number;
    at_risk_tasks: number;
    in_progress_tasks: number;
  };
  analysis: ProjectAnalysis;
}

// 风险等级颜色
const riskColors = {
  low: "text-green-400 bg-green-500/10",
  medium: "text-yellow-400 bg-yellow-500/10",
  high: "text-red-400 bg-red-500/10",
};

// 可折叠卡片组件
function CollapsibleSection({
  title,
  icon: Icon,
  count,
  children,
  defaultOpen = true,
  color = "purple",
}: {
  title: string;
  icon: React.ElementType;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
  color?: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const colorMap: Record<string, string> = {
    purple: "bg-purple-500/10 text-purple-400",
    red: "bg-red-500/10 text-red-400",
    blue: "bg-blue-500/10 text-blue-400",
    yellow: "bg-yellow-500/10 text-yellow-400",
    green: "bg-green-500/10 text-green-400",
    orange: "bg-orange-500/10 text-orange-400",
  };

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg ${colorMap[color]} flex items-center justify-center`}>
            <Icon className="w-4 h-4" />
          </div>
          <span className="font-medium text-white">{title}</span>
          <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full">
            {count}
          </span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-zinc-500" />
        ) : (
          <ChevronDown className="w-4 h-4 text-zinc-500" />
        )}
      </button>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

export default function ProjectsDailyReportPage() {
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 默认昨天
  const [date, setDate] = useState(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.toISOString().split("T")[0];
  });

  const maxDate = (() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.toISOString().split("T")[0];
  })();

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/projects/summary?date=${date}`);
      const data = await res.json();
      if (data.summary) {
        setSummary(data.summary);
      } else {
        setSummary(null);
      }
    } catch (e) {
      setError("加载失败");
    } finally {
      setLoading(false);
    }
  };

  const generateSummary = async () => {
    setGenerating(true);
    try {
      await fetch(`${API_BASE}/api/info-hub/projects/summary/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date }),
      });
      // 等待生成完成
      setTimeout(() => {
        fetchSummary();
        setGenerating(false);
      }, 5000);
    } catch (e) {
      setError("生成失败");
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [date]);

  const analysis = summary?.analysis;
  const stats = summary?.stats;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* 头部 */}
      <Link
        href="/info-hub/daily-report"
        className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        返回日报总览
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <FolderKanban className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">项目工作简报</h1>
            <p className="text-sm text-zinc-500">Asana风格的项目管理日报</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="date"
            value={date}
            max={maxDate}
            onChange={(e) => setDate(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white"
          />
          <button
            onClick={generateSummary}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-white rounded-lg text-sm transition-colors"
          >
            {generating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {generating ? "生成中..." : "生成简报"}
          </button>
        </div>
      </div>

      {/* 加载状态 */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <div className="text-center py-10 text-red-400">{error}</div>
      )}

      {/* 无数据状态 */}
      {!loading && !summary && (
        <div className="text-center py-20 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <div className="w-16 h-16 rounded-full bg-purple-500/10 flex items-center justify-center mx-auto mb-4">
            <FolderKanban className="w-8 h-8 text-purple-400" />
          </div>
          <h3 className="text-lg font-medium text-zinc-400 mb-2">暂无简报数据</h3>
          <p className="text-sm text-zinc-600 mb-4">点击"生成简报"按钮，AI将分析项目数据并生成工作简报</p>
          <button
            onClick={generateSummary}
            disabled={generating}
            className="inline-flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {generating ? "正在生成..." : "生成简报"}
          </button>
        </div>
      )}

      {/* 有数据时显示 */}
      {!loading && summary && analysis && (
        <>
          {/* 统计概览 */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 text-center">
              <div className="text-2xl font-bold text-white">{stats?.total_projects || 0}</div>
              <div className="text-xs text-zinc-500">项目总数</div>
            </div>
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 text-center">
              <div className="text-2xl font-bold text-white">{stats?.total_tasks || 0}</div>
              <div className="text-xs text-zinc-500">任务总数</div>
            </div>
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 text-center">
              <div className="text-2xl font-bold text-green-400">{stats?.completed_tasks || 0}</div>
              <div className="text-xs text-zinc-500">已完成</div>
            </div>
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">{stats?.in_progress_tasks || 0}</div>
              <div className="text-xs text-zinc-500">进行中</div>
            </div>
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 text-center">
              <div className="text-2xl font-bold text-red-400">{stats?.blocked_tasks || 0}</div>
              <div className="text-xs text-zinc-500">已阻塞</div>
            </div>
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 text-center">
              <div className="text-2xl font-bold text-yellow-400">{stats?.at_risk_tasks || 0}</div>
              <div className="text-xs text-zinc-500">有风险</div>
            </div>
          </div>

          {/* AI总结 */}
          {analysis.summary && (
            <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-xl border border-purple-500/20 p-4 mb-6">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                  <Eye className="w-4 h-4 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-purple-300 mb-1">AI 总结</h3>
                  <p className="text-sm text-zinc-300 leading-relaxed">{analysis.summary}</p>
                </div>
              </div>
            </div>
          )}

          {/* 六维度内容 */}
          <div className="space-y-4">
            {/* 1. 本周关键里程碑 */}
            <CollapsibleSection
              title="本周关键里程碑"
              icon={Target}
              count={analysis.milestones?.length || 0}
              color="purple"
            >
              {analysis.milestones?.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {analysis.milestones.map((m, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`px-2 py-0.5 rounded text-xs ${riskColors[m.risk_level]}`}>
                          {m.risk_level === "high" ? "高风险" : m.risk_level === "medium" ? "中风险" : "低风险"}
                        </div>
                        <div>
                          <div className="text-sm text-white">{m.title}</div>
                          <div className="text-xs text-zinc-500">{m.project}</div>
                        </div>
                      </div>
                      <div className="text-xs text-zinc-400">{m.due_date}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 mt-2">暂无即将到期的里程碑</div>
              )}
            </CollapsibleSection>

            {/* 2. 遗留问题清单 */}
            <CollapsibleSection
              title="遗留问题清单"
              icon={AlertTriangle}
              count={analysis.leftover_issues?.length || 0}
              color="red"
            >
              {analysis.leftover_issues?.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {analysis.leftover_issues.map((issue, i) => (
                    <div key={i} className="p-3 bg-zinc-800/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-sm text-white font-medium">{issue.issue}</div>
                        <div className="text-xs text-zinc-500">{issue.owner}</div>
                      </div>
                      {issue.blocked_reason && (
                        <div className="text-xs text-red-400 mb-1">阻塞原因: {issue.blocked_reason}</div>
                      )}
                      {issue.suggested_action && (
                        <div className="text-xs text-green-400">建议: {issue.suggested_action}</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 mt-2">暂无遗留问题</div>
              )}
            </CollapsibleSection>

            {/* 3. 资源分配分析 */}
            <CollapsibleSection
              title="资源分配分析"
              icon={Users}
              count={analysis.resource_allocation?.length || 0}
              color="blue"
            >
              {analysis.resource_allocation?.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {analysis.resource_allocation.map((r, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center text-sm text-white">
                          {r.person.charAt(0)}
                        </div>
                        <div>
                          <div className="text-sm text-white">{r.person}</div>
                          <div className="text-xs text-zinc-500">{r.projects?.join(", ")}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-zinc-400">{r.task_count}个任务</span>
                        {r.overloaded && (
                          <span className="text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded">过载</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 mt-2">暂无资源分配数据</div>
              )}
            </CollapsibleSection>

            {/* 4. 需要重点监控的项目 */}
            <CollapsibleSection
              title="重点监控项目"
              icon={Eye}
              count={analysis.projects_needing_attention?.length || 0}
              color="yellow"
            >
              {analysis.projects_needing_attention?.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {analysis.projects_needing_attention.map((p, i) => (
                    <div key={i} className="p-3 bg-zinc-800/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-sm text-white font-medium">{p.project}</div>
                        <div className={`text-xs px-2 py-0.5 rounded ${riskColors[p.priority]}`}>
                          {p.priority === "high" ? "高优先" : p.priority === "medium" ? "中优先" : "低优先"}
                        </div>
                      </div>
                      <div className="text-xs text-zinc-400">{p.reason}</div>
                      {p.risk_factors?.length > 0 && (
                        <div className="flex gap-1 mt-2 flex-wrap">
                          {p.risk_factors.map((rf, j) => (
                            <span key={j} className="text-xs bg-zinc-700 px-2 py-0.5 rounded text-zinc-300">
                              {rf}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 mt-2">暂无需要重点关注的项目</div>
              )}
            </CollapsibleSection>

            {/* 5. 团队工作量预警 */}
            <CollapsibleSection
              title="工作量预警"
              icon={Bell}
              count={analysis.workload_warnings?.length || 0}
              color="orange"
            >
              {analysis.workload_warnings?.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {analysis.workload_warnings.map((w, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
                      <div>
                        <div className="text-sm text-white">{w.person}</div>
                        <div className="text-xs text-orange-400">{w.warning}</div>
                      </div>
                      <div className="text-xs text-zinc-500">{w.deadline_pressure}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 mt-2">暂无工作量预警</div>
              )}
            </CollapsibleSection>

            {/* 6. 跨部门协作风险点 */}
            <CollapsibleSection
              title="跨部门协作风险"
              icon={GitBranch}
              count={analysis.cross_department_risks?.length || 0}
              color="green"
            >
              {analysis.cross_department_risks?.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {analysis.cross_department_risks.map((cr, i) => (
                    <div key={i} className="p-3 bg-zinc-800/50 rounded-lg">
                      <div className="text-sm text-white mb-2">{cr.risk}</div>
                      <div className="text-xs text-zinc-500">
                        涉及: {cr.involved_projects?.join(", ")} | {cr.involved_people?.join(", ")}
                      </div>
                      {cr.mitigation && (
                        <div className="text-xs text-green-400 mt-1">缓解建议: {cr.mitigation}</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 mt-2">暂无跨部门协作风险</div>
              )}
            </CollapsibleSection>
          </div>

          {/* 生成时间 */}
          <div className="mt-6 text-center text-xs text-zinc-600">
            生成时间: {summary.generated_at ? new Date(summary.generated_at).toLocaleString("zh-CN") : "-"}
          </div>
        </>
      )}
    </div>
  );
}
