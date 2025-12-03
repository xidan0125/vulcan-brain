"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  MessageSquare,
  FolderKanban,
  Mail,
  FileCheck,
  Users,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  ListTodo,
  Star,
  Clock,
  RefreshCw,
  Send,
  XCircle,
  FileText,
  TrendingUp,
  Building,
  Briefcase,
} from "lucide-react";

// ========== 类型定义 ==========
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

interface EmailAIAnalysis {
  summary: string;
  action_items: string[];
  vip_updates: string[];
  urgent_matters: string[];
  key_topics: string[];
  sentiment: string;
}

interface EmailSummary {
  total: number;
  received: number;
  sent: number;
  important: number;
  external_count: number;
  top_contacts: Array<{ name: string; address: string; count: number }>;
  vip_emails: Array<{ email_id: string; subject: string; from: { name: string; address: string }; client: string }>;
  ai_analysis: EmailAIAnalysis;
}

interface ApprovalSummary {
  date: string;
  total_count: number;
  pending_count: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  summary: string;
  highlights: string[];
  pending_attention: string[];
  risks: string[];
  recommendations: string[];
}

interface ApprovalItem {
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

interface DailyReport {
  date: string;
  chat: {
    total_chats: number;
    total_messages: number;
    summaries: ChatSummary[];
  };
  email: EmailSummary;
  projects: { total_count: number };
  approval: { total_count: number };
  people: { total_count: number };
}

type Dimension = "chat" | "email" | "projects" | "approval" | "people";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ========== 五维度卡片配置 ==========
const dimensionConfig = [
  { id: "chat" as Dimension, label: "聊天记录", description: "飞书群聊", icon: MessageSquare, color: "text-blue-400", bgColor: "bg-blue-500/10", borderColor: "border-blue-500/30" },
  { id: "email" as Dimension, label: "邮件", description: "Outlook", icon: Mail, color: "text-amber-400", bgColor: "bg-amber-500/10", borderColor: "border-amber-500/30" },
  { id: "projects" as Dimension, label: "项目", description: "飞书任务", icon: FolderKanban, color: "text-purple-400", bgColor: "bg-purple-500/10", borderColor: "border-purple-500/30", coming: true },
  { id: "approval" as Dimension, label: "审批", description: "飞书审批", icon: FileCheck, color: "text-emerald-400", bgColor: "bg-emerald-500/10", borderColor: "border-emerald-500/30" },
  { id: "people" as Dimension, label: "人员", description: "活跃度", icon: Users, color: "text-rose-400", bgColor: "bg-rose-500/10", borderColor: "border-rose-500/30" },
];

const APPROVAL_STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: any }> = {
  PENDING: { label: "待审批", color: "text-amber-400", bgColor: "bg-amber-500/10", icon: Clock },
  APPROVED: { label: "已通过", color: "text-green-400", bgColor: "bg-green-500/10", icon: CheckCircle2 },
  REJECTED: { label: "已拒绝", color: "text-red-400", bgColor: "bg-red-500/10", icon: XCircle },
  CANCELED: { label: "已撤销", color: "text-zinc-400", bgColor: "bg-zinc-500/10", icon: AlertTriangle },
};

