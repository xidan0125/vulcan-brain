"use client";

import { useState, useEffect } from "react";
import {
  Users,
  MessageSquare,
  Mail,
  Building,
  Clock,
  RefreshCw,
  Hash,
  TrendingUp,
  Activity,
  BarChart3,
  ChevronRight,
  X,
  Zap,
  ArrowUpRight,
  ArrowDownLeft,
  Filter,
} from "lucide-react";
import { EmployeeProfileV2 as EmployeeAIProfile, ProfileV2 as EmployeeProfileData } from "@/components/enterprise/EmployeeProfileV2";

// ========== Types ==========
interface DashboardStats {
  total_people: number;
  active_today: number;
  department_count: number;
  function_count: number;
}

interface GroupStats {
  name: string;
  count: number;
  active_count: number;
}

interface Dashboard {
  date: string;
  stats: DashboardStats;
  by_department: GroupStats[];
  by_function: GroupStats[];
}

interface Person {
  user_id: string;
  name: string;
  email?: string;
  department: string;
  function: string;
  projects: string[];
  ms365_job_title?: string;
  email_sent_total: number;
  email_received_total: number;
  last_active?: string;
}

interface ChatGroup {
  chat_id: string;
  chat_name: string;
  total_messages: number;
}

interface FeishuUser {
  name: string;
  open_id: string;
  message_count: number;
  chat_count: number;
  last_active: string;
}

