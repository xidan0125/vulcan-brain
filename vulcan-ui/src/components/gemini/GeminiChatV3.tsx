"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Cloud,
  Loader2,
  Sparkles,
  AlertTriangle,
  Trash2,
  Search,
  Code,
  Link as LinkIcon,
  Plus,
  MessageSquare,
  ChevronRight,
  ChevronLeft,
  Brain,
  ExternalLink,
  Paperclip,
  X,
  FileText,
  Image as ImageIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import MarkdownRenderer from "@/components/ui/MarkdownRenderer";
import {
  createSession as apiCreateSession,
  listSessions as apiListSessions,
  getSession as apiGetSession,
  saveMessages as apiSaveMessages,
  deleteSession as apiDeleteSession,
} from "@/services/chatApi";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  groundingMetadata?: {
    searchQueries?: string[];
    webSearchQueries?: { query: string }[];
    groundingChunks?: { web?: { uri: string; title: string } }[];
  };
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
  tools: ToolConfig;
}

interface ToolConfig {
  googleSearch: boolean;
  codeExecution: boolean;
  urlContext: boolean;
}

// 配置
const GEMINI_API_KEY = process.env.NEXT_PUBLIC_GEMINI_API_KEY || "";
const GEMINI_MODEL = "gemini-3-pro-preview";

// Backend storage - no localStorage needed

