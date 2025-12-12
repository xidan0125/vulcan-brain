'use client';

import React, { useState, useEffect } from 'react';
import {
  MessageSquare, Mail, Users, CheckSquare, Layout,
  Calendar, ChevronLeft, ChevronRight, TrendingUp,
  TrendingDown, AlertTriangle, Search,
  Briefcase, Code, DollarSign, X, UserCog, Megaphone
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- Types ---

interface Person {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  avatar_initial: string;
  health_score: number;
  activity_level: string;
  trend: 'up' | 'stable' | 'down';
  category: string;
  responsibilities: string[];
  projects: string[];
  last_active: string;
  top_collaborators: string[];
  total_interactions: number;
}

// --- Components ---

const Card = ({ children, className = "", onClick }: { children: React.ReactNode, className?: string, onClick?: () => void }) => (
  <motion.div
    whileHover={{ y: -2, borderColor: 'rgba(249, 115, 22, 0.3)' }}
    onClick={onClick}
    className={`bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm transition-all hover:bg-zinc-800/50 cursor-pointer ${className}`}
  >
    {children}
  </motion.div>
);

const Badge = ({ type, text }: { type: 'success' | 'warning' | 'danger' | 'neutral', text: string }) => {
  const colors = {
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warning: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    neutral: 'bg-zinc-800 text-zinc-400 border-zinc-700'
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${colors[type]}`}>
      {text}
    </span>
  );
};

const HealthBar = ({ score }: { score: number }) => {
  let color = 'bg-emerald-500';
  if (score < 80) color = 'bg-orange-500';
  if (score < 50) color = 'bg-rose-500';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-500">{score}</span>
    </div>
  );
};

const CategoryIcon = ({ category }: { category: string }) => {
  const icons: Record<string, React.ReactNode> = {
    management: <Briefcase size={14} />,
    executive: <Briefcase size={14} />,
    sales: <DollarSign size={14} />,
    engineering: <Code size={14} />,
    operations: <UserCog size={14} />,
    hr: <Users size={14} />,
    finance: <DollarSign size={14} />,
    marketing: <Megaphone size={14} />,
    admin: <Layout size={14} />,
  };
  return <>{icons[category] || <Users size={14} />}</>;
};

const LoadingSpinner = () => (
  <div className="flex items-center justify-center h-64">
    <div className="animate-spin w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full" />
  </div>
);

// --- Daily Report View ---

export function DailyReportView() {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/info-hub/daily/${date}`)
      .then(res => res.json())
      .then(result => {
        setData(result);
        setLoading(false);
      })
      .catch(() => {
        setData(null);
        setLoading(false);
      });
  }, [date]);

  const changeDate = (delta: number) => {
    const d = new Date(date);
    d.setDate(d.getDate() + delta);
    setDate(d.toISOString().split('T')[0]);
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const stats = data ? {
    chat: {
      count: data.chat?.total_messages || 0,
      groups: data.chat?.total_groups || 0,
      highlights: data.chat?.highlights || []
    },
    email: {
      sent: data.email?.total_sent || 0,
      received: data.email?.total_received || 0,
    },
    people: {
      total: data.people?.total_count || 0,
      active: data.people?.active_count || 0,
    },
    approval: {
      pending: data.approval?.pending || 0,
      approved: data.approval?.approved_today || 0,
    },
    projects: {
      total: data.projects?.total || 0,
      active: data.projects?.active || 0,
      blocked: data.projects?.blocked || 0,
    }
  } : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Daily Overview</h1>
          <p className="text-zinc-500 text-sm mt-1">企业运营状态一览</p>
        </div>
        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
          <button onClick={() => changeDate(-1)} className="p-1.5 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors">
            <ChevronLeft size={18} />
          </button>
          <div className="flex items-center gap-2 px-3 py-1 text-sm font-mono text-zinc-200">
            <Calendar size={14} className="text-orange-500" />
            <span>{formatDate(date)}</span>
          </div>
          <button onClick={() => changeDate(1)} className="p-1.5 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors">
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Chat */}
          <Card className="md:col-span-2 group">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-zinc-400 text-sm font-medium uppercase tracking-wider">聊天动态</h3>
              <MessageSquare size={18} className="text-zinc-700 group-hover:text-orange-500 transition-colors" />
            </div>
            <div className="flex items-end gap-4 mb-4">
              <span className="text-4xl font-mono text-white tracking-tighter">
                {stats?.chat.count.toLocaleString() || 0}
              </span>
              <span className="text-sm text-zinc-500 mb-1">条消息</span>
              <span className="text-sm text-emerald-400 flex items-center mb-1 ml-2">
                <TrendingUp size={14} className="mr-1" /> {stats?.chat.groups || 0} 个群组
              </span>
            </div>
            {stats?.chat.highlights && stats.chat.highlights.length > 0 && (
              <div className="space-y-2">
                {stats.chat.highlights.slice(0, 2).map((h: string, i: number) => (
                  <div key={i} className="text-sm text-zinc-400 bg-zinc-950/50 p-2 rounded border border-zinc-800/50 flex items-center gap-2">
                    <div className="w-1 h-1 rounded-full bg-orange-500 flex-shrink-0"></div>
                    <span className="line-clamp-1">{h}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* People */}
          <Card className="group">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-zinc-400 text-sm font-medium uppercase tracking-wider">人员</h3>
              <Users size={18} className="text-zinc-700 group-hover:text-orange-500 transition-colors" />
            </div>
            <div className="text-3xl font-mono text-white mb-1">
              {stats?.people.active || 0}
              <span className="text-lg text-zinc-500 ml-1">/ {stats?.people.total || 0}</span>
            </div>
            <div className="text-xs text-zinc-500 mt-3 pt-3 border-t border-zinc-800">
              活跃率: <span className="text-orange-400 font-medium">
                {stats?.people.total ? Math.round((stats.people.active / stats.people.total) * 100) : 0}%
              </span>
            </div>
          </Card>

          {/* Email */}
          <Card className="group">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-zinc-400 text-sm font-medium uppercase tracking-wider">邮件</h3>
              <Mail size={18} className="text-zinc-700 group-hover:text-orange-500 transition-colors" />
            </div>
            <div className="text-3xl font-mono text-white mb-1">
              {((stats?.email.sent || 0) + (stats?.email.received || 0)).toLocaleString()}
            </div>
            <div className="flex gap-4 text-xs text-zinc-500 mt-3 pt-3 border-t border-zinc-800">
              <span>发送 <span className="text-zinc-300">{stats?.email.sent || 0}</span></span>
              <span>接收 <span className="text-zinc-300">{stats?.email.received || 0}</span></span>
            </div>
          </Card>

          {/* Approvals */}
          <Card className="group">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-zinc-400 text-sm font-medium uppercase tracking-wider">审批</h3>
              <CheckSquare size={18} className="text-zinc-700 group-hover:text-orange-500 transition-colors" />
            </div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-3xl font-mono text-white">{stats?.approval.pending || 0}</span>
              {(stats?.approval.pending || 0) > 0 && <Badge type="warning" text="待处理" />}
            </div>
            <div className="text-xs text-zinc-500 mt-3 pt-3 border-t border-zinc-800">
              今日已批: <span className="text-emerald-400">{stats?.approval.approved || 0}</span>
            </div>
          </Card>

          {/* Projects */}
          <Card className="group">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-zinc-400 text-sm font-medium uppercase tracking-wider">项目</h3>
              <Layout size={18} className="text-zinc-700 group-hover:text-orange-500 transition-colors" />
            </div>
            <div className="text-3xl font-mono text-white mb-3">{stats?.projects.total || 0}</div>
            <div className="flex gap-3 text-xs">
              <span className="text-emerald-400">{stats?.projects.active || 0} 进行中</span>
              {(stats?.projects.blocked || 0) > 0 && (
                <span className="text-rose-400">{stats?.projects?.blocked} 阻塞</span>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

// --- People View ---

export function PeopleView() {
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetch('/api/info-hub/people/list?limit=100')
      .then(res => res.json())
      .then(result => {
        const transformed = (result.people || []).map((p: any) => ({
          id: p.user_id || p.email,
          name: p.name || 'Unknown',
          email: p.email || '',
          role: p.job_title || p.role_cn || 'Team Member',
          department: p.department || 'General',
          avatar_initial: (p.name || '?').charAt(0).toUpperCase(),
          health_score: p.health_score || 50,
          activity_level: p.activity_level || 'medium',
          trend: p.health_trend === 'active' ? 'up' : p.health_trend === 'inactive' ? 'down' : 'stable',
          category: (p.job_category || p.role || 'general').toLowerCase().replace(/\s+/g, '_'),
          responsibilities: p.responsibilities || [],
          projects: p.projects || [],
          last_active: p.last_active ? new Date(p.last_active).toLocaleDateString('zh-CN') : '未知',
          top_collaborators: p.top_collaborators || [],
          total_interactions: p.total_interactions || 0
        }));
        setPeople(transformed);
        setTotal(result.total || transformed.length);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Get unique categories
  const categories = Array.from(new Set(people.map(p => p.category)))
    .filter(c => c && c !== 'unknown')
    .map(cat => ({
      id: cat,
      label: cat.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
      count: people.filter(p => p.category === cat).length
    }))
    .sort((a, b) => b.count - a.count);

  // Filter people
  const filteredPeople = people.filter(p => {
    const matchesSearch = !searchQuery ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !categoryFilter || p.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  // Risk people
  const riskPeople = people.filter(p => p.health_score < 50 && p.trend === 'down');
  const avgHealth = people.length > 0 ? Math.round(people.reduce((sum, p) => sum + p.health_score, 0) / people.length) : 0;

  // Group by category
  const groupedPeople = categoryFilter
    ? [{ id: categoryFilter, label: categoryFilter.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '), members: filteredPeople }]
    : categories.map(cat => ({
        ...cat,
        members: filteredPeople.filter(p => p.category === cat.id)
      })).filter(c => c.members.length > 0);

  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">总人数</span>
          <div className="flex items-end gap-2 mt-1">
            <span className="text-2xl font-mono text-white">{total}</span>
            <span className="text-xs text-emerald-500 mb-1">
              {people.filter(p => p.activity_level === 'high').length} 高度活跃
            </span>
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">平均健康度</span>
          <div className="flex items-end gap-2 mt-1">
            <span className="text-2xl font-mono text-orange-500">{avgHealth}</span>
            <span className="text-xs text-zinc-500 mb-1">/ 100</span>
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl relative overflow-hidden">
          <div className="absolute right-2 top-2 opacity-10">
            <AlertTriangle size={36} className="text-rose-500" />
          </div>
          <span className="text-xs text-rose-400 uppercase tracking-wider font-bold">风险提示</span>
          <div className="mt-2 text-xs text-zinc-300">
            {riskPeople.length > 0 ? (
              <><span className="text-rose-400 font-bold">{riskPeople[0]?.name}</span> 活跃度异常下降</>
            ) : (
              <span className="text-emerald-400">暂无风险信号</span>
            )}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 pb-4 border-b border-zinc-800">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="搜索姓名或邮箱..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-orange-500/50 transition-colors"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCategoryFilter(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${!categoryFilter ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700'}`}
          >
            全部
          </button>
          {categories.slice(0, 5).map(cat => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(categoryFilter === cat.id ? null : cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${categoryFilter === cat.id ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700'}`}
            >
              {cat.label} ({cat.count})
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : filteredPeople.length === 0 ? (
        <div className="text-center py-12 text-zinc-500">
          <Users size={48} className="mx-auto mb-4 opacity-30" />
          <p>没有找到匹配的人员</p>
        </div>
      ) : (
        <div className="space-y-8">
          {groupedPeople.map(cat => (
            <div key={cat.id}>
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 bg-zinc-800 rounded text-zinc-400">
                  <CategoryIcon category={cat.id} />
                </div>
                <h3 className="text-zinc-200 font-medium">{cat.label}</h3>
                <span className="text-xs text-zinc-600 font-mono">{cat.members.length}</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {cat.members.map(person => (
                  <motion.div
                    key={person.id}
                    whileHover={{ y: -2 }}
                    onClick={() => setSelectedPerson(person)}
                    className="group bg-zinc-900/40 border border-zinc-800 hover:border-orange-500/30 rounded-xl p-4 cursor-pointer transition-all"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 flex items-center justify-center text-zinc-300 font-bold text-sm border border-zinc-700">
                          {person.avatar_initial}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-zinc-200 group-hover:text-orange-400 transition-colors">
                            {person.name}
                          </div>
                          <div className="text-xs text-zinc-500">{person.role}</div>
                        </div>
                      </div>
                      {person.trend === 'down' && <TrendingDown size={14} className="text-rose-500" />}
                      {person.trend === 'up' && <TrendingUp size={14} className="text-emerald-500" />}
                    </div>

                    <div className="space-y-3">
                      <HealthBar score={person.health_score} />
                      <div className="flex justify-between items-center text-[11px] text-zinc-500">
                        <span>{person.total_interactions.toLocaleString()} 互动</span>
                        <span>最近: {person.last_active}</span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      <AnimatePresence>
        {selectedPerson && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              onClick={() => setSelectedPerson(null)}
            />
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-lg bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl overflow-hidden"
            >
              <div className="relative h-20 bg-gradient-to-r from-orange-500/20 to-zinc-900">
                <button onClick={() => setSelectedPerson(null)} className="absolute top-3 right-3 p-1.5 text-zinc-400 hover:text-white bg-black/30 rounded-full transition-colors">
                  <X size={16} />
                </button>
              </div>

              <div className="px-6 pb-6 -mt-8">
                <div className="flex justify-between items-end mb-4">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-orange-500/30 to-zinc-800 border-4 border-zinc-900 flex items-center justify-center text-xl text-white font-bold shadow-lg">
                    {selectedPerson.avatar_initial}
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-mono text-white">{selectedPerson.health_score}</div>
                    <div className="text-[10px] uppercase text-zinc-500 tracking-wider">健康度</div>
                  </div>
                </div>

                <h2 className="text-xl font-bold text-white">{selectedPerson.name}</h2>
                <p className="text-zinc-400 text-sm">{selectedPerson.role} · {selectedPerson.department}</p>
                <p className="text-zinc-600 text-xs mt-1">{selectedPerson.email}</p>

                <div className="mt-5 space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-zinc-950/50 p-3 rounded-lg">
                      <div className="text-lg font-mono text-white">{selectedPerson.total_interactions.toLocaleString()}</div>
                      <div className="text-[10px] text-zinc-500 uppercase">总互动</div>
                    </div>
                    <div className="bg-zinc-950/50 p-3 rounded-lg">
                      <div className="text-lg font-mono text-white capitalize">{selectedPerson.activity_level}</div>
                      <div className="text-[10px] text-zinc-500 uppercase">活跃度</div>
                    </div>
                  </div>

                  {selectedPerson.projects.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-zinc-500 uppercase mb-2">参与项目</h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedPerson.projects.map((p, i) => (
                          <span key={i} className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-300">
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-5 pt-4 border-t border-zinc-800 flex justify-between items-center">
                  <span className="text-xs text-zinc-600">最近活跃: {selectedPerson.last_active}</span>
                  <button className="px-4 py-2 bg-orange-500 text-white text-sm font-medium rounded-lg hover:bg-orange-600 transition-colors">
                    查看详情
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 导出默认组件（兼容旧代码）
export default function InfoHubV2() {
  return <DailyReportView />;
}
