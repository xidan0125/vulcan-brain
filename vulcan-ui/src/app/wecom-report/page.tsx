'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import {
  Calendar, ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  Sparkles, AlertTriangle, RefreshCw, Loader2, Brain, TrendingUp,
  Users, Truck, Building2, Briefcase, FileText, DollarSign, Eye, Clock,
  ShoppingCart, Shield, Package, Folder, Mail, CheckCircle2, Zap,
  Send, Star, ListTodo, Globe
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// ========== 公司配置 ==========
type CompanyType = 'shanghai' | 'guangxi' | 'vsg';

interface CompanyConfig {
  id: CompanyType;
  label: string;
  shortLabel: string;
  color: string;
  bgColor: string;
  borderColor: string;
  emailSource: string;
}

const companyConfig: CompanyConfig[] = [
  { id: 'shanghai', label: '上海公司', shortLabel: '上海', color: 'text-orange-400', bgColor: 'bg-orange-500/10', borderColor: 'border-orange-500/30', emailSource: '企微邮件' },
  { id: 'guangxi', label: '广西公司', shortLabel: '广西', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', borderColor: 'border-emerald-500/30', emailSource: '企微邮件' },
  { id: 'vsg', label: 'VSG国际', shortLabel: 'VSG', color: 'text-indigo-400', bgColor: 'bg-indigo-500/10', borderColor: 'border-indigo-500/30', emailSource: '微软邮件' },
];

// ========== 榕融类型定义 (上海/广西) ==========
interface TensionPoint {
  point: string;
  implication: string;
}

interface FinancialItem {
  amount: string;
  source?: string;
  destination?: string;
  event: string;
}

interface KeyPerson {
  name: string;
  count: number;
  activities: string[];
}

interface WatchlistItem {
  item: string;
  timeframe: string;
  why: string;
}

interface Insights {
  executive_summary: string;
  tension_points: TensionPoint[];
  financial_summary: {
    inflows: FinancialItem[];
    outflows: FinancialItem[];
  };
  key_people: KeyPerson[];
  watchlist: WatchlistItem[];
}

interface ExtractionItem {
  tag: string;
  style: string;
  summary: string;
  highlights: {
    entities: string[];
    numbers: string[];
  };
  source_id: string;
}

interface ExtractionResults {
  SALES: ExtractionItem[];
  GOVERNANCE: ExtractionItem[];
  DELIVERY: ExtractionItem[];
  OPERATIONS: ExtractionItem[];
  ADMIN: ExtractionItem[];
  FILE: ExtractionItem[];
}

interface RongrongData {
  date: string;
  insights: Insights | null;
  extraction_results: ExtractionResults | null;
  stats: {
    total_emails: number;
    processed: number;
  };
}

// ========== VSG 类型定义 ==========
interface VSGEmailAI {
  summary: string;
  action_items: string[];
  vip_updates: string[] | string;
  urgent_matters: string[] | string;
  key_topics: string[];
  sentiment: string;
}

interface VSGContact {
  address: string;
  name: string;
  count: number;
}

interface VSGData {
  date: string;
  total: number;
  received: number;
  sent: number;
  important: number;
  external_count: number;
  with_attachments: number;
  top_contacts: VSGContact[];
  ai_analysis: VSGEmailAI | null;
}

// Helper function
const toArray = (value: string | string[] | undefined): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return [value];
};

// ========== 样式配置 ==========
const styleConfig: Record<string, { bg: string; border: string; text: string; label: string }> = {
  GAIN: { bg: 'bg-emerald-500/5', border: 'border-emerald-500/10', text: 'text-emerald-400', label: '进展' },
  RISK: { bg: 'bg-red-500/5', border: 'border-red-500/10', text: 'text-red-400', label: '风险' },
  INSIGHT: { bg: 'bg-blue-500/5', border: 'border-blue-500/10', text: 'text-blue-400', label: '洞察' },
  LOG: { bg: 'bg-zinc-800/30', border: 'border-zinc-700/30', text: 'text-zinc-400', label: '日常' },
};

