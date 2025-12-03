"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  MessageSquare,
  Calendar,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ListTodo,
  AlertTriangle,
  Users,
  Sparkles,
} from "lucide-react";

interface ChatSummary {
  chat_id: string;
  chat_name: string;
  message_count: number;
  summary: string;
  decisions: string[];
  action_items: string[];
  risks: string[];
  topics: string[];
  activity_level: string;
  sentiment: string;
}

interface ChatData {
  total_chats: number;
  total_messages: number;
  summaries: ChatSummary[];
}

export default function ChatDailyReportPage() {
  const searchParams = useSearchParams();
  const initialDate = searchParams.get("date") || new Date().toISOString().split("T")[0];

  const [date, setDate] = useState(initialDate);
  const [chatData, setChatData] = useState<ChatData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchReport = async (targetDate: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/info-hub/daily/${targetDate}`);
      if (res.ok) {
        const data = await res.json();
        setChatData(data.report?.chat || null);
      } else {
        setChatData(null);
      }
    } catch (error) {
      console.error("获取聊天日报失败:", error);
      setChatData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport(date);
  }, [date]);

  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    setDate(current.toISOString().split("T")[0]);
  };

  // 计算统计数据
  const getTotals = () => {
    if (!chatData?.summaries) return { messages: 0, decisions: 0, actions: 0, risks: 0 };
    return {
      messages: chatData.total_messages || 0,
      decisions: chatData.summaries.reduce((sum, c) => sum + (c.decisions?.length || 0), 0),
      actions: chatData.summaries.reduce((sum, c) => sum + (c.action_items?.length || 0), 0),
      risks: chatData.summaries.reduce((sum, c) => sum + (c.risks?.length || 0), 0),
    };
  };

  const totals = getTotals();

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* 标题 */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">聊天日报</h1>
              <p className="text-sm text-zinc-500">飞书群聊消息 AI 分析</p>
            </div>
          </div>

          {/* 日期选择器 */}
          <div className="flex items-center gap-2 bg-zinc-900 rounded-lg p-1">
            <button onClick={() => changeDate(-1)} className="p-2 hover:bg-zinc-800 rounded-md">
              <ChevronLeft className="w-4 h-4 text-zinc-400" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5">
              <Calendar className="w-4 h-4 text-blue-400" />
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

      {/* 统计概览 */}
      {chatData && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { icon: MessageSquare, label: "消息总数", value: totals.messages, color: "text-blue-400" },
            { icon: CheckCircle2, label: "决策", value: totals.decisions, color: "text-green-400" },
            { icon: ListTodo, label: "待办事项", value: totals.actions, color: "text-amber-400" },
            { icon: AlertTriangle, label: "风险提醒", value: totals.risks, color: "text-red-400" },
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
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-5 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse">
              <div className="h-6 w-48 bg-zinc-800 rounded mb-4" />
              <div className="h-20 bg-zinc-800/50 rounded mb-4" />
              <div className="flex gap-4">
                <div className="h-16 flex-1 bg-zinc-800/30 rounded" />
                <div className="h-16 flex-1 bg-zinc-800/30 rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 无数据 */}
      {!loading && (!chatData || !chatData.summaries?.length) && (
        <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <MessageSquare className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-400">暂无 {date} 的聊天日报</h3>
          <p className="text-sm text-zinc-600 mt-2">当日没有群聊消息记录</p>
        </div>
      )}

      {/* 群聊列表 */}
      {!loading && chatData?.summaries && chatData.summaries.length > 0 && (
        <div className="space-y-4">
          {chatData.summaries.map((chat, idx) => (
            <div key={idx} className="p-5 bg-zinc-900/50 rounded-xl border border-zinc-800">
              {/* 群聊标题 */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                    <MessageSquare className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <h3 className="font-medium text-white">{chat.chat_name}</h3>
                    <div className="flex items-center gap-3 text-xs text-zinc-500">
                      <span>{chat.message_count} 条消息</span>
                      {chat.activity_level === "high" && (
                        <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">活跃</span>
                      )}
                    </div>
                  </div>
                </div>
                <Link
                  href={`/info-hub/chat?chat_id=${chat.chat_id}`}
                  className="text-xs text-zinc-500 hover:text-blue-400 transition-colors"
                >
                  查看原始消息 →
                </Link>
              </div>

              {/* AI 摘要 */}
              {chat.summary && (
                <div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/10 mb-4">
                  <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-2">
                    <Sparkles className="w-3 h-3" />
                    AI 摘要
                  </div>
                  <p className="text-sm text-zinc-300 leading-relaxed">{chat.summary}</p>
                </div>
              )}

              {/* 关键信息 */}
              <div className="grid grid-cols-2 gap-4">
                {/* 决策 */}
                {chat.decisions?.length > 0 && (
                  <div className="p-3 bg-green-500/5 rounded-lg border border-green-500/10">
                    <div className="flex items-center gap-2 text-xs text-green-400 font-mono mb-2">
                      <CheckCircle2 className="w-3 h-3" />
                      决策 ({chat.decisions.length})
                    </div>
                    <ul className="space-y-1">
                      {chat.decisions.map((d, i) => (
                        <li key={i} className="text-xs text-zinc-400">• {d}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 待办 */}
                {chat.action_items?.length > 0 && (
                  <div className="p-3 bg-amber-500/5 rounded-lg border border-amber-500/10">
                    <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-2">
                      <ListTodo className="w-3 h-3" />
                      待办 ({chat.action_items.length})
                    </div>
                    <ul className="space-y-1">
                      {chat.action_items.map((a, i) => (
                        <li key={i} className="text-xs text-zinc-400">• {a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 风险 */}
                {chat.risks?.length > 0 && (
                  <div className="p-3 bg-red-500/5 rounded-lg border border-red-500/10">
                    <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-2">
                      <AlertTriangle className="w-3 h-3" />
                      风险 ({chat.risks.length})
                    </div>
                    <ul className="space-y-1">
                      {chat.risks.map((r, i) => (
                        <li key={i} className="text-xs text-zinc-400">• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 话题 */}
                {chat.topics?.length > 0 && (
                  <div className="p-3 bg-purple-500/5 rounded-lg border border-purple-500/10">
                    <div className="text-xs text-purple-400 font-mono mb-2">关键话题</div>
                    <div className="flex flex-wrap gap-1">
                      {chat.topics.map((t, i) => (
                        <span key={i} className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-xs rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
