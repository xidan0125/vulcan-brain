"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import {
  MessageSquare,
  Calendar,
  Search,
  Users,
  ChevronDown,
  Clock,
  RefreshCw,
} from "lucide-react";
import InfoHubBreadcrumb from "@/components/info-hub/InfoHubBreadcrumb";

interface ChatGroup {
  chat_id: string;
  chat_name: string;
  message_count: number;
  last_message_at?: string;
}

interface Message {
  message_id: string;
  sender: {
    id?: string;
    open_id?: string;
    name?: string;
    id_type?: string;
    sender_type?: string;
  };
  content: string;
  content_type?: string;
  timestamp: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ChatHistoryPage() {
  const searchParams = useSearchParams();
  const chatIdParam = searchParams.get("chat_id");

  const [chatGroups, setChatGroups] = useState<ChatGroup[]>([]);
  const [selectedChat, setSelectedChat] = useState<string | null>(chatIdParam);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [dateFilter, setDateFilter] = useState("");

  // 获取群聊列表
  const fetchChatGroups = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/chats`);
      if (res.ok) {
        const data = await res.json();
        setChatGroups(data.chats || []);
      }
    } catch (error) {
      console.error("获取群聊列表失败:", error);
    } finally {
      setLoading(false);
    }
  };

  // 获取消息列表
  const fetchMessages = async (chatId: string) => {
    setLoadingMessages(true);
    try {
      let url = `${API_BASE}/api/info-hub/chat/${chatId}/messages?limit=100`;
      if (dateFilter) {
        url += `&date=${dateFilter}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (error) {
      console.error("获取消息失败:", error);
    } finally {
      setLoadingMessages(false);
    }
  };

  useEffect(() => {
    fetchChatGroups();
  }, []);

  useEffect(() => {
    if (selectedChat) {
      fetchMessages(selectedChat);
    }
  }, [selectedChat, dateFilter]);

  const filteredMessages = messages.filter(
    (m) =>
      m.content?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (m.sender?.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (m.sender?.id || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  // 获取当前选中群聊的名称
  const selectedChatName = chatGroups.find(c => c.chat_id === selectedChat)?.chat_name;

  return (
    <div className="flex flex-col h-full">
      {/* 面包屑 */}
      <div className="px-4 pt-4 border-b border-zinc-800 pb-3">
        <InfoHubBreadcrumb
          items={[
            { label: "群聊分析", href: "/info-hub/chat" },
            ...(selectedChatName ? [{ label: selectedChatName }] : []),
          ]}
        />
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* 群聊列表 */}
        <div className="w-72 border-r border-zinc-800 flex flex-col">
          <div className="p-4 border-b border-zinc-800">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare className="w-5 h-5 text-blue-400" />
              <h2 className="font-semibold text-white">聊天记录</h2>
            </div>
            <p className="text-xs text-zinc-500">选择群聊查看历史消息</p>
          </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="p-3 bg-zinc-900/50 rounded-lg animate-pulse">
                  <div className="h-4 w-32 bg-zinc-800 rounded mb-2" />
                  <div className="h-3 w-20 bg-zinc-800/50 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <div className="p-2">
              {chatGroups.map((chat) => (
                <button
                  key={chat.chat_id}
                  onClick={() => setSelectedChat(chat.chat_id)}
                  className={`w-full p-3 rounded-lg text-left transition-colors mb-1 ${
                    selectedChat === chat.chat_id
                      ? "bg-blue-500/10 border border-blue-500/20"
                      : "hover:bg-zinc-800/50 border border-transparent"
                  }`}
                >
                  <div className="font-medium text-sm text-white truncate">
                    {chat.chat_name}
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500">
                    <span>{chat.message_count} 条消息</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 消息内容 */}
      <div className="flex-1 flex flex-col">
        {/* 工具栏 */}
        <div className="p-4 border-b border-zinc-800 flex items-center gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="搜索消息..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-zinc-500" />
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <button
            onClick={() => selectedChat && fetchMessages(selectedChat)}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 text-zinc-400 ${loadingMessages ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-4">
          {!selectedChat ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500">
              <MessageSquare className="w-12 h-12 mb-4 opacity-50" />
              <p>请选择一个群聊查看消息</p>
            </div>
          ) : loadingMessages ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="w-8 h-8 bg-zinc-800 rounded-full" />
                  <div className="flex-1">
                    <div className="h-4 w-24 bg-zinc-800 rounded mb-2" />
                    <div className="h-16 bg-zinc-800/50 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredMessages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500">
              <MessageSquare className="w-12 h-12 mb-4 opacity-50" />
              <p>暂无消息</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredMessages.map((msg) => (
                <div key={msg.message_id} className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-blue-400 text-xs font-medium">
                      {(msg.sender?.name || msg.sender?.id || "?")[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm text-white">{msg.sender?.name || msg.sender?.id || "未知"}</span>
                      <span className="text-xs text-zinc-600">
                        {new Date(msg.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="p-3 bg-zinc-900/50 rounded-lg text-sm text-zinc-300 break-words">
                      {msg.content}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
