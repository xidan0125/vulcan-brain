import { useState } from 'react';
import { Mail, Clock, CalendarCheck, Filter } from 'lucide-react';
import { useNeedsReply, useWaitingOn } from '../hooks/useEmailIntel';
import type { ActionItem } from '../types';

type TabType = 'needs_reply' | 'waiting_on' | 'follow_up';
type PriorityFilter = 'all' | 'high' | 'medium' | 'low';

function ActionItemRow({ item, showType }: { item: ActionItem; showType?: boolean }) {
  const priorityColors = {
    high: 'bg-red-500',
    medium: 'bg-yellow-500',
    low: 'bg-zinc-500',
  };

  const typeLabels = {
    needs_reply: '需要回复',
    waiting_on: '等待回复',
    follow_up: '需要跟进',
  };

  return (
    <div className="group bg-zinc-900/30 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 hover:bg-zinc-900/50 transition-all cursor-pointer">
      <div className="flex items-start gap-4">
        {/* Priority Indicator */}
        <div className={`w-1 h-full min-h-[60px] rounded-full ${priorityColors[item.priority]}`} />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-white font-medium">{item.from.company || item.from.name}</span>
            {showType && (
              <span className="text-xs px-2 py-0.5 bg-zinc-800 rounded text-zinc-400">
                {typeLabels[item.type]}
              </span>
            )}
          </div>
          <p className="text-sm text-zinc-300 truncate">{item.subject}</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-zinc-500">
            <span>{item.from.name}</span>
            <span>{item.from.email}</span>
          </div>
          {item.ai_summary && (
            <p className="mt-2 text-xs text-zinc-500 bg-zinc-800/50 rounded p-2">
              AI: {item.ai_summary}
            </p>
          )}
        </div>

        {/* Meta */}
        <div className="text-right flex-shrink-0">
          <div className="text-sm text-zinc-400">
            {item.days_waiting === 0 ? '今天' : `${item.days_waiting} 天前`}
          </div>
          {item.due_date && (
            <div className="text-xs text-orange-400 mt-1">
              截止: {new Date(item.due_date).toLocaleDateString('zh-CN')}
            </div>
          )}
          <div className={`text-xs mt-1 ${
            item.priority === 'high' ? 'text-red-400' :
            item.priority === 'medium' ? 'text-yellow-400' : 'text-zinc-500'
          }`}>
            {item.priority === 'high' ? '紧急' : item.priority === 'medium' ? '重要' : '普通'}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ActionCenter() {
  const [activeTab, setActiveTab] = useState<TabType>('needs_reply');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');

  const { data: needsReply, isLoading: loadingNeeds } = useNeedsReply();
  const { data: waitingOn, isLoading: loadingWaiting } = useWaitingOn();

  const isLoading = loadingNeeds || loadingWaiting;

  const tabs = [
    { id: 'needs_reply', label: '需要回复', icon: Mail, count: needsReply?.length || 0 },
    { id: 'waiting_on', label: '等待回复', icon: Clock, count: waitingOn?.length || 0 },
    { id: 'follow_up', label: '需要跟进', icon: CalendarCheck, count: 0 },
  ];

  // Get current tab's data
  let currentData: ActionItem[] = [];
  if (activeTab === 'needs_reply') {
    currentData = needsReply || [];
  } else if (activeTab === 'waiting_on') {
    currentData = waitingOn || [];
  }

  // Apply filter
  if (priorityFilter !== 'all') {
    currentData = currentData.filter(item => item.priority === priorityFilter);
  }

  // Sort by priority score
  currentData = [...currentData].sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0));

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Action Center</h2>
        <p className="text-sm text-zinc-500 mt-1">待处理邮件行动项</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 bg-zinc-900/50 p-1 rounded-lg">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'bg-orange-500/20 text-orange-400'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                <span className={`px-1.5 py-0.5 rounded text-xs ${
                  activeTab === tab.id ? 'bg-orange-500/30' : 'bg-zinc-800'
                }`}>
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-zinc-500" />
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as PriorityFilter)}
            className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-orange-500"
          >
            <option value="all">全部优先级</option>
            <option value="high">紧急</option>
            <option value="medium">重要</option>
            <option value="low">普通</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
          </div>
        ) : currentData.length > 0 ? (
          <div className="space-y-3">
            {currentData.map((item) => (
              <ActionItemRow key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
            <Mail className="w-12 h-12 mb-4 opacity-50" />
            <p>暂无待处理项目</p>
          </div>
        )}
      </div>

      {/* Stats Footer */}
      <div className="mt-4 pt-4 border-t border-zinc-800 flex items-center justify-between text-sm text-zinc-500">
        <span>显示 {currentData.length} 项</span>
        <div className="flex gap-4">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            紧急: {currentData.filter(i => i.priority === 'high').length}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-500" />
            重要: {currentData.filter(i => i.priority === 'medium').length}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-zinc-500" />
            普通: {currentData.filter(i => i.priority === 'low').length}
          </span>
        </div>
      </div>
    </div>
  );
}
