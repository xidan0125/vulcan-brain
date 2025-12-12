/**
 * 统计卡片组件
 * 用于展示单个统计数据
 */
import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: number | string;
  icon?: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'gray';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  className?: string;
}

const colorStyles = {
  blue: 'text-blue-400 bg-blue-500/10',
  green: 'text-green-400 bg-green-500/10',
  yellow: 'text-yellow-400 bg-yellow-500/10',
  red: 'text-red-400 bg-red-500/10',
  purple: 'text-purple-400 bg-purple-500/10',
  gray: 'text-gray-400 bg-gray-500/10',
};

const sizeStyles = {
  sm: { card: 'p-2', value: 'text-lg', label: 'text-xs', icon: 'w-4 h-4' },
  md: { card: 'p-3', value: 'text-2xl', label: 'text-sm', icon: 'w-5 h-5' },
  lg: { card: 'p-4', value: 'text-3xl', label: 'text-base', icon: 'w-6 h-6' },
};

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  trendValue,
  color = 'blue',
  size = 'md',
  loading = false,
  className = '',
}: StatCardProps) {
  const styles = sizeStyles[size];
  const colorStyle = colorStyles[color];

  if (loading) {
    return (
      <div className={`bg-gray-800 rounded-lg ${styles.card} animate-pulse ${className}`}>
        <div className="h-4 bg-gray-700 rounded w-1/2 mb-2"></div>
        <div className="h-8 bg-gray-700 rounded w-3/4"></div>
      </div>
    );
  }

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400';

  return (
    <div className={`bg-gray-800 rounded-lg ${styles.card} ${className}`}>
      <div className="flex items-center justify-between mb-1">
        <span className={`${styles.label} text-gray-400`}>{label}</span>
        {Icon && (
          <div className={`${colorStyle} p-1.5 rounded`}>
            <Icon className={styles.icon} />
          </div>
        )}
      </div>
      <div className="flex items-end gap-2">
        <span className={`${styles.value} font-bold text-white`}>{value}</span>
        {trend && trendValue && (
          <div className={`flex items-center gap-0.5 ${trendColor} text-xs mb-1`}>
            <TrendIcon className="w-3 h-3" />
            <span>{trendValue}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default StatCard;
