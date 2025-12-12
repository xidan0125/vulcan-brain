/**
 * 聊天摘要卡片组件
 * 用于展示单个群聊的 AI 分析结果
 */
import React from 'react';
import Link from 'next/link';
import {
  MessageSquare,
  Sparkles,
  CheckCircle2,
  ListTodo,
  AlertTriangle,
} from 'lucide-react';
import type { ChatSummary } from '@/types/info-hub';

interface ChatSummaryCardProps {
  chat: ChatSummary;
  className?: string;
}

export function ChatSummaryCard({ chat, className = '' }: ChatSummaryCardProps) {
  return (
    <div className={`p-5 bg-zinc-900/50 rounded-xl border border-zinc-800 ${className}`}>
      {/* 群聊标题 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">{chat.chat_name}</h3>
            <div className="flex items-center gap-3 text-xs text-zinc-500">
              <span>{chat.message_count} 条消息</span>
              {chat.activity_level === 'high' && (
                <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">
                  活跃
                </span>
              )}
            </div>
          </div>
        </div>
        <Link
          href={`/info-hub/chat?chat_id=${chat.chat_id}`}
          className="text-xs text-zinc-500 hover:text-blue-400 transition-colors"
        >
          查看原始消息 →
        </Link>
      </div>

      {/* AI 摘要 */}
      {chat.summary && (
        <div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/10 mb-4">
          <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-2">
            <Sparkles className="w-3 h-3" />
            AI 摘要
          </div>
          <p className="text-sm text-zinc-300 leading-relaxed">{chat.summary}</p>
        </div>
      )}

      {/* 关键信息 - 2 列布局 */}
      <div className="grid grid-cols-2 gap-4">
        {/* 决策 */}
        {chat.decisions?.length > 0 && (
          <div className="p-3 bg-green-500/5 rounded-lg border border-green-500/10">
            <div className="flex items-center gap-2 text-xs text-green-400 font-mono mb-2">
              <CheckCircle2 className="w-3 h-3" />
              决策 ({chat.decisions.length})
            </div>
            <ul className="space-y-1">
              {chat.decisions.map((d, i) => (
                <li key={i} className="text-xs text-zinc-400">• {d}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 待办 */}
        {chat.action_items?.length > 0 && (
          <div className="p-3 bg-amber-500/5 rounded-lg border border-amber-500/10">
            <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-2">
              <ListTodo className="w-3 h-3" />
              待办 ({chat.action_items.length})
            </div>
            <ul className="space-y-1">
              {chat.action_items.map((a, i) => (
                <li key={i} className="text-xs text-zinc-400">• {a}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 风险 */}
        {chat.risks?.length > 0 && (
          <div className="p-3 bg-red-500/5 rounded-lg border border-red-500/10">
            <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-2">
              <AlertTriangle className="w-3 h-3" />
              风险 ({chat.risks.length})
            </div>
            <ul className="space-y-1">
              {chat.risks.map((r, i) => (
                <li key={i} className="text-xs text-zinc-400">• {r}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 话题 */}
        {chat.topics?.length > 0 && (
          <div className="p-3 bg-purple-500/5 rounded-lg border border-purple-500/10">
            <div className="text-xs text-purple-400 font-mono mb-2">关键话题</div>
            <div className="flex flex-wrap gap-1">
              {chat.topics.map((t, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-xs rounded"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatSummaryCard;
