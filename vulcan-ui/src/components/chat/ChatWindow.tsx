"use client";

import { useState, useRef, useEffect } from "react";
import { Send, StopCircle, Check } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import MessageBubble from "./MessageBubble";

export default function ChatWindow() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const { 
    messages, 
    isLoading, 
    sessionId,
    isSaving,
    lastSavedAt,
    unsavedCount,
    addMessage, 
    setLoading, 
    updateLastMessage,
    initSession,
    autoSave 
  } = useChatStore();

  useEffect(() => {
    if (!sessionId) {
      initSession("vulcan");
    }
  }, [sessionId, initSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

    addMessage({
      role: "user",
      content: userMessage,
    });

    const controller = new AbortController();
    setAbortController(controller);

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, stream: true }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      addMessage({
        role: "assistant",
        content: "",
        isStreaming: true,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      if (!reader) throw new Error("Response body is null");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data:")) {
            try {
              const data = JSON.parse(line.slice(5).trim());

              if (data.type === "token") {
                updateLastMessage((prev) => ({
                  ...prev,
                  content: prev.content + data.content,
                  isStreaming: true,
                }));
              } else if (data.type === "thinking") {
                updateLastMessage((prev) => ({
                  ...prev,
                  thinkingSteps: [
                    ...(prev.thinkingSteps || []),
                    { type: "thinking", content: data.content, timestamp: Date.now() }
                  ],
                  isStreaming: true,
                }));
              } else if (data.type === "code") {
                updateLastMessage((prev) => ({
                  ...prev,
                  thinkingSteps: [
                    ...(prev.thinkingSteps || []),
                    { type: "code", content: data.content, timestamp: Date.now() }
                  ],
                  isStreaming: true,
                }));
              } else if (data.type === "tool_output" || data.type === "tool") {
                updateLastMessage((prev) => ({
                  ...prev,
                  thinkingSteps: [
                    ...(prev.thinkingSteps || []),
                    { type: "tool_output", content: data.content, timestamp: Date.now() }
                  ],
                  isStreaming: true,
                }));
              } else if (data.type === "done") {
                updateLastMessage((prev) => ({ ...prev, isStreaming: false }));
                setTimeout(() => autoSave(), 500);
              }
            } catch (e) {
              console.warn("Failed to parse SSE data:", line, e);
            }
          }
        }
      }

      updateLastMessage((prev) => ({ ...prev, isStreaming: false }));
      setTimeout(() => autoSave(), 500);

    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log("Request aborted");
      } else {
        console.error("Chat stream error:", error);
        addMessage({
          role: "assistant",
          content: `Error: ${error.message}`,
          isStreaming: false,
        });
      }
    } finally {
      setLoading(false);
      setAbortController(null);
    }
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
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-2 border-b text-xs text-muted-foreground">
        <span>Session: {sessionId?.slice(0, 8) || "Loading..."}</span>
        <div className="flex items-center gap-2">
          {isSaving && <span className="animate-pulse">Saving...</span>}
          {lastSavedAt && !isSaving && (
            <span className="flex items-center gap-1 text-green-600">
              <Check className="w-3 h-3" />
              Saved
            </span>
          )}
          {unsavedCount > 0 && !isSaving && (
            <span className="text-yellow-600">{unsavedCount} unsaved</span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4 max-w-md">
              <div className="w-16 h-16 bg-primary/10 rounded-full mx-auto flex items-center justify-center">
                <span className="text-3xl font-bold text-primary">V</span>
              </div>
              <h2 className="text-xl font-semibold">Vulcan Brain</h2>
              <p className="text-muted-foreground text-sm">AI Agent with Auto-Save</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} onFeedback={handleFeedback} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="border-t p-4">
        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type message... (Shift+Enter for newline)"
            rows={1}
            className="flex-1 px-4 py-3 bg-background border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary max-h-32"
            disabled={isLoading}
          />
          {isLoading ? (
            <button onClick={handleStop} className="px-4 py-3 bg-destructive text-white rounded-xl">
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button onClick={handleSend} disabled={!input.trim()} className="px-4 py-3 bg-primary text-white rounded-xl disabled:opacity-50">
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
