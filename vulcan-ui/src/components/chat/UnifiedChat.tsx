"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Cloud,
  Cpu,
  Loader2,
  Sparkles,
  Trash2,
  Plus,
  MessageSquare,
  ChevronRight,
  ChevronLeft,
  Bot,
  User,
  Search,
  Zap,
  Settings2,
  Terminal,
  Globe
} from "lucide-react";
import { cn } from "@/lib/utils";
import MarkdownRenderer from "@/components/ui/MarkdownRenderer";
import ThinkingBlock from "./ThinkingBlock";
import {
  chatStreamEvents,
  VULCAN_BRAINS,
  getToolDisplayName,
  type ModelType,
  type ChatRequest,
  type StreamEvent
} from "@/services/unifiedChatApi";
import MemoryConfirmCard from "./MemoryConfirmCard";
import {
  confirmMemory,
  rejectMemory,
  editAndConfirmMemory,
  type PendingMemory
} from "@/services/memoryApi";

// --- Types ---

interface ToolCall {
  id: string;
  name: string;
  arguments: string;
  result?: string;
  status: 'calling' | 'done';
}

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  model?: string;
  agentId?: string;
  toolCalls?: ToolCall[];  // 工具调用记录
  thinkingContent?: string;  // 思考过程内容
  isStreaming?: boolean;  // 是否正在流式输出
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
  modelPreference: ModelType;
  agentPreference: string;
  serverSessionId?: string;  // 后端 session ID
}

// --- Component ---

