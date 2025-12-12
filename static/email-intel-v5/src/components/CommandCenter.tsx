import { AlertTriangle, Clock, TrendingUp, Mail, Users, ArrowUp, ArrowDown } from 'lucide-react';
import { useCommandCenter, useNeedsReply, useWaitingOn } from '../hooks/useEmailIntel';
import type { ActionItem, RelationshipAlert } from '../types';

function StatCard({ icon: Icon, value, label, color, trend }: {
  icon: React.ElementType;
  value: number;
  label: string;
  color: string;
  trend?: 'up' | 'down';
}) {
  return (
    <div className={`bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 hover:border-zinc-700 transition-colors`}>
      <div className="flex items-center gap-3">
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-white">{value}</span>
            {trend && (
              <span className={trend === 'up' ? 'text-green-400' : 'text-red-400'}>
                {trend === 'up' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
              </span>
            )}
          </div>
          <span className="text-sm text-zinc-500">{label}</span>
        </div>
      </div>
    </div>
  );
}

function ActionItemCard({ item }: { item: ActionItem }) {
  const priorityColors = {
    high: 'border-red-500/30 bg-red-500/5',
    medium: 'border-yellow-500/30 bg-yellow-500/5',
    low: 'border-zinc-700 bg-zinc-900/50',
  };

  const priorityDots = {
    high: 'bg-red-500',
    medium: 'bg-yellow-500',
    low: 'bg-zinc-500',
  };

  return (
    <div className={`border rounded-lg p-3 ${priorityColors[item.priority]} hover:border-zinc-600 transition-colors cursor-pointer`}>
      <div className="flex items-start gap-3">
        <div className={`w-2 h-2 rounded-full mt-2 ${priorityDots[item.priority]}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-white truncate">{item.from.company || item.from.name}</span>
            <span className="text-xs text-zinc-500 whitespace-nowrap">
              {item.days_waiting === 0 ? '今天' : `${item.days_waiting}天前`}
            </span>
          </div>
          <p className="text-sm text-zinc-400 truncate mt-0.5">{item.subject}</p>
          <p className="text-xs text-zinc-600 mt-1">{item.from.name}</p>
        </div>
      </div>
    </div>
  );
}

function AlertCard({ alert }: { alert: RelationshipAlert }) {
  const severityColors = {
    high: 'text-red-400 bg-red-500/10',
    medium: 'text-yellow-400 bg-yellow-500/10',
    low: 'text-blue-400 bg-blue-500/10',
  };

  return (
    <div className="flex items-start gap-3 p-3 bg-zinc-900/30 rounded-lg border border-zinc-800">
      <div className={`p-1.5 rounded ${severityColors[alert.severity]}`}>
        <AlertTriangle className="w-4 h-4" />
      </div>
      <div>
        <p className="text-sm text-zinc-300">{alert.message}</p>
        {alert.suggested_action && (
          <p className="text-xs text-zinc-500 mt-1">{alert.suggested_action}</p>
        )}
      </div>
    </div>
  );
}

export default function CommandCenter() {
  const { data: commandData, isLoading: loadingCommand } = useCommandCenter();
  const { data: needsReply, isLoading: loadingNeeds } = useNeedsReply();
  const { data: waitingOn, isLoading: loadingWaiting } = useWaitingOn();

  const isLoading = loadingCommand || loadingNeeds || loadingWaiting;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
      </div>
    );
  }

  const urgentCount = commandData?.urgent_count || needsReply?.filter(i => i.priority === 'high').length || 0;
  const waitingCount = commandData?.waiting_count || waitingOn?.length || 0;
  const opportunityCount = commandData?.opportunity_count || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-white">Command Center</h2>
        <p className="text-sm text-zinc-500 mt-1">今日概览 - {new Date().toLocaleDateString('zh-CN')}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          icon={AlertTriangle}
          value={urgentCount}
          label="紧急响应"
          color="bg-red-500/20 text-red-400"
        />
        <StatCard
          icon={Clock}
          value={waitingCount}
          label="等待回复"
          color="bg-yellow-500/20 text-yellow-400"
        />
        <StatCard
          icon={TrendingUp}
          value={opportunityCount}
          label="新机会"
          color="bg-green-500/20 text-green-400"
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-2 gap-6">
        {/* Needs Reply */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
              <Mail className="w-4 h-4" />
              需要回复
            </h3>
            <span className="text-xs text-zinc-600">{needsReply?.length || 0} 封</span>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
            {needsReply?.slice(0, 5).map((item) => (
              <ActionItemCard key={item.id} item={item} />
            ))}
            {(!needsReply || needsReply.length === 0) && (
              <p className="text-sm text-zinc-600 text-center py-8">暂无待回复邮件</p>
            )}
          </div>
        </div>

        {/* Waiting On */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              等待回复
            </h3>
            <span className="text-xs text-zinc-600">{waitingOn?.length || 0} 封</span>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
            {waitingOn?.slice(0, 5).map((item) => (
              <ActionItemCard key={item.id} item={item} />
            ))}
            {(!waitingOn || waitingOn.length === 0) && (
              <p className="text-sm text-zinc-600 text-center py-8">暂无等待中邮件</p>
            )}
          </div>
        </div>
      </div>

      {/* Relationship Alerts */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
          <Users className="w-4 h-4" />
          关系预警
        </h3>
        <div className="space-y-2">
          {commandData?.relationship_alerts?.slice(0, 3).map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
          {(!commandData?.relationship_alerts || commandData.relationship_alerts.length === 0) && (
            <p className="text-sm text-zinc-600 text-center py-4">所有关系状态良好</p>
          )}
        </div>
      </div>
    </div>
  );
}
