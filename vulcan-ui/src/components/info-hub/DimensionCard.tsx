/**
 * 维度卡片组件
 * 用于展示 InfoHub 各维度的汇总信息
 */
import React from 'react';
import Link from 'next/link';
import { LucideIcon, ChevronRight, AlertTriangle, CheckCircle2, Sparkles } from 'lucide-react';

interface DimensionCardProps {
  title: string;
  icon: LucideIcon;
  href: string;
  stats: Array<{ label: string; value: number | string; highlight?: boolean }>;
  highlights?: string[];
  risks?: string[];
  loading?: boolean;
  className?: string;
}

export function DimensionCard({
  title,
  icon: Icon,
  href,
  stats,
  highlights = [],
  risks = [],
  loading = false,
  className = '',
}: DimensionCardProps) {
  if (loading) {
    return (
      <div className={`bg-gray-800 rounded-lg p-4 animate-pulse ${className}`}>
        <div className="h-6 bg-gray-700 rounded w-1/3 mb-4"></div>
        <div className="space-y-2">
          <div className="h-4 bg-gray-700 rounded w-1/2"></div>
          <div className="h-4 bg-gray-700 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  return (
    <Link href={href} className={`block ${className}`}>
      <div className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition-colors cursor-pointer border border-gray-700 hover:border-blue-500/50">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-blue-400" />
            <h3 className="font-medium text-white">{title}</h3>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-500" />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          {stats.map((stat, idx) => (
            <div key={idx} className="text-center p-2 bg-gray-900/50 rounded">
              <div className={`text-lg font-bold ${stat.highlight ? 'text-yellow-400' : 'text-white'}`}>
                {stat.value}
              </div>
              <div className="text-xs text-gray-400">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Highlights */}
        {highlights.length > 0 && (
          <div className="mb-2">
            <div className="flex items-center gap-1 text-xs text-green-400 mb-1">
              <Sparkles className="w-3 h-3" />
              <span>亮点</span>
            </div>
            <ul className="text-xs text-gray-300 space-y-1">
              {highlights.slice(0, 2).map((h, idx) => (
                <li key={idx} className="flex items-start gap-1">
                  <CheckCircle2 className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                  <span className="line-clamp-1">{h}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Risks */}
        {risks.length > 0 && (
          <div>
            <div className="flex items-center gap-1 text-xs text-red-400 mb-1">
              <AlertTriangle className="w-3 h-3" />
              <span>风险</span>
            </div>
            <ul className="text-xs text-gray-300 space-y-1">
              {risks.slice(0, 2).map((r, idx) => (
                <li key={idx} className="flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />
                  <span className="line-clamp-1">{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Link>
  );
}

export default DimensionCard;
