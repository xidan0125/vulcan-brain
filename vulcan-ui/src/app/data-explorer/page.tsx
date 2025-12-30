"use client";

import { useState, useEffect } from "react";
import {
  DollarSign, Truck, FileText, Package, MessageSquare, AlertTriangle,
  Clock, CheckCircle, ArrowRight, Users, Building2, ArrowUpRight, 
  ArrowDownLeft, Mail, ChevronRight, Activity, Target, Zap, 
  BarChart3, Network, ArrowLeft, RefreshCw
} from "lucide-react";
import EmailAgentChat from "@/components/email-intel/EmailAgentChat";

const API_BASE = "https://api.vsg-brain.com/api/graph";

// ========== 类型定义 ==========
interface EventRecord {
  id: string;
  event_type: string;
  event_date?: string;
  date?: string;
  summary: string;
  amount: number;
  currency: string;
  direction: string;
  status: string;
  counterparty: string;
  counterparty_role: string;
}

interface FullStats {
  total_events: number;
  by_type: Array<{ type: string; count: number; amount: number }>;
  by_status: Record<string, number>;
  by_direction: Record<string, { count: number; amount: number }>;
  counterparties: Array<{ name: string; role: string; count: number; amount: number }>;
  by_role: Record<string, number>;
}

// ========== 常量 ==========
const EVENT_TYPE_CN: Record<string, string> = {
  Payment: "付款", Shipment: "物流", Contract: "合同",
  Order: "订单", Quotation: "报价", Inquiry: "询价", General: "其他"
};

const EVENT_TYPE_ICON: Record<string, any> = {
  Payment: DollarSign, Shipment: Truck, Contract: FileText,
  Order: Package, Quotation: Target, Inquiry: MessageSquare, General: Activity
};

const EVENT_TYPE_COLOR: Record<string, string> = {
  Payment: "text-green-400", Shipment: "text-blue-400", Contract: "text-purple-400",
  Order: "text-orange-400", Quotation: "text-cyan-400", Inquiry: "text-amber-400", General: "text-zinc-400"
};

const ROLE_CN: Record<string, string> = {
  customer: "客户", supplier: "供应商", logistics: "物流", bank: "银行", other: "其他"
};

// ========== 辅助函数 ==========
const formatAmount = (amount: number) => {
  if (!amount) return "-";
  if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
  if (amount >= 1000) return `$${(amount / 1000).toFixed(0)}K`;
  return `$${amount.toFixed(0)}`;
};

const DirectionBadge = ({ direction }: { direction: string }) => {
  if (direction === "inbound") return (
    <span className="inline-flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded">
      <ArrowDownLeft className="w-3 h-3" /> 收入
    </span>
  );
  if (direction === "outbound") return (
    <span className="inline-flex items-center gap-1 text-xs text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded">
      <ArrowUpRight className="w-3 h-3" /> 支出
    </span>
  );
  return <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded">内部</span>;
};

const StatusBadge = ({ status }: { status: string }) => {
  if (status === "completed") return (
    <span className="inline-flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded">
      <CheckCircle className="w-3 h-3" /> 已完成
    </span>
  );
  if (status === "pending") return (
    <span className="inline-flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
      <Clock className="w-3 h-3" /> 进行中
    </span>
  );
  return <span className="text-xs text-zinc-500">未知</span>;
};

