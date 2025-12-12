'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.vsg-brain.com';
const TARGET_EMAILS = 17600;

interface PipelineStats {
  total_processed: number;
  total_success: number;
  success_rate: number;
  total_entities: number;
  total_actions: number;
  intent_distribution: Record<string, number>;
  speed_per_minute: number;
  is_running: boolean;
  updated_at: string;
}

interface RecentItem {
  email_id: string;
  subject: string;
  intent: string;
  confidence: number;
  entity_count: number;
  processed_at: string;
}

const intentColors: Record<string, string> = {
  ORDER_CONFIRM: 'bg-green-900 text-green-300',
  QUOTE_REQUEST: 'bg-amber-900 text-amber-300',
  QUOTE_RESPONSE: 'bg-blue-900 text-blue-300',
  SHIPPING_UPDATE: 'bg-purple-900 text-purple-300',
  INVOICE: 'bg-red-900 text-red-300',
  PAYMENT: 'bg-teal-900 text-teal-300',
  COMPLIANCE: 'bg-yellow-900 text-yellow-300',
  QUALITY: 'bg-pink-900 text-pink-300',
  GENERAL: 'bg-gray-700 text-gray-300',
};

export default function PipelineMonitor() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('-');

  const fetchData = async () => {
    try {
      const [statsRes, recentRes] = await Promise.all([
        fetch(`${API_BASE}/api/email-intel/v2/pipeline/stats`),
        fetch(`${API_BASE}/api/email-intel/v2/pipeline/recent?limit=10`),
      ]);

      if (!statsRes.ok || !recentRes.ok) {
        throw new Error('API 请求失败');
      }

      const statsData = await statsRes.json();
      const recentData = await recentRes.json();

      setStats(statsData);
      setRecent(recentData.items || []);
      setError(null);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err) {
      setError('无法连接到 API');
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const progress = stats ? Math.min((stats.total_processed / TARGET_EMAILS) * 100, 100) : 0;
  const remaining = stats ? TARGET_EMAILS - stats.total_processed : 0;
  const etaMins = stats && stats.speed_per_minute > 0 ? remaining / stats.speed_per_minute : 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <header className="text-center mb-8">
          <h1 className="text-3xl font-bold text-cyan-400 mb-1">📧 Email Intelligence V2.0</h1>
          <p className="text-gray-400 text-sm">Pipeline Monitor - 实时处理监控</p>
        </header>

        {/* Error */}
        {error && (
          <div className="bg-red-900/30 border border-red-500 rounded-lg p-4 mb-6 text-center text-red-300">
            ⚠️ {error}
          </div>
        )}

        {/* Status Banner */}
        <div
          className={`flex items-center justify-center gap-3 p-4 rounded-xl mb-6 text-lg font-semibold ${
            stats?.is_running
              ? 'bg-gradient-to-r from-slate-800 to-emerald-900/50 border border-emerald-500'
              : 'bg-gradient-to-r from-slate-800 to-red-900/50 border border-red-500'
          }`}
        >
          <div
            className={`w-3 h-3 rounded-full ${
              stats?.is_running ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
            }`}
          />
          <span>{stats?.is_running ? '🚀 正在处理中...' : '⏹️ 处理已停止'}</span>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <StatCard label="已处理" value={stats?.total_processed.toLocaleString() || '-'} />
          <StatCard
            label="成功率"
            value={stats ? `${stats.success_rate.toFixed(1)}%` : '-'}
            color="text-emerald-400"
          />
          <StatCard
            label="提取实体"
            value={stats?.total_entities.toLocaleString() || '-'}
          />
          <StatCard
            label="封/分钟"
            value={stats?.speed_per_minute.toFixed(1) || '-'}
          />
          <StatCard
            label="行动项"
            value={stats?.total_actions.toLocaleString() || '-'}
            color="text-amber-400"
          />
          <StatCard
            label="预计剩余"
            value={etaMins > 60 ? `${(etaMins / 60).toFixed(1)}h` : `${Math.round(etaMins)}m`}
          />
        </div>

        {/* Progress Bar */}
        <div className="bg-white/5 rounded-xl p-6 mb-6 border border-white/10">
          <h2 className="text-cyan-400 mb-4 flex items-center gap-2">📊 处理进度</h2>
          <div className="bg-black/30 rounded-lg h-6 overflow-hidden mb-2">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 rounded-lg transition-all duration-500 flex items-center justify-center text-xs font-bold text-black"
              style={{ width: `${Math.max(progress, 2)}%` }}
            >
              {progress.toFixed(1)}%
            </div>
          </div>
          <div className="flex justify-between text-sm text-gray-400">
            <span>已处理 {stats?.total_processed.toLocaleString() || 0} 封</span>
            <span>目标: {TARGET_EMAILS.toLocaleString()} 封</span>
          </div>
        </div>

        {/* Intent Distribution */}
        <div className="bg-white/5 rounded-xl p-6 mb-6 border border-white/10">
          <h2 className="text-cyan-400 mb-4 flex items-center gap-2">📋 意图分布</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {stats &&
              Object.entries(stats.intent_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([intent, count]) => (
                  <div
                    key={intent}
                    className="bg-black/20 rounded-lg p-3 flex justify-between items-center"
                  >
                    <span className="text-xs text-gray-400">{intent}</span>
                    <span className="text-lg font-semibold text-cyan-400">{count}</span>
                  </div>
                ))}
          </div>
        </div>

        {/* Recent List */}
        <div className="bg-white/5 rounded-xl p-6 border border-white/10">
          <h2 className="text-cyan-400 mb-4 flex items-center gap-2">🕐 最近处理</h2>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {recent.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 p-3 bg-black/20 rounded-lg hover:bg-black/30 transition"
              >
                <span
                  className={`text-xs px-2 py-1 rounded font-semibold min-w-[90px] text-center ${
                    intentColors[item.intent] || 'bg-gray-700 text-gray-300'
                  }`}
                >
                  {item.intent}
                </span>
                <span className="flex-1 text-sm text-gray-300 truncate">
                  {item.subject || '(无主题)'}
                </span>
                <span className="text-sm text-cyan-400 min-w-[60px] text-right">
                  {item.entity_count} 实体
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-gray-500 text-xs mt-6">
          自动刷新: 每 5 秒 | 最后更新: {lastUpdate}
        </p>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color = 'text-cyan-400',
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-white/5 rounded-xl p-4 text-center border border-white/10 hover:border-cyan-500/30 transition">
      <div className={`text-2xl md:text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-400 uppercase tracking-wide mt-1">{label}</div>
    </div>
  );
}
