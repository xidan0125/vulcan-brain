"use client";

import { useState, useEffect } from "react";
import {
  Brain,
  Inbox,
  Send,
  Users,
  Search,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  Building,
  RefreshCw,
  LayoutGrid,
  Mail,
  Zap,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// --- Types ---
interface Contact {
  email: string;
  name: string;
  domain: string;
  sent_count: number;
  received_count: number;
  total_interactions: number;
  health_score: number;
  health_trend: "active" | "stable" | "cooling" | "inactive" | "unknown";
  first_contact?: string;
  last_sent?: string;
  last_received?: string;
}

interface Company {
  domain: string;
  name: string;
  relation_type: string;
  confidence: string;
  email_count: number;
  contact_count: number;
  health_score: number;
  health_trend: string;
  first_contact?: string;
  last_contact?: string;
}

interface DashboardStats {
  total_contacts: number;
  active_contacts: number;
  total_companies: number;
  needs_attention: number;
  avg_health_score: number;
  health_distribution: {
    active: number;
    stable: number;
    cooling: number;
    inactive: number;
  };
  relation_distribution: Record<string, number>;
}

interface NeedsReplyEmail {
  _id: string;
  subject: string;
  from: { name: string; address: string };
  received_at: string;
  days_waiting: number;
  health_score: number;
  company_name: string;
  relation_type: string;
}

// --- Utility Components ---
const HealthRing = ({ score, size = 24 }: { score: number; size?: number }) => {
  const radius = size / 2 - 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  let color = "text-red-500";
  if (score > 80) color = "text-emerald-500";
  else if (score > 60) color = "text-yellow-500";
  else if (score > 40) color = "text-orange-500";

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg className="transform -rotate-90 w-full h-full">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#333"
          strokeWidth="3"
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth="3"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`${color} transition-all duration-500`}
        />
      </svg>
      {size > 30 && (
        <span className="absolute text-[10px] font-bold text-zinc-300">
          {score}
        </span>
      )}
    </div>
  );
};

const TrendIcon = ({ type }: { type: string }) => {
  switch (type) {
    case "active":
      return <TrendingUp size={14} className="text-emerald-500" />;
    case "stable":
      return <Minus size={14} className="text-blue-500" />;
    case "cooling":
      return <TrendingDown size={14} className="text-yellow-500" />;
    case "inactive":
      return <AlertTriangle size={14} className="text-red-500" />;
    default:
      return <Clock size={14} className="text-zinc-500" />;
  }
};