const categoryConfig: Record<string, {
  icon: typeof ShoppingCart;
  label: string;
}> = {
  SALES: { icon: ShoppingCart, label: '销售/客户' },
  GOVERNANCE: { icon: Shield, label: '公司治理' },
  DELIVERY: { icon: Truck, label: '物流交付' },
  OPERATIONS: { icon: Package, label: '生产运营' },
  ADMIN: { icon: Briefcase, label: '行政事务' },
  FILE: { icon: Folder, label: '文件传输' },
};

// ========== Style 小卡片（独立滚动） ==========
function StyleMiniCard({ style, items }: { style: string; items: ExtractionItem[] }) {
  const cfg = styleConfig[style];
  if (!items.length) return null;

  const textureConfig: Record<string, string> = {
    RISK: 'bg-zinc-950/80 border-red-500/20 shadow-red-900/10',
    GAIN: 'bg-zinc-950/80 border-emerald-500/20 shadow-emerald-900/10',
    INSIGHT: 'bg-zinc-950/80 border-blue-500/20 shadow-blue-900/10',
    LOG: 'bg-zinc-950/60 border-zinc-700/30 shadow-zinc-900/10',
  };

  return (
    <div className={`rounded-xl border shadow-lg ${textureConfig[style]} overflow-hidden`}>
      <div className={`px-3 py-2 border-b ${style === 'LOG' ? 'border-zinc-800/50' : cfg.border} flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${
            style === 'RISK' ? 'bg-red-400' :
            style === 'GAIN' ? 'bg-emerald-400' :
            style === 'INSIGHT' ? 'bg-blue-400' : 'bg-zinc-500'
          }`} />
          <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
        </div>
        <span className="text-[10px] text-zinc-500 bg-zinc-800/80 px-1.5 py-0.5 rounded">{items.length}</span>
      </div>
      <div className="max-h-[160px] overflow-y-auto p-2 space-y-1.5 scrollbar-thin">
        {items.map((item, i) => {
          const keyNumber = item.highlights?.numbers?.[0];
          return (
            <div key={i} className="p-2 bg-zinc-900/60 rounded-lg border border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
              <div className="flex items-center gap-1.5 mb-1">
                <span className={`text-[10px] ${cfg.text} font-medium px-1.5 py-0.5 rounded bg-zinc-800`}>{item.tag}</span>
                {keyNumber && (
                  <span className="text-[10px] text-amber-400 font-medium">({keyNumber})</span>
                )}
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed line-clamp-2">{item.summary}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ========== 可折叠分类卡片 ==========
function CollapsibleCard({ category, items, defaultOpen = true }: {
  category: string;
  items: ExtractionItem[];
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const cfg = categoryConfig[category];
  if (!cfg) return null;
  const Icon = cfg.icon;

  const groupedByStyle: Record<string, ExtractionItem[]> = {};
  items.forEach(item => {
    const style = item.style || 'LOG';
    if (!groupedByStyle[style]) groupedByStyle[style] = [];
    groupedByStyle[style].push(item);
  });

  const styleOrder = ['RISK', 'GAIN', 'INSIGHT', 'LOG'];
  const orderedStyles = styleOrder.filter(s => groupedByStyle[s]?.length);

  const riskCount = groupedByStyle['RISK']?.length || 0;
  const gainCount = groupedByStyle['GAIN']?.length || 0;

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 shadow-lg shadow-black/20 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/30 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Icon className="w-4 h-4 text-zinc-400" />
          </div>
          <div className="text-left">
            <span className="text-sm font-medium text-white">{cfg.label}</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-zinc-500">{items.length} 事项</span>
              {riskCount > 0 && <span className="text-[10px] text-red-400 bg-red-500/10 px-1.5 rounded">{riskCount} 风险</span>}
              {gainCount > 0 && <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 rounded">{gainCount} 进展</span>}
            </div>
          </div>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
      </button>

      {isOpen && items.length > 0 && (
        <div className="px-4 pb-4">
          <div className="grid grid-cols-1 gap-3">
            {orderedStyles.map(style => (
              <StyleMiniCard key={style} style={style} items={groupedByStyle[style]} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ========== 合并的行政/文件卡片 ==========
function MergedAdminFileCard({ adminItems, fileItems }: {
  adminItems: ExtractionItem[];
  fileItems: ExtractionItem[];
}) {
  const [isOpen, setIsOpen] = useState(true);
  const totalCount = adminItems.length + fileItems.length;

  if (totalCount === 0) return null;

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 shadow-lg shadow-black/20 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/30 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Briefcase className="w-4 h-4 text-zinc-400" />
          </div>
          <div className="text-left">
            <span className="text-sm font-medium text-white">日常事务</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-zinc-500">{totalCount} 事项</span>
              <span className="text-[10px] text-zinc-500">行政 {adminItems.length} · 文件 {fileItems.length}</span>
            </div>
          </div>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
      </button>

      {isOpen && (
        <div className="px-4 pb-4">
          <div className="grid grid-cols-2 gap-4">
            {/* 行政事务列 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-1">
                <Briefcase className="w-3 h-3 text-zinc-500" />
                <span className="text-xs text-zinc-500 font-medium">行政事务</span>
                <span className="text-[10px] text-zinc-600">({adminItems.length})</span>
              </div>
              <div className="h-[180px] overflow-y-auto space-y-1.5 pr-1 scrollbar-thin">
                {adminItems.map((item, i) => (
                  <div key={i} className="p-2 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] text-zinc-400 font-medium px-1.5 py-0.5 rounded bg-zinc-900">{item.tag}</span>
                    </div>
                    <p className="text-xs text-zinc-400 leading-relaxed line-clamp-2">{item.summary}</p>
                  </div>
                ))}
                {adminItems.length === 0 && <p className="text-xs text-zinc-600 text-center py-4">暂无行政事务</p>}
              </div>
            </div>

            {/* 文件传输列 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-1">
                <Folder className="w-3 h-3 text-zinc-500" />
                <span className="text-xs text-zinc-500 font-medium">文件传输</span>
                <span className="text-[10px] text-zinc-600">({fileItems.length})</span>
              </div>
              <div className="h-[180px] overflow-y-auto space-y-1.5 pr-1 scrollbar-thin">
                {fileItems.map((item, i) => (
                  <div key={i} className="p-2 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] text-zinc-400 font-medium px-1.5 py-0.5 rounded bg-zinc-900">{item.tag}</span>
                    </div>
                    <p className="text-xs text-zinc-400 leading-relaxed line-clamp-2">{item.summary}</p>
                  </div>
                ))}
                {fileItems.length === 0 && <p className="text-xs text-zinc-600 text-center py-4">暂无文件传输</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ========== 统计卡片 ==========
function StatCard({ icon: Icon, label, value, color }: {
  icon: typeof Mail;
  label: string;
  value: number;
  color: 'orange' | 'red' | 'blue' | 'emerald' | 'indigo';
}) {
  const colorConfig = {
    orange: { text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
    red: { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
    blue: { text: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    emerald: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
    indigo: { text: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20' },
  };
  const cfg = colorConfig[color];

  return (
    <div className={`p-3 ${cfg.bg} rounded-xl border ${cfg.border} shadow-lg shadow-black/20`}>
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-6 h-6 rounded-md ${cfg.bg} border ${cfg.border} flex items-center justify-center`}>
          <Icon className={`w-3.5 h-3.5 ${cfg.text}`} />
        </div>
        <span className="text-xs text-zinc-500 font-medium">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${cfg.text}`}>{value}</div>
    </div>
  );
}

// ========== VSG 邮件日报组件 ==========
function VSGEmailReport({ data, loading }: { data: VSGData | null; loading: boolean }) {
  const ai = data?.ai_analysis;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  return (
    <>
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Mail} label="收到邮件" value={data?.received || 0} color="indigo" />
        <StatCard icon={Send} label="发送邮件" value={data?.sent || 0} color="emerald" />
        <StatCard icon={Star} label="重要邮件" value={data?.important || 0} color="orange" />
        <StatCard icon={Users} label="外部邮件" value={data?.external_count || 0} color="blue" />
      </div>

      {/* AI 分析 */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center">
            <Brain className="w-3.5 h-3.5 text-indigo-400" />
          </div>
          <span className="text-sm font-medium text-white">AI 分析</span>
        </div>

        {/* 摘要 */}
        <div className="p-4 bg-indigo-500/5 rounded-xl border border-indigo-500/10 shadow-lg shadow-black/20">
          <div className="flex items-center gap-2 text-xs text-indigo-400 font-mono mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            邮件摘要
          </div>
          <p className="text-sm text-zinc-300 leading-relaxed">
            {ai?.summary || '暂无摘要，请等待 AI 分析'}
          </p>
        </div>

        {/* 待办 + 紧急 + VIP */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 待办事项 */}
          <div className="p-4 bg-blue-500/5 rounded-xl border border-blue-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-3">
              <ListTodo className="w-3.5 h-3.5" />
              待办事项 ({ai?.action_items?.length || 0})
            </div>
            {ai?.action_items?.length ? (
              <ul className="space-y-2">
                {ai.action_items.map((item, i) => (
                  <li key={i} className="text-xs text-zinc-400 flex gap-2">
                    <span className="text-blue-400">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-zinc-600">暂无待办事项</p>
            )}
          </div>

          {/* 紧急事项 */}
          <div className="p-4 bg-red-500/5 rounded-xl border border-red-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-3">
              <AlertTriangle className="w-3.5 h-3.5" />
              紧急事项 ({toArray(ai?.urgent_matters).length})
            </div>
            {toArray(ai?.urgent_matters).length ? (
              <ul className="space-y-2">
                {toArray(ai?.urgent_matters).map((item, i) => (
                  <li key={i} className="text-xs text-zinc-400 flex gap-2">
                    <span className="text-red-400">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-zinc-600">暂无紧急事项</p>
            )}
          </div>

          {/* VIP 更新 */}
          <div className="p-4 bg-yellow-500/5 rounded-xl border border-yellow-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-yellow-400 font-mono mb-3">
              <Star className="w-3.5 h-3.5" />
              重要客户 ({toArray(ai?.vip_updates).length})
            </div>
            {toArray(ai?.vip_updates).length ? (
              <ul className="space-y-2">
                {toArray(ai?.vip_updates).map((item, i) => (
                  <li key={i} className="text-xs text-zinc-400 flex gap-2">
                    <span className="text-yellow-400">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-zinc-600">暂无 VIP 更新</p>
            )}
          </div>
        </div>

        {/* 关键话题 */}
        {ai?.key_topics?.length ? (
          <div className="p-4 bg-purple-500/5 rounded-xl border border-purple-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-purple-400 font-mono mb-3">
              <Zap className="w-3.5 h-3.5" />
              关键话题
            </div>
            <div className="flex flex-wrap gap-2">
              {ai.key_topics.map((topic, i) => (
                <span key={i} className="px-2.5 py-1 bg-purple-500/10 text-purple-300 text-xs rounded-lg border border-purple-500/20">
                  {topic}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {/* 活跃联系人 */}
        {data?.top_contacts?.length ? (
          <div className="p-4 bg-zinc-800/30 rounded-xl border border-zinc-700/30 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono mb-3">
              <Users className="w-3.5 h-3.5" />
              活跃联系人
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {data.top_contacts.slice(0, 8).map((contact, i) => (
                <div key={i} className="p-2 bg-zinc-900/50 rounded-lg border border-zinc-800">
                  <div className="text-xs text-zinc-300 truncate">{contact.name || contact.address}</div>
                  <div className="text-[10px] text-zinc-600 mt-0.5">{contact.count} 封邮件</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}

// ========== 榕融日报组件 (上海/广西) ==========
function RongrongReport({ data, loading }: { data: RongrongData | null; loading: boolean }) {
  const insights = data?.insights;
  const extraction = data?.extraction_results;

  const totalEmails = data?.stats?.total_emails || 0;
  const tensionCount = insights?.tension_points?.length || 0;
  const watchCount = insights?.watchlist?.length || 0;
  const totalItems = extraction ?
    (extraction.SALES?.length || 0) +
    (extraction.GOVERNANCE?.length || 0) +
    (extraction.DELIVERY?.length || 0) +
    (extraction.OPERATIONS?.length || 0) : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <>
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Mail} label="处理邮件" value={totalEmails} color="orange" />
        <StatCard icon={AlertTriangle} label="张力点" value={tensionCount} color="red" />
        <StatCard icon={Eye} label="待跟进" value={watchCount} color="blue" />
        <StatCard icon={CheckCircle2} label="业务事项" value={totalItems} color="emerald" />
      </div>

      {/* CEO 洞察 */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-orange-500/10 border border-orange-500/30 flex items-center justify-center">
            <Brain className="w-3.5 h-3.5 text-orange-400" />
          </div>
          <span className="text-sm font-medium text-white">CEO 洞察</span>
        </div>

        {/* 执行摘要 */}
        <div className="p-4 bg-orange-500/5 rounded-xl border border-orange-500/10 shadow-lg shadow-black/20">
          <div className="flex items-center gap-2 text-xs text-orange-400 font-mono mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            执行摘要
          </div>
          <p className="text-sm text-zinc-300 leading-relaxed">
            {insights?.executive_summary || '暂无执行摘要'}
          </p>
        </div>

        {/* 张力点 */}
        <div className="p-4 bg-red-500/5 rounded-xl border border-red-500/10 shadow-lg shadow-black/20">
          <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-3">
            <TrendingUp className="w-3.5 h-3.5" />
            张力点 ({tensionCount})
          </div>
          {insights?.tension_points?.length ? (
            <div className="space-y-3">
              {insights.tension_points.map((tp, i) => (
                <div key={i} className="flex gap-3 p-2 bg-zinc-900/30 rounded-lg">
                  <span className="text-red-400 font-bold shrink-0">{i + 1}.</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white font-medium">{tp.point}</div>
                    <div className="text-xs text-zinc-500 mt-0.5 flex items-center gap-1">
                      <span className="text-red-400/60">→</span> {tp.implication}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-600">今日无显著张力</p>
          )}
        </div>

        {/* 财务摘要 + 关键人物 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 财务摘要 */}
          <div className="p-4 bg-emerald-500/5 rounded-xl border border-emerald-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono mb-3">
              <DollarSign className="w-3.5 h-3.5" />
              财务摘要
            </div>
            <div className="space-y-3">
              {insights?.financial_summary?.inflows?.length ? (
                <div className="p-2 bg-emerald-500/5 rounded-lg border border-emerald-500/10">
                  <div className="text-xs text-emerald-400 mb-1.5 font-medium">流入:</div>
                  {insights.financial_summary.inflows.slice(0, 3).map((item, i) => (
                    <div key={i} className="text-sm text-zinc-300 truncate">
                      <span className="text-emerald-400">+</span> <span className="text-emerald-400 font-medium">{item.amount}</span>
                      <span className="text-zinc-500 ml-1">{item.source} ({item.event})</span>
                    </div>
                  ))}
                </div>
              ) : null}
              {insights?.financial_summary?.outflows?.length ? (
                <div className="p-2 bg-red-500/5 rounded-lg border border-red-500/10">
                  <div className="text-xs text-red-400 mb-1.5 font-medium">流出:</div>
                  {insights.financial_summary.outflows.slice(0, 3).map((item, i) => (
                    <div key={i} className="text-sm text-zinc-300 truncate">
                      <span className="text-red-400">-</span> <span className="text-red-400 font-medium">{item.amount}</span>
                      <span className="text-zinc-500 ml-1">{item.destination} ({item.event})</span>
                    </div>
                  ))}
                </div>
              ) : null}
              {!insights?.financial_summary?.inflows?.length && !insights?.financial_summary?.outflows?.length && (
                <p className="text-sm text-zinc-600">暂无财务动态</p>
              )}
            </div>
          </div>

          {/* 关键人物 */}
          <div className="p-4 bg-blue-500/5 rounded-xl border border-blue-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-3">
              <Users className="w-3.5 h-3.5" />
              关键人物
            </div>
            {insights?.key_people?.length ? (
              <div className="space-y-2">
                {insights.key_people.slice(0, 4).map((person, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-zinc-900/30 rounded-lg">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center text-xs text-blue-400 font-medium">
                        {person.name[0]}
                      </div>
                      <span className="text-sm text-zinc-300">{person.name}</span>
                    </div>
                    <span className="text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">{person.count} 次</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-600">暂无关键人物</p>
            )}
          </div>
        </div>

        {/* 待跟进 */}
        {insights?.watchlist?.length ? (
          <div className="p-4 bg-purple-500/5 rounded-xl border border-purple-500/10 shadow-lg shadow-black/20">
            <div className="flex items-center gap-2 text-xs text-purple-400 font-mono mb-3">
              <Eye className="w-3.5 h-3.5" />
              待跟进 ({watchCount})
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {insights.watchlist.map((item, i) => (
                <div key={i} className="p-2 bg-zinc-900/30 rounded-lg">
                  <div className="text-sm text-zinc-300">{item.item}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-purple-400">{item.timeframe}</span>
                    <span className="text-xs text-zinc-600">· {item.why}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {/* 业务事项 */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Briefcase className="w-3.5 h-3.5 text-zinc-400" />
          </div>
          <span className="text-sm font-medium text-white">业务事项</span>
        </div>

        {/* 核心业务 - 响应式双列 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <CollapsibleCard category="SALES" items={extraction?.SALES || []} defaultOpen={true} />
          <CollapsibleCard category="GOVERNANCE" items={extraction?.GOVERNANCE || []} defaultOpen={true} />
        </div>

        {/* 运营 - 响应式双列 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <CollapsibleCard category="DELIVERY" items={extraction?.DELIVERY || []} defaultOpen={true} />
          <CollapsibleCard category="OPERATIONS" items={extraction?.OPERATIONS || []} defaultOpen={true} />
        </div>

        {/* 日常事务 - 合并ADMIN和FILE */}
        <MergedAdminFileCard
          adminItems={extraction?.ADMIN || []}
          fileItems={extraction?.FILE || []}
        />
      </section>
    </>
  );
}

// ========== 持久化 Key ==========
const STORAGE_KEY = 'rongrong-report-state';

interface PersistedState {
  company: CompanyType;
  dates: Record<CompanyType, string>;
}

const getDefaultDates = (): Record<CompanyType, string> => {
  const today = new Date().toISOString().split('T')[0];
  return { shanghai: today, guangxi: today, vsg: today };
};

const loadPersistedState = (): PersistedState => {
  if (typeof window === 'undefined') {
    return { company: 'shanghai', dates: getDefaultDates() };
  }
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      // 验证数据结构
      if (parsed.company && parsed.dates) {
        return {
          company: parsed.company as CompanyType,
          dates: { ...getDefaultDates(), ...parsed.dates }
        };
      }
    }
  } catch (e) {
    console.warn('Failed to load persisted state:', e);
  }
  return { company: 'shanghai', dates: getDefaultDates() };
};

const savePersistedState = (state: PersistedState) => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.warn('Failed to save persisted state:', e);
  }
};

// ========== 主页面 ==========
export default function RongrongReportPage() {
  // 初始化时从 localStorage 加载
  const [company, setCompany] = useState<CompanyType>('shanghai');
  const [dates, setDates] = useState<Record<CompanyType, string>>(getDefaultDates);
  const [isHydrated, setIsHydrated] = useState(false);
  const [rongrongData, setRongrongData] = useState<RongrongData | null>(null);
  const [vsgData, setVsgData] = useState<VSGData | null>(null);
  const [loading, setLoading] = useState(true);
  const [availableDates, setAvailableDates] = useState<Record<CompanyType, string[]>>({ shanghai: [], guangxi: [], vsg: [] });

  // 客户端 hydration - 从 localStorage 恢复状态
  useEffect(() => {
    const persisted = loadPersistedState();
    setCompany(persisted.company);
    setDates(persisted.dates);
    setIsHydrated(true);
  }, []);

  // 状态变化时持久化
  useEffect(() => {
    if (isHydrated) {
      savePersistedState({ company, dates });
    }
  }, [company, dates, isHydrated]);

  const currentCompany = companyConfig.find(c => c.id === company)!;
  const currentDate = dates[company];

  // 获取可用日期列表
  const fetchAvailableDates = async (companyId: CompanyType) => {
    try {
      if (companyId === 'vsg') {
        // VSG 暂时用最近7天
        const dates: string[] = [];
        for (let i = 0; i < 7; i++) {
          const d = new Date();
          d.setDate(d.getDate() - i);
          dates.push(d.toISOString().split('T')[0]);
        }
        return dates;
      }
      const res = await fetch(`${API_BASE}/api/rongrong/dates?company=${companyId}`);
      if (res.ok) {
        const data = await res.json();
        return data.dates || [];
      }
    } catch (e) {
      console.warn('Failed to fetch available dates:', e);
    }
    return [];
  };

  // 加载可用日期
  useEffect(() => {
    if (!isHydrated) return;
    const loadDates = async () => {
      const dates = await fetchAvailableDates(company);
      setAvailableDates(prev => ({ ...prev, [company]: dates }));
      // 如果当前日期不在可用列表中，选择最新的
      if (dates.length > 0 && !dates.includes(currentDate)) {
        setCurrentDate(dates[0]);
      }
    };
    loadDates();
  }, [company, isHydrated]);

  const fetchReport = async () => {
    if (!isHydrated) return; // 等待 hydration 完成
    setLoading(true);
    try {
      if (company === 'vsg') {
        // VSG: 调用 info-hub API
        const res = await fetch(`${API_BASE}/api/info-hub/daily/v2/${currentDate}`);
        if (!res.ok) {
          setVsgData({ date: currentDate, total: 0, received: 0, sent: 0, important: 0, external_count: 0, with_attachments: 0, top_contacts: [], ai_analysis: null });
          return;
        }
        const json = await res.json();
        setVsgData(json.email || { date: currentDate, total: 0, received: 0, sent: 0, important: 0, external_count: 0, with_attachments: 0, top_contacts: [], ai_analysis: null });
      } else {
        // 上海/广西: 调用 rongrong API
        const res = await fetch(`${API_BASE}/api/rongrong/report/${currentDate}?company=${company}`);
        if (!res.ok) {
          setRongrongData({ date: currentDate, insights: null, extraction_results: null, stats: { total_emails: 0, processed: 0 } });
          return;
        }
        const json = await res.json();
        setRongrongData(json);
      }
    } catch (e: any) {
      if (company === 'vsg') {
        setVsgData({ date: currentDate, total: 0, received: 0, sent: 0, important: 0, external_count: 0, with_attachments: 0, top_contacts: [], ai_analysis: null });
      } else {
        setRongrongData({ date: currentDate, insights: null, extraction_results: null, stats: { total_emails: 0, processed: 0 } });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReport(); }, [currentDate, company, isHydrated]);

  const setCurrentDate = (newDate: string) => {
    setDates(prev => ({ ...prev, [company]: newDate }));
  };

  const changeDate = (delta: number) => {
    const dates = availableDates[company];
    if (dates.length === 0) {
      // 无可用日期列表时，按天切换
      const d = new Date(currentDate);
      d.setDate(d.getDate() + delta);
      setCurrentDate(d.toISOString().split('T')[0]);
      return;
    }
    const currentIndex = dates.indexOf(currentDate);
    if (currentIndex === -1) {
      // 当前日期不在列表中，选择最新的
      setCurrentDate(dates[0]);
      return;
    }
    // delta < 0 表示往前（更新的日期），delta > 0 表示往后（更旧的日期）
    const newIndex = currentIndex - delta;
    if (newIndex >= 0 && newIndex < dates.length) {
      setCurrentDate(dates[newIndex]);
    }
  };

  return (
    <DashboardLayout>
      <div className="h-full overflow-auto text-zinc-200 p-4 md:p-6">
        {/* 大卡片容器 */}
        <div className="max-w-6xl mx-auto bg-zinc-900/80 rounded-2xl border border-zinc-800 shadow-2xl shadow-black/50 p-5 md:p-8 space-y-6">

          {/* Header */}
          <header className="flex flex-col gap-4 pb-4 border-b border-zinc-800">
            {/* 标题行 */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-lg ${currentCompany.bgColor} border ${currentCompany.borderColor} flex items-center justify-center`}>
                    <Brain className={`w-4 h-4 ${currentCompany.color}`} />
                  </div>
                  榕融日报
                </h1>
                <p className="text-sm text-zinc-500 mt-1">AI 驱动的企业邮件智能分析</p>
              </div>
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="flex items-center gap-1 bg-zinc-900 rounded-lg p-1 border border-zinc-800 shadow-lg shadow-black/20">
                  <button onClick={() => changeDate(-1)} className="p-1.5 hover:bg-zinc-800 rounded-md cursor-pointer">
                    <ChevronLeft className="w-4 h-4 text-zinc-400" />
                  </button>
                  <div className="flex items-center gap-1.5 px-2 py-1">
                    <Calendar className={`w-4 h-4 ${currentCompany.color}`} />
                    <input
                      type="date"
                      value={currentDate}
                      onChange={(e) => setCurrentDate(e.target.value)}
                      className="bg-transparent text-sm text-white focus:outline-none w-28"
                    />
                  </div>
                  <button onClick={() => changeDate(1)} className="p-1.5 hover:bg-zinc-800 rounded-md cursor-pointer">
                    <ChevronRight className="w-4 h-4 text-zinc-400" />
                  </button>
                </div>
                <button
                  onClick={fetchReport}
                  disabled={loading}
                  className={`flex items-center gap-1.5 px-3 py-2 ${currentCompany.bgColor} hover:opacity-80 border ${currentCompany.borderColor} rounded-lg text-sm ${currentCompany.color} transition-colors shadow-lg shadow-black/20 cursor-pointer disabled:opacity-50`}
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  <span className="hidden sm:inline">刷新</span>
                </button>
              </div>
            </div>

            {/* 公司切换 Tab */}
            <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800 w-fit">
              {companyConfig.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCompany(c.id)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all cursor-pointer ${
                    company === c.id
                      ? `${c.bgColor} ${c.color} border ${c.borderColor}`
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
                  }`}
                >
                  <span className="hidden sm:inline">{c.label}</span>
                  <span className="sm:hidden">{c.shortLabel}</span>
                </button>
              ))}
            </div>

            {/* 当前公司信息 */}
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <Globe className="w-3.5 h-3.5" />
              <span>{currentCompany.label}</span>
              <span className="text-zinc-700">·</span>
              <span>{currentCompany.emailSource}</span>
              <span className="text-zinc-700">·</span>
              <span>{currentDate}</span>
            </div>
          </header>

          {/* 根据公司类型渲染不同内容 */}
          {company === 'vsg' ? (
            <VSGEmailReport data={vsgData} loading={loading} />
          ) : (
            <RongrongReport data={rongrongData} loading={loading} />
          )}

          {/* Footer */}
          <div className="text-xs text-zinc-600 text-center pt-6">
            <span className="px-3 py-1.5 bg-zinc-800/50 rounded-full border border-zinc-700/50">
              {currentCompany.label} · {currentDate}
            </span>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