export default function DailyReportPage() {
  const [date, setDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [selectedDimension, setSelectedDimension] = useState<Dimension>("chat");

  // 审批相关状态
  const [approvalSummary, setApprovalSummary] = useState<ApprovalSummary | null>(null);
  const [approvalList, setApprovalList] = useState<ApprovalItem[]>([]);
  const [approvalLoading, setApprovalLoading] = useState(false);

  // 人员统计
  const [peopleStats, setPeopleStats] = useState<{total: number; active: number} | null>(null);

  useEffect(() => {
    const fetchReport = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/info-hub/daily/${date}`);
        if (res.ok) {
          const data = await res.json();
          setReport(data.report || null);
        }
      } catch (e) {
        console.error("获取日报失败:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [date]);

  // 获取审批数据
  useEffect(() => {
    if (selectedDimension === "approval") {
      fetchApprovalData();
    }
  }, [selectedDimension, date]);

  // 获取人员统计
  useEffect(() => {
    const fetchPeopleStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/info-hub/people/dashboard?date=${date}`);
        if (res.ok) {
          const data = await res.json();
          setPeopleStats({
            total: data.stats?.total_people || 0,
            active: data.stats?.active_today || 0
          });
        }
      } catch (e) {
        console.error("获取人员统计失败:", e);
      }
    };
    fetchPeopleStats();
  }, [date]);

  const fetchApprovalData = async () => {
    setApprovalLoading(true);
    try {
      // 并行获取仪表盘和列表
      const [dashboardRes, listRes] = await Promise.all([
        fetch(`${API_BASE}/api/info-hub/approval/dashboard?date=${date}`),
        fetch(`${API_BASE}/api/info-hub/approval/list?date=${date}&limit=20`),
      ]);

      if (dashboardRes.ok) {
        const data = await dashboardRes.json();
        setApprovalSummary(data.summary);
      }

      if (listRes.ok) {
        const data = await listRes.json();
        setApprovalList(data.approvals || []);
      }
    } catch (e) {
      console.error("获取审批数据失败:", e);
    } finally {
      setApprovalLoading(false);
    }
  };

  const generateReport = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/daily/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date }),
      });
      if (res.ok) {
        const fetchRes = await fetch(`${API_BASE}/api/info-hub/daily/${date}`);
        if (fetchRes.ok) {
          const data = await fetchRes.json();
          setReport(data.report || null);
        }
      }
    } catch (e) {
      console.error("生成日报失败:", e);
    } finally {
      setGenerating(false);
    }
  };

  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    setDate(current.toISOString().split("T")[0]);
  };

  const getCount = (dimId: Dimension): number => {
    if (!report) return 0;
    switch (dimId) {
      case "chat": return report.chat?.total_messages || 0;
      case "email": return report.email?.total || 0;
      case "projects": return report.projects?.total_count || 0;
      case "approval": return approvalSummary?.total_count || report.approval?.total_count || 0;
      case "people": return peopleStats?.total || 0;
      default: return 0;
    }
  };

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

  const selectedDim = dimensionConfig.find((d) => d.id === selectedDimension)!;
  const emailData = report?.email;
  const emailAI = emailData?.ai_analysis;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* 页面标题 + 日期选择 + 生成按钮 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">日报总览</h1>
          <p className="text-sm text-zinc-500">五维度企业数据汇总</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-zinc-900 rounded-lg p-1">
            <button onClick={() => changeDate(-1)} className="p-2 hover:bg-zinc-800 rounded-md">
              <ChevronLeft className="w-4 h-4 text-zinc-400" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5">
              <Calendar className="w-4 h-4 text-orange-400" />
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="bg-transparent text-sm text-white focus:outline-none" />
            </div>
            <button onClick={() => changeDate(1)} className="p-2 hover:bg-zinc-800 rounded-md">
              <ChevronRight className="w-4 h-4 text-zinc-400" />
            </button>
          </div>
          <button onClick={generateReport} disabled={generating} className="flex items-center gap-2 px-4 py-2 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/20 rounded-lg text-sm text-orange-400 transition-colors disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
            {generating ? "生成中..." : "生成日报"}
          </button>
        </div>
      </div>

      {/* 五维度卡片选择器 */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {dimensionConfig.map((dim) => {
          const Icon = dim.icon;
          const isSelected = selectedDimension === dim.id;
          const count = getCount(dim.id);
          return (
            <button key={dim.id} onClick={() => !dim.coming && setSelectedDimension(dim.id)} disabled={dim.coming}
              className={`p-3 rounded-xl border text-center transition-all ${isSelected ? `${dim.bgColor} ${dim.borderColor} border-2` : dim.coming ? "bg-zinc-900/30 border-zinc-800/50 opacity-50 cursor-not-allowed" : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 cursor-pointer"}`}>
              <div className={`w-10 h-10 rounded-lg ${dim.bgColor} flex items-center justify-center mx-auto mb-2`}>
                <Icon className={`w-5 h-5 ${dim.color}`} />
              </div>
              <div className={`text-sm font-medium ${isSelected ? "text-white" : "text-zinc-300"}`}>{dim.label}</div>
              <div className="text-[10px] text-zinc-500">{dim.description}</div>
              <div className={`text-lg font-bold mt-1 ${dim.color}`}>{dim.coming ? "-" : loading ? "-" : count}</div>
            </button>
          );
        })}
      </div>

      {/* 内容区域 */}
      <div className="border-t border-zinc-800 pt-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className={`w-4 h-4 ${selectedDim.color}`} />
          <span className="text-sm text-zinc-400">{selectedDim.label} AI 日报</span>
          {(loading || approvalLoading) && <span className="text-xs text-zinc-600 ml-2">加载中...</span>}
        </div>

        {/* Coming Soon 维度 */}
        {selectedDim.coming ? (
          <div className="text-center py-16 bg-zinc-900/30 rounded-xl border border-zinc-800">
            <div className={`w-16 h-16 rounded-full ${selectedDim.bgColor} flex items-center justify-center mx-auto mb-4`}>
              <selectedDim.icon className={`w-8 h-8 ${selectedDim.color}`} />
            </div>
            <h3 className="text-lg font-medium text-zinc-400 mb-2">{selectedDim.label}日报</h3>
            <p className="text-sm text-zinc-600 mb-4">即将上线</p>
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800/50 rounded-lg text-sm text-zinc-500">
              <Clock className="w-4 h-4" />Coming Soon
            </div>
          </div>
        ) : selectedDimension === "chat" ? (
          /* ===== 聊天日报 ===== */
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: MessageSquare, label: "消息总数", value: report?.chat?.total_messages || 0, color: "text-blue-400" },
                { icon: CheckCircle2, label: "决策", value: report?.chat?.summaries?.reduce((s, c) => s + (c.decisions?.length || 0), 0) || 0, color: "text-green-400" },
                { icon: ListTodo, label: "待办事项", value: report?.chat?.summaries?.reduce((s, c) => s + (c.action_items?.length || 0), 0) || 0, color: "text-amber-400" },
                { icon: AlertTriangle, label: "风险提醒", value: report?.chat?.summaries?.reduce((s, c) => s + (c.risks?.length || 0), 0) || 0, color: "text-red-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{loading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>
            {loading ? (
              <div className="p-5 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse"><div className="h-6 w-48 bg-zinc-800 rounded mb-4" /><div className="h-20 bg-zinc-800/50 rounded" /></div>
            ) : report?.chat?.summaries?.length ? (
              report.chat.summaries.map((chat, idx) => (
                <div key={idx} className="p-5 bg-zinc-900/50 rounded-xl border border-zinc-800">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center"><MessageSquare className="w-4 h-4 text-blue-400" /></div>
                      <div><h3 className="font-medium text-white">{chat.chat_name}</h3><span className="text-xs text-zinc-500">{chat.message_count} 条消息</span></div>
                    </div>
                    <Link href={`/info-hub/chat?chat_id=${chat.chat_id}`} className="text-xs text-zinc-500 hover:text-blue-400">查看原始消息 →</Link>
                  </div>
                  {chat.summary && (<div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/10 mb-4"><div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-2"><Sparkles className="w-3 h-3" />AI 摘要</div><p className="text-sm text-zinc-300 leading-relaxed">{chat.summary}</p></div>)}
                  <div className="grid grid-cols-2 gap-3">
                    {chat.risks?.length > 0 && (<div className="p-3 bg-red-500/5 rounded-lg border border-red-500/10"><div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-2"><AlertTriangle className="w-3 h-3" />风险 ({chat.risks.length})</div><ul className="space-y-1">{chat.risks.map((r, i) => <li key={i} className="text-xs text-zinc-400">• {r}</li>)}</ul></div>)}
                    {chat.action_items?.length > 0 && (<div className="p-3 bg-amber-500/5 rounded-lg border border-amber-500/10"><div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-2"><ListTodo className="w-3 h-3" />待办 ({chat.action_items.length})</div><ul className="space-y-1">{chat.action_items.map((a, i) => <li key={i} className="text-xs text-zinc-400">• {a}</li>)}</ul></div>)}
                    {chat.decisions?.length > 0 && (<div className="p-3 bg-green-500/5 rounded-lg border border-green-500/10"><div className="flex items-center gap-2 text-xs text-green-400 font-mono mb-2"><CheckCircle2 className="w-3 h-3" />决策 ({chat.decisions.length})</div><ul className="space-y-1">{chat.decisions.map((d, i) => <li key={i} className="text-xs text-zinc-400">• {d}</li>)}</ul></div>)}
                    {chat.topics?.length > 0 && (<div className="p-3 bg-purple-500/5 rounded-lg border border-purple-500/10"><div className="text-xs text-purple-400 font-mono mb-2">关键话题</div><div className="flex flex-wrap gap-1">{chat.topics.map((t, i) => <span key={i} className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-xs rounded">{t}</span>)}</div></div>)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-12 bg-zinc-900/30 rounded-xl border border-zinc-800"><MessageSquare className="w-12 h-12 mx-auto mb-4 text-zinc-600" /><p className="text-zinc-500">暂无 {date} 的聊天数据</p><p className="text-xs text-zinc-600 mt-2">点击"生成日报"获取数据</p></div>
            )}
          </div>
        ) : selectedDimension === "email" ? (
          /* ===== 邮件日报 ===== */
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: Mail, label: "收到邮件", value: emailData?.received || 0, color: "text-blue-400" },
                { icon: Send, label: "发送邮件", value: emailData?.sent || 0, color: "text-green-400" },
                { icon: Star, label: "重要邮件", value: emailData?.important || 0, color: "text-yellow-400" },
                { icon: Users, label: "外部邮件", value: emailData?.external_count || 0, color: "text-amber-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{loading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>
            <div className="p-4 bg-amber-500/5 rounded-lg border border-amber-500/10">
              <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-2"><Sparkles className="w-3 h-3" />AI 摘要</div>
              <p className="text-sm text-zinc-300 leading-relaxed">{emailAI?.summary || "暂无摘要，点击「生成日报」获取 AI 分析"}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-blue-500/5 rounded-lg border border-blue-500/10">
                <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-2"><ListTodo className="w-3 h-3" />待办事项 ({emailAI?.action_items?.length || 0})</div>
                {emailAI?.action_items?.length ? (<ul className="space-y-1">{emailAI.action_items.map((item, i) => <li key={i} className="text-xs text-zinc-400">• {item}</li>)}</ul>) : <p className="text-xs text-zinc-600">暂无待办事项</p>}
              </div>
              <div className="p-3 bg-red-500/5 rounded-lg border border-red-500/10">
                <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-2"><AlertTriangle className="w-3 h-3" />紧急事项 ({emailAI?.urgent_matters?.length || 0})</div>
                {emailAI?.urgent_matters?.length ? (<ul className="space-y-1">{emailAI.urgent_matters.map((item, i) => <li key={i} className="text-xs text-zinc-400">• {item}</li>)}</ul>) : <p className="text-xs text-zinc-600">暂无紧急事项</p>}
              </div>
              <div className="p-3 bg-yellow-500/5 rounded-lg border border-yellow-500/10">
                <div className="flex items-center gap-2 text-xs text-yellow-400 font-mono mb-2"><Star className="w-3 h-3" />重要客户 ({emailAI?.vip_updates?.length || 0})</div>
                {emailAI?.vip_updates?.length ? (<ul className="space-y-1">{emailAI.vip_updates.map((item, i) => <li key={i} className="text-xs text-zinc-400">• {item}</li>)}</ul>) : <p className="text-xs text-zinc-600">暂无 VIP 客户更新</p>}
              </div>
              <div className="p-3 bg-purple-500/5 rounded-lg border border-purple-500/10">
                <div className="text-xs text-purple-400 font-mono mb-2">关键话题 ({emailAI?.key_topics?.length || 0})</div>
                {emailAI?.key_topics?.length ? (<div className="flex flex-wrap gap-1">{emailAI.key_topics.map((topic, i) => <span key={i} className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-xs rounded">{topic}</span>)}</div>) : <p className="text-xs text-zinc-600">暂无关键话题</p>}
              </div>
            </div>
            <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
              <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono mb-3"><Users className="w-3 h-3" />高频联系人</div>
              {emailData?.top_contacts?.length ? (
                <div className="flex flex-wrap gap-2">
                  {emailData.top_contacts.map((contact, idx) => (
                    <div key={idx} className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg">
                      <div className="w-6 h-6 rounded-full bg-amber-500/10 flex items-center justify-center"><span className="text-amber-400 text-xs font-medium">{contact.name?.[0] || contact.address?.[0] || "?"}</span></div>
                      <div><div className="text-xs text-zinc-300">{contact.name || contact.address}</div><div className="text-[10px] text-zinc-600">{contact.count} 封邮件</div></div>
                    </div>
                  ))}
                </div>
              ) : <p className="text-xs text-zinc-600">暂无联系人数据</p>}
            </div>
          </div>
        ) : selectedDimension === "approval" ? (
          /* ===== 审批日报 ===== */
          <div className="space-y-4">
            {/* 统计卡片 */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: FileText, label: "总审批", value: approvalSummary?.total_count || 0, color: "text-emerald-400" },
                { icon: Clock, label: "待处理", value: approvalSummary?.pending_count || approvalSummary?.by_status?.PENDING || 0, color: "text-amber-400" },
                { icon: CheckCircle2, label: "已通过", value: approvalSummary?.by_status?.APPROVED || 0, color: "text-green-400" },
                { icon: XCircle, label: "已拒绝", value: approvalSummary?.by_status?.REJECTED || 0, color: "text-red-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{approvalLoading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>

            {/* AI 摘要 */}
            <div className="p-4 bg-emerald-500/5 rounded-lg border border-emerald-500/10">
              <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono mb-2"><Sparkles className="w-3 h-3" />AI 摘要</div>
              <p className="text-sm text-zinc-300 leading-relaxed">{approvalSummary?.summary || "暂无摘要数据"}</p>
            </div>

            {/* 重点事项和需关注 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-emerald-500/5 rounded-lg border border-emerald-500/10">
                <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono mb-2"><Star className="w-3 h-3" />重点事项 ({approvalSummary?.highlights?.length || 0})</div>
                {approvalSummary?.highlights?.length ? (
                  <ul className="space-y-1">{approvalSummary.highlights.map((h, i) => <li key={i} className="text-xs text-zinc-400">• {h}</li>)}</ul>
                ) : <p className="text-xs text-zinc-600">暂无重点事项</p>}
              </div>
              <div className="p-3 bg-amber-500/5 rounded-lg border border-amber-500/10">
                <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-2"><AlertTriangle className="w-3 h-3" />需关注 ({approvalSummary?.pending_attention?.length || 0})</div>
                {approvalSummary?.pending_attention?.length ? (
                  <ul className="space-y-1">{approvalSummary.pending_attention.map((p, i) => <li key={i} className="text-xs text-zinc-400">• {p}</li>)}</ul>
                ) : <p className="text-xs text-zinc-600">暂无需关注事项</p>}
              </div>
            </div>

            {/* 按类型分布 */}
            {approvalSummary?.by_type && Object.keys(approvalSummary.by_type).length > 0 && (
              <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono mb-3"><FileCheck className="w-3 h-3" />按类型分布</div>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {Object.entries(approvalSummary.by_type).map(([type, count]) => (
                    <div key={type} className="p-2 bg-zinc-800/50 rounded-lg text-center">
                      <div className="text-lg font-bold text-emerald-400">{count as number}</div>
                      <div className="text-[10px] text-zinc-500 truncate">{type}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 审批列表 */}
            <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono"><FileText className="w-3 h-3" />最近审批 ({approvalList.length})</div>
                <Link href="/info-hub/approval" className="text-xs text-emerald-400 hover:underline">查看全部 →</Link>
              </div>
              {approvalLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-zinc-800/50 rounded-lg animate-pulse" />)}
                </div>
              ) : approvalList.length > 0 ? (
                <div className="space-y-2">
                  {approvalList.slice(0, 5).map((approval) => {
                    const statusConfig = APPROVAL_STATUS_CONFIG[approval.status] || APPROVAL_STATUS_CONFIG.PENDING;
                    const StatusIcon = statusConfig.icon;
                    return (
                      <div key={approval.instance_code} className="flex items-center justify-between p-3 bg-zinc-800/30 rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg ${statusConfig.bgColor} flex items-center justify-center`}>
                            <FileText className={`w-4 h-4 ${statusConfig.color}`} />
                          </div>
                          <div>
                            <div className="text-sm text-zinc-300">{approval.approval_name}</div>
                            <div className="text-[10px] text-zinc-600">#{approval.serial_number} · {formatTime(approval.start_time)}</div>
                          </div>
                        </div>
                        <div className={`flex items-center gap-1 px-2 py-1 rounded ${statusConfig.bgColor}`}>
                          <StatusIcon className={`w-3 h-3 ${statusConfig.color}`} />
                          <span className={`text-xs ${statusConfig.color}`}>{statusConfig.label}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileCheck className="w-10 h-10 mx-auto mb-2 text-zinc-700" />
                  <p className="text-xs text-zinc-600">暂无审批记录</p>
                </div>
              )}
            </div>
          </div>
        ) : selectedDimension === "people" ? (
          /* ===== 人员日报 ===== */
          <div className="space-y-4">
            {/* 统计卡片 */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: Users, label: "总人数", value: peopleStats?.total || 0, color: "text-rose-400" },
                { icon: TrendingUp, label: "今日活跃", value: peopleStats?.active || 0, color: "text-green-400" },
                { icon: Building, label: "部门", value: 0, color: "text-blue-400" },
                { icon: Briefcase, label: "职能", value: 4, color: "text-purple-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                  </div>
                );
              })}
            </div>
            {/* 提示跳转到详情页 */}
            <div className="p-4 bg-rose-500/5 rounded-lg border border-rose-500/10">
              <div className="flex items-center gap-2 text-xs text-rose-400 font-mono mb-2"><Sparkles className="w-3 h-3" />人员活跃度</div>
              <p className="text-sm text-zinc-300 leading-relaxed mb-3">共 {peopleStats?.total || 0} 名员工，今日 {peopleStats?.active || 0} 人有邮件活动</p>
              <Link href={`/info-hub/daily-report/people?date=${date}`} className="inline-flex items-center gap-2 px-3 py-1.5 bg-rose-500/10 text-rose-400 rounded-lg text-sm hover:bg-rose-500/20 transition-colors">
                <Users className="w-4 h-4" />查看人员详情 →
              </Link>
            </div>
          </div>

        ) : null}
      </div>
    </div>
  );
}
