"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Cloud, Loader2, Sparkles, AlertTriangle, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

// 配置 - 可以改成环境变量或后端代理
const GEMINI_API_KEY = process.env.NEXT_PUBLIC_GEMINI_API_KEY || "";
const GEMINI_MODEL = "gemini-3-pro-preview";

export default function GeminiChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const callGeminiAPI = async (userMessage: string, history: Message[]) => {
    // 构建对话历史
    const contents = history
      .filter((m) => m.role !== "system")
      .map((m) => ({
        role: m.role === "user" ? "user" : "model",
        parts: [{ text: m.content }],
      }));

    // 添加当前消息
    contents.push({
      role: "user",
      parts: [{ text: userMessage }],
    });

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
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
        }),
      }
    );

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.error?.message || "Gemini API Error");
    }

    const data = await response.json();
    return data.candidates?.[0]?.content?.parts?.[0]?.text || "No response";
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    if (!GEMINI_API_KEY) {
      setError("请配置 GEMINI_API_KEY 环境变量");
      return;
    }

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await callGeminiAPI(userMessage.content, messages);

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_assistant`,
        role: "assistant",
        content: response,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
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

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="h-full flex flex-col bg-[#09090b]">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <Cloud className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
                Gemini Cloud
                <Sparkles className="w-4 h-4 text-blue-400" />
              </h1>
              <p className="text-xs text-zinc-500">Google Gemini 3 Pro</p>
            </div>
          </div>

          {/* Clear Button */}
          <button
            onClick={clearChat}
            className="p-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded-lg transition-colors"
            title="清空对话"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* Warning Banner */}
        <div className="mt-3 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
          <p className="text-xs text-amber-400">
            ⚠️ 云端模式：数据将发送至 Google 服务器，请勿上传敏感信息
          </p>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mb-4">
              <Sparkles className="w-8 h-8 text-blue-400" />
            </div>
            <h2 className="text-lg font-medium text-zinc-300 mb-2">Gemini 云端助手</h2>
            <p className="text-sm text-zinc-500 max-w-md">
              连接 Google Gemini 3 Pro，适合创意写作、复杂推理、通用知识问答
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {["帮我写一首诗", "解释量子计算", "分析这段代码"].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => setInput(prompt)}
                  className="px-3 py-1.5 bg-zinc-800 text-zinc-400 text-xs rounded-full hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
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
            className={cn(
              "flex",
              message.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[80%] px-4 py-3 rounded-2xl",
                message.role === "user"
                  ? "bg-blue-600 text-white rounded-br-md"
                  : "bg-zinc-800 text-zinc-100 rounded-bl-md"
              )}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              <span className="text-[10px] opacity-50 mt-1 block">
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
            <div className="bg-zinc-800 px-4 py-3 rounded-2xl rounded-bl-md">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                <span className="text-sm text-zinc-400">Gemini 思考中...</span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div className="px-4 py-2 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400">❌ {error}</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 p-4 border-t border-zinc-800">
        <div className="flex gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Shift+Enter 换行)"
            rows={1}
            className="flex-1 px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-sm text-zinc-100
              placeholder:text-zinc-500 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50
              focus:border-blue-500/50 transition-all"
            style={{ minHeight: "48px", maxHeight: "120px" }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className={cn(
              "px-4 py-3 rounded-xl font-medium text-sm transition-all flex items-center gap-2",
              input.trim() && !isLoading
                ? "bg-blue-600 text-white hover:bg-blue-500"
                : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
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
  );
}
