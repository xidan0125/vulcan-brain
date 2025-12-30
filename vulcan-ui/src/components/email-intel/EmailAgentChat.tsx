"use client";

import { useState, useRef, useEffect } from "react";
import {
  MessageSquare, Send, X, Loader2, Database, Code,
  ChevronDown, ChevronUp, Sparkles, History, Trash2,
  Download, Maximize2
} from "lucide-react";

const API_BASE = "https://api.vsg-brain.com/api/email-intel";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  cypher?: string;
  data?: any[];
  image?: string;
  chartHtml?: string;
  pythonCode?: string;
  timestamp: Date;
}

interface Session {
  session_id: string;
  created_at: string;
  last_message?: string;
}

export default function EmailAgentChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showCypher, setShowCypher] = useState<Record<string, boolean>>({});
  const [showSessions, setShowSessions] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [enlargedImage, setEnlargedImage] = useState<string | null>(null);
  const [enlargedHtml, setEnlargedHtml] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const loadSessions = async () => {
    try {
      const token = localStorage.getItem("vulcan_token");
      const res = await fetch(`${API_BASE}/sessions`, {
        headers: token ? { "Authorization": `Bearer ${token}` } : {}
      });
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (e) {
      console.error("Failed to load sessions:", e);
    }
  };

  const startNewSession = () => {
    setSessionId(null);
    setMessages([]);
    setShowSessions(false);
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: userMessage,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const token = localStorage.getItem("vulcan_token");
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);

      const res = await fetch(`${API_BASE}/agent`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          query: userMessage,
          session_id: sessionId
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!res.ok) throw new Error(`服务器错误 ${res.status}`);

      const data = await res.json();

      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer,
        cypher: data.cypher,
        data: data.data,
        image: data.image,
        chartHtml: data.chart_html,
        pythonCode: data.python_code,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, assistantMsg]);

    } catch (error: any) {
      let errorText = "未知错误";
      if (error.name === "AbortError") {
        errorText = "查询超时，请稍后重试";
      } else if (error.message.includes("Failed to fetch")) {
        errorText = "网络连接失败，请检查网络";
      } else {
        errorText = error.message;
      }
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `查询失败: ${errorText}`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
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

  const toggleCypher = (id: string) => {
    setShowCypher(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const downloadImage = (base64: string) => {
    const link = document.createElement('a');
    link.href = `data:image/png;base64,${base64}`;
    link.download = `chart_${Date.now()}.png`;
    link.click();
  };

  const quickQueries = [
    "有多少订单？",
    "画一个事件类型分布饼图",
    "哪些公司交易最多？",
    "画一个Top10公司交易量柱状图"
  ];

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all ${
          isOpen
            ? "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
            : "bg-gradient-to-r from-orange-500 to-amber-500 text-white hover:from-orange-600 hover:to-amber-600"
        }`}
      >
        {isOpen ? <X className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
      </button>

      {/* 聊天面板 */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 z-50 w-[420px] h-[600px] bg-zinc-900 rounded-2xl border border-zinc-800 shadow-2xl flex flex-col overflow-hidden">
          {/* 头部 */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-white">邮件数据助手</h3>
                <p className="text-xs text-zinc-500">
                  {sessionId ? `会话 ${sessionId.slice(0, 8)}` : "新会话"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => { loadSessions(); setShowSessions(!showSessions); }}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
                title="历史会话"
              >
                <History className="w-4 h-4" />
              </button>
              <button
                onClick={startNewSession}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
                title="新建会话"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 会话列表 */}
          {showSessions && (
            <div className="absolute top-14 left-0 right-0 bg-zinc-900 border-b border-zinc-800 max-h-48 overflow-y-auto z-10">
              {sessions.length === 0 ? (
                <div className="p-4 text-center text-zinc-500 text-sm">暂无历史会话</div>
              ) : (
                sessions.map(s => (
                  <button
                    key={s.session_id}
                    onClick={() => { setSessionId(s.session_id); setShowSessions(false); setMessages([]); }}
                    className="w-full px-4 py-2 text-left hover:bg-zinc-800 transition-colors"
                  >
                    <div className="text-sm text-zinc-300 truncate">{s.last_message || "空会话"}</div>
                    <div className="text-xs text-zinc-500">{s.session_id.slice(0, 8)} · {new Date(s.created_at).toLocaleDateString()}</div>
                  </button>
                ))
              )}
            </div>
          )}

          {/* 消息区域 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center">
                <Database className="w-12 h-12 text-zinc-700 mb-4" />
                <p className="text-zinc-400 text-sm mb-4">向我询问邮件业务数据</p>
                <div className="space-y-2">
                  {quickQueries.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(q)}
                      className="block w-full px-3 py-2 text-xs text-left text-zinc-400 bg-zinc-800/50 hover:bg-zinc-800 rounded-lg transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] ${
                      msg.role === "user"
                        ? "bg-orange-500/20 text-orange-100 border border-orange-500/30"
                        : "bg-zinc-800 text-zinc-200 border border-zinc-700"
                    } rounded-xl px-4 py-3`}>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>

                      {/* 交互式图表 (优先) */}
                      {msg.chartHtml && (
                        <div className="mt-3 rounded-lg overflow-hidden border border-zinc-600 relative group">
                          <iframe
                            srcDoc={msg.chartHtml}
                            className="w-full h-[320px] bg-white"
                            sandbox="allow-scripts"
                            title="交互式图表"
                          />
                          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => setEnlargedHtml(msg.chartHtml!)}
                              className="p-1.5 bg-black/60 hover:bg-black/80 rounded text-white"
                              title="放大查看"
                            >
                              <Maximize2 className="w-4 h-4" />
                            </button>
                          </div>
                          <div className="absolute bottom-2 left-2 px-2 py-0.5 bg-black/50 rounded text-[10px] text-white/70">
                            可交互 · 悬停查看数值
                          </div>
                        </div>
                      )}

                      {/* 静态图片 (备选) */}
                      {!msg.chartHtml && msg.image && (
                        <div className="mt-3 rounded-lg overflow-hidden border border-zinc-600 relative group">
                          <img
                            src={`data:image/png;base64,${msg.image}`}
                            alt="生成的图表"
                            className="w-full bg-white cursor-pointer"
                            onClick={() => setEnlargedImage(msg.image!)}
                          />
                          <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => setEnlargedImage(msg.image!)}
                              className="p-1.5 bg-black/60 hover:bg-black/80 rounded text-white"
                              title="放大"
                            >
                              <Maximize2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => downloadImage(msg.image!)}
                              className="p-1.5 bg-black/60 hover:bg-black/80 rounded text-white"
                              title="下载"
                            >
                              <Download className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Cypher 查询 */}
                      {msg.cypher && (
                        <div className="mt-2 pt-2 border-t border-zinc-700/50">
                          <button
                            onClick={() => toggleCypher(msg.id)}
                            className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"
                          >
                            <Code className="w-3 h-3" />
                            Cypher查询
                            {showCypher[msg.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>
                          {showCypher[msg.id] && (
                            <pre className="mt-2 p-2 bg-zinc-900 rounded text-xs text-cyan-400 overflow-x-auto">
                              {msg.cypher}
                            </pre>
                          )}
                        </div>
                      )}

                      {msg.data && msg.data.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-zinc-700/50">
                          <span className="text-xs text-zinc-500">{msg.data.length} 条数据</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3">
                      <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* 输入区域 */}
          <div className="p-4 border-t border-zinc-800 bg-zinc-900/80 backdrop-blur">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="问我关于邮件数据的问题..."
                className="flex-1 px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-xl text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500/50"
                disabled={isLoading}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="p-2.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:from-orange-600 hover:to-amber-600 transition-all"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 图片放大模态框 */}
      {enlargedImage && (
        <div
          className="fixed inset-0 z-[100] bg-black/90 flex items-center justify-center p-4"
          onClick={() => setEnlargedImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh]">
            <img
              src={`data:image/png;base64,${enlargedImage}`}
              alt="放大的图表"
              className="max-w-full max-h-[85vh] object-contain bg-white rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="absolute top-4 right-4 flex gap-2">
              <button
                onClick={(e) => { e.stopPropagation(); downloadImage(enlargedImage); }}
                className="p-2 bg-white/90 hover:bg-white rounded-lg text-zinc-800 shadow-lg"
                title="下载"
              >
                <Download className="w-5 h-5" />
              </button>
              <button
                onClick={() => setEnlargedImage(null)}
                className="p-2 bg-white/90 hover:bg-white rounded-lg text-zinc-800 shadow-lg"
                title="关闭"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* HTML图表放大模态框 */}
      {enlargedHtml && (
        <div
          className="fixed inset-0 z-[100] bg-black/90 flex items-center justify-center p-4"
          onClick={() => setEnlargedHtml(null)}
        >
          <div className="relative w-[90vw] h-[85vh] bg-white rounded-lg overflow-hidden">
            <iframe
              srcDoc={enlargedHtml}
              className="w-full h-full"
              sandbox="allow-scripts"
              title="放大的交互式图表"
            />
            <button
              onClick={() => setEnlargedHtml(null)}
              className="absolute top-4 right-4 p-2 bg-zinc-800/80 hover:bg-zinc-800 rounded-lg text-white shadow-lg"
              title="关闭"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
