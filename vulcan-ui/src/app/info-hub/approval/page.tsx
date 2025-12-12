"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import {
  FileCheck,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Search,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Filter,
  TrendingUp,
  FileText,
  User,
  Building,
} from "lucide-react";
import InfoHubBreadcrumb from "@/components/info-hub/InfoHubBreadcrumb";

interface ApprovalStats {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  pending_count: number;
}

interface ApprovalSummary {
  date: string;
  total_count: number;
  summary: string;
  highlights: string[];
  pending_attention: string[];
  risks: string[];
  recommendations: string[];
}

interface Dashboard {
  date: string;
  stats: ApprovalStats;
  summary: ApprovalSummary | null;
  pending_count: number;
}

interface Approval {
  instance_code: string;
  approval_code: string;
  approval_name: string;
  status: string;
  user_id: string;
  open_id: string;
  start_time: string;
  end_time: string | null;
  serial_number: string;
}

interface ApprovalDefinition {
  approval_code: string;
  approval_name: string;
  is_external: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: any }> = {
  PENDING: { label: "待审批", color: "text-amber-400", bgColor: "bg-amber-500/10", icon: Clock },
  APPROVED: { label: "已通过", color: "text-green-400", bgColor: "bg-green-500/10", icon: CheckCircle2 },
  REJECTED: { label: "已拒绝", color: "text-red-400", bgColor: "bg-red-500/10", icon: XCircle },
  CANCELED: { label: "已撤销", color: "text-zinc-400", bgColor: "bg-zinc-500/10", icon: AlertCircle },
};

export default function ApprovalPage() {
  const searchParams = useSearchParams();
  const initialDate = searchParams.get("date") || new Date().toISOString().split("T")[0];

  const [date, setDate] = useState(initialDate);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [definitions, setDefinitions] = useState<ApprovalDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  // Filters
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");

  const fetchDashboard = async (targetDate: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/approval/dashboard?date=${targetDate}`);
      if (res.ok) {
        const data = await res.json();
        setDashboard(data);
      }
    } catch (error) {
      console.error("获取仪表盘失败:", error);
    }
  };

  const fetchApprovals = async () => {
    try {
      const params = new URLSearchParams({ limit: "100", date });
      if (filterStatus !== "all") params.append("status", filterStatus);
      if (filterType !== "all") params.append("approval_code", filterType);

      const res = await fetch(`${API_BASE}/api/info-hub/approval/list?${params}`);
      if (res.ok) {
        const data = await res.json();
        setApprovals(data.approvals || []);
      }
    } catch (error) {
      console.error("获取审批列表失败:", error);
    }
  };

  const fetchDefinitions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/approval/definitions`);
      if (res.ok) {
        const data = await res.json();
        setDefinitions(data.definitions || []);
      }
    } catch (error) {
      console.error("获取审批定义失败:", error);
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchDashboard(date), fetchApprovals(), fetchDefinitions()]).finally(() =>
      setLoading(false)
    );
  }, [date]);

  useEffect(() => {
    fetchApprovals();
  }, [filterStatus, filterType]);

  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    setDate(current.toISOString().split("T")[0]);
  };

  const stats = dashboard?.stats;
  const summary = dashboard?.summary;

  // Filter approvals by search term
  const filteredApprovals = approvals.filter(
    (a) =>
      !searchTerm ||
      a.approval_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      a.serial_number.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "-";
    try {
      return new Date(timeStr).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return timeStr;
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* 面包屑 */}
      <InfoHubBreadcrumb items={[{ label: "审批中心" }]} />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <FileCheck className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">审批中心</h1>
            <p className="text-sm text-zinc-500">飞书审批记录与分析</p>
          </div>
        </div>

        {/* Date Selector */}
        <div className="flex items-center gap-2 bg-zinc-900 rounded-lg p-1">
          <button onClick={() => changeDate(-1)} className="p-2 hover:bg-zinc-800 rounded-md">
            <ChevronLeft className="w-4 h-4 text-zinc-400" />
          </button>
          <div className="flex items-center gap-2 px-3 py-1.5">
            <Calendar className="w-4 h-4 text-emerald-400" />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent text-sm text-white focus:outline-none"
            />
          </div>
          <button onClick={() => changeDate(1)} className="p-2 hover:bg-zinc-800 rounded-md">
            <ChevronRight className="w-4 h-4 text-zinc-400" />
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            {
              icon: FileText,
              label: "总审批",
              value: stats.total,
              color: "text-emerald-400",
            },
            {
              icon: Clock,
              label: "待处理",
              value: stats.pending_count,
              color: "text-amber-400",
            },
            {
              icon: CheckCircle2,
              label: "已通过",
              value: stats.by_status?.APPROVED || 0,
              color: "text-green-400",
            },
            {
              icon: XCircle,
              label: "已拒绝",
              value: stats.by_status?.REJECTED || 0,
              color: "text-red-400",
            },
          ].map((stat, idx) => {
            const Icon = stat.icon;
            return (
              <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`w-4 h-4 ${stat.color}`} />
                  <span className="text-xs text-zinc-500">{stat.label}</span>
                </div>
                <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* AI Summary */}
      {summary && summary.summary && (
        <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium text-white">AI 分析摘要</span>
          </div>
          <p className="text-sm text-zinc-300 mb-3">{summary.summary}</p>

          {summary.highlights && summary.highlights.length > 0 && (
            <div className="mb-3">
              <span className="text-xs text-zinc-500 mb-1 block">重点事项</span>
              <div className="flex flex-wrap gap-2">
                {summary.highlights.map((h, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs rounded"
                  >
                    {h}
                  </span>
                ))}
              </div>
            </div>
          )}

          {summary.pending_attention && summary.pending_attention.length > 0 && (
            <div>
              <span className="text-xs text-zinc-500 mb-1 block">需关注</span>
              <div className="flex flex-wrap gap-2">
                {summary.pending_attention.map((p, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 bg-amber-500/10 text-amber-400 text-xs rounded"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filters Row */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        {/* By Type */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-zinc-500" />
          <span className="text-xs text-zinc-500">类型:</span>
          <div className="flex flex-wrap gap-1">
            <button
              onClick={() => setFilterType("all")}
              className={`px-2 py-1 text-xs rounded ${
                filterType === "all"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              全部
            </button>
            {definitions.slice(0, 6).map((def) => (
              <button
                key={def.approval_code}
                onClick={() =>
                  setFilterType(filterType === def.approval_code ? "all" : def.approval_code)
                }
                className={`px-2 py-1 text-xs rounded ${
                  filterType === def.approval_code
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
              >
                {def.approval_name}
              </button>
            ))}
          </div>
        </div>

        {/* By Status */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">状态:</span>
          <div className="flex gap-1">
            <button
              onClick={() => setFilterStatus("all")}
              className={`px-2 py-1 text-xs rounded ${
                filterStatus === "all"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              全部
            </button>
            {Object.entries(STATUS_CONFIG).map(([status, config]) => (
              <button
                key={status}
                onClick={() => setFilterStatus(filterStatus === status ? "all" : status)}
                className={`px-2 py-1 text-xs rounded flex items-center gap-1 ${
                  filterStatus === status
                    ? `${config.bgColor} ${config.color}`
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
              >
                <config.icon className="w-3 h-3" />
                {config.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          type="text"
          placeholder="搜索审批名称、编号..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50"
        />
      </div>

      {/* Approval List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-zinc-800 rounded-lg" />
                  <div>
                    <div className="h-5 w-32 bg-zinc-800 rounded mb-2" />
                    <div className="h-4 w-48 bg-zinc-800/50 rounded" />
                  </div>
                </div>
                <div className="h-6 w-16 bg-zinc-800 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredApprovals.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <FileCheck className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-400">暂无审批数据</h3>
          <p className="text-sm text-zinc-600 mt-2">
            {filterStatus !== "all" || filterType !== "all"
              ? "尝试调整筛选条件"
              : "当天无审批记录"}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredApprovals.map((approval) => {
            const statusConfig = STATUS_CONFIG[approval.status] || STATUS_CONFIG.PENDING;
            const StatusIcon = statusConfig.icon;

            return (
              <div
                key={approval.instance_code}
                className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 hover:border-zinc-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    {/* Type Icon */}
                    <div
                      className={`w-10 h-10 rounded-lg ${statusConfig.bgColor} flex items-center justify-center`}
                    >
                      <FileText className={`w-5 h-5 ${statusConfig.color}`} />
                    </div>

                    {/* Info */}
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-white">{approval.approval_name}</h3>
                        <span className="text-xs text-zinc-600">#{approval.serial_number}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-zinc-500">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {approval.open_id?.slice(-6) || "未知"}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTime(approval.start_time)}
                        </span>
                        {approval.end_time && (
                          <span className="flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            {formatTime(approval.end_time)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Status Badge */}
                  <div
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg ${statusConfig.bgColor}`}
                  >
                    <StatusIcon className={`w-4 h-4 ${statusConfig.color}`} />
                    <span className={`text-sm font-medium ${statusConfig.color}`}>
                      {statusConfig.label}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Stats by Type */}
      {stats && stats.by_type && Object.keys(stats.by_type).length > 0 && (
        <div className="mt-6 p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <div className="flex items-center gap-2 mb-3">
            <Building className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium text-white">按类型分布</span>
          </div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {Object.entries(stats.by_type).map(([type, count]) => (
              <div
                key={type}
                className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50 text-center"
              >
                <div className="text-lg font-bold text-emerald-400">{count as number}</div>
                <div className="text-xs text-zinc-500 truncate">{type}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
