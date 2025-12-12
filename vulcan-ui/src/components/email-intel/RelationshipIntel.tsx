"use client";

import { useEffect, useState } from "react";
import { Search, Users, Building2, Handshake, HelpCircle, Mail, Clock, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.vsg-brain.com/api";

// 实体类型筛选
const RELATION_FILTERS = [
  { value: "all", label: "全部", icon: Users },
  { value: "client", label: "客户", icon: Building2 },
  { value: "vendor", label: "供应商", icon: Building2 },
  { value: "partner", label: "合作伙伴", icon: Handshake },
  { value: "government", label: "政府", icon: Building2 },
  { value: "unknown", label: "未分类", icon: HelpCircle },
] as const;

type RelationFilter = typeof RELATION_FILTERS[number]["value"];

interface Contact {
  id: string;
  name: string;
  email: string;
  company: string;
  company_domain?: string;
  relation_type: string;
  total_emails: number;
  last_contact: string;
  days_since_contact: number;
}

interface ContactEmail {
  _id: string;
  subject: string;
  from: { address: string; name?: string };
  to: Array<{ address: string; name?: string }>;
  received_at: string;
  snippet: string;
}

interface RelationshipData {
  contacts: Contact[];
  total_contacts: number;
  client_count: number;
  vendor_count: number;
  partner_count: number;
  government_count: number;
  unknown_count: number;
}

// 实体类型标签
function RelationBadge({ type }: { type: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    client: { bg: "bg-emerald-500/10", text: "text-emerald-400", label: "客户" },
    vendor: { bg: "bg-blue-500/10", text: "text-blue-400", label: "供应商" },
    partner: { bg: "bg-purple-500/10", text: "text-purple-400", label: "合作伙伴" },
    government: { bg: "bg-amber-500/10", text: "text-amber-400", label: "政府" },
    internal: { bg: "bg-gray-500/10", text: "text-gray-400", label: "内部" },
    unknown: { bg: "bg-gray-500/10", text: "text-gray-500", label: "未分类" },
  };
  const c = config[type] || config.unknown;
  return (
    <span className={cn("text-xs px-2 py-0.5 rounded font-medium", c.bg, c.text)}>
      {c.label}
    </span>
  );
}

function ContactCard({ contact, onClick }: { contact: Contact; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="bg-card border border-border rounded-xl p-4 hover:border-primary/50 transition-colors cursor-pointer"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-white truncate">{contact.name}</h4>
          <p className="text-sm text-muted-foreground truncate">{contact.email}</p>
          {contact.company && (
            <p className="text-xs text-primary truncate">{contact.company}</p>
          )}
        </div>
        <RelationBadge type={contact.relation_type} />
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Mail className="w-3 h-3" />
          {contact.total_emails} 封邮件
        </span>
        <span className={cn(
          "flex items-center gap-1",
          contact.days_since_contact < 7 ? "text-emerald-400" :
          contact.days_since_contact < 30 ? "text-amber-400" : "text-red-400"
        )}>
          <Clock className="w-3 h-3" />
          {contact.days_since_contact}天前
        </span>
      </div>
    </div>
  );
}

export default function RelationshipIntel() {
  const [data, setData] = useState<RelationshipData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<RelationFilter>("all");
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contactEmails, setContactEmails] = useState<ContactEmail[]>([]);
  const [emailsLoading, setEmailsLoading] = useState(false);

  async function fetchData() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/email-intel/relationships`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (selectedContact?.email) {
      setEmailsLoading(true);
      fetch(`${API_BASE}/email-intel/contact/${encodeURIComponent(selectedContact.email)}/emails?limit=30`)
        .then(res => res.json())
        .then(data => {
          setContactEmails(data.emails || []);
          setEmailsLoading(false);
        })
        .catch(err => {
          console.error('Failed to fetch contact emails:', err);
          setContactEmails([]);
          setEmailsLoading(false);
        });
    } else {
      setContactEmails([]);
    }
  }, [selectedContact]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400">
        <p>{error}</p>
        <button onClick={fetchData} className="mt-2 text-primary hover:underline">重试</button>
      </div>
    );
  }

  if (!data) return null;

  const filteredContacts = data.contacts.filter(contact => {
    const matchesSearch = !searchQuery ||
      contact.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      contact.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      contact.company?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesFilter = filter === "all" || contact.relation_type === filter;

    return matchesSearch && matchesFilter;
  });

  // 统计各类型数量
  const countByType = data.contacts.reduce((acc, c) => {
    const t = c.relation_type || "unknown";
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6">
      {/* Stats - 按实体类型统计 */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <Users className="w-5 h-5 text-muted-foreground mb-2" />
          <div className="text-2xl font-bold text-white">{data.total_contacts}</div>
          <div className="text-sm text-muted-foreground">总联系人</div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="w-5 h-5 rounded-full bg-emerald-500 mb-2" />
          <div className="text-2xl font-bold text-emerald-400">{countByType.client || 0}</div>
          <div className="text-sm text-muted-foreground">客户</div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="w-5 h-5 rounded-full bg-blue-500 mb-2" />
          <div className="text-2xl font-bold text-blue-400">{countByType.vendor || 0}</div>
          <div className="text-sm text-muted-foreground">供应商</div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="w-5 h-5 rounded-full bg-purple-500 mb-2" />
          <div className="text-2xl font-bold text-purple-400">{countByType.partner || 0}</div>
          <div className="text-sm text-muted-foreground">合作伙伴</div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="w-5 h-5 rounded-full bg-amber-500 mb-2" />
          <div className="text-2xl font-bold text-amber-400">{countByType.government || 0}</div>
          <div className="text-sm text-muted-foreground">政府</div>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="w-5 h-5 rounded-full bg-gray-500 mb-2" />
          <div className="text-2xl font-bold text-gray-400">{countByType.unknown || 0}</div>
          <div className="text-sm text-muted-foreground">未分类</div>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="搜索联系人..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-card border border-border rounded-lg text-sm text-white placeholder-muted-foreground focus:outline-none focus:border-primary"
          />
        </div>
        <button
          onClick={fetchData}
          className="p-2 bg-card border border-border rounded-lg text-muted-foreground hover:text-white hover:border-primary transition-colors"
          title="刷新"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
        </button>
      </div>

      {/* 实体类型筛选 */}
      <div className="flex flex-wrap gap-2">
        {RELATION_FILTERS.map((f) => {
          const count = f.value === "all" ? data.total_contacts : (countByType[f.value] || 0);
          const Icon = f.icon;
          return (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                filter === f.value
                  ? "bg-primary/10 text-primary"
                  : "bg-card border border-border text-muted-foreground hover:text-white"
              )}
            >
              <Icon className="w-4 h-4" />
              {f.label}
              <span className="opacity-60">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Contacts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredContacts.length === 0 ? (
          <p className="text-muted-foreground col-span-full text-center py-8">
            没有找到联系人
          </p>
        ) : (
          filteredContacts.slice(0, 30).map((contact) => (
            <ContactCard
              key={contact.id}
              contact={contact}
              onClick={() => setSelectedContact(contact)}
            />
          ))
        )}
      </div>

      {/* Contact Details Modal */}
      {selectedContact && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedContact(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-800 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              {/* Contact Header */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-white mb-2">{selectedContact.name}</h2>
                  <p className="text-zinc-400 mb-1">{selectedContact.email}</p>
                  {selectedContact.company && (
                    <p className="text-primary text-sm">{selectedContact.company}</p>
                  )}
                </div>
                <button
                  onClick={() => setSelectedContact(null)}
                  className="text-zinc-500 hover:text-white transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Contact Stats */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-zinc-400 text-sm mb-1">
                    <Mail className="w-4 h-4" />
                    总邮件数
                  </div>
                  <div className="text-2xl font-bold text-white">{selectedContact.total_emails}</div>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-zinc-400 text-sm mb-1">
                    <Clock className="w-4 h-4" />
                    最后联系
                  </div>
                  <div className="text-2xl font-bold text-white">{selectedContact.days_since_contact}天前</div>
                </div>
              </div>

              {/* Email History */}
              <div className="mt-6">
                <h3 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
                  <Mail size={16} />
                  邮件往来记录 ({contactEmails.length})
                </h3>
                {emailsLoading ? (
                  <div className="text-center py-4 text-zinc-500">加载中...</div>
                ) : contactEmails.length > 0 ? (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {contactEmails.map((email) => (
                      <div key={email._id} className="p-3 rounded-lg bg-zinc-800/50 hover:bg-zinc-800 transition cursor-pointer">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-white truncate">{email.subject || '(无主题)'}</p>
                            <p className="text-xs text-zinc-500 mt-1">
                              {email.from?.address === selectedContact.email ? '发送给您' : '来自'}: {email.from?.name || email.from?.address}
                            </p>
                          </div>
                          <span className="text-xs text-zinc-500 whitespace-nowrap">
                            {new Date(email.received_at).toLocaleDateString('zh-CN', {month: 'short', day: 'numeric'})}
                          </span>
                        </div>
                        {email.snippet && (
                          <p className="text-xs text-zinc-600 mt-2 line-clamp-2">{email.snippet}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-zinc-600 text-sm">暂无邮件记录</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