const UrgencyBadge = ({ days }: { days: number }) => {
  let bg = "bg-emerald-500/10 text-emerald-400";
  if (days > 7) bg = "bg-red-500/10 text-red-400";
  else if (days >= 3) bg = "bg-yellow-500/10 text-yellow-400";

  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${bg} border border-white/5`}
    >
      {days}d
    </span>
  );
};

const RelationBadge = ({ type }: { type: string }) => {
  const colors: Record<string, string> = {
    client: "border-purple-500/20 text-purple-400 bg-purple-500/5",
    vendor: "border-blue-500/20 text-blue-400 bg-blue-500/5",
    partner: "border-emerald-500/20 text-emerald-400 bg-emerald-500/5",
    internal: "border-orange-500/20 text-orange-400 bg-orange-500/5",
    unknown: "border-zinc-500/20 text-zinc-400 bg-zinc-500/5",
  };

  return (
    <span
      className={`text-[10px] px-2 py-0.5 rounded border ${
        colors[type] || colors.unknown
      }`}
    >
      {type}
    </span>
  );
};

// --- Main Component ---
export default function EmailIntelligencePage() {
  const [activeTab, setActiveTab] = useState<
    "command" | "action" | "relationships"
  >("command");
  const [actionSubTab, setActionSubTab] = useState<"needs_reply" | "waiting_on">(
    "needs_reply"
  );

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [needsReply, setNeedsReply] = useState<NeedsReplyEmail[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/email-intel/command-center`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (error) {
      console.error("Failed to fetch dashboard:", error);
    }
  };

  const fetchNeedsReply = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/email-intel/actions/needs-reply?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setNeedsReply(data.emails || []);
      }
    } catch (error) {
      console.error("Failed to fetch needs-reply:", error);
    }
  };

  const fetchContacts = async () => {
    try {
      const params = new URLSearchParams({ limit: "50", sort_by: "health" });
      if (searchTerm) params.append("search", searchTerm);
      const res = await fetch(`${API_BASE}/api/email-intel/relationships?${params}`);
      if (res.ok) {
        const data = await res.json();
        setContacts(data.contacts || []);
      }
    } catch (error) {
      console.error("Failed to fetch contacts:", error);
    }
  };

  const fetchCompanies = async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/email-intel/companies?limit=20&sort_by=health`
      );
      if (res.ok) {
        const data = await res.json();
        setCompanies(data.companies || []);
      }
    } catch (error) {
      console.error("Failed to fetch companies:", error);
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDashboard(),
      fetchNeedsReply(),
      fetchContacts(),
      fetchCompanies(),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchContacts();
  }, [searchTerm]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "N/A";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
    if (diff === 0) return "Today";
    if (diff === 1) return "Yesterday";
    if (diff < 7) return `${diff} days ago`;
    if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
            <Brain className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Email Intelligence</h1>
            <p className="text-sm text-zinc-500">关系健康度追踪</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex bg-zinc-900 p-1 rounded-lg border border-zinc-800">
          {[
            { id: "command", label: "总览", icon: LayoutGrid },
            { id: "action", label: "待处理", icon: Inbox },
            { id: "relationships", label: "关系网", icon: Users },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm transition-all ${
                  activeTab === tab.id
                    ? "bg-indigo-500/20 text-indigo-400"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <button
          onClick={() => {
            setLoading(true);
            Promise.all([
              fetchDashboard(),
              fetchNeedsReply(),
              fetchContacts(),
              fetchCompanies(),
            ]).finally(() => setLoading(false));
          }}
          className="p-2 hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-zinc-200"
          title="刷新"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Loading State */}
      {loading && !stats ? (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-32 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <>
          {/* TAB: COMMAND CENTER */}
          {activeTab === "command" && stats && (
            <div className="space-y-6">
              {/* KPI Cards */}
              <div className="grid grid-cols-4 gap-4">
                {[
                  {
                    label: "联系人",
                    value: stats.total_contacts,
                    icon: Users,
                    color: "text-blue-400",
                  },
                  {
                    label: "活跃关系",
                    value: stats.active_contacts,
                    icon: TrendingUp,
                    color: "text-emerald-400",
                  },
                  {
                    label: "公司",
                    value: stats.total_companies,
                    icon: Building,
                    color: "text-purple-400",
                  },
                  {
                    label: "需关注",
                    value: stats.needs_attention,
                    icon: AlertTriangle,
                    color: "text-amber-400",
                  },
                ].map((stat) => {
                  const Icon = stat.icon;
                  return (
                    <div
                      key={stat.label}
                      className="bg-zinc-900/50 border border-zinc-800 p-4 rounded-xl flex flex-col justify-between h-32 hover:border-zinc-700 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-zinc-500">{stat.label}</span>
                        <Icon size={16} className={stat.color} />
                      </div>
                      <span className="text-3xl font-light text-white">
                        {stat.value?.toLocaleString() || 0}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Health Distribution & Alerts */}
              <div className="grid grid-cols-2 gap-4">
                {/* Health Distribution */}
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-4 text-emerald-400">
                    <TrendingUp size={18} />
                    <span className="font-medium">关系健康分布</span>
                    <span className="ml-auto text-2xl font-light text-white">
                      {stats.avg_health_score?.toFixed(0) || 0}
                    </span>
                    <span className="text-xs text-zinc-500">平均分</span>
                  </div>
                  <div className="grid grid-cols-4 gap-3">
                    {[
                      {
                        key: "active",
                        label: "活跃",
                        color: "bg-emerald-500",
                        text: "text-emerald-400",
                      },
                      {
                        key: "stable",
                        label: "稳定",
                        color: "bg-blue-500",
                        text: "text-blue-400",
                      },
                      {
                        key: "cooling",
                        label: "降温",
                        color: "bg-yellow-500",
                        text: "text-yellow-400",
                      },
                      {
                        key: "inactive",
                        label: "沉寂",
                        color: "bg-red-500",
                        text: "text-red-400",
                      },
                    ].map((item) => {
                      const count =
                        stats.health_distribution?.[
                          item.key as keyof typeof stats.health_distribution
                        ] || 0;
                      const pct =
                        stats.total_contacts > 0
                          ? ((count / stats.total_contacts) * 100).toFixed(0)
                          : 0;
                      return (
                        <div
                          key={item.key}
                          className="bg-zinc-800/50 p-3 rounded-lg border border-zinc-700/50"
                        >
                          <div
                            className={`w-2 h-2 rounded-full ${item.color} mb-2`}
                          />
                          <div className={`text-xl font-medium ${item.text}`}>
                            {count}
                          </div>
                          <div className="text-[10px] text-zinc-600">
                            {item.label} ({pct}%)
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Top Companies */}
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-4 text-purple-400">
                    <Building size={18} />
                    <span className="font-medium">重要公司</span>
                  </div>
                  <div className="space-y-2">
                    {companies.slice(0, 5).map((company) => (
                      <div
                        key={company.domain}
                        className="flex items-center justify-between p-2 rounded-lg hover:bg-zinc-800/50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <HealthRing score={company.health_score} size={28} />
                          <div>
                            <div className="text-sm text-zinc-200">
                              {company.name}
                            </div>
                            <div className="text-[10px] text-zinc-600">
                              {company.email_count} 邮件 · {company.contact_count} 联系人
                            </div>
                          </div>
                        </div>
                        <RelationBadge type={company.relation_type} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Relation Type Distribution */}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-4 text-indigo-400">
                  <Zap size={18} />
                  <span className="font-medium">关系类型分布</span>
                </div>
                <div className="flex gap-4">
                  {Object.entries(stats.relation_distribution || {}).map(
                    ([type, count]) => (
                      <div
                        key={type}
                        className="flex-1 bg-zinc-800/50 p-4 rounded-lg border border-zinc-700/50"
                      >
                        <div className="text-2xl font-light text-white mb-1">
                          {count}
                        </div>
                        <div className="text-sm text-zinc-500 capitalize">
                          {type === "unknown" ? "未分类" : type}
                        </div>
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB: ACTION CENTER */}
          {activeTab === "action" && (
            <div className="h-[calc(100vh-200px)] flex flex-col">
              <div className="flex gap-4 mb-4 border-b border-zinc-800 pb-4">
                <button
                  onClick={() => setActionSubTab("needs_reply")}
                  className={`text-sm font-medium transition-colors ${
                    actionSubTab === "needs_reply"
                      ? "text-white"
                      : "text-zinc-500"
                  }`}
                >
                  待回复{" "}
                  <span className="ml-1 text-xs bg-zinc-800 px-1.5 py-0.5 rounded-full">
                    {needsReply.length}
                  </span>
                </button>
                <button
                  onClick={() => setActionSubTab("waiting_on")}
                  className={`text-sm font-medium transition-colors ${
                    actionSubTab === "waiting_on"
                      ? "text-white"
                      : "text-zinc-500"
                  }`}
                >
                  等待回复
                </button>
              </div>

              <div className="flex-1 overflow-auto space-y-1">
                {needsReply.length === 0 ? (
                  <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <Mail className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-zinc-400">
                      暂无待回复邮件
                    </h3>
                    <p className="text-sm text-zinc-600 mt-2">
                      所有邮件都已处理
                    </p>
                  </div>
                ) : (
                  needsReply.map((email) => (
                    <div
                      key={email._id}
                      className="group flex items-center justify-between p-3 rounded-lg hover:bg-zinc-900/50 border border-transparent hover:border-zinc-800 transition-all cursor-pointer"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 flex items-center justify-center text-sm font-medium text-zinc-300">
                          {email.from?.name?.[0] || "?"}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-zinc-200">
                              {email.from?.name || email.from?.address}
                            </span>
                            {email.company_name && (
                              <span className="text-xs text-zinc-600 px-1.5 rounded border border-zinc-700/50">
                                {email.company_name}
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-zinc-400 mt-0.5 max-w-md truncate">
                            {email.subject}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <UrgencyBadge days={email.days_waiting} />
                        <HealthRing score={email.health_score || 50} size={28} />
                        <RelationBadge type={email.relation_type || "unknown"} />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TAB: RELATIONSHIPS */}
          {activeTab === "relationships" && (
            <div className="h-[calc(100vh-200px)] flex gap-6">
              {/* Left: Contact List */}
              <div className="w-1/2 flex flex-col">
                <div className="mb-4">
                  <div className="relative">
                    <Search
                      size={14}
                      className="absolute left-3 top-3 text-zinc-500"
                    />
                    <input
                      type="text"
                      placeholder="搜索联系人..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-lg py-2 pl-9 pr-4 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/50"
                    />
                  </div>
                </div>
                <div className="flex-1 overflow-auto space-y-2 pr-2">
                  {contacts.map((contact) => (
                    <div
                      key={contact.email}
                      onClick={() => setSelectedContact(contact)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                        selectedContact?.email === contact.email
                          ? "bg-zinc-900/80 border-indigo-500/30"
                          : "border-transparent hover:bg-zinc-900/50 hover:border-zinc-800"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <HealthRing score={contact.health_score} size={32} />
                        <div>
                          <div className="text-sm font-medium text-zinc-200">
                            {contact.name}
                          </div>
                          <div className="text-xs text-zinc-600">
                            {contact.domain}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-zinc-600">
                          {contact.total_interactions} 次
                        </span>
                        <TrendIcon type={contact.health_trend} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: Contact Detail */}
              <div className="w-1/2 bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
                {selectedContact ? (
                  <div className="h-full flex flex-col">
                    <div className="flex items-start justify-between mb-6">
                      <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-full bg-gradient-to-b from-zinc-700 to-zinc-800 flex items-center justify-center text-xl font-light text-white">
                          {selectedContact.name[0]}
                        </div>
                        <div>
                          <h3 className="text-lg font-medium text-white">
                            {selectedContact.name}
                          </h3>
                          <p className="text-indigo-400 text-sm">
                            {selectedContact.email}
                          </p>
                          <p className="text-zinc-600 text-sm mt-1">
                            {selectedContact.domain}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-3xl font-light text-white">
                          {selectedContact.health_score}
                        </div>
                        <div className="text-xs text-zinc-600 uppercase tracking-wider">
                          健康分
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="bg-zinc-800/50 p-4 rounded-lg border border-zinc-700/50">
                        <div className="text-zinc-500 text-xs mb-1">
                          <Send className="w-3 h-3 inline mr-1" />
                          发送
                        </div>
                        <div className="text-xl text-white">
                          {selectedContact.sent_count}
                        </div>
                      </div>
                      <div className="bg-zinc-800/50 p-4 rounded-lg border border-zinc-700/50">
                        <div className="text-zinc-500 text-xs mb-1">
                          <Inbox className="w-3 h-3 inline mr-1" />
                          接收
                        </div>
                        <div className="text-xl text-white">
                          {selectedContact.received_count}
                        </div>
                      </div>
                      <div className="bg-zinc-800/50 p-4 rounded-lg border border-zinc-700/50">
                        <div className="text-zinc-500 text-xs mb-1">
                          <TrendingUp className="w-3 h-3 inline mr-1" />
                          趋势
                        </div>
                        <div className="text-xl text-white flex items-center gap-2 capitalize">
                          <TrendIcon type={selectedContact.health_trend} />
                          {selectedContact.health_trend}
                        </div>
                      </div>
                    </div>

                    <div className="flex-1">
                      <h4 className="text-xs font-semibold text-zinc-600 uppercase tracking-wider mb-3">
                        互动时间线
                      </h4>
                      <div className="space-y-3">
                        {selectedContact.last_sent && (
                          <div className="flex items-center gap-3 text-sm">
                            <Send className="w-4 h-4 text-blue-400" />
                            <span className="text-zinc-400">最后发送</span>
                            <span className="text-zinc-200">
                              {formatDate(selectedContact.last_sent)}
                            </span>
                          </div>
                        )}
                        {selectedContact.last_received && (
                          <div className="flex items-center gap-3 text-sm">
                            <Inbox className="w-4 h-4 text-emerald-400" />
                            <span className="text-zinc-400">最后接收</span>
                            <span className="text-zinc-200">
                              {formatDate(selectedContact.last_received)}
                            </span>
                          </div>
                        )}
                        {selectedContact.first_contact && (
                          <div className="flex items-center gap-3 text-sm">
                            <Clock className="w-4 h-4 text-zinc-400" />
                            <span className="text-zinc-400">首次联系</span>
                            <span className="text-zinc-200">
                              {formatDate(selectedContact.first_contact)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="mt-auto pt-6 border-t border-zinc-800 flex justify-end gap-3">
                      <button className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors">
                        查看邮件
                      </button>
                      <button className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 text-sm transition-colors font-medium">
                        发送邮件
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-zinc-600 flex-col gap-2">
                    <Users size={32} className="opacity-20" />
                    <p>选择联系人查看详情</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