export default function GeminiChatV3() {
  // Session management
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Chat state
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tool toggles
  const [tools, setTools] = useState<ToolConfig>({
    googleSearch: true,
    codeExecution: false,
    urlContext: false,
  });

  // Thinking mode
  const [thinkingLevel, setThinkingLevel] = useState<"none" | "low" | "medium" | "high">("medium");

  // File uploads
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load sessions from backend
  useEffect(() => {
    const loadSessions = async () => {
      try {
        setIsLoadingSessions(true);
        const data = await apiListSessions("gemini", 50);
        if (data.sessions && data.sessions.length > 0) {
          const localSessions: ChatSession[] = data.sessions.map((s: any) => ({
            id: s.session_id,
            title: s.title || "New Chat",
            messages: [],
            createdAt: new Date(s.created_at).getTime(),
            updatedAt: new Date(s.updated_at).getTime(),
            tools: { googleSearch: true, codeExecution: false, urlContext: false },
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
  }, []);

  // Load full session when switching
  useEffect(() => {
    const loadFullSession = async () => {
      if (!currentSessionId) return;
      const session = sessions.find(s => s.id === currentSessionId);
      if (session && session.messages.length === 0) {
        try {
          const data = await apiGetSession(currentSessionId);
          if (data.messages && data.messages.length > 0) {
            setSessions(prev => prev.map(s => 
              s.id === currentSessionId 
                ? { ...s, messages: data.messages.map((m: any) => ({
                    id: m.timestamp?.toString() || String(Date.now()),
                    role: m.role,
                    content: m.content,
                    timestamp: m.timestamp || Date.now(),
                  }))}
                : s
            ));
          }
        } catch (e) {
          console.error("Failed to load session:", e);
        }
      }
    };
    loadFullSession();
  }, [currentSessionId]);

  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const messages = currentSession?.messages || [];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Create new session - returns the new session ID
  const createNewSession = async (title: string = "New Chat"): Promise<string> => {
    try {
      const data = await apiCreateSession("gemini", title);
      const newSession: ChatSession = {
        id: data.session_id,
        title: title,
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        tools: { ...tools },
      };
      setSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(data.session_id);
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
        tools: { ...tools },
      };
      setSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(newId);
      return newId;
    }
  };

  // Delete session
  const deleteSession = async (sessionId: string) => {
    try {
      await apiDeleteSession(sessionId);
    } catch (e) {
      console.error("Failed to delete session from backend:", e);
    }
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setCurrentSessionId(remaining.length > 0 ? remaining[0].id : null);
    }
  };

  // Update session title based on first message
  const updateSessionTitle = (sessionId: string, firstMessage: string) => {
    const title = firstMessage.slice(0, 30) + (firstMessage.length > 30 ? "..." : "");
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s))
    );
  };

  // Call Gemini API with tools
  const callGeminiAPI = async (userMessage: string, history: Message[]) => {
    const contents = history
      .filter((m) => m.role !== "system")
      .map((m) => ({
        role: m.role === "user" ? "user" : "model",
        parts: [{ text: m.content }],
      }));

    contents.push({
      role: "user",
      parts: [{ text: userMessage }],
    });

    // Build tools array
    const toolsConfig: any[] = [];
    if (tools.googleSearch) {
      toolsConfig.push({ google_search: {} });
    }
    if (tools.codeExecution) {
      toolsConfig.push({ code_execution: {} });
    }

    const requestBody: any = {
      contents,
      generationConfig: {
        temperature: 0.7,
        topK: 40,
        topP: 0.95,
        maxOutputTokens: 8192,
      },
      safetySettings: [
        { category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_NONE" },
        { category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_NONE" },
        { category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_NONE" },
        { category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_NONE" },
      ],
    };

    // Add tools if any enabled
    if (toolsConfig.length > 0) {
      requestBody.tools = toolsConfig;
    }

    // Add thinking config for supported models
    if (thinkingLevel !== "none") {
      requestBody.generationConfig.thinkingConfig = {
        thinkingBudget: thinkingLevel === "low" ? 1024 : thinkingLevel === "medium" ? 8192 : 24576,
      };
    }

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      }
    );

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.error?.message || "Gemini API Error");
    }

    const data = await response.json();
    const candidate = data.candidates?.[0];
    const text = candidate?.content?.parts?.[0]?.text || "No response";
    const groundingMetadata = candidate?.groundingMetadata;

    return { text, groundingMetadata };
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    if (!GEMINI_API_KEY) {
      setError("请配置 GEMINI_API_KEY 环境变量");
      return;
    }

    // Create session if none exists, get the active session ID
    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
      const title = input.trim().slice(0, 30) + (input.trim().length > 30 ? "..." : "");
      activeSessionId = await createNewSession(title);
    }

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
    };

    // Update session with new message
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? { ...s, messages: [...s.messages, userMessage], updatedAt: Date.now() }
          : s
      )
    );

    // Update title if first message
    if (messages.length === 0) {
      updateSessionTitle(activeSessionId, userMessage.content);
    }

    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const { text, groundingMetadata } = await callGeminiAPI(userMessage.content, messages);

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_assistant`,
        role: "assistant",
        content: text,
        timestamp: Date.now(),
        groundingMetadata,
      };

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, messages: [...s.messages, assistantMessage], updatedAt: Date.now() }
            : s
        )
      );

      // Save to backend
      try {
        await apiSaveMessages(activeSessionId, [
          { role: userMessage.role, content: userMessage.content, timestamp: userMessage.timestamp },
          { role: assistantMessage.role, content: assistantMessage.content, timestamp: assistantMessage.timestamp },
        ]);
      } catch (saveErr) {
        console.error("Failed to save messages:", saveErr);
      }
    } catch (err: any) {
      console.error("Gemini error:", err);
      setError(err.message || "调用 Gemini 失败");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearCurrentChat = () => {
    if (currentSessionId) {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId ? { ...s, messages: [], title: "New Chat" } : s
        )
      );
    }
    setError(null);
  };

  // Format relative time
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

  return (
    <div className="h-full flex bg-[#050505]">
      {/* History Sidebar */}
      <div
        className={cn(
          "flex-shrink-0 border-r border-white/10 bg-zinc-900/40 backdrop-blur-sm transition-all duration-300",
          sidebarOpen ? "w-64" : "w-0 overflow-hidden"
        )}
      >
        <div className="h-full flex flex-col">
          {/* Sidebar Header */}
          <div className="p-3 border-b border-white/10">
            <button
              onClick={() => createNewSession()}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-gradient-to-r from-orange-500/20 to-red-500/20 hover:from-orange-500/30 hover:to-red-500/30 border border-orange-500/30 rounded-md text-orange-400 text-xs font-mono tracking-wider transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              NEW CHAT
            </button>
          </div>

          {/* Session List */}
          <div className="flex-1 overflow-y-auto py-2">
            {sessions.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <MessageSquare className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                <p className="text-xs text-zinc-600 font-mono">No conversations yet</p>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => {
                    setCurrentSessionId(session.id);
                    setTools(session.tools);
                  }}
                  className={cn(
                    "group mx-2 mb-1 px-3 py-2.5 rounded-md cursor-pointer transition-all",
                    session.id === currentSessionId
                      ? "bg-orange-500/10 border border-orange-500/20"
                      : "hover:bg-white/5 border border-transparent"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p
                        className={cn(
                          "text-xs font-medium truncate",
                          session.id === currentSessionId ? "text-orange-400" : "text-zinc-400"
                        )}
                      >
                        {session.title}
                      </p>
                      <p className="text-[10px] text-zinc-600 font-mono mt-0.5">
                        {formatTime(session.updatedAt)} · {session.messages.length} msgs
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSession(session.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded transition-all text-zinc-500 hover:text-rose-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Sidebar Footer */}
          <div className="p-3 border-t border-white/10">
            <div className="text-[9px] text-zinc-600 font-mono tracking-wider text-center">
              {sessions.length} CONVERSATIONS
            </div>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex-shrink-0 px-4 py-3 border-b border-white/10 bg-zinc-900/40 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Toggle Sidebar */}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-1.5 hover:bg-white/5 rounded-md transition-colors text-zinc-500 hover:text-zinc-300"
              >
                {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </button>

              <div className="w-8 h-8 bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-white/10 rounded-md flex items-center justify-center">
                <Cloud className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <h1 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
                  Gemini Cloud
                  <Sparkles className="w-3 h-3 text-blue-400" />
                </h1>
                <p className="text-[10px] text-zinc-600 font-mono">{GEMINI_MODEL}</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              {/* Thinking Level Toggle */}
              <div className="flex items-center gap-1 px-2 py-1 bg-zinc-800/50 border border-white/10 rounded-md">
                <Brain className="w-3 h-3 text-purple-400" />
                <select
                  value={thinkingLevel}
                  onChange={(e) => setThinkingLevel(e.target.value as any)}
                  className="bg-transparent text-[10px] text-zinc-400 font-mono focus:outline-none cursor-pointer"
                >
                  <option value="none">OFF</option>
                  <option value="low">LOW</option>
                  <option value="medium">MED</option>
                  <option value="high">HIGH</option>
                </select>
              </div>

              <button
                onClick={clearCurrentChat}
                className="p-1.5 text-zinc-500 hover:text-zinc-300 hover:bg-white/5 rounded-md transition-colors"
                title="清空对话"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Warning Banner */}
        <div className="mx-4 mt-3 px-3 py-2 bg-amber-500/5 border border-amber-500/20 rounded-md flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
          <p className="text-[10px] text-amber-400/80 font-mono">
            CLOUD MODE: Data sent to Google servers. Do not upload sensitive information.
          </p>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-14 h-14 bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/10 rounded-md flex items-center justify-center mb-4">
                <Sparkles className="w-6 h-6 text-blue-400" />
              </div>
              <h2 className="text-base font-medium text-zinc-300 mb-1">Gemini Cloud Assistant</h2>
              <p className="text-xs text-zinc-600 font-mono max-w-sm">
                Google Gemini 2.5 Pro with Search, Code Execution & Deep Thinking
              </p>
              <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-md">
                {[
                  "搜索最新AI新闻",
                  "帮我写个Python脚本",
                  "解释量子计算原理",
                  "分析这段代码的性能",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setInput(prompt)}
                    className="px-3 py-1.5 bg-zinc-800/50 border border-white/10 text-zinc-500 text-[11px] font-mono rounded-md hover:bg-zinc-800 hover:text-zinc-300 hover:border-white/20 transition-all"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[85%] px-4 py-3 rounded-md",
                  message.role === "user"
                    ? "bg-gradient-to-r from-orange-500/20 to-red-500/20 border border-orange-500/20 text-zinc-200"
                    : "bg-zinc-800/50 border border-white/10 text-zinc-300"
                )}
              >
                {message.role === "assistant" ? <MarkdownRenderer content={message.content} /> : <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>}

                {/* Grounding Sources */}
                {message.groundingMetadata?.groundingChunks &&
                  message.groundingMetadata.groundingChunks.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/10">
                      <p className="text-[10px] text-zinc-500 font-mono mb-2 tracking-wider">
                        SOURCES:
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {message.groundingMetadata.groundingChunks
                          .filter((c) => c.web)
                          .slice(0, 5)
                          .map((chunk, idx) => (
                            <a
                              key={idx}
                              href={chunk.web!.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 px-2 py-1 bg-zinc-700/50 border border-white/10 rounded text-[10px] text-zinc-400 hover:text-zinc-200 hover:border-white/20 transition-all"
                            >
                              <ExternalLink className="w-2.5 h-2.5" />
                              {chunk.web!.title?.slice(0, 25) || "Source"}
                            </a>
                          ))}
                      </div>
                    </div>
                  )}

                <span className="text-[10px] text-zinc-600 font-mono mt-2 block">
                  {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-zinc-800/50 border border-white/10 px-4 py-3 rounded-md">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border border-blue-500/50 border-t-blue-500 rounded-sm animate-spin" />
                  <span className="text-xs text-zinc-500 font-mono">
                    {thinkingLevel !== "none" ? "DEEP THINKING..." : "PROCESSING..."}
                  </span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-center">
              <div className="px-4 py-2 bg-rose-500/10 border border-rose-500/30 rounded-md">
                <p className="text-xs text-rose-400 font-mono">ERROR: {error}</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area with Tools */}
        <div className="flex-shrink-0 border-t border-white/10 bg-zinc-900/40">
          {/* Tools Bar - above input */}
          <div className="px-4 pt-3 pb-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {/* File Upload Button */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*,.pdf,.txt,.md,.json,.csv"
                onChange={(e) => {
                  if (e.target.files) {
                    setAttachedFiles(prev => [...prev, ...Array.from(e.target.files!)]);
                  }
                }}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-2 hover:bg-white/5 rounded-md transition-colors text-zinc-500 hover:text-zinc-300"
                title="上传文件"
              >
                <Paperclip className="w-4 h-4" />
              </button>

              <div className="w-px h-4 bg-white/10 mx-1" />

              {/* Tool Toggles */}
              <button
                onClick={() => setTools((t) => ({ ...t, googleSearch: !t.googleSearch }))}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono transition-all",
                  tools.googleSearch
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-zinc-500 hover:text-zinc-400 hover:bg-white/5"
                )}
                title="Google Search"
              >
                <Search className="w-3 h-3" />
                <span className="hidden sm:inline">Search</span>
              </button>
              <button
                onClick={() => setTools((t) => ({ ...t, codeExecution: !t.codeExecution }))}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono transition-all",
                  tools.codeExecution
                    ? "bg-blue-500/10 text-blue-400"
                    : "text-zinc-500 hover:text-zinc-400 hover:bg-white/5"
                )}
                title="Code Execution"
              >
                <Code className="w-3 h-3" />
                <span className="hidden sm:inline">Code</span>
              </button>
              <button
                onClick={() => setTools((t) => ({ ...t, urlContext: !t.urlContext }))}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono transition-all",
                  tools.urlContext
                    ? "bg-amber-500/10 text-amber-400"
                    : "text-zinc-500 hover:text-zinc-400 hover:bg-white/5"
                )}
                title="URL Context"
              >
                <LinkIcon className="w-3 h-3" />
                <span className="hidden sm:inline">URL</span>
              </button>
            </div>

            {/* Active tools indicator */}
            {(tools.googleSearch || tools.codeExecution || tools.urlContext) && (
              <div className="text-[9px] text-zinc-600 font-mono">
                {[
                  tools.googleSearch && "Search",
                  tools.codeExecution && "Code",
                  tools.urlContext && "URL"
                ].filter(Boolean).join(" + ")} enabled
              </div>
            )}
          </div>

          {/* Attached Files Preview */}
          {attachedFiles.length > 0 && (
            <div className="px-4 pb-2 flex flex-wrap gap-2">
              {attachedFiles.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-2 py-1 bg-zinc-800/50 border border-white/10 rounded-md text-xs"
                >
                  {file.type.startsWith("image/") ? (
                    <ImageIcon className="w-3 h-3 text-purple-400" />
                  ) : (
                    <FileText className="w-3 h-3 text-blue-400" />
                  )}
                  <span className="text-zinc-400 max-w-[100px] truncate">{file.name}</span>
                  <button
                    onClick={() => setAttachedFiles(prev => prev.filter((_, i) => i !== idx))}
                    className="text-zinc-500 hover:text-zinc-300"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input Row */}
          <div className="px-4 pb-4 flex gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Send a message... (Shift+Enter for new line)"
              rows={1}
              className="flex-1 px-4 py-3 bg-zinc-800/50 border border-white/10 rounded-md text-sm text-zinc-200
                placeholder:text-zinc-600 resize-none focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20
                transition-all"
              style={{ minHeight: "48px", maxHeight: "120px" }}
            />
            <button
              onClick={handleSend}
              disabled={(!input.trim() && attachedFiles.length === 0) || isLoading}
              className={cn(
                "px-4 py-3 rounded-md font-mono text-xs tracking-wider transition-all flex items-center gap-2",
                (input.trim() || attachedFiles.length > 0) && !isLoading
                  ? "bg-gradient-to-r from-orange-500 to-red-600 text-white hover:from-orange-600 hover:to-red-700 shadow-lg shadow-orange-500/20"
                  : "bg-zinc-800 border border-white/10 text-zinc-600 cursor-not-allowed"
              )}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
