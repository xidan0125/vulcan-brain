"use client";

import { useEffect, useState, useCallback } from "react";
import { Building2, Users, Mail, Globe, Search, Clock, Activity, AlertTriangle, TrendingUp, RefreshCw, ChevronLeft, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.vsg-brain.com/api";

// 分类筛选
const RELATION_FILTERS = [
  { value: "all", label: "全部" },
  { value: "client", label: "客户" },
  { value: "vendor", label: "供应商" },
  { value: "partner", label: "合作伙伴" },
  { value: "internal", label: "内部" },
  { value: "unknown", label: "未分类" },
] as const;

// 排序选项
const SORT_OPTIONS = [
  { value: "emails", label: "业务量", icon: Mail },
  { value: "recent30", label: "近30天", icon: Activity },
  { value: "silent", label: "沉默警告", icon: AlertTriangle },
] as const;

type RelationFilter = typeof RELATION_FILTERS[number]["value"];
type SortOption = typeof SORT_OPTIONS[number]["value"];

interface Company {
  domain: string;
  name: string;
  email_count: number;
  contact_count: number;
  last_contact: string | null;
  days_silent: number;
  recent_activity: number;
  relation_type: string;
  key_contacts?: Array<{
    name: string;
    email: string;
    sent_count?: number;
    received_count?: number;
  }>;
}

// 公司详情数据
interface CompanyDetail {
  domain: string;
  name: string;
  relation_type: string;
  stats: {
    email_count: number;
    contact_count: number;
    first_contact: string | null;
    last_contact: string | null;
  };
  contacts: Array<{
    email: string;
    name: string;
    health_score: number;
    total_interactions: number;
  }>;
  recent_emails: Array<{
    subject: string;
    from: string;
    date: string;
  }>;
}

// 联系人邮件数据
interface ContactEmail {
  _id: string;
  subject: string;
  from: { address: string; name?: string };
  to: Array<{ address: string; name?: string }>;
  received_at: string;
  snippet?: string;
  body_text?: string;
}

// 邮件详情
interface EmailDetail {
  _id: string;
  subject: string;
  from: { address: string; name?: string };
  to: Array<{ address: string; name?: string }>;
  received_at: string;
  body_text: string;
  body_html?: string;
}

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
    <span className={cn("text-xs px-2 py-0.5 rounded", c.bg, c.text)}>
      {c.label}
    </span>
  );
}

