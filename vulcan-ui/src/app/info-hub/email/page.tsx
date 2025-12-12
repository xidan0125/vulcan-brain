"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import {
  Mail,
  Calendar,
  Search,
  Star,
  Paperclip,
  RefreshCw,
  Inbox,
  Send,
  Users,
  Clock,
  AlertCircle,
  Filter,
} from "lucide-react";
import InfoHubBreadcrumb from "@/components/info-hub/InfoHubBreadcrumb";

interface Email {
  email_id: string;
  from: { name: string; address: string };
  to: { name: string; address: string }[];
  subject: string;
  body_preview: string;
  importance: string;
  is_read: boolean;
  has_attachments: boolean;
  received_at: string;
  folder: string;
}

interface Contact {
  address: string;
  name: string;
  count: number;
  last_email: string;
}

export default function EmailHistoryPage() {
  const searchParams = useSearchParams();
  const dateParam = searchParams.get("date");

  const [emails, setEmails] = useState<Email[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"inbox" | "sent" | "contacts">("inbox");
  const [dateFilter, setDateFilter] = useState(dateParam || "");
  const [searchTerm, setSearchTerm] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [stats, setStats] = useState({ total: 0, unread: 0, important: 0 });

  const fetchEmails = async (folder: string) => {
    setLoading(true);
    try {
      let url = `/api/info-hub/email/list?folder=${folder}&limit=100`;
      if (dateFilter) {
        url += `&date=${dateFilter}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setEmails(data.emails || []);
        // 计算统计
        const emailList = data.emails || [];
        setStats({
          total: emailList.length,
          unread: emailList.filter((e: Email) => !e.is_read).length,
          important: emailList.filter((e: Email) => e.importance === "high").length,
        });
      }
    } catch (error) {
      console.error("获取邮件失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchContacts = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/info-hub/email/contacts?days=30&limit=50`);
      if (res.ok) {
        const data = await res.json();
        setContacts(data.contacts || []);
      }
    } catch (error) {
      console.error("获取联系人失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const syncEmails = async () => {
    setSyncing(true);
    try {
      await fetch(`/api/info-hub/email/sync?days=7`, { method: "POST" });
      await new Promise((r) => setTimeout(r, 3000));
      if (tab === "contacts") {
        await fetchContacts();
      } else {
        await fetchEmails(tab === "inbox" ? "inbox" : "sentItems");
      }
    } catch (error) {
      console.error("同步失败:", error);
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    if (tab === "contacts") {
      fetchContacts();
    } else {
      fetchEmails(tab === "inbox" ? "inbox" : "sentItems");
    }
  }, [tab, dateFilter]);

  const filteredEmails = emails.filter(
    (e) =>
      e.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.from.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.from.address.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredContacts = contacts.filter(
    (c) =>
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.address.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* 面包屑 */}
      <InfoHubBreadcrumb items={[{ label: "邮件分析" }]} />

      {/* 页面标题 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <Mail className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">邮件分析</h1>
            <p className="text-sm text-zinc-500">Microsoft 365 邮件历史记录</p>
          </div>
        </div>

        <button
          onClick={syncEmails}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 rounded-lg text-sm text-amber-400 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "同步中..." : "同步邮件"}
        </button>
      </div>

      {/* 统计卡片 - 始终显示 */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <div className="flex items-center gap-2 mb-2">
            <Mail className="w-4 h-4 text-amber-400" />
            <span className="text-xs text-zinc-500">邮件总数</span>
          </div>
          <div className="text-2xl font-bold text-amber-400">{loading ? "-" : stats.total}</div>
        </div>
        <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-zinc-500">未读邮件</span>
          </div>
          <div className="text-2xl font-bold text-blue-400">{loading ? "-" : stats.unread}</div>
        </div>
        <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
          <div className="flex items-center gap-2 mb-2">
            <Star className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-zinc-500">重要邮件</span>
          </div>
          <div className="text-2xl font-bold text-yellow-400">{loading ? "-" : stats.important}</div>
        </div>
      </div>

      {/* Tab 切换 + 搜索过滤 */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex bg-zinc-900 rounded-lg p-1">
          {[
            { id: "inbox", label: "收件箱", icon: Inbox },
            { id: "sent", label: "已发送", icon: Send },
            { id: "contacts", label: "联系人", icon: Users },
          ].map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
                  tab === t.id
                    ? "bg-amber-500/20 text-amber-400"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4" />
                {t.label}
              </button>
            );
          })}
        </div>

        <div className="flex-1 flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="搜索邮件主题、发件人..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500/50"
            />
          </div>

          {tab !== "contacts" && (
            <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
              <Calendar className="w-4 h-4 text-zinc-500" />
              <input
                type="date"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                className="bg-transparent text-sm text-white focus:outline-none"
              />
            </div>
          )}
        </div>
      </div>

      {/* 内容区 */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-zinc-800" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-zinc-800 rounded mb-2" />
                  <div className="h-3 w-full bg-zinc-800/50 rounded mb-1" />
                  <div className="h-3 w-2/3 bg-zinc-800/30 rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : tab === "contacts" ? (
        /* 联系人列表 */
        <div className="space-y-2">
          {filteredContacts.length === 0 ? (
            <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
              <Users className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-zinc-400">暂无联系人数据</h3>
              <p className="text-sm text-zinc-600 mt-2">点击"同步邮件"获取联系人信息</p>
            </div>
          ) : (
            filteredContacts.map((contact, idx) => (
              <div
                key={idx}
                className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 flex items-center gap-4 hover:bg-zinc-900/70 transition-colors"
              >
                <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                  <span className="text-amber-400 font-medium">
                    {contact.name ? contact.name[0].toUpperCase() : contact.address[0].toUpperCase()}
                  </span>
                </div>
                <div className="flex-1">
                  <div className="font-medium text-white">{contact.name || contact.address}</div>
                  <div className="text-xs text-zinc-500">{contact.address}</div>
                </div>
                <div className="text-right">
                  <div className="text-amber-400 font-medium">{contact.count} 封</div>
                  <div className="text-xs text-zinc-600 flex items-center gap-1 justify-end">
                    <Clock className="w-3 h-3" />
                    {new Date(contact.last_email).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* 邮件列表 */
        <div className="space-y-2">
          {filteredEmails.length === 0 ? (
            <div className="text-center py-16 bg-zinc-900/50 rounded-xl border border-zinc-800">
              <Mail className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-zinc-400">暂无邮件</h3>
              <p className="text-sm text-zinc-600 mt-2">点击"同步邮件"从 Microsoft 365 获取最新数据</p>
            </div>
          ) : (
            filteredEmails.map((email) => (
              <div
                key={email.email_id}
                className={`p-4 rounded-xl border transition-colors cursor-pointer ${
                  email.is_read
                    ? "bg-zinc-900/30 border-zinc-800 hover:bg-zinc-900/50"
                    : "bg-zinc-900/50 border-zinc-700 hover:border-zinc-600"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-amber-400 text-sm font-medium">
                      {email.from.name ? email.from.name[0].toUpperCase() : email.from.address[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`font-medium text-sm ${email.is_read ? "text-zinc-400" : "text-white"}`}>
                        {email.from.name || email.from.address}
                      </span>
                      {!email.is_read && (
                        <span className="w-2 h-2 rounded-full bg-blue-400" />
                      )}
                      {email.importance === "high" && (
                        <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
                      )}
                      {email.has_attachments && (
                        <Paperclip className="w-3 h-3 text-zinc-500" />
                      )}
                      <span className="text-xs text-zinc-600 ml-auto">
                        {new Date(email.received_at).toLocaleString()}
                      </span>
                    </div>
                    <div className={`text-sm mb-1 ${email.is_read ? "text-zinc-500" : "text-zinc-300"}`}>
                      {email.subject || "(无主题)"}
                    </div>
                    <div className="text-xs text-zinc-600 truncate">{email.body_preview}</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
