/**
 * AI 洞察卡片组件
 * 用于展示 AI 分析结果（摘要、待办、风险等）
 */
import React from 'react';
import {
  Sparkles,
  ListTodo,
  AlertTriangle,
  CheckCircle2,
  Star,
  Clock,
  LucideIcon
} from 'lucide-react';

type InsightType = 'summary' | 'action' | 'risk' | 'highlight' | 'pending' | 'custom';

interface AIInsightCardProps {
  type: InsightType;
  title?: string;
  icon?: LucideIcon;
  items: string[];
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'amber';
  loading?: boolean;
  emptyText?: string;
  className?: string;
}

const typeConfig: Record<InsightType, { icon: LucideIcon; title: string; color: string }> = {
  summary: { icon: Sparkles, title: 'AI 摘要', color: 'blue' },
  action: { icon: ListTodo, title: '待办事项', color: 'amber' },
  risk: { icon: AlertTriangle, title: '风险提醒', color: 'red' },
  highlight: { icon: Star, title: '亮点', color: 'green' },
  pending: { icon: Clock, title: '需关注', color: 'yellow' },
  custom: { icon: Sparkles, title: '洞察', color: 'purple' },
};

const colorStyles: Record<string, { bg: string; border: string; text: string; iconBg: string }> = {
  blue: { bg: 'bg-blue-500/5', border: 'border-blue-500/10', text: 'text-blue-400', iconBg: 'bg-blue-500/10' },
  green: { bg: 'bg-green-500/5', border: 'border-green-500/10', text: 'text-green-400', iconBg: 'bg-green-500/10' },
  yellow: { bg: 'bg-yellow-500/5', border: 'border-yellow-500/10', text: 'text-yellow-400', iconBg: 'bg-yellow-500/10' },
  red: { bg: 'bg-red-500/5', border: 'border-red-500/10', text: 'text-red-400', iconBg: 'bg-red-500/10' },
  purple: { bg: 'bg-purple-500/5', border: 'border-purple-500/10', text: 'text-purple-400', iconBg: 'bg-purple-500/10' },
  amber: { bg: 'bg-amber-500/5', border: 'border-amber-500/10', text: 'text-amber-400', iconBg: 'bg-amber-500/10' },
};

export function AIInsightCard({
  type,
  title,
  icon,
  items,
  color,
  loading = false,
  emptyText = '暂无数据',
  className = '',
}: AIInsightCardProps) {
  const config = typeConfig[type];
  const Icon = icon || config.icon;
  const displayTitle = title || config.title;
  const colorKey = color || config.color;
  const styles = colorStyles[colorKey];

  if (loading) {
    return (
      <div className={`p-3 rounded-lg border animate-pulse ${styles.bg} ${styles.border} ${className}`}>
        <div className="h-4 bg-gray-700 rounded w-1/3 mb-2"></div>
        <div className="space-y-1">
          <div className="h-3 bg-gray-700 rounded w-full"></div>
          <div className="h-3 bg-gray-700 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  // 摘要类型特殊处理 - 单段文字
  if (type === 'summary') {
    return (
      <div className={`p-4 rounded-lg border ${styles.bg} ${styles.border} ${className}`}>
        <div className={`flex items-center gap-2 text-xs font-mono mb-2 ${styles.text}`}>
          <Icon className="w-3 h-3" />
          <span>{displayTitle}</span>
        </div>
        <p className="text-sm text-zinc-300 leading-relaxed">
          {items[0] || emptyText}
        </p>
      </div>
    );
  }

  // 列表类型
  return (
    <div className={`p-3 rounded-lg border ${styles.bg} ${styles.border} ${className}`}>
      <div className={`flex items-center gap-2 text-xs font-mono mb-2 ${styles.text}`}>
        <Icon className="w-3 h-3" />
        <span>{displayTitle} ({items.length})</span>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-1">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-xs text-zinc-400">
              <span className="mt-1.5 w-1 h-1 rounded-full bg-current flex-shrink-0" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-zinc-600">{emptyText}</p>
      )}
    </div>
  );
}

export default AIInsightCard;