export default function UnifiedChat() {
  // Layout State
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  // Session State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  
  // Chat Configuration State
  const [selectedModel, setSelectedModel] = useState<ModelType>("gemini");
  const [selectedAgentId, setSelectedAgentId] = useState<string>("general");
  
  // Feature Toggles
  const [webSearchEnabled, setWebSearchEnabled] = useState(true); // Gemini only
  const [soulModeEnabled, setSoulModeEnabled] = useState(false); // Qwen only (High Temp)
  
  // Input State
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Memory State
  const [pendingMemories, setPendingMemories] = useState<PendingMemory[]>([]);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // --- Initialization & Session Management ---

  // Load sessions from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("vulcan_chat_sessions");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSessions(parsed);
        if (parsed.length > 0) {
          setCurrentSessionId(parsed[0].id);
          // Restore preferences from last session
          setSelectedModel(parsed[0].modelPreference || "gemini");
          setSelectedAgentId(parsed[0].agentPreference || "general");
        }
      } catch (e) {
        console.error("Failed to parse sessions", e);
      }
    } else {
      createNewSession();
    }
  }, []);

  // Save sessions to localStorage whenever they change
  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem("vulcan_chat_sessions", JSON.stringify(sessions));
    }
  }, [sessions]);

  // Scroll to bottom on new messages
  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const messages = currentSession?.messages || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const createNewSession = () => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: "New Operation",
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      modelPreference: selectedModel,
      agentPreference: selectedAgentId,
    };
    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    return newSession.id;
  };

  const deleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const newSessions = sessions.filter((s) => s.id !== id);
    setSessions(newSessions);
    localStorage.setItem("vulcan_chat_sessions", JSON.stringify(newSessions));
    
    if (currentSessionId === id) {
      setCurrentSessionId(newSessions.length > 0 ? newSessions[0].id : null);
    }
  };

  const updateSessionTitle = (sessionId: string, firstMessage: string) => {
    const title = firstMessage.slice(0, 30) + (firstMessage.length > 30 ? "..." : "");
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s))
    );
  };

  // --- Chat Logic ---

  // Memory confirmation handlers
  const handleConfirmMemory = async (id: string) => {
    await confirmMemory(id);
    setPendingMemories(prev => prev.filter(m => m.id !== id));
  };

  const handleRejectMemory = async (id: string) => {
    await rejectMemory(id);
    setPendingMemories(prev => prev.filter(m => m.id !== id));
  };

  const handleEditMemory = async (id: string, newValue: string) => {
    await editAndConfirmMemory(id, newValue);
    setPendingMemories(prev => prev.filter(m => m.id !== id));
  };

  const handleDismissAllMemories = () => {
    // Reject all pending memories
    pendingMemories.forEach(m => rejectMemory(m.id));
    setPendingMemories([]);
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    // Ensure active session
    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
      activeSessionId = createNewSession();
    }

    const userContent = input.trim();
    setInput("");
    
    // 1. Add User Message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: userContent,
      timestamp: Date.now(),
    };

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            messages: [...s.messages, userMessage],
            updatedAt: Date.now(),
            // Update title if it's the first message
            title: s.messages.length === 0 ? 
              (userContent.slice(0, 30) + (userContent.length > 30 ? "..." : "")) : s.title
          };
        }
        return s;
      })
    );

    setIsLoading(true);

    // 2. Prepare API Request
    const requestPayload: ChatRequest = {
      messages: messages.concat(userMessage).map(m => ({ role: m.role, content: m.content })),
      model: selectedModel,
      stream: true,
      enable_search: selectedModel === 'gemini' ? webSearchEnabled : undefined,
      enable_tools: selectedModel === 'qwen3' ? true : undefined,  // Qwen3 自动启用工具
      agent_id: selectedModel === 'qwen3' ? selectedAgentId : undefined,
      temperature: soulModeEnabled && selectedModel === 'qwen3' ? 0.9 : 0.7,
      session_id: currentSession?.serverSessionId || undefined
    };

    // 3. Stream Response
    try {
      let fullResponse = "";
      let fullThinking = "";  // 思考内容累积
      const assistantMsgId = (Date.now() + 1).toString();
      
      // Create placeholder for assistant message
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? {
                ...s,
                messages: [
                  ...s.messages,
                  {
                    id: assistantMsgId,
                    role: "assistant",
                    content: "",
                    timestamp: Date.now(),
                    model: selectedModel,
                    agentId: selectedModel === 'qwen3' ? selectedAgentId : undefined,
                    thinkingContent: "",
                    isStreaming: true
                  },
                ],
              }
            : s
        )
      );

      const stream = chatStreamEvents(requestPayload);
      let currentToolCalls: ToolCall[] = [];

      for await (const event of stream) {
        // 保存后端 session ID
        if (event.type === 'session' && event.session_id) {
          setSessions((prev) =>
            prev.map((s) =>
              s.id === activeSessionId
                ? { ...s, serverSessionId: event.session_id }
                : s
            )
          );
          continue;
        }
        // 处理思考内容 (thinking event from backend)
        if (event.type === 'thinking' && event.content) {
          fullThinking += event.content;
        } else if (event.type === 'token' && event.content) {
          fullResponse += event.content;
        } else if (event.type === 'tool_call') {
          // 工具调用开始
          currentToolCalls.push({
            id: event.id || '',
            name: event.name || '',
            arguments: event.arguments || '',
            status: 'calling'
          });
        } else if (event.type === 'tool_result') {
          // 工具调用完成
          const idx = currentToolCalls.findIndex(t => t.id === event.id);
          if (idx !== -1) {
            currentToolCalls[idx] = {
              ...currentToolCalls[idx],
              result: event.result,
              status: 'done'
            };
            
            // 检测 remember 工具返回的 pending_memory
            if (currentToolCalls[idx].name === 'remember' && event.result) {
              try {
                const parsed = JSON.parse(event.result);
                if (parsed.type === 'pending_memory' && parsed.pending_id) {
                  setPendingMemories(prev => [...prev, {
                    id: parsed.pending_id,
                    key: parsed.key,
                    value: parsed.value,
                    category: parsed.category || 'fact',
                    confidence: 0.95
                  }]);
                }
              } catch (e) {
                // 不是 JSON，忽略
              }
            }
          }
        } else if (event.type === 'error') {
          throw new Error(event.content || 'Stream error');
        }

        // 更新消息
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === activeSessionId) {
              const updatedMessages = [...s.messages];
              const lastMsgIndex = updatedMessages.findIndex(m => m.id === assistantMsgId);
              if (lastMsgIndex !== -1) {
                updatedMessages[lastMsgIndex] = {
                  ...updatedMessages[lastMsgIndex],
                  content: fullResponse,
                  toolCalls: currentToolCalls.length > 0 ? [...currentToolCalls] : undefined,
                  thinkingContent: fullThinking || undefined,
                  isStreaming: true
                };
              }
              return { ...s, messages: updatedMessages };
            }
            return s;
          })
        );
      }

      // 流式结束后，设置 isStreaming 为 false
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSessionId) {
            const updatedMessages = [...s.messages];
            const lastMsgIndex = updatedMessages.findIndex(m => m.id === assistantMsgId);
            if (lastMsgIndex !== -1) {
              updatedMessages[lastMsgIndex] = {
                ...updatedMessages[lastMsgIndex],
                isStreaming: false
              };
            }
            return { ...s, messages: updatedMessages };
          }
          return s;
        })
      );

    } catch (error: any) {
      console.error("Chat error:", error);
      // Add error message
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? {
                ...s,
                messages: [
                  ...s.messages,
                  {
                    id: Date.now().toString(),
                    role: "system",
                    content: `Error: ${error.message || "Connection failed"}`,
                    timestamp: Date.now(),
                  },
                ],
              }
            : s
        )
      );
    } finally {
      setIsLoading(false);
      // Focus input after generation
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // 检测中文输入法组合状态，避免在输入拼音时误触发发送
    if (e.nativeEvent.isComposing || e.keyCode === 229) {
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // --- Render Helpers ---

  const getBrainName = (id: string) => VULCAN_BRAINS.find(b => b.id === id)?.name || "Vulcan 本地大脑";
  const getBrainIcon = (id: string) => VULCAN_BRAINS.find(b => b.id === id)?.icon || "🧠";

  return (
    <div className="h-full flex bg-[#050505] text-zinc-300 font-sans overflow-hidden">
      
      {/* --- Sidebar --- */}
      <div
        className={cn(
          "flex-shrink-0 border-r border-zinc-800/50 bg-zinc-900/40 backdrop-blur-sm transition-all duration-300 flex flex-col",
          sidebarOpen ? "w-72" : "w-0 overflow-hidden"
        )}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-zinc-800/50 flex items-center justify-between">
          <div className="flex items-center gap-2 text-zinc-100 font-medium">
            <Terminal className="w-5 h-5 text-red-500" />
            <span>VULCAN BRAIN</span>
          </div>
          <button 
            onClick={createNewSession}
            className="p-1.5 hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-white transition-colors"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => setCurrentSessionId(session.id)}
              className={cn(
                "group flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all border border-transparent",
                currentSessionId === session.id
                  ? "bg-red-500/10 border-red-500/20 text-red-100"
                  : "hover:bg-zinc-800/50 text-zinc-400 hover:text-zinc-200"
              )}
            >
              <MessageSquare className={cn("w-4 h-4", currentSessionId === session.id ? "text-red-500" : "text-zinc-600")} />
              <div className="flex-1 overflow-hidden">
                <div className="truncate text-sm font-medium">{session.title}</div>
                <div className="text-xs text-zinc-600 font-mono mt-0.5">
                  {new Date(session.updatedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </div>
              </div>
              <button
                onClick={(e) => deleteSession(e, session.id)}
                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/20 hover:text-red-400 rounded transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* --- Main Chat Area --- */}
      <div className="flex-1 flex flex-col relative min-w-0">
        
        {/* Header / Toolbar */}
        <div className="h-16 border-b border-zinc-800/50 bg-zinc-900/30 backdrop-blur flex items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 transition-colors"
            >
              {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
            </button>

            {/* Model Switcher */}
            <div className="flex bg-zinc-900 p-1 rounded-lg border border-zinc-800">
              {/* Gemini Cloud Tab */}
              <button
                onClick={() => setSelectedModel("gemini")}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                  selectedModel === "gemini"
                    ? "bg-zinc-800 text-white shadow-sm"
                    : "text-zinc-500 hover:text-zinc-300"
                )}
              >
                <Cloud className="w-4 h-4" />
                Gemini Cloud
              </button>

              {/* Vulcan 本地大脑 Tab + Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setSelectedModel("qwen3")}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                    selectedModel === "qwen3"
                      ? "bg-zinc-800 text-white shadow-sm"
                      : "text-zinc-500 hover:text-zinc-300"
                  )}
                >
                  <span>{getBrainIcon(selectedAgentId)}</span>
                  <span>{getBrainName(selectedAgentId)}</span>
                  <ChevronRight className={cn("w-3 h-3 transition-transform", selectedModel === "qwen3" && "rotate-90")} />
                </button>
                {selectedModel === "qwen3" && (
                  <select
                    value={selectedAgentId}
                    onChange={(e) => setSelectedAgentId(e.target.value)}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  >
                    {VULCAN_BRAINS.map((brain) => (
                      <option key={brain.id} value={brain.id}>
                        {brain.icon} {brain.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          </div>

          {/* Status Indicator */}
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full animate-pulse", isLoading ? "bg-red-500" : "bg-zinc-700")} />
            <span className="text-xs font-mono text-zinc-500 uppercase">
              {isLoading ? "Processing" : "Ready"}
            </span>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar bg-[#050505]">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-zinc-900/50 border border-zinc-800 flex items-center justify-center">
                <Terminal className="w-8 h-8 text-zinc-500" />
              </div>
              <div className="text-center">
                <h3 className="text-zinc-300 font-medium">Vulcan Unified Interface</h3>
                <p className="text-sm text-zinc-500 mt-1">Select a model and start operations.</p>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="p-3 bg-zinc-900/30 border border-zinc-800/50 rounded-lg text-xs text-zinc-400">
                  <span className="text-red-400 font-mono block mb-1">GEMINI PRO</span>
                  Cloud-based reasoning with web access.
                </div>
                <div className="p-3 bg-zinc-900/30 border border-zinc-800/50 rounded-lg text-xs text-zinc-400">
                  <span className="text-red-400 font-mono block mb-1">QWEN3 LOCAL</span>
                  Private, specialized agent execution.
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={msg.id}
                className={cn(
                  "flex gap-4 max-w-4xl mx-auto",
                  msg.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {/* Assistant Avatar */}
                {msg.role !== "user" && (
                  <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center flex-shrink-0 mt-1">
                    {msg.role === "system" ? (
                      <Settings2 className="w-4 h-4 text-red-500" />
                    ) : msg.model === "qwen3" ? (
                      <span className="text-lg leading-none">{getBrainIcon(msg.agentId || "general")}</span>
                    ) : (
                      <Sparkles className="w-4 h-4 text-blue-400" />
                    )}
                  </div>
                )}

                {/* Message Bubble */}
                <div
                  className={cn(
                    "relative px-5 py-3.5 rounded-2xl max-w-[85%] shadow-sm",
                    msg.role === "user"
                      ? "bg-red-500/10 border border-red-500/20 text-zinc-100 rounded-tr-sm"
                      : msg.role === "system"
                      ? "bg-red-900/20 border border-red-500/50 text-red-200 font-mono text-xs w-full"
                      : "bg-zinc-900/60 border border-zinc-800/60 text-zinc-300 rounded-tl-sm"
                  )}
                >
                  {/* Metadata Header for Assistant */}
                  {msg.role === "assistant" && (
                    <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/5">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                        {msg.model === "qwen3" ? getBrainName(msg.agentId || "general") : "GEMINI PRO"}
                      </span>
                    </div>
                  )}

                  {/* Tool Calls Display */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="mb-3 space-y-2">
                      {msg.toolCalls.map((tool) => (
                        <div
                          key={tool.id}
                          className="bg-zinc-950/50 border border-zinc-800/50 rounded-lg p-2.5 text-xs"
                        >
                          <div className="flex items-center gap-2 text-zinc-400">
                            {tool.status === 'calling' ? (
                              <Loader2 className="w-3 h-3 animate-spin text-yellow-500" />
                            ) : (
                              <Search className="w-3 h-3 text-green-500" />
                            )}
                            <span className="font-medium">{getToolDisplayName(tool.name)}</span>
                            <span className="text-zinc-600">
                              {tool.status === 'calling' ? '调用中...' : '完成'}
                            </span>
                          </div>
                          {tool.arguments && (
                            <div className="mt-1.5 text-zinc-500 font-mono text-[10px] truncate">
                              参数: {tool.arguments}
                            </div>
                          )}
                          {tool.result && (
                            <details className="mt-2">
                              <summary className="text-zinc-500 cursor-pointer hover:text-zinc-400 text-[10px]">
                                查看结果
                              </summary>
                              <div className="mt-1.5 p-2 bg-zinc-900/50 rounded text-zinc-400 max-h-32 overflow-y-auto custom-scrollbar whitespace-pre-wrap">
                                {tool.result.slice(0, 500)}{tool.result.length > 500 ? '...' : ''}
                              </div>
                            </details>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 思考过程折叠块 */}
                  {msg.thinkingContent && (
                    <ThinkingBlock
                      content={msg.thinkingContent}
                      isStreaming={msg.isStreaming}
                      defaultExpanded={false}
                    />
                  )}

                  <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-800">
                    <MarkdownRenderer content={msg.content} />
                  </div>
                  
                  {/* Timestamp Footer */}
                  <div className={cn(
                    "text-[10px] mt-2 font-mono opacity-50",
                    msg.role === "user" ? "text-red-200 text-right" : "text-zinc-500"
                  )}>
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                </div>

                {/* User Avatar */}
                {msg.role === "user" && (
                  <div className="w-8 h-8 rounded-lg bg-red-500/20 border border-red-500/30 flex items-center justify-center flex-shrink-0 mt-1">
                    <User className="w-4 h-4 text-red-400" />
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
          
          {/* Memory Confirmation Card */}
          <MemoryConfirmCard
            memories={pendingMemories}
            onConfirm={handleConfirmMemory}
            onReject={handleRejectMemory}
            onEdit={handleEditMemory}
            onDismissAll={handleDismissAllMemories}
          />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-zinc-950/80 backdrop-blur border-t border-zinc-800/50">
          <div className="max-w-4xl mx-auto space-y-3">
            
            {/* Input Controls */}
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-4">
                {selectedModel === "gemini" ? (
                  <button
                    onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                    className={cn(
                      "flex items-center gap-1.5 text-xs font-medium transition-colors px-2 py-1 rounded",
                      webSearchEnabled ? "text-blue-400 bg-blue-400/10" : "text-zinc-500 hover:text-zinc-300"
                    )}
                  >
                    <Globe className="w-3.5 h-3.5" />
                    Web Search
                  </button>
                ) : (
                  <button
                    onClick={() => setSoulModeEnabled(!soulModeEnabled)}
                    className={cn(
                      "flex items-center gap-1.5 text-xs font-medium transition-colors px-2 py-1 rounded",
                      soulModeEnabled ? "text-purple-400 bg-purple-400/10" : "text-zinc-500 hover:text-zinc-300"
                    )}
                  >
                    <Zap className="w-3.5 h-3.5" />
                    Soul Mode
                  </button>
                )}
              </div>
              <span className="text-[10px] font-mono text-zinc-600">
                {input.length} chars
              </span>
            </div>

            {/* Text Input */}
            <div className="relative flex items-end gap-2 bg-zinc-900 border border-zinc-800 rounded-xl p-2 focus-within:border-zinc-700 focus-within:ring-1 focus-within:ring-zinc-700 transition-all shadow-lg">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedModel === "gemini"
                    ? "Ask Gemini anything (Web enabled)..."
                    : `向 ${getBrainName(selectedAgentId)} 提问...`
                }
                className="w-full bg-transparent border-none focus:ring-0 resize-none min-h-[44px] max-h-32 py-2.5 px-2 text-sm text-zinc-200 placeholder:text-zinc-600 custom-scrollbar"
                rows={1}
                style={{ height: "auto" }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = "auto";
                  target.style.height = `${Math.min(target.scrollHeight, 128)}px`;
                }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className={cn(
                  "p-2.5 rounded-lg mb-0.5 transition-all duration-200 flex-shrink-0",
                  input.trim() && !isLoading
                    ? "bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-900/20"
                    : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                )}
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
            
            <div className="text-center">
              <p className="text-[10px] text-zinc-600">
                Vulcan AI can make mistakes. Verify critical industrial data.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}