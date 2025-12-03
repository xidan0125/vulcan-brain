"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Users,
  Calendar,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  Mail,
  TrendingUp,
  Building,
  Briefcase,
  Search,
  Clock,
} from "lucide-react";

interface DashboardStats {
  total_people: number;
  active_today: number;
  department_count: number;
  function_count: number;
  project_count: number;
}

interface GroupStats {
  name: string;
  count: number;
  active_count: number;
  email_count?: number;
}

interface Dashboard {
  date: string;
  stats: DashboardStats;
  by_department: GroupStats[];
  by_function: GroupStats[];
  by_project: GroupStats[];
}

interface Person {
  user_id: string;
  name: string;
  email?: string;
  department: string;
  function: string;
  ms365_job_title?: string;
  email_sent_total: number;
  email_received_total: number;
  last_active?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function PeopleDailyReportPage() {
  const searchParams = useSearchParams();
  const initialDate = searchParams.get("date") || new Date().toISOString().split("T")[0];

  const [date, setDate] = useState(initialDate);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterDept, setFilterDept] = useState<string>("all");
  const [filterFunc, setFilterFunc] = useState<string>("all");

  const fetchData = async (targetDate: string) => {
    setLoading(true);
    try {
      // Fetch dashboard
      const dashRes = await fetch(`${API_BASE}/api/info-hub/people/dashboard?date=${targetDate}`);
      if (dashRes.ok) {
        const data = await dashRes.json();
        setDashboard(data);
      }

      // Fetch people list
      const params = new URLSearchParams({ limit: "50", sort_by: "activity" });
      if (filterDept !== "all") params.append("department", filterDept);
      if (filterFunc !== "all") params.append("function", filterFunc);
      if (searchTerm) params.append("search", searchTerm);

      const peopleRes = await fetch(`${API_BASE}/api/info-hub/people?${params}`);
      if (peopleRes.ok) {
        const data = await peopleRes.json();
        setPeople(data.people || []);
      }
    } catch (error) {
      console.error("获取人员数据失败:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(date);
  }, [date, filterDept, filterFunc, searchTerm]);

  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    setDate(current.toISOString().split("T")[0]);
  };

  const stats = dashboard?.stats;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/info-hub/daily-report"
          className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          返回日报总览
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-rose-500/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-rose-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">人员日报</h1>
              <p className="text-sm text-zinc-500">组织架构与活跃度</p>
            </div>
          </div>

          {/* Date Selector */}
          <div className="flex items-center gap-2 bg-zinc-900 rounded-lg p-1">
            <button onClick={() => changeDate(-1)} className="p-2 hover:bg-zinc-800 rounded-md">
              <ChevronLeft className="w-4 h-4 text-zinc-400" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5">
              <Calendar className="w-4 h-4 text-rose-400" />
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
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { icon: Users, label: "总人数", value: stats.total_people, color: "text-rose-400" },
            { icon: TrendingUp, label: "今日活跃", value: stats.active_today, color: "text-green-400" },
            { icon: Building, label: "部门", value: stats.department_count || "-", color: "text-blue-400" },
            { icon: Briefcase, label: "职能", value: stats.function_count, color: "text-purple-400" },
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

      {/* Organization View */}
      {dashboard && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* By Department */}
          <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
            <div className="flex items-center gap-2 mb-3">
              <Building className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-white">按部门</span>
            </div>
            <div className="space-y-2">
              {dashboard.by_department.map((dept, idx) => (
                <button
                  key={idx}
                  onClick={() => setFilterDept(filterDept === dept.name ? "all" : dept.name)}
                  className={`w-full p-3 rounded-lg border transition-all text-left ${
                    filterDept === dept.name
                      ? "bg-blue-500/10 border-blue-500/30"
                      : "bg-zinc-800/50 border-zinc-700/50 hover:border-zinc-600"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-white">{dept.name}</span>
                    <span className="text-xs text-zinc-500">{dept.count} 人</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-green-400">{dept.active_count} 活跃</span>
                    {dept.email_count !== undefined && dept.email_count > 0 && (
                      <span className="text-zinc-500">{dept.email_count} 邮件</span>
                    )}
                  </div>
                  <div className="mt-2 h-1 bg-zinc-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${dept.count > 0 ? (dept.active_count / dept.count) * 100 : 0}%` }}
                    />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* By Function */}
          <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
            <div className="flex items-center gap-2 mb-3">
              <Briefcase className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-white">按职能</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {dashboard.by_function.map((func, idx) => (
                <button
                  key={idx}
                  onClick={() => setFilterFunc(filterFunc === func.name ? "all" : func.name)}
                  className={`px-3 py-2 rounded-lg border transition-all ${
                    filterFunc === func.name
                      ? "bg-purple-500/10 border-purple-500/30"
                      : "bg-zinc-800/50 border-zinc-700/50 hover:border-zinc-600"
                  }`}
                >
                  <div className="text-sm text-white">{func.name}</div>
                  <div className="text-xs text-zinc-500">
                    {func.count} 人 · {func.active_count} 活跃
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="搜索姓名、邮箱..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-rose-500/50"
          />
        </div>

        {(filterDept !== "all" || filterFunc !== "all") && (
          <button
            onClick={() => {
              setFilterDept("all");
              setFilterFunc("all");
            }}
            className="px-3 py-1.5 text-sm text-zinc-400 hover:text-white"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse flex items-center gap-4"
            >
              <div className="w-10 h-10 bg-zinc-800 rounded-full" />
              <div className="flex-1">
                <div className="h-4 w-32 bg-zinc-800 rounded mb-2" />
                <div className="h-3 w-48 bg-zinc-800/50 rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No Data */}
      {!loading && people.length === 0 && (
        <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <Users className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-400">暂无人员数据</h3>
          <p className="text-sm text-zinc-600 mt-2">请先同步 MS365 人员数据</p>
        </div>
      )}

      {/* People List */}
      {!loading && people.length > 0 && (
        <div className="space-y-3">
          <div className="text-sm text-zinc-500 mb-2">
            {filterDept !== "all" || filterFunc !== "all"
              ? `筛选结果: ${people.length} 人`
              : `活跃度排行 (${people.length} 人)`}
          </div>
          {people.map((person, idx) => (
            <div
              key={person.user_id}
              className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 flex items-center gap-4"
            >
              {/* Rank */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  idx === 0
                    ? "bg-yellow-500/20 text-yellow-400"
                    : idx === 1
                    ? "bg-zinc-400/20 text-zinc-300"
                    : idx === 2
                    ? "bg-amber-600/20 text-amber-500"
                    : "bg-zinc-800 text-zinc-500"
                }`}
              >
                {idx + 1}
              </div>

              {/* Avatar */}
              <div className="w-10 h-10 rounded-full bg-rose-500/10 flex items-center justify-center">
                <span className="text-rose-400 font-medium">{person.name[0]}</span>
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-white">{person.name}</span>
                  {person.function !== "未定义" && (
                    <span className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">
                      {person.function}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-zinc-500">
                  <span className="flex items-center gap-1">
                    <Building className="w-3 h-3" />
                    {person.department}
                  </span>
                  {person.ms365_job_title && (
                    <span>{person.ms365_job_title}</span>
                  )}
                  {person.last_active && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(person.last_active).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              {/* Email Activity */}
              <div className="text-right">
                <div className="flex items-center gap-1 text-rose-400">
                  <Mail className="w-4 h-4" />
                  <span className="font-medium">
                    {person.email_sent_total}/{person.email_received_total}
                  </span>
                </div>
                <div className="text-[10px] text-zinc-600">发/收邮件</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
