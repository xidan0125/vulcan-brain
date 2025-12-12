"use client";

import { useState, useEffect } from "react";
import { MessageSquare, Calendar, Search, User } from "lucide-react";

interface Message {
  message_id: string;
  sender: {
    open_id?: string;
    name?: string;
    sender_type?: string;
  };
  content: string;
  timestamp: string;
}

interface ChatPanelContentProps {
  chatId: string;
  date?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ChatPanelContent({ chatId, date }: ChatPanelContentProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    async function fetchMessages() {
      setLoading(true);
      setError(null);
      try {
        let url = `${API_BASE}/api/info-hub/chat/${chatId}/messages?limit=50`;
        if (date) {
          url += `&date=${date}`;
        }
        const res = await fetch(url);
        if (!res.ok) throw new Error("Failed to fetch messages");
        const data = await res.json();
        setMessages(data.messages || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    if (chatId) {
      fetchMessages();
    }
  }, [chatId, date]);

  const filteredMessages = messages.filter(
    (m) =>
      m.content?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (m.sender?.name || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="p-4 space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="animate-pulse flex gap-3">
            <div className="w-8 h-8 rounded-full bg-zinc-800" />
            <div className="flex-1 space-y-2">
              <div className="h-3 bg-zinc-800 rounded w-24" />
              <div className="h-4 bg-zinc-800 rounded w-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 搜索框 */}
      <div className="p-3 border-b border-zinc-800">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="搜索消息..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-zinc-900 border border-zinc-800 rounded-md text-white placeholder:text-zinc-600 focus:outline-none focus:border-zinc-700"
          />
        </div>
        <div className="flex items-center gap-2 mt-2 text-xs text-zinc-500">
          <MessageSquare className="w-3.5 h-3.5" />
          <span>{filteredMessages.length} 条消息</span>
          {date && (
            <>
              <Calendar className="w-3.5 h-3.5 ml-2" />
              <span>{date}</span>
            </>
          )}
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {filteredMessages.length === 0 ? (
          <div className="text-center py-8 text-zinc-500 text-sm">
            暂无消息
          </div>
        ) : (
          filteredMessages.map((msg) => (
            <div key={msg.message_id} className="flex gap-2.5">
              <div className="w-7 h-7 rounded-full bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                <span className="text-blue-400 text-xs font-medium">
                  {(msg.sender?.name || "?")[0].toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-medium text-xs text-white">
                    {msg.sender?.name || "未知"}
                  </span>
                  <span className="text-[10px] text-zinc-600">
                    {new Date(msg.timestamp).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="text-sm text-zinc-300 break-words leading-relaxed">
                  {msg.content}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
