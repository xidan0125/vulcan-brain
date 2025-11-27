"use client";

import { useState, useRef, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Send, Loader2, Trash2, Zap, Bot } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolOutput?: string;  // 工具执行输出
}

interface AgentPageProps {
  agentType: string;
  agentName: string;
  englishName: string;
  icon: React.ReactNode;
  color: string;
  placeholder: string;
}

// LOD API 地址 (使用本地 Kernel)
const LOD_API_BASE = "http://192.168.31.8:8001";

export default function AgentChatPageLOD({
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
  const [streamingContent, setStreamingContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);
    setStreamingContent("");

    try {
      // 使用 SSE 流式端点
      const response = await fetch(`${LOD_API_BASE}/api/agents/${agentType}/chat/lod/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, session_id: sessionId }),
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";
      let toolOutput = "";

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "token") {
                fullContent += data.content;
                setStreamingContent(fullContent);
              } else if (data.type === "tool") {
                toolOutput = data.content;
              } else if (data.type === "done") {
                // 流结束
              }
            } catch {}
          }
        }
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: fullContent, toolOutput: toolOutput || undefined },
      ]);
      setStreamingContent("");

    } catch (error) {
      console.error("LOD Chat error:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "抱歉，LOD Kernel 连接失败，请稍后重试。" },
      ]);
      setStreamingContent("");
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
    setStreamingContent("");
  };

  return (
    <DashboardLayout>
      <div className="h-full flex flex-col bg-[#09090b]">
        {/* Header with LOD badge */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-zinc-800 text-zinc-100">{icon}</div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-zinc-100">{agentName}</h1>
                <span className="px-2 py-0.5 text-xs font-medium bg-emerald-600/20 text-emerald-400 rounded-full flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  LOD
                </span>
              </div>
              <p className="text-sm text-zinc-500">{englishName} · 动态工具加载</p>
            </div>
          </div>
          <button onClick={clearChat} className="p-2 hover:bg-zinc-800 rounded-lg" title="清空对话">
            <Trash2 className="w-5 h-5 text-zinc-500" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !streamingContent && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-zinc-500">
                <div className="p-6 rounded-full bg-zinc-800 mx-auto w-fit mb-4">{icon}</div>
                <p className="text-lg font-medium text-zinc-300 mb-2">开始与{agentName}对话</p>
                <p className="text-sm">{placeholder}</p>
                <p className="text-xs text-emerald-500 mt-2">✨ 已启用 LOD 动态工具加载</p>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user" ? "bg-emerald-600 text-white" : "bg-zinc-800 text-zinc-100"
              }`}>
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                {msg.toolOutput && (
                  <div className="mt-2 p-2 bg-zinc-900 rounded-lg text-xs font-mono text-emerald-400">
                    <div className="flex items-center gap-1 text-zinc-500 mb-1">
                      <Bot className="w-3 h-3" />
                      <span>工具执行结果</span>
                    </div>
                    <pre className="overflow-x-auto">{msg.toolOutput}</pre>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Streaming content */}
          {streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-[80%] bg-zinc-800 rounded-2xl px-4 py-3 text-zinc-100">
                <p className="whitespace-pre-wrap text-sm">{streamingContent}</p>
                <span className="inline-block w-2 h-4 bg-emerald-400 animate-pulse ml-1" />
              </div>
            </div>
          )}

          {isLoading && !streamingContent && (
            <div className="flex justify-start">
              <div className="bg-zinc-800 rounded-2xl px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
                <span className="text-sm text-zinc-400">LOD Kernel 处理中...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
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
