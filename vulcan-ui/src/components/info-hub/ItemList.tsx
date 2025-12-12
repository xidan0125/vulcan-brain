/**
 * 通用列表组件
 * 用于展示审批、邮件、聊天等列表
 */
import React from 'react';
import Link from 'next/link';
import { LucideIcon, ChevronRight, Clock } from 'lucide-react';

interface ItemListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  title?: string;
  icon?: LucideIcon;
  viewAllHref?: string;
  viewAllText?: string;
  loading?: boolean;
  emptyIcon?: LucideIcon;
  emptyText?: string;
  maxItems?: number;
  className?: string;
}

export function ItemList<T>({
  items,
  renderItem,
  title,
  icon: Icon,
  viewAllHref,
  viewAllText = '查看全部',
  loading = false,
  emptyIcon: EmptyIcon = Clock,
  emptyText = '暂无数据',
  maxItems,
  className = '',
}: ItemListProps<T>) {
  const displayItems = maxItems ? items.slice(0, maxItems) : items;

  if (loading) {
    return (
      <div className={`p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 ${className}`}>
        {title && (
          <div className="h-4 bg-zinc-800 rounded w-1/4 mb-4"></div>
        )}
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-zinc-800/50 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 ${className}`}>
      {/* Header */}
      {(title || viewAllHref) && (
        <div className="flex items-center justify-between mb-3">
          {title && (
            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
              {Icon && <Icon className="w-3 h-3" />}
              <span>{title} ({items.length})</span>
            </div>
          )}
          {viewAllHref && (
            <Link
              href={viewAllHref}
              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
            >
              {viewAllText}
              <ChevronRight className="w-3 h-3" />
            </Link>
          )}
        </div>
      )}

      {/* Content */}
      {displayItems.length > 0 ? (
        <div className="space-y-2">
          {displayItems.map((item, idx) => renderItem(item, idx))}
        </div>
      ) : (
        <div className="text-center py-8">
          <EmptyIcon className="w-10 h-10 mx-auto mb-2 text-zinc-700" />
          <p className="text-xs text-zinc-600">{emptyText}</p>
        </div>
      )}

      {/* Show more hint */}
      {maxItems && items.length > maxItems && (
        <div className="mt-3 pt-3 border-t border-zinc-800 text-center">
          <span className="text-xs text-zinc-500">
            还有 {items.length - maxItems} 条记录
          </span>
        </div>
      )}
    </div>
  );
}

export default ItemList;