interface Message {
  message_id: string;
  sender: { id?: string; name?: string; sender_type?: string };
  content: string;
  timestamp: string;
  chat_name?: string;
  chat_id?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ========== Helper Functions ==========
const getAvatarColor = (name?: string) => {
  const colors = [
    "from-blue-500 to-blue-600",
    "from-emerald-500 to-emerald-600",
    "from-violet-500 to-violet-600",
    "from-amber-500 to-amber-600",
    "from-rose-500 to-rose-600",
    "from-cyan-500 to-cyan-600",
    "from-indigo-500 to-indigo-600",
    "from-pink-500 to-pink-600",
    "from-teal-500 to-teal-600",
  ];
  if (!name) return colors[0];
  const hash = name.split("").reduce((a, b) => a + b.charCodeAt(0), 0);
  return colors[hash % colors.length];
};

type DataSource = "email" | "feishu";
type FeishuDetailType = "user" | "chat" | null;

// ========== Main Component ==========
export default function EnterprisePage() {
  const [activeSource, setActiveSource] = useState<DataSource>("email");

  // Email system state
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [peopleLoading, setPeopleLoading] = useState(true);
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [filterDept, setFilterDept] = useState<string | null>(null);

  // Feishu state
  const [feishuUsers, setFeishuUsers] = useState<FeishuUser[]>([]);
  const [feishuLoading, setFeishuLoading] = useState(true);
  const [chatGroups, setChatGroups] = useState<ChatGroup[]>([]);
  const [recentMessages, setRecentMessages] = useState<Message[]>([]);

  // Feishu detail panel state
  const [feishuDetailType, setFeishuDetailType] = useState<FeishuDetailType>(null);
  const [selectedFeishuUser, setSelectedFeishuUser] = useState<FeishuUser | null>(null);
  const [selectedChat, setSelectedChat] = useState<ChatGroup | null>(null);
  const [detailMessages, setDetailMessages] = useState<Message[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  // AI Profile state
  const [profileData, setProfileData] = useState<EmployeeProfileData | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // Email list state
  const [showEmails, setShowEmails] = useState(false);
  const [personEmails, setPersonEmails] = useState<Array<{
    email_id: string;
    subject: string;
    from: { address: string; name: string };
    to: { address: string; name: string }[];
    received_at?: string;
    sent_at?: string;
    folder: string;
  }>>([]);
  const [emailsLoading, setEmailsLoading] = useState(false);

  // ========== Email System Data Fetching ==========
  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/people/dashboard`);
      if (res.ok) setDashboard(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchPeople = async (dept?: string | null) => {
    setPeopleLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100", sort_by: "activity" });
      if (dept) params.append("department", dept);
      const res = await fetch(`${API_BASE}/api/info-hub/people?${params}`);
      if (res.ok) setPeople((await res.json()).people || []);
    } catch (e) { console.error(e); }
    finally { setPeopleLoading(false); }
  };

  const fetchPersonEmails = async (person: Person) => {
    setEmailsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/emails?user_email=${encodeURIComponent(person.email || person.user_id)}&limit=20`);
      if (res.ok) {
        const data = await res.json();
        setPersonEmails(data.emails || []);
      }
    } catch (e) { console.error(e); }
    finally { setEmailsLoading(false); }
  };

  // ========== Feishu Data Fetching ==========
  const fetchFeishuUsers = async () => {
    setFeishuLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/feishu/users`);
      if (res.ok) {
        const data = await res.json();
        setFeishuUsers(data.users || []);
      }
    } catch (e) { console.error(e); }
    finally { setFeishuLoading(false); }
  };

  const fetchChatGroups = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/chats`);
      if (res.ok) setChatGroups((await res.json()).chats || []);
    } catch (e) { console.error(e); }
  };

  const fetchRecentMessages = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/feishu/messages?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setRecentMessages(data.messages || []);
      }
    } catch (e) { console.error(e); }
  };

  const fetchUserMessages = async (user: FeishuUser) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/feishu/user/${encodeURIComponent(user.name)}/messages?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setDetailMessages(data.messages || []);
      }
    } catch (e) { console.error(e); }
    finally { setDetailLoading(false); }
  };

  const fetchChatMessages = async (chat: ChatGroup) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/feishu/chat/${encodeURIComponent(chat.chat_id)}/messages?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setDetailMessages(data.messages || []);
      }
    } catch (e) { console.error(e); }
    finally { setDetailLoading(false); }
  };

  // ========== Handlers ==========
  const handleSelectFeishuUser = (user: FeishuUser) => {
    setSelectedFeishuUser(user);
    setSelectedChat(null);
    setFeishuDetailType("user");
    fetchUserMessages(user);
  };

  const handleSelectChat = (chat: ChatGroup) => {
    setSelectedChat(chat);
    setSelectedFeishuUser(null);
    setFeishuDetailType("chat");
    fetchChatMessages(chat);
  };

  const handleCloseFeishuDetail = () => {
    setFeishuDetailType(null);
    setSelectedFeishuUser(null);
    setSelectedChat(null);
    setDetailMessages([]);
  };

  const handleSelectDept = (dept: string) => {
    if (filterDept === dept) {
      setFilterDept(null);
      fetchPeople(null);
    } else {
      setFilterDept(dept);
      fetchPeople(dept);
    }
    setSelectedPerson(null);
  };

  const handleMessageClick = (msg: Message) => {
    // 尝试找到对应的用户
    const user = feishuUsers.find(u => u.name === msg.sender?.name);
    if (user) {
      handleSelectFeishuUser(user);
    } else if (msg.chat_id) {
      // 尝试找到对应的群聊
      const chat = chatGroups.find(c => c.chat_id === msg.chat_id);
      if (chat) {
        handleSelectChat(chat);
      }
    }
  };

  const handleGenerateProfile = () => {
    if (!selectedPerson?.email) return;
    setProfileLoading(true);
    setProfileData(null);
    fetch(`${API_BASE}/api/employee-profile/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: selectedPerson.email, force_refresh: true })
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) setProfileData(data.profile);
      })
      .catch(console.error)
      .finally(() => setProfileLoading(false));
  };

  // ========== Effects ==========
  useEffect(() => {
    if (activeSource === "email") {
      fetchDashboard();
      fetchPeople(filterDept);
    } else {
      fetchFeishuUsers();
      fetchChatGroups();
      fetchRecentMessages();
    }
  }, [activeSource]);

  useEffect(() => {
    if (selectedPerson) {
      // 重置邮件状态
      setShowEmails(false);
      setPersonEmails([]);
      // 自动生成AI画像
      setProfileLoading(true);
      setProfileData(null);
      fetch(`${API_BASE}/api/employee-profile/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: selectedPerson.email })
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) setProfileData(data.profile);
        })
        .catch(console.error)
        .finally(() => setProfileLoading(false));
    }
  }, [selectedPerson]);

  // ========== Computed Stats ==========
  const totalEmailSent = people.reduce((sum, p) => sum + (p.email_sent_total || 0), 0);
  const totalEmailReceived = people.reduce((sum, p) => sum + (p.email_received_total || 0), 0);
  const topEmailSenders = [...people].sort((a, b) => b.email_sent_total - a.email_sent_total).slice(0, 10);
  const departments = dashboard?.by_department || [];
  const totalFeishuMessages = feishuUsers.reduce((sum, u) => sum + u.message_count, 0);

  // ========== Render ==========
  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 text-white overflow-auto">
      {/* Header with Source Toggle */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/50 bg-zinc-900/30 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-rose-500 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Building className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">企业情报中心</h1>
            </div>

            {/* Source Toggle */}
            <div className="flex items-center bg-zinc-800/50 rounded-xl p-1 ml-4">
              <button
                onClick={() => { setActiveSource("email"); setSelectedPerson(null); setFilterDept(null); }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeSource === "email"
                    ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Mail className="w-4 h-4" />
                邮件系统
              </button>
              <button
                onClick={() => { setActiveSource("feishu"); handleCloseFeishuDetail(); }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeSource === "feishu"
                    ? "bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-lg"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <MessageSquare className="w-4 h-4" />
                飞书
              </button>
            </div>

            {/* Department Filter Badge */}
            {activeSource === "email" && filterDept && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-violet-500/20 border border-violet-500/30 rounded-lg">
                <Filter className="w-3 h-3 text-violet-400" />
                <span className="text-sm text-violet-400">{filterDept}</span>
                <button onClick={() => { setFilterDept(null); fetchPeople(null); }} className="text-violet-400 hover:text-violet-300">
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>

          <div className="text-sm text-zinc-500">
            {activeSource === "email" ? (
              <>共 <span className="text-blue-400 font-semibold">{filterDept ? people.length : dashboard?.stats.total_people || 0}</span> 名员工</>
            ) : (
              <>共 <span className="text-emerald-400 font-semibold">{feishuUsers.length}</span> 名用户</>
            )}
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 p-6 overflow-auto">
        {activeSource === "email" ? (
          /* ========== Email System View ========== */
          <div className="grid grid-cols-12 gap-6">
            {/* Left Column */}
            <div className="col-span-5 space-y-6">
              {/* Stats Overview - 可点击 */}
              <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5">
                <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                  <Zap className="w-4 h-4 text-blue-500" />
                  邮件概览
                </h2>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    onClick={() => { setFilterDept(null); fetchPeople(null); }}
                    className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/30 hover:border-blue-500/30 hover:bg-blue-500/5 transition-all text-left"
                  >
                    <div className="text-2xl font-bold text-blue-400">{dashboard?.stats.total_people || 0}</div>
                    <div className="text-xs text-zinc-500 mt-1">员工总数</div>
                  </button>
                  <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/30">
                    <div className="text-2xl font-bold text-emerald-400">{totalEmailSent.toLocaleString()}</div>
                    <div className="text-xs text-zinc-500 mt-1">发送总量</div>
                  </div>
                  <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/30">
                    <div className="text-2xl font-bold text-violet-400">{totalEmailReceived.toLocaleString()}</div>
                    <div className="text-xs text-zinc-500 mt-1">接收总量</div>
                  </div>
                </div>
              </div>

              {/* Department Distribution - 可点击筛选 */}
              <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5">
                <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                  <BarChart3 className="w-4 h-4 text-violet-500" />
                  部门分布
                  <span className="text-[10px] text-zinc-600 ml-auto">点击筛选</span>
                </h2>
                <div className="space-y-2">
                  {departments.slice(0, 6).map((dept) => (
                    <button
                      key={dept.name}
                      onClick={() => handleSelectDept(dept.name)}
                      className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${
                        filterDept === dept.name
                          ? "bg-violet-500/20 border-violet-500/30"
                          : "bg-zinc-800/30 border-zinc-700/30 hover:bg-zinc-800/50 hover:border-zinc-600/50"
                      }`}
                    >
                      <span className="text-sm text-zinc-300">{dept.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white">{dept.count}</span>
                        <ChevronRight className="w-4 h-4 text-zinc-600" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* All Employees List */}
              <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5">
                <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                  <Users className="w-4 h-4 text-blue-500" />
                  {filterDept ? `${filterDept} 员工` : "全部员工"}
                  <span className="text-xs text-zinc-500 ml-auto">{people.length} 人</span>
                </h2>
                <div className="space-y-2 max-h-[500px] overflow-auto">
                  {peopleLoading ? (
                    <div className="flex justify-center py-8">
                      <RefreshCw className="w-5 h-5 animate-spin text-zinc-500" />
                    </div>
                  ) : people.length === 0 ? (
                    <div className="text-center py-8 text-zinc-500 text-sm">暂无数据</div>
                  ) : (
                    people.map((person) => (
                      <button
                        key={person.user_id}
                        onClick={() => setSelectedPerson(person)}
                        className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                          selectedPerson?.user_id === person.user_id
                            ? "bg-blue-500/20 border-blue-500/30"
                            : "bg-zinc-800/30 border-zinc-700/30 hover:bg-zinc-800/50"
                        }`}
                      >
                        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${getAvatarColor(person.name)} flex items-center justify-center text-white text-sm font-medium`}>
                          {person.name?.charAt(0)}
                        </div>
                        <div className="flex-1 text-left">
                          <div className="text-sm font-medium text-white truncate">{person.name}</div>
                          <div className="text-xs text-zinc-600 truncate">{person.ms365_job_title || person.department || ""}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-semibold text-blue-400">{person.email_sent_total}</div>
                          <div className="text-[10px] text-zinc-600">发送</div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-zinc-600" />
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Right Column - Person Detail */}
            <div className="col-span-7">
              {selectedPerson ? (
                <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 h-full flex flex-col">
                  {/* Person Header */}
                  <div className="p-6 border-b border-zinc-800/50">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${getAvatarColor(selectedPerson.name)} flex items-center justify-center text-white text-2xl font-bold shadow-lg`}>
                          {selectedPerson.name?.charAt(0)}
                        </div>
                        <div>
                          <h2 className="text-xl font-bold text-white">{selectedPerson.name}</h2>
                          <p className="text-sm text-zinc-400">{selectedPerson.ms365_job_title || selectedPerson.function || "未设置职位"}</p>
                          <p className="text-xs text-zinc-600 mt-1">{selectedPerson.email}</p>
                        </div>
                      </div>
                      <button onClick={() => setSelectedPerson(null)} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
                        <X className="w-4 h-4 text-zinc-500" />
                      </button>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-4 mt-4">
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 rounded-lg">
                        <ArrowUpRight className="w-4 h-4 text-emerald-400" />
                        <span className="text-sm font-medium text-emerald-400">{selectedPerson.email_sent_total}</span>
                        <span className="text-xs text-zinc-500">发送</span>
                      </div>
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 rounded-lg">
                        <ArrowDownLeft className="w-4 h-4 text-blue-400" />
                        <span className="text-sm font-medium text-blue-400">{selectedPerson.email_received_total}</span>
                        <span className="text-xs text-zinc-500">接收</span>
                      </div>
                      {selectedPerson.department && selectedPerson.department !== "未定义" && (
                        <button
                          onClick={() => handleSelectDept(selectedPerson.department)}
                          className="px-3 py-1.5 bg-violet-500/10 text-violet-400 rounded-lg text-xs hover:bg-violet-500/20 transition-colors"
                        >
                          {selectedPerson.department}
                        </button>
                      )}
                    </div>

                    {/* Email Toggle Button */}
                    <div className="mt-4">
                      <button
                        onClick={() => {
                          if (!showEmails) {
                            setShowEmails(true);
                            fetchPersonEmails(selectedPerson);
                          } else {
                            setShowEmails(false);
                          }
                        }}
                        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                          showEmails
                            ? "bg-blue-500 text-white"
                            : "bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400"
                        }`}
                      >
                        <Mail className="w-4 h-4" />
                        {showEmails ? "收起邮件" : "查看最近邮件"}
                        <ChevronRight className={`w-4 h-4 transition-transform ${showEmails ? "rotate-90" : ""}`} />
                      </button>
                    </div>

                    {/* Inline Email List */}
                    {showEmails && (
                      <div className="mt-4 p-4 bg-zinc-800/30 rounded-xl border border-zinc-700/30 max-h-[300px] overflow-auto">
                        {emailsLoading ? (
                          <div className="flex justify-center py-6">
                            <RefreshCw className="w-5 h-5 animate-spin text-zinc-500" />
                          </div>
                        ) : personEmails.length === 0 ? (
                          <div className="text-center py-6">
                            <Mail className="w-10 h-10 text-zinc-700 mx-auto mb-2" />
                            <p className="text-sm text-zinc-500">暂无邮件记录</p>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {personEmails.map((email) => (
                              <div
                                key={email.email_id}
                                className="p-3 bg-zinc-900/50 rounded-lg border border-zinc-700/20 hover:bg-zinc-900/80 transition-all"
                              >
                                <div className="flex items-center gap-2 mb-1">
                                  <span className={`px-2 py-0.5 rounded text-xs ${
                                    email.folder === "sentitems" || email.folder === "sent"
                                      ? "bg-emerald-500/10 text-emerald-400"
                                      : "bg-blue-500/10 text-blue-400"
                                  }`}>
                                    {email.folder === "sentitems" || email.folder === "sent" ? "发送" : "收件"}
                                  </span>
                                  <span className="text-xs text-zinc-600">
                                    {new Date(email.received_at || email.sent_at || "").toLocaleString("zh-CN", {
                                      month: "short",
                                      day: "numeric",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })}
                                  </span>
                                </div>
                                <h4 className="text-sm font-medium text-white line-clamp-1">{email.subject || "(无主题)"}</h4>
                                <div className="text-xs text-zinc-500 mt-1">
                                  {email.folder === "sentitems" || email.folder === "sent" ? (
                                    <>收件人: {email.to?.map(t => t.name || t.address).join(", ")}</>
                                  ) : (
                                    <>发件人: {email.from?.name || email.from?.address}</>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Content Area - AI Profile */}
                  <div className="flex-1 overflow-auto">
                    <EmployeeAIProfile
                      data={profileData}
                      isLoading={profileLoading}
                      onRefresh={handleGenerateProfile}
                      employeeName={selectedPerson.name}
                      employeeEmail={selectedPerson.email}
                    />
                  </div>
                </div>
              ) : (
                <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 h-full flex items-center justify-center">
                  <div className="text-center">
                    <Mail className="w-16 h-16 text-zinc-700 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-zinc-400 mb-2">选择一位员工</h3>
                    <p className="text-sm text-zinc-600">查看邮件往来记录</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* ========== Feishu View ========== */
          <div className="grid grid-cols-12 gap-6">
            {/* Left Column */}
            <div className="col-span-5 space-y-6">
              {/* Stats Overview - 可点击 */}
              <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5">
                <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                  <Zap className="w-4 h-4 text-emerald-500" />
                  飞书概览
                </h2>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    onClick={handleCloseFeishuDetail}
                    className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/30 hover:border-emerald-500/30 hover:bg-emerald-500/5 transition-all text-left"
                  >
                    <div className="text-2xl font-bold text-emerald-400">{feishuUsers.length}</div>
                    <div className="text-xs text-zinc-500 mt-1">活跃用户</div>
                  </button>
                  <button
                    onClick={handleCloseFeishuDetail}
                    className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/30 hover:border-cyan-500/30 hover:bg-cyan-500/5 transition-all text-left"
                  >
                    <div className="text-2xl font-bold text-cyan-400">{chatGroups.length}</div>
                    <div className="text-xs text-zinc-500 mt-1">群聊</div>
                  </button>
                  <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/30">
                    <div className="text-2xl font-bold text-violet-400">{totalFeishuMessages.toLocaleString()}</div>
                    <div className="text-xs text-zinc-500 mt-1">消息总量</div>
                  </div>
                </div>
              </div>

              {/* Chat Groups - 可点击 */}
              <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5">
                <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                  <Hash className="w-4 h-4 text-cyan-500" />
                  群聊列表
                  <span className="text-[10px] text-zinc-600 ml-auto">点击查看</span>
                </h2>
                <div className="space-y-2">
                  {chatGroups.slice(0, 6).map((chat) => (
                    <button
                      key={chat.chat_id}
                      onClick={() => handleSelectChat(chat)}
                      className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${
                        selectedChat?.chat_id === chat.chat_id
                          ? "bg-cyan-500/20 border-cyan-500/30"
                          : "bg-zinc-800/30 border-zinc-700/30 hover:bg-zinc-800/50"
                      }`}
                    >
                      <span className="text-sm text-zinc-300 truncate">{chat.chat_name}</span>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded text-xs">{chat.total_messages} 条</span>
                        <ChevronRight className="w-4 h-4 text-zinc-600" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Active Users */}
              <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5">
                <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                  <TrendingUp className="w-4 h-4 text-orange-500" />
                  消息活跃榜
                </h2>
                <div className="space-y-2">
                  {feishuLoading ? (
                    <div className="flex justify-center py-8">
                      <RefreshCw className="w-5 h-5 animate-spin text-zinc-500" />
                    </div>
                  ) : (
                    feishuUsers.slice(0, 10).map((user, idx) => (
                      <button
                        key={user.open_id || user.name}
                        onClick={() => handleSelectFeishuUser(user)}
                        className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                          selectedFeishuUser?.name === user.name
                            ? "bg-emerald-500/20 border-emerald-500/30"
                            : "bg-zinc-800/30 border-zinc-700/30 hover:bg-zinc-800/50"
                        }`}
                      >
                        <span className="text-xs text-zinc-600 w-5">{idx + 1}</span>
                        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${getAvatarColor(user.name)} flex items-center justify-center text-white text-sm font-medium`}>
                          {user.name?.charAt(0)}
                        </div>
                        <div className="flex-1 text-left">
                          <div className="text-sm font-medium text-white truncate">{user.name}</div>
                          <div className="text-xs text-zinc-600">{user.chat_count} 个群聊</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-semibold text-emerald-400">{user.message_count}</div>
                          <div className="text-[10px] text-zinc-600">消息</div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-zinc-600" />
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Right Column - Detail Panel or Recent Messages */}
            <div className="col-span-7">
              {feishuDetailType ? (
                <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 h-full flex flex-col">
                  {/* Detail Header */}
                  <div className="p-6 border-b border-zinc-800/50">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        {feishuDetailType === "user" && selectedFeishuUser ? (
                          <>
                            <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${getAvatarColor(selectedFeishuUser.name)} flex items-center justify-center text-white text-2xl font-bold shadow-lg`}>
                              {selectedFeishuUser.name?.charAt(0)}
                            </div>
                            <div>
                              <h2 className="text-xl font-bold text-white">{selectedFeishuUser.name}</h2>
                              <p className="text-sm text-zinc-400">飞书用户</p>
                            </div>
                          </>
                        ) : selectedChat ? (
                          <>
                            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-cyan-600 flex items-center justify-center text-white shadow-lg">
                              <Hash className="w-8 h-8" />
                            </div>
                            <div>
                              <h2 className="text-xl font-bold text-white">{selectedChat.chat_name}</h2>
                              <p className="text-sm text-zinc-400">群聊 · {selectedChat.total_messages} 条消息</p>
                            </div>
                          </>
                        ) : null}
                      </div>
                      <button onClick={handleCloseFeishuDetail} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
                        <X className="w-4 h-4 text-zinc-500" />
                      </button>
                    </div>

                    {/* Stats */}
                    {feishuDetailType === "user" && selectedFeishuUser && (
                      <div className="flex items-center gap-4 mt-4">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 rounded-lg">
                          <MessageSquare className="w-4 h-4 text-emerald-400" />
                          <span className="text-sm font-medium text-emerald-400">{selectedFeishuUser.message_count}</span>
                          <span className="text-xs text-zinc-500">消息</span>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/10 rounded-lg">
                          <Hash className="w-4 h-4 text-cyan-400" />
                          <span className="text-sm font-medium text-cyan-400">{selectedFeishuUser.chat_count}</span>
                          <span className="text-xs text-zinc-500">群聊</span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Messages */}
                  <div className="flex-1 p-6 overflow-auto">
                    <h3 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                      <Activity className="w-4 h-4 text-emerald-500" />
                      {feishuDetailType === "user" ? "发言记录" : "群聊消息"}
                    </h3>
                    {detailLoading ? (
                      <div className="flex justify-center py-8">
                        <RefreshCw className="w-5 h-5 animate-spin text-zinc-500" />
                      </div>
                    ) : detailMessages.length === 0 ? (
                      <div className="text-center py-12">
                        <MessageSquare className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
                        <p className="text-sm text-zinc-500">暂无消息记录</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {detailMessages.map((msg) => (
                          <div
                            key={msg.message_id}
                            className="p-4 bg-zinc-800/30 rounded-xl border border-zinc-700/30 hover:bg-zinc-800/50 transition-all cursor-pointer"
                            onClick={() => {
                              if (feishuDetailType === "chat") {
                                const user = feishuUsers.find(u => u.name === msg.sender?.name);
                                if (user) handleSelectFeishuUser(user);
                              }
                            }}
                          >
                            <div className="flex items-center justify-between mb-2">
                              {feishuDetailType === "chat" ? (
                                <div className="flex items-center gap-2">
                                  <div className={`w-6 h-6 rounded bg-gradient-to-br ${getAvatarColor(msg.sender?.name)} flex items-center justify-center text-white text-xs`}>
                                    {msg.sender?.name?.charAt(0)}
                                  </div>
                                  <span className="text-sm font-medium text-white">{msg.sender?.name}</span>
                                </div>
                              ) : (
                                <span className="px-2 py-0.5 bg-orange-500/10 text-orange-400 rounded text-xs">{msg.chat_name}</span>
                              )}
                              <span className="text-xs text-zinc-600">
                                {new Date(msg.timestamp).toLocaleString("zh-CN", {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            </div>
                            <p className="text-sm text-zinc-300">{msg.content}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* Recent Messages - 可点击 */
                <div className="bg-zinc-900/50 rounded-2xl border border-zinc-800/50 p-5 h-full">
                  <h2 className="text-sm font-semibold text-zinc-400 flex items-center gap-2 mb-4">
                    <Clock className="w-4 h-4 text-amber-500" />
                    最新消息
                    <span className="text-[10px] text-zinc-600 ml-auto">点击查看详情</span>
                  </h2>
                  <div className="space-y-3 max-h-[600px] overflow-auto">
                    {recentMessages.map((msg) => (
                      <button
                        key={msg.message_id}
                        onClick={() => handleMessageClick(msg)}
                        className="w-full p-4 bg-zinc-800/30 rounded-xl border border-zinc-700/30 hover:bg-zinc-800/50 hover:border-zinc-600/50 transition-all text-left"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <div className={`w-6 h-6 rounded bg-gradient-to-br ${getAvatarColor(msg.sender?.name)} flex items-center justify-center text-white text-xs`}>
                              {msg.sender?.name?.charAt(0)}
                            </div>
                            <span className="text-sm font-medium text-white">{msg.sender?.name}</span>
                            <span className="px-1.5 py-0.5 bg-zinc-700/50 text-zinc-500 rounded text-[10px]">{msg.chat_name}</span>
                          </div>
                          <span className="text-xs text-zinc-600">
                            {new Date(msg.timestamp).toLocaleString("zh-CN", {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <p className="text-sm text-zinc-400 line-clamp-2">{msg.content}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>


    </div>
  );
}
