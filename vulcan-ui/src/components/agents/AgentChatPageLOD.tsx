"use client";

import { useState, useRef, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Send, Loader2, Trash2, Zap, Brain, Search, Terminal, ChevronDown, ChevronRight, Plus, MessageSquare, ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import MarkdownRenderer from "@/components/ui/MarkdownRenderer";
import {
  createSession as apiCreateSession,
  listSessions as apiListSessions,
  getSession as apiGetSession,
  saveMessages as apiSaveMessages,
  deleteSession as apiDeleteSession,
} from "@/services/chatApi";

interface ThinkingStep {
  type: 'thinking' | 'code' | 'tool_output';
  content: string;
  label: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp?: number;
  thinkingSteps?: ThinkingStep[];
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

interface AgentPageProps {
  agentType: string;
  agentName: string;
  englishName: string;
  icon: React.ReactNode;
  color: string;
  placeholder: string;
}

function extractCodeLabel(code: string): string {
  if (code.includes('web_search')) {
    const match = code.match(/web_search\s*\(\s*(?:query\s*=\s*)?["']([^"']+)["']/);
    if (match) return `搜索: ${match[1].slice(0, 30)}${match[1].length > 30 ? '...' : ''}`;
    return '正在搜索...';
  }
  if (code.includes('remember_info')) return '正在记忆信息...';
  if (code.includes('recall_info')) return '正在回忆信息...';
  if (code.includes('search_knowledge')) return '正在查询知识库...';
  return '正在执行代码...';
}

function extractOutputLabel(output: string): string {
  if (output.includes('搜索') && output.includes('结果')) {
    const lines = output.split('\n').filter(l => l.trim());
    const resultCount = lines.filter(l => /^\d+\./.test(l.trim())).length;
    return `找到 ${resultCount} 条结果`;
  }
  if (output.length > 100) {
    return `执行完成 (${output.length} 字符)`;
  }
  return '执行完成';
}

function removeCodeBlocks(content: string): string {
  return content.replace(/```python[\s\S]*?```/g, '').trim();
}

const LOD_API_BASE = "";
// 获取认证头
const getAuthHeaders = (): Record<string, string> => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('vulcan_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};


export default function AgentChatPageLOD({
  agentType,
  agentName,
  englishName,
  icon,
  placeholder,
}: AgentPageProps) {
  // Session management
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);

  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingSteps, setStreamingSteps] = useState<ThinkingStep[]>([]);
  const [currentStatus, setCurrentStatus] = useState<string>("");
  const [showThinking, setShowThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load sessions from backend
  useEffect(() => {
    const loadSessions = async () => {
      try {
        setIsLoadingSessions(true);
        const data = await apiListSessions(`agent_${agentType}`, 50);
        if (data.sessions && data.sessions.length > 0) {
          const localSessions: ChatSession[] = data.sessions.map((s: any) => ({
            id: s.session_id,
            title: s.title || "New Chat",
            messages: [],
            createdAt: new Date(s.created_at).getTime(),
            updatedAt: new Date(s.updated_at).getTime(),
          }));
          setSessions(localSessions);
          setCurrentSessionId(localSessions[0].id);
        }
      } catch (e) {
        console.error("Failed to load sessions:", e);
      } finally {
        setIsLoadingSessions(false);
      }
    };
    loadSessions();
  }, [agentType]);

  // Load full session when switching
  useEffect(() => {
    const loadFullSession = async () => {
      if (!currentSessionId) {
        setMessages([]);
        return;
      }
      const session = sessions.find(s => s.id === currentSessionId);
      if (session && session.messages.length > 0) {
        setMessages(session.messages);
        return;
      }
      try {
        const data = await apiGetSession(currentSessionId);
        if (data.messages && data.messages.length > 0) {
          const loadedMessages = data.messages.map((m: any) => ({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp || Date.now(),
          }));
          setMessages(loadedMessages);
          setSessions(prev => prev.map(s =>
            s.id === currentSessionId ? { ...s, messages: loadedMessages } : s
          ));
        } else {
          setMessages([]);
        }
      } catch (e) {
        console.error("Failed to load session:", e);
        setMessages([]);
      }
    };
    loadFullSession();
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, streamingSteps, currentStatus]);

  const createNewSession = async (title: string = "New Chat"): Promise<string> => {
    try {
      const data = await apiCreateSession(`agent_${agentType}`, title);
      const newSession: ChatSession = {
        id: data.session_id,
        title: title,
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      setSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(data.session_id);
      setMessages([]);
      return data.session_id;
    } catch (e) {
      console.error("Failed to create session:", e);
      const newId = "local_" + String(Date.now());
      const newSession: ChatSession = {
        id: newId,
        title: title,
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      setSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(newId);
      setMessages([]);
      return newId;
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      await apiDeleteSession(sessionId);
    } catch (e) {
      console.error("Failed to delete session:", e);
    }
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      const remaining = sessions.filter((s) => s.id !== sessionId);
      if (remaining.length > 0) {
        setCurrentSessionId(remaining[0].id);
      } else {
        setCurrentSessionId(null);
        setMessages([]);
      }
    }
  };

  const formatTime = (timestamp: number) => {
    const diff = Date.now() - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (minutes < 1) return "刚刚";
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    return `${days}天前`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    let activeSessionId = currentSessionId;

    if (!activeSessionId) {
      const title = userMessage.slice(0, 30) + (userMessage.length > 30 ? "..." : "");
      activeSessionId = await createNewSession(title);
    }

    const userMsg: Message = { role: "user", content: userMessage, timestamp: Date.now() };
    setInput("");
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setStreamingContent("");
    setStreamingSteps([]);
    setCurrentStatus("正在思考...");

    try {
      const response = await fetch(`${LOD_API_BASE}/api/agents/${agentType}/chat/lod/stream`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ message: userMessage, session_id: activeSessionId }),
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";
      let thinkingSteps: ThinkingStep[] = [];

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
                setStreamingContent(removeCodeBlocks(fullContent));
              } else if (data.type === "code") {
                const label = extractCodeLabel(data.content);
                setCurrentStatus(label);
                thinkingSteps = [...thinkingSteps, { type: 'code', content: data.content, label }];
                setStreamingSteps([...thinkingSteps]);
              } else if (data.type === "tool_output") {
                const label = extractOutputLabel(data.content);
                setCurrentStatus(label);
                thinkingSteps = [...thinkingSteps, { type: 'tool_output', content: data.content, label }];
                setStreamingSteps([...thinkingSteps]);
                setTimeout(() => setCurrentStatus("正在生成回答..."), 500);
              } else if (data.type === "done") {
                setCurrentStatus("");
              }
            } catch {}
          }
        }
      }

      const cleanContent = removeCodeBlocks(fullContent);
      const assistantMsg: Message = {
        role: "assistant",
        content: cleanContent,
        timestamp: Date.now(),
        thinkingSteps: thinkingSteps.length > 0 ? thinkingSteps : undefined
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // Update session in local state
      setSessions(prev => prev.map(s =>
        s.id === activeSessionId
          ? { ...s, messages: [...s.messages, userMsg, assistantMsg], updatedAt: Date.now() }
          : s
      ));

      // Save to backend
      try {
        await apiSaveMessages(activeSessionId!, [
          { role: userMsg.role, content: userMsg.content, timestamp: userMsg.timestamp },
          { role: assistantMsg.role, content: assistantMsg.content, timestamp: assistantMsg.timestamp },
        ]);
      } catch (saveErr) {
        console.error("Failed to save messages:", saveErr);
      }

      setStreamingContent("");
      setStreamingSteps([]);
      setCurrentStatus("");

    } catch (error) {
      console.error("LOD Chat error:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "抱歉，LOD Kernel 连接失败，请稍后重试。" }]);
      setStreamingContent("");
      setCurrentStatus("");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="h-full flex bg-[#09090b]">
        {/* History Sidebar */}
        <div className={cn(
          "flex-shrink-0 border-r border-zinc-800 bg-zinc-900/40 transition-all duration-300",
          sidebarOpen ? "w-64" : "w-0 overflow-hidden"
        )}>
          <div className="h-full flex flex-col">
            <div className="p-3 border-b border-zinc-800">
              <button
                onClick={() => createNewSession()}
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-600/30 rounded-md text-emerald-400 text-xs font-mono tracking-wider transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                NEW CHAT
              </button>
            </div>
            <div className="flex-1 overflow-y-auto py-2">
              {isLoadingSessions ? (
                <div className="px-4 py-8 text-center">
                  <Loader2 className="w-6 h-6 text-zinc-600 mx-auto animate-spin" />
                </div>
              ) : sessions.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <MessageSquare className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="text-xs text-zinc-600 font-mono">No conversations yet</p>
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => setCurrentSessionId(session.id)}
                    className={cn(
                      "group mx-2 mb-1 px-3 py-2.5 rounded-md cursor-pointer transition-all",
                      session.id === currentSessionId
                        ? "bg-emerald-600/10 border border-emerald-600/20"
                        : "hover:bg-zinc-800 border border-transparent"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className={cn(
                          "text-xs font-medium truncate",
                          session.id === currentSessionId ? "text-emerald-400" : "text-zinc-400"
                        )}>
                          {session.title}
                        </p>
                        <p className="text-[10px] text-zinc-600 font-mono mt-0.5">
                          {formatTime(session.updatedAt)}
                        </p>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-zinc-700 rounded transition-all text-zinc-500 hover:text-rose-400"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="p-3 border-t border-zinc-800">
              <div className="text-[9px] text-zinc-600 font-mono tracking-wider text-center">
                {sessions.length} CONVERSATIONS
              </div>
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-zinc-800">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-1.5 hover:bg-zinc-800 rounded-md transition-colors text-zinc-500 hover:text-zinc-300"
              >
                {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </button>
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
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && !streamingContent && !isLoading && (
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
                  {msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
                    <div className="mb-3">
                      <button
                        onClick={() => setShowThinking(!showThinking)}
                        className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                      >
                        {showThinking ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        <Brain className="w-3 h-3" />
                        <span>思考过程 ({msg.thinkingSteps.length} 步)</span>
                      </button>
                      {showThinking && (
                        <div className="mt-2 p-2 bg-zinc-900/50 rounded-lg space-y-1">
                          {msg.thinkingSteps.map((step, stepIdx) => (
                            <div key={stepIdx} className="flex items-center gap-2 text-xs text-zinc-400">
                              {step.type === 'code' ? <Search className="w-3 h-3 text-blue-400" /> : <Terminal className="w-3 h-3 text-green-400" />}
                              <span>{step.label}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {msg.role === "assistant" ? <MarkdownRenderer content={msg.content} /> : <p className="whitespace-pre-wrap text-sm">{msg.content}</p>}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="max-w-[80%] bg-zinc-800 rounded-2xl px-4 py-3 text-zinc-100">
                  {(currentStatus || streamingSteps.length > 0) && (
                    <div className="mb-3 p-2 bg-zinc-900/50 rounded-lg">
                      {streamingSteps.map((step, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
                          {step.type === 'code' ? <Search className="w-3 h-3 text-blue-400" /> : <Terminal className="w-3 h-3 text-green-400" />}
                          <span>{step.label}</span>
                          {idx === streamingSteps.length - 1 && !streamingContent && <Loader2 className="w-3 h-3 animate-spin text-emerald-400" />}
                        </div>
                      ))}
                      {currentStatus && streamingSteps.length === 0 && (
                        <div className="flex items-center gap-2 text-xs text-zinc-400">
                          <Brain className="w-3 h-3 text-purple-400" />
                          <span>{currentStatus}</span>
                          <Loader2 className="w-3 h-3 animate-spin text-emerald-400" />
                        </div>
                      )}
                    </div>
                  )}
                  {streamingContent ? (
                    <>
                      <MarkdownRenderer content={streamingContent} />
                      <span className="inline-block w-2 h-4 bg-emerald-400 animate-pulse ml-1" />
                    </>
                  ) : (
                    !currentStatus && streamingSteps.length === 0 && (
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
                        <span className="text-sm text-zinc-400">正在连接...</span>
                      </div>
                    )
                  )}
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
      </div>
    </DashboardLayout>
  );
}