function CompanyCard({ company, onSelect, isSelected }: { company: Company; onSelect: () => void; isSelected: boolean }) {
  const needsAttention = company.days_silent > 14 && company.email_count > 100;

  return (
    <div
      onClick={onSelect}
      className={cn(
        "border rounded-lg p-3 cursor-pointer transition-all",
        isSelected
          ? "bg-primary/10 border-primary"
          : needsAttention
            ? "bg-card border-amber-500/30 hover:border-amber-500/50"
            : "bg-card border-border hover:border-primary/50"
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Building2 className={cn(
            "w-4 h-4 flex-shrink-0",
            needsAttention ? "text-amber-500" : "text-primary"
          )} />
          <div className="min-w-0">
            <h4 className="font-medium text-white text-sm truncate">{company.name}</h4>
            <p className="text-xs text-muted-foreground truncate">{company.domain}</p>
          </div>
        </div>
        <RelationBadge type={company.relation_type} />
      </div>

      <div className="flex items-center gap-3 text-xs">
        <div className="flex items-center gap-1">
          <Mail className="w-3 h-3 text-muted-foreground" />
          <span className="text-white">{company.email_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1">
          <Activity className={cn(
            "w-3 h-3",
            company.recent_activity > 10 ? "text-emerald-400" :
            company.recent_activity > 0 ? "text-amber-400" : "text-gray-500"
          )} />
          <span className="text-white">{company.recent_activity}</span>
        </div>
        <div className="flex items-center gap-1">
          <Clock className={cn(
            "w-3 h-3",
            company.days_silent < 7 ? "text-emerald-400" :
            company.days_silent < 30 ? "text-amber-400" : "text-red-400"
          )} />
          <span className={cn(
            company.days_silent < 7 ? "text-emerald-400" :
            company.days_silent < 30 ? "text-amber-400" : "text-red-400"
          )}>{company.days_silent}d</span>
        </div>
      </div>

      {needsAttention && (
        <div className="mt-2 flex items-center gap-1 text-xs text-amber-400">
          <AlertTriangle className="w-3 h-3" />
          <span>重要客户 {company.days_silent} 天未联系</span>
        </div>
      )}
    </div>
  );
}

// 邮件详情模态框
function EmailModal({ email, onClose }: { email: EmailDetail | null; onClose: () => void }) {
  if (!email) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-border flex items-start justify-between">
          <div className="flex-1 min-w-0 pr-4">
            <h3 className="font-bold text-white text-lg truncate">{email.subject || '(No Subject)'}</h3>
            <div className="text-sm text-muted-foreground mt-1">
              <span>From: {email.from?.name || email.from?.address}</span>
              <span className="mx-2">|</span>
              <span>{email.received_at ? new Date(email.received_at).toLocaleString('zh-CN') : ''}</span>
            </div>
            {email.to && email.to.length > 0 && (
              <div className="text-sm text-muted-foreground">
                To: {email.to.map(t => t.name || t.address).join(', ')}
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1 hover:bg-background rounded">
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap text-white/90">
            {email.body_text || '(No content)'}
          </div>
        </div>
      </div>
    </div>
  );
}

// 联系人邮件列表
function ContactEmailList({
  contactEmail,
  contactName,
  emails,
  loading,
  onSelectEmail,
  onBack
}: {
  contactEmail: string;
  contactName: string;
  emails: ContactEmail[];
  loading: boolean;
  onSelectEmail: (emailId: string) => void;
  onBack: () => void;
}) {
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={onBack} className="p-1 hover:bg-background rounded">
          <ChevronLeft className="w-5 h-5 text-muted-foreground" />
        </button>
        <div className="min-w-0">
          <h4 className="font-medium text-white truncate">{contactName}</h4>
          <p className="text-xs text-muted-foreground truncate">{contactEmail}</p>
        </div>
      </div>

      {/* Email List */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
        </div>
      ) : emails.length === 0 ? (
        <p className="text-muted-foreground text-center py-8">暂无邮件记录</p>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-2">
          {emails.map((email) => (
            <div
              key={email._id}
              onClick={() => onSelectEmail(email._id)}
              className="p-3 bg-background rounded-lg cursor-pointer hover:bg-background/80 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <h5 className="font-medium text-white text-sm truncate">{email.subject || '(No Subject)'}</h5>
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{email.snippet || ''}</p>
                </div>
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {email.received_at ? new Date(email.received_at).toLocaleDateString('zh-CN') : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CompanyDetail({ company, onClose }: { company: Company; onClose: () => void }) {
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedContact, setSelectedContact] = useState<{email: string; name: string} | null>(null);
  const [contactEmails, setContactEmails] = useState<ContactEmail[]>([]);
  const [contactEmailsLoading, setContactEmailsLoading] = useState(false);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [emailDetail, setEmailDetail] = useState<EmailDetail | null>(null);

  // 获取公司详情
  useEffect(() => {
    async function fetchDetail() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/email-intel/companies/${company.domain}`);
        if (res.ok) {
          const data = await res.json();
          setDetail(data);
        }
      } catch (err) {
        console.error('Failed to fetch company detail:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchDetail();
  }, [company.domain]);

  // 获取联系人邮件
  const fetchContactEmails = useCallback(async (email: string) => {
    setContactEmailsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/email-intel/contact/${encodeURIComponent(email)}/emails?limit=30`);
      if (res.ok) {
        const data = await res.json();
        // Sort emails by received_at, newest first
        const emails = (data.emails || []).sort((a: ContactEmail, b: ContactEmail) => {
          return new Date(b.received_at).getTime() - new Date(a.received_at).getTime();
        });
        setContactEmails(emails);
      }
    } catch (err) {
      console.error('Failed to fetch contact emails:', err);
    } finally {
      setContactEmailsLoading(false);
    }
  }, []);

  // 获取邮件详情
  const fetchEmailDetail = useCallback(async (emailId: string) => {
    try {
      const res = await fetch(`${API_BASE}/email-intel/email/${emailId}`);
      if (res.ok) {
        const data = await res.json();
        setEmailDetail(data);
      }
    } catch (err) {
      console.error('Failed to fetch email detail:', err);
    }
  }, []);

  // 处理选择联系人
  const handleSelectContact = (email: string, name: string) => {
    setSelectedContact({ email, name });
    fetchContactEmails(email);
  };

  // 处理选择邮件
  const handleSelectEmail = (emailId: string) => {
    setSelectedEmailId(emailId);
    fetchEmailDetail(emailId);
  };

  // 返回联系人列表
  const handleBackToContacts = () => {
    setSelectedContact(null);
    setContactEmails([]);
  };

  // 关闭邮件详情
  const handleCloseEmailDetail = () => {
    setSelectedEmailId(null);
    setEmailDetail(null);
  };

  // 如果选择了联系人，显示邮件列表
  if (selectedContact) {
    return (
      <div className="bg-card border border-border rounded-xl p-5 h-full">
        <ContactEmailList
          contactEmail={selectedContact.email}
          contactName={selectedContact.name}
          emails={contactEmails}
          loading={contactEmailsLoading}
          onSelectEmail={handleSelectEmail}
          onBack={handleBackToContacts}
        />
        {emailDetail && (
          <EmailModal email={emailDetail} onClose={handleCloseEmailDetail} />
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-xl p-5 h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const contacts = detail?.contacts || [];
  const recentEmails = detail?.recent_emails || [];

  return (
    <div className="bg-card border border-border rounded-xl p-5 h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
            <Building2 className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">{detail?.name || company.name}</h3>
            <div className="flex items-center gap-2">
              <Globe className="w-3 h-3 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{company.domain}</span>
              <RelationBadge type={detail?.relation_type || company.relation_type} />
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-background rounded-lg p-3 text-center">
          <Mail className="w-4 h-4 mx-auto text-blue-400 mb-1" />
          <div className="text-xl font-bold text-white">{(detail?.stats?.email_count || company.email_count).toLocaleString()}</div>
          <div className="text-xs text-muted-foreground">邮件总数</div>
        </div>
        <div className="bg-background rounded-lg p-3 text-center">
          <Users className="w-4 h-4 mx-auto text-purple-400 mb-1" />
          <div className="text-xl font-bold text-white">{detail?.stats?.contact_count || company.contact_count}</div>
          <div className="text-xs text-muted-foreground">联系人数</div>
        </div>
        <div className="bg-background rounded-lg p-3 text-center">
          <Activity className={cn(
            "w-4 h-4 mx-auto mb-1",
            company.recent_activity > 10 ? "text-emerald-400" : "text-amber-400"
          )} />
          <div className="text-xl font-bold text-white">{company.recent_activity}</div>
          <div className="text-xs text-muted-foreground">近30天</div>
        </div>
      </div>

      {/* Last Contact & Silent Days */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <div className="bg-background rounded-lg p-3">
          <div className="text-xs text-muted-foreground mb-1">最后互动</div>
          <div className="text-sm text-white">
            {detail?.stats?.last_contact
              ? new Date(detail.stats.last_contact).toLocaleDateString('zh-CN')
              : company.last_contact
              ? new Date(company.last_contact).toLocaleDateString('zh-CN')
              : '无记录'}
          </div>
        </div>
        <div className="bg-background rounded-lg p-3">
          <div className="text-xs text-muted-foreground mb-1">沉默时间</div>
          <div className={cn(
            "text-sm font-medium",
            company.days_silent < 7 ? "text-emerald-400" :
            company.days_silent < 30 ? "text-amber-400" : "text-red-400"
          )}>
            {company.days_silent} 天
          </div>
        </div>
      </div>

      {/* Key Contacts */}
      <div className="mb-5">
        <h4 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
          <Users className="w-4 h-4" />
          关联联系人
          <span className="text-xs text-muted-foreground">（点击查看邮件）</span>
        </h4>
        {contacts.length > 0 ? (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {contacts.map((contact, idx) => (
              <div
                key={idx}
                onClick={() => handleSelectContact(contact.email, contact.name)}
                className="flex items-center justify-between p-2 bg-background rounded-lg text-sm cursor-pointer hover:bg-background/80 transition-colors"
              >
                <div className="min-w-0">
                  <div className="font-medium text-white truncate">{contact.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{contact.email}</div>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground flex-shrink-0">
                  <span className="text-primary">
                    <Mail className="w-3 h-3 inline mr-0.5" />{contact.total_interactions}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无联系人数据</p>
        )}
      </div>

      {/* Recent Emails */}
      <div>
        <h4 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4" />
          最近邮件
        </h4>
        {recentEmails.length > 0 ? (
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {recentEmails.map((email, idx) => (
              <div key={idx} className="p-2 bg-background rounded-lg text-sm">
                <div className="font-medium text-white truncate">{email.subject || '(No Subject)'}</div>
                <div className="flex items-center justify-between text-xs text-muted-foreground mt-1">
                  <span className="truncate">{email.from}</span>
                  <span>{email.date ? new Date(email.date).toLocaleDateString('zh-CN') : ''}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无邮件记录</p>
        )}
      </div>
    </div>
  );
}

export default function CompanyIntel() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [relationFilter, setRelationFilter] = useState<RelationFilter>("all");
  const [sortBy, setSortBy] = useState<SortOption>("emails");

  async function fetchData() {
    setLoading(true);
    try {
      const url = `${API_BASE}/email-intel/companies?sort_by=${sortBy}&limit=100`;
      console.log('[CompanyIntel] Fetching:', url, 'sortBy:', sortBy);
      const res = await fetch(url);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const json = await res.json();
      setCompanies(json.companies || json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    console.log('[CompanyIntel] useEffect triggered, sortBy:', sortBy);
    fetchData();
  }, [sortBy]);

  // 筛选 + 搜索
  const filteredCompanies = companies.filter(company => {
    // 分类筛选
    if (relationFilter !== "all" && company.relation_type !== relationFilter) {
      return false;
    }
    // 搜索筛选
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return company.name.toLowerCase().includes(q) ||
             company.domain.toLowerCase().includes(q);
    }
    return true;
  });

  // 统计各分类数量
  const countByRelation = companies.reduce((acc, c) => {
    const t = c.relation_type || "unknown";
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  if (loading && companies.length === 0) {
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

  return (
    <div className="flex gap-6 h-full">
      {/* 左侧：列表 */}
      <div className="w-1/2 flex flex-col">
        {/* 搜索 + 排序 */}
        <div className="flex gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="搜索公司..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-card border border-border rounded-lg text-sm text-white placeholder-muted-foreground focus:outline-none focus:border-primary"
            />
          </div>
          <div className="flex gap-1 bg-card border border-border rounded-lg p-1">
            {SORT_OPTIONS.map((option) => {
              const Icon = option.icon;
              return (
                <button
                  key={option.value}
                  onClick={() => setSortBy(option.value)}
                  className={cn(
                    "flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
                    sortBy === option.value
                      ? "bg-primary text-white"
                      : "text-muted-foreground hover:text-white"
                  )}
                  title={option.label}
                >
                  <Icon className="w-3 h-3" />
                  <span className="hidden sm:inline">{option.label}</span>
                </button>
              );
            })}
          </div>
          <button
            onClick={fetchData}
            className="p-2 bg-card border border-border rounded-lg text-muted-foreground hover:text-white hover:border-primary transition-colors"
            title="刷新"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>

        {/* 分类筛选 */}
        <div className="flex flex-wrap gap-2 mb-4">
          {RELATION_FILTERS.map((filter) => {
            const count = filter.value === "all"
              ? companies.length
              : (countByRelation[filter.value] || 0);
            return (
              <button
                key={filter.value}
                onClick={() => setRelationFilter(filter.value)}
                className={cn(
                  "px-3 py-1 rounded-full text-xs transition-colors",
                  relationFilter === filter.value
                    ? "bg-primary text-white"
                    : "bg-card border border-border text-muted-foreground hover:text-white hover:border-primary"
                )}
              >
                {filter.label}
                <span className="ml-1 opacity-60">({count})</span>
              </button>
            );
          })}
        </div>

        {/* 公司列表 */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {filteredCompanies.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              {searchQuery || relationFilter !== "all" ? "没有匹配的公司" : "暂无数据"}
            </p>
          ) : (
            filteredCompanies.map((company) => (
              <CompanyCard
                key={company.domain}
                company={company}
                isSelected={selectedCompany?.domain === company.domain}
                onSelect={() => setSelectedCompany(company)}
              />
            ))
          )}
        </div>
      </div>

      {/* 右侧：详情 */}
      <div className="w-1/2">
        {selectedCompany ? (
          <CompanyDetail
            company={selectedCompany}
            onClose={() => setSelectedCompany(null)}
          />
        ) : (
          <div className="h-full flex items-center justify-center bg-card border border-border rounded-xl">
            <p className="text-muted-foreground">选择公司查看详情</p>
          </div>
        )}
      </div>
    </div>
  );
}
