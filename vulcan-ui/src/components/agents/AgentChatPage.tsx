"use client";

import { useState, useRef, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Send, Loader2, Trash2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface AgentPageProps {
  agentType: string;
  agentName: string;
  englishName: string;
  icon: React.ReactNode;
  color: string;
  placeholder: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// 获取认证头
const getAuthHeaders = (): Record<string, string> => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('vulcan_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};


export default function AgentChatPage({
  agentType,
  agentName,
  englishName,
  icon,
  placeholder,
}: AgentPageProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/agents/${agentType}/chat`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ message: userMessage, session_id: sessionId }),
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const data = await response.json();
      setSessionId(data.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "抱歉，发生了错误，请稍后重试。" }]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  return (
    <DashboardLayout>
      <div className="h-full flex flex-col bg-[#09090b]">
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-zinc-800 text-zinc-100">{icon}</div>
            <div>
              <h1 className="text-xl font-bold text-zinc-100">{agentName}</h1>
              <p className="text-sm text-zinc-500">{englishName}</p>
            </div>
          </div>
          <button onClick={clearChat} className="p-2 hover:bg-zinc-800 rounded-lg" title="清空对话">
            <Trash2 className="w-5 h-5 text-zinc-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-zinc-500">
                <div className="p-6 rounded-full bg-zinc-800 mx-auto w-fit mb-4">{icon}</div>
                <p className="text-lg font-medium text-zinc-300 mb-2">开始与{agentName}对话</p>
                <p className="text-sm">{placeholder}</p>
              </div>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user" ? "bg-emerald-600 text-white" : "bg-zinc-800 text-zinc-100"
              }`}>
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-zinc-800 rounded-2xl px-4 py-3">
                <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="p-4 border-t border-zinc-800">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="bg-emerald-600 text-white rounded-xl px-4 py-3 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}
