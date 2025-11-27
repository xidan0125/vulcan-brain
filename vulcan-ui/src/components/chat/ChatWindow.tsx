"use client";

import { useState, useRef, useEffect } from "react";
import { Send, StopCircle } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import MessageBubble from "./MessageBubble";

export default function ChatWindow() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const { messages, isLoading, addMessage, setLoading, updateLastMessage } = useChatStore();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);

    // Add user message
    addMessage({
      role: "user",
      content: userMessage,
    });

    // ========== 真实 SSE 集成开始 ==========
    const controller = new AbortController();
    setAbortController(controller);

    try {
      const response = await fetch('http://100.79.150.62:8001/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          stream: true,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // 创建 AI 消息占位
      const aiMessageId = addMessage({
        role: "assistant",
        content: "",
        isStreaming: true,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      if (!reader) {
        throw new Error('Response body is null');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              
              if (data.type === 'token') {
                // 流式追加 token
                updateLastMessage((prev) => ({
                  ...prev,
                  content: prev.content + data.content,
                  isStreaming: true,
                }));
              } else if (data.type === 'tool_output') {
                // 工具执行结果
                updateLastMessage((prev) => ({
                  ...prev,
                  content: prev.content + "\n\n```\n" + data.content + "\n```\n\n",
                }));
              } else if (data.type === 'done') {
                // 结束流式
                updateLastMessage((prev) => ({
                  ...prev,
                  isStreaming: false,
                }));
              }
            } catch (e) {
              console.warn('Failed to parse SSE data:', line, e);
            }
          } else if (line.startsWith('event:')) {
            // 处理 event 行（如果需要）
            console.log('Event:', line.slice(6).trim());
          }
        }
      }

      // 流结束
      updateLastMessage((prev) => ({
        ...prev,
        isStreaming: false,
      }));

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Request aborted by user');
      } else {
        console.error('Chat stream error:', error);
        addMessage({
          role: "assistant",
          content: `❌ 错误：${error.message}\n\n请检查后端 API 服务是否正常运行。`,
          isStreaming: false,
        });
      }
    } finally {
      setLoading(false);
      setAbortController(null);
    }
    // ========== 真实 SSE 集成结束 ==========
  };

  const handleStop = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFeedback = (messageId: string, feedback: "positive" | "negative") => {
    console.log(`Feedback for message ${messageId}: ${feedback}`);
    // TODO: Send feedback to backend API
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4 max-w-md">
              <div className="w-16 h-16 bg-primary/10 rounded-full mx-auto flex items-center justify-center">
                <span className="text-3xl font-bold text-primary">V</span>
              </div>
              <h2 className="text-xl font-semibold">Vulcan Brain Operations Center</h2>
              <p className="text-muted-foreground text-sm">
                高性能 AI Agent 对话系统 · 双 RTX 5090 · 72GB VRAM
              </p>
              <div className="flex gap-2 justify-center">
                <div className="px-3 py-1.5 bg-accent rounded-lg text-xs">
                  流式对话
                </div>
                <div className="px-3 py-1.5 bg-accent rounded-lg text-xs">
                  代码执行
                </div>
                <div className="px-3 py-1.5 bg-accent rounded-lg text-xs">
                  工具调用
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onFeedback={handleFeedback}
              />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t p-4">
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息... (Shift+Enter 换行)"
              rows={1}
              className="w-full px-4 py-3 bg-background border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary max-h-32 overflow-y-auto"
              disabled={isLoading}
            />
          </div>
          {isLoading ? (
            <button
              onClick={handleStop}
              className="px-4 py-3 bg-destructive text-destructive-foreground rounded-xl hover:bg-destructive/90 transition-colors flex items-center gap-2"
            >
              <StopCircle className="w-4 h-4" />
              停止
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="px-4 py-3 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