// ========== 主组件 ==========
export default function DataExplorer() {
  const [stats, setStats] = useState<FullStats | null>(null);
  const [recentEvents, setRecentEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  
  // 导航状态
  const [layer, setLayer] = useState<"overview" | "list" | "detail">("overview");
  const [filter, setFilter] = useState<{ type: string; value: string; label: string } | null>(null);
  const [filteredEvents, setFilteredEvents] = useState<EventRecord[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<EventRecord | null>(null);
  const [filterLoading, setFilterLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE}/dashboard/full-stats`),
        fetch(`${API_BASE}/events?limit=20`)  // 只取最近20条用于展示
      ]);
      setStats(await statsRes.json());
      const eventsData = await eventsRes.json();
      setRecentEvents(eventsData.events || []);
      setLoading(false);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  // 点击筛选 - 从后端查询
  const handleFilter = async (type: string, value: string, label: string) => {
    setFilter({ type, value, label });
    setFilterLoading(true);
    setLayer("list");
    
    try {
      // 构建查询参数
      let url = `${API_BASE}/events?limit=500`;
      if (type === "event_type") url += `&event_type=${value}`;
      else if (type === "status") url += `&status=${value}`;
      else if (type === "direction") url += `&direction=${value}`;
      else if (type === "counterparty") url += `&counterparty=${encodeURIComponent(value)}`;
      else if (type === "role") url += `&role=${value}`;
      
      const res = await fetch(url);
      const data = await res.json();
      const validTypes = ["Order", "Quotation", "Shipment", "Contract"]; setFilteredEvents((data.events || []).filter((e: EventRecord) => validTypes.includes(e.event_type)));
    } catch (e) {
      console.error(e);
      setFilteredEvents([]);
    }
    setFilterLoading(false);
  };

  const handleEventClick = (event: EventRecord) => {
    setSelectedEvent(event);
    setLayer("detail");
  };

  const handleBack = () => {
    if (layer === "detail") {
      setLayer("list");
      setSelectedEvent(null);
    } else {
      setLayer("overview");
      setFilter(null);
      setFilteredEvents([]);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-6 h-6 text-orange-500 animate-spin" />
      </div>
    );
  }

  // ========== Layer 2: 事件详情 ==========
  if (layer === "detail" && selectedEvent) {
    return <EventDetail event={selectedEvent} onBack={handleBack} allEvents={filteredEvents} />;
  }

  // ========== Layer 1: 筛选列表 ==========
  if (layer === "list" && filter) {
    return (
      <div className="max-w-5xl mx-auto p-4 space-y-4">
        <button onClick={handleBack} className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" /> 返回总览
        </button>
        
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-white">{filter.label}</h1>
          <span className="text-sm text-zinc-500">{filteredEvents.length} 条记录</span>
        </div>

        {filterLoading ? (
          <div className="flex justify-center py-12">
            <RefreshCw className="w-6 h-6 text-orange-500 animate-spin" />
          </div>
        ) : (
          <div className="space-y-2">
            {filteredEvents.map((event) => {
              const Icon = EVENT_TYPE_ICON[event.event_type] || Activity;
              return (
                <div 
                  key={event.id}
                  onClick={() => handleEventClick(event)}
                  className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4 hover:border-zinc-700 cursor-pointer transition-all group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <Icon className={`w-4 h-4 ${EVENT_TYPE_COLOR[event.event_type] || "text-zinc-400"}`} />
                        <span className="text-xs text-zinc-500">{EVENT_TYPE_CN[event.event_type]}</span>
                        <StatusBadge status={event.status} />
                        <DirectionBadge direction={event.direction} />
                      </div>
                      <p className="text-sm text-zinc-300 line-clamp-2">{event.summary}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-zinc-500">
                        <span>{event.event_date || event.date}</span>
                        {event.counterparty && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{event.counterparty}</span>}
                      </div>
                    </div>
                    <div className="text-right">
                      {event.amount > 0 && (
                        <div className="text-sm font-mono text-white">{formatAmount(event.amount)}</div>
                      )}
                      <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 mt-2" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // ========== Layer 0: 总览 ==========
  return (
    <><div className="max-w-7xl mx-auto p-4 space-y-4">
      {/* 顶部统计 */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">邮件情报中心</h1>
        <div className="text-sm text-zinc-500">
          共 <span className="text-white font-mono">{stats?.total_events}</span> 条业务事件
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* ===== 左栏 (5列) ===== */}
        <div className="col-span-12 lg:col-span-5 space-y-4">
          
          {/* 状态概览 */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" /> 处理状态
            </h2>
            <div className="grid grid-cols-3 gap-2">
              <div 
                onClick={() => handleFilter("status", "pending", "进行中的事件")}
                className="p-3 bg-amber-500/5 rounded-lg border border-amber-500/20 cursor-pointer hover:bg-amber-500/10 transition-all"
              >
                <div className="text-2xl font-bold text-amber-400 font-mono">{stats?.by_status.pending || 0}</div>
                <div className="text-xs text-zinc-500">进行中</div>
              </div>
              <div 
                onClick={() => handleFilter("status", "completed", "已完成的事件")}
                className="p-3 bg-green-500/5 rounded-lg border border-green-500/20 cursor-pointer hover:bg-green-500/10 transition-all"
              >
                <div className="text-2xl font-bold text-green-400 font-mono">{stats?.by_status.completed || 0}</div>
                <div className="text-xs text-zinc-500">已完成</div>
              </div>
              <div className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700">
                <div className="text-2xl font-bold text-zinc-500 font-mono">{stats?.by_status.unknown || 0}</div>
                <div className="text-xs text-zinc-500">待分类</div>
              </div>
            </div>
          </div>

          {/* 收支流向 */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" /> 资金流向
            </h2>
            <div className="space-y-2">
              <div 
                onClick={() => handleFilter("direction", "inbound", "收入相关事件")}
                className="flex items-center justify-between p-3 rounded-lg bg-green-500/5 border border-green-500/20 cursor-pointer hover:bg-green-500/10 transition-all"
              >
                <div className="flex items-center gap-2">
                  <ArrowDownLeft className="w-5 h-5 text-green-400" />
                  <div>
                    <div className="text-sm text-green-400">收入</div>
                    <div className="text-xs text-zinc-500">{stats?.by_direction.inbound?.count || 0} 事件</div>
                  </div>
                </div>
                <div className="text-lg font-mono text-green-400">{formatAmount(stats?.by_direction.inbound?.amount || 0)}</div>
              </div>
              
              <div 
                onClick={() => handleFilter("direction", "outbound", "支出相关事件")}
                className="flex items-center justify-between p-3 rounded-lg bg-orange-500/5 border border-orange-500/20 cursor-pointer hover:bg-orange-500/10 transition-all"
              >
                <div className="flex items-center gap-2">
                  <ArrowUpRight className="w-5 h-5 text-orange-400" />
                  <div>
                    <div className="text-sm text-orange-400">支出</div>
                    <div className="text-xs text-zinc-500">{stats?.by_direction.outbound?.count || 0} 事件</div>
                  </div>
                </div>
                <div className="text-lg font-mono text-orange-400">{formatAmount(stats?.by_direction.outbound?.amount || 0)}</div>
              </div>
              
              <div 
                onClick={() => handleFilter("direction", "internal", "内部流转事件")}
                className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 cursor-pointer hover:bg-zinc-800 transition-all"
              >
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-5 h-5 text-zinc-400" />
                  <div>
                    <div className="text-sm text-zinc-400">内部</div>
                    <div className="text-xs text-zinc-500">{stats?.by_direction.internal?.count || 0} 事件</div>
                  </div>
                </div>
                <div className="text-lg font-mono text-zinc-400">{formatAmount(stats?.by_direction.internal?.amount || 0)}</div>
              </div>
            </div>
          </div>

          {/* 最新动态 */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-purple-400" /> 最新动态
            </h2>
            <div className="space-y-1">
              {recentEvents.slice(0, 6).map((event) => {
                const Icon = EVENT_TYPE_ICON[event.event_type] || Activity;
                return (
                  <div 
                    key={event.id}
                    onClick={() => { setSelectedEvent(event); setLayer("detail"); }}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800/50 cursor-pointer transition-all group"
                  >
                    <Icon className={`w-4 h-4 ${EVENT_TYPE_COLOR[event.event_type] || "text-zinc-400"}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-zinc-300 truncate">{event.summary}</p>
                      <span className="text-xs text-zinc-500">{event.event_date || event.date}</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400" />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ===== 右栏 (7列) ===== */}
        <div className="col-span-12 lg:col-span-7 space-y-4">
          
          {/* 事件类型分布 */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-cyan-400" /> 事件类型
            </h2>
            <div className="grid grid-cols-3 gap-2">
              {stats?.by_type.filter(t => ["Order", "Quotation", "Shipment", "Contract"].includes(t.type)).map((item) => {
                const Icon = EVENT_TYPE_ICON[item.type] || Activity;
                return (
                  <div 
                    key={item.type}
                    onClick={() => handleFilter("event_type", item.type, `${EVENT_TYPE_CN[item.type]}事件`)}
                    className="p-3 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/60 cursor-pointer transition-all border border-transparent hover:border-zinc-700"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className={`w-4 h-4 ${EVENT_TYPE_COLOR[item.type]}`} />
                      <span className="text-xs text-zinc-400">{EVENT_TYPE_CN[item.type]}</span>
                    </div>
                    <div className="text-xl font-bold text-white font-mono">{item.count}</div>
                    <div className="text-xs text-zinc-500">{formatAmount(item.amount)}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 交易对手 Top 10 */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Users className="w-4 h-4 text-emerald-400" /> 主要交易对手
            </h2>
            <div className="space-y-1">
              {stats?.counterparties.slice(0, 10).map((cp, i) => (
                <div 
                  key={cp.name}
                  onClick={() => handleFilter("counterparty", cp.name, cp.name)}
                  className="flex items-center justify-between p-2 rounded-lg hover:bg-zinc-800/50 cursor-pointer transition-all group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs text-zinc-600 w-4">{i + 1}</span>
                    <Building2 className="w-4 h-4 text-zinc-500" />
                    <span className="text-sm text-zinc-300 truncate">{cp.name}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">
                      {ROLE_CN[cp.role] || cp.role}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-zinc-500">{cp.count} 事件</span>
                    <span className="text-xs font-mono text-zinc-400">{formatAmount(cp.amount)}</span>
                    <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 角色分布 */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Network className="w-4 h-4 text-rose-400" /> 对手方角色
            </h2>
            <div className="flex flex-wrap gap-2">
              {stats?.by_role && Object.entries(stats.by_role).map(([role, count]) => (
                <div 
                  key={role}
                  onClick={() => handleFilter("role", role, ROLE_CN[role] || role)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/50 border border-zinc-700 cursor-pointer hover:bg-zinc-700/50 hover:border-zinc-600 transition-all"
                >
                  <span className="text-sm text-zinc-400">{ROLE_CN[role] || role}</span>
                  <span className="text-sm font-mono text-white">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
      <EmailAgentChat /></>
  );
}

// ========== 事件详情组件 ==========
function EventDetail({ event, onBack, allEvents }: { event: EventRecord; onBack: () => void; allEvents: EventRecord[] }) {
  const Icon = EVENT_TYPE_ICON[event.event_type] || Activity;
  
  // 业务生命周期
  const lifecycle = ["Inquiry", "Quotation", "Contract", "Order", "Shipment", "Payment"];
  const currentStage = lifecycle.indexOf(event.event_type);
  
  // 同一对手的相关事件
  const relatedEvents = allEvents
    .filter((e: EventRecord) => e.counterparty === event.counterparty && e.id !== event.id)
    .slice(0, 5);

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-4">
      <button onClick={onBack} className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white">
        <ArrowLeft className="w-4 h-4" /> 返回列表
      </button>

      {/* 主卡片 */}
      <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-6">
        <div className="flex items-center gap-3 mb-4">
          <Icon className={`w-6 h-6 ${EVENT_TYPE_COLOR[event.event_type]}`} />
          <span className="text-lg font-bold text-white">{EVENT_TYPE_CN[event.event_type]}</span>
          <StatusBadge status={event.status} />
          <DirectionBadge direction={event.direction} />
        </div>

        <p className="text-zinc-300 mb-6">{event.summary}</p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-zinc-500 mb-1">日期</div>
            <div className="text-white">{event.event_date || event.date || "-"}</div>
          </div>
          <div>
            <div className="text-zinc-500 mb-1">金额</div>
            <div className="text-white font-mono">{event.amount > 0 ? `${event.currency} ${event.amount.toLocaleString()}` : "-"}</div>
          </div>
          <div>
            <div className="text-zinc-500 mb-1">交易对手</div>
            <div className="text-white">{event.counterparty || "-"}</div>
          </div>
          <div>
            <div className="text-zinc-500 mb-1">对手角色</div>
            <div className="text-white">{ROLE_CN[event.counterparty_role] || event.counterparty_role || "-"}</div>
          </div>
        </div>

        <button className="mt-6 flex items-center gap-2 px-4 py-2 bg-purple-500/10 border border-purple-500/30 rounded-lg text-purple-400 hover:bg-purple-500/20 transition-all">
          <Mail className="w-4 h-4" /> 查看原始邮件
        </button>
      </div>

      {/* 业务生命周期 */}
      {currentStage >= 0 && (
        <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-4">业务生命周期</h3>
          <div className="flex items-center justify-between">
            {lifecycle.map((stage, i) => {
              const StageIcon = EVENT_TYPE_ICON[stage];
              const isActive = i === currentStage;
              const isPast = i < currentStage;
              return (
                <div key={stage} className="flex flex-col items-center gap-2">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    isActive ? "bg-orange-500 text-white" :
                    isPast ? "bg-green-500/20 text-green-400" :
                    "bg-zinc-800 text-zinc-500"
                  }`}>
                    <StageIcon className="w-5 h-5" />
                  </div>
                  <span className={`text-xs ${isActive ? "text-orange-400" : isPast ? "text-green-400" : "text-zinc-500"}`}>
                    {EVENT_TYPE_CN[stage]}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 相关事件 */}
      {relatedEvents.length > 0 && (
        <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-3">同一对手的其他事件</h3>
          <div className="space-y-2">
            {relatedEvents.map((e) => {
              const EIcon = EVENT_TYPE_ICON[e.event_type] || Activity;
              return (
                <div key={e.id} className="flex items-center gap-3 p-2 rounded-lg bg-zinc-800/30">
                  <EIcon className={`w-4 h-4 ${EVENT_TYPE_COLOR[e.event_type]}`} />
                  <span className="text-xs text-zinc-500">{EVENT_TYPE_CN[e.event_type]}</span>
                  <span className="text-sm text-zinc-300 truncate flex-1">{e.summary}</span>
                  <span className="text-xs text-zinc-500">{e.event_date || e.date}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
