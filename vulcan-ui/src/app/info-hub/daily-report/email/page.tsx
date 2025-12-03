"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Mail,
  Calendar,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Star,
  AlertTriangle,
  ListTodo,
  ArrowLeft,
  Sparkles,
  Users,
} from "lucide-react";

interface EmailSummary {
  summary: string;
  action_items: string[];
  vip_updates: string[];
  urgent_matters: string[];
  key_topics: string[];
  sentiment: string;
}

interface EmailStats {
  total: number;
  important: number;
  unread: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function EmailDailyReportPage() {
  const searchParams = useSearchParams();
  const initialDate = searchParams.get("date") || new Date().toISOString().split("T")[0];

  const [date, setDate] = useState(initialDate);
  const [summary, setSummary] = useState<EmailSummary | null>(null);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const fetchData = async (targetDate: string) => {
    setLoading(true);
    try {
      // 并行获取统计和摘要
      const [statsRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/info-hub/email/stats?date=${targetDate}`),
        fetch(`${API_BASE}/info-hub/email/summary/${targetDate}`),
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData.stats);
      }

      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setSummary(summaryData.summary);
      } else {
        setSummary(null);
      }
    } catch (error) {
      console.error("获取邮件日报失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const syncEmails = async () => {
    setGenerating(true);
    try {
      await fetch(`${API_BASE}/info-hub/email/sync?days=1`, { method: "POST" });
      // 等待一小段时间让同步启动
      await new Promise((r) => setTimeout(r, 2000));
      await fetchData(date);
    } catch (error) {
      console.error("同步邮件失败:", error);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchData(date);
  }, [date]);

  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    setDate(current.toISOString().split("T")[0]);
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case "positive": return "text-green-400 bg-green-500/10";
      case "negative": return "text-red-400 bg-red-500/10";
      case "mixed": return "text-amber-400 bg-amber-500/10";
      default: return "text-zinc-400 bg-zinc-500/10";
    }
  };

  const getSentimentLabel = (sentiment: string) => {
    switch (sentiment) {
      case "positive": return "积极";
      case "negative": return "消极";
      case "mixed": return "中性";
      default: return "正常";
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* 返回按钮 + 标题 */}
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
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">邮件日报</h1>
              <p className="text-sm text-zinc-500">Microsoft 365 邮件 AI 分析</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* 日期选择器 */}
            <div className="flex items-center gap-2 bg-zinc-900 rounded-lg p-1">
              <button onClick={() => changeDate(-1)} className="p-2 hover:bg-zinc-800 rounded-md">
                <ChevronLeft className="w-4 h-4 text-zinc-400" />
              </button>
              <div className="flex items-center gap-2 px-3 py-1.5">
                <Calendar className="w-4 h-4 text-amber-400" />
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

            {/* 同步按钮 */}
            <button
              onClick={syncEmails}
              disabled={generating}
              className="flex items-center gap-2 px-4 py-2.5 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 rounded-lg text-sm text-amber-400 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
              同步邮件
            </button>
          </div>
        </div>
      </div>

      {/* 统计概览 */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { icon: Mail, label: "邮件总数", value: stats.total, color: "text-amber-400" },
            { icon: Star, label: "重要邮件", value: stats.important, color: "text-yellow-400" },
            { icon: Mail, label: "未读邮件", value: stats.unread || 0, color: "text-blue-400" },
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

      {/* 加载状态 */}
      {loading && (
        <div className="space-y-4">
          <div className="h-32 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-40 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse" />
            <div className="h-40 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse" />
          </div>
        </div>
      )}

      {/* 无数据 */}
      {!loading && !summary && (
        <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <Mail className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-400">暂无 {date} 的邮件分析</h3>
          <p className="text-sm text-zinc-600 mt-2">点击"同步邮件"获取最新邮件数据</p>
        </div>
      )}

      {/* AI 分析结果 */}
      {!loading && summary && (
        <div className="space-y-4">
          {/* 整体摘要 */}
          <div className="p-5 bg-amber-500/5 rounded-xl border border-amber-500/10">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-sm text-amber-400 font-mono">
                <Sparkles className="w-4 h-4" />
                AI 摘要
              </div>
              {summary.sentiment && (
                <span className={`px-2 py-1 rounded text-xs ${getSentimentColor(summary.sentiment)}`}>
                  情绪: {getSentimentLabel(summary.sentiment)}
                </span>
              )}
            </div>
            <p className="text-sm text-zinc-300 leading-relaxed">{summary.summary}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* 待办事项 */}
            {summary.action_items.length > 0 && (
              <div className="p-4 bg-blue-500/5 rounded-xl border border-blue-500/10">
                <div className="flex items-center gap-2 text-sm text-blue-400 font-mono mb-3">
                  <ListTodo className="w-4 h-4" />
                  待办事项 ({summary.action_items.length})
                </div>
                <ul className="space-y-2">
                  {summary.action_items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* VIP 客户动态 */}
            {summary.vip_updates.length > 0 && (
              <div className="p-4 bg-purple-500/5 rounded-xl border border-purple-500/10">
                <div className="flex items-center gap-2 text-sm text-purple-400 font-mono mb-3">
                  <Star className="w-4 h-4" />
                  VIP 客户动态 ({summary.vip_updates.length})
                </div>
                <ul className="space-y-2">
                  {summary.vip_updates.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400 mt-1.5 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 紧急事项 */}
            {summary.urgent_matters.length > 0 && (
              <div className="p-4 bg-red-500/5 rounded-xl border border-red-500/10">
                <div className="flex items-center gap-2 text-sm text-red-400 font-mono mb-3">
                  <AlertTriangle className="w-4 h-4" />
                  紧急事项 ({summary.urgent_matters.length})
                </div>
                <ul className="space-y-2">
                  {summary.urgent_matters.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 关键话题 */}
            {summary.key_topics.length > 0 && (
              <div className="p-4 bg-emerald-500/5 rounded-xl border border-emerald-500/10">
                <div className="text-sm text-emerald-400 font-mono mb-3">关键话题</div>
                <div className="flex flex-wrap gap-2">
                  {summary.key_topics.map((topic, i) => (
                    <span key={i} className="px-3 py-1 bg-emerald-500/10 text-emerald-300 text-sm rounded-full">
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 查看邮件列表入口 */}
          <Link
            href={`/info-hub/email?date=${date}`}
            className="block p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 hover:border-zinc-700 transition-colors text-center"
          >
            <span className="text-sm text-zinc-400">查看完整邮件列表 →</span>
          </Link>
        </div>
      )}
    </div>
  );
}
