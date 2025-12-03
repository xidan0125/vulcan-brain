"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, User, Cpu, ChevronDown, ChevronRight, Brain, Code, Terminal } from "lucide-react";
import { Message, ThinkingStep } from "@/store/useChatStore";
import CodeBlock from "./CodeBlock";

interface MessageBubbleProps {
  message: Message;
  onFeedback?: (messageId: string, feedback: "positive" | "negative") => void;
}

export default function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const [showThinking, setShowThinking] = useState(false);

  const hasThinkingSteps = message.thinkingSteps && message.thinkingSteps.length > 0;

  // 渲染思考过程步骤
  const renderThinkingStep = (step: ThinkingStep, index: number) => {
    const icons = {
      thinking: <Brain className="w-3 h-3 text-purple-400" />,
      code: <Code className="w-3 h-3 text-blue-400" />,
      tool_output: <Terminal className="w-3 h-3 text-green-400" />,
    };
    const labels = {
      thinking: "思考中",
      code: "执行代码",
      tool_output: "工具输出",
    };

    return (
      <div key={index} className="border-l-2 border-border pl-3 py-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
          {icons[step.type]}
          <span>{labels[step.type]}</span>
        </div>
        <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap overflow-x-auto max-h-32 overflow-y-auto">
          {step.content.length > 500 ? step.content.slice(0, 500) + "..." : step.content}
        </pre>
      </div>
    );
  };

  // Parse code blocks from content
  const renderContent = () => {
    const parts = message.content.split(/(```[\s\S]*?```)/g);

    return parts.map((part, index) => {
      // Check if it's a code block
      if (part.startsWith("```") && part.endsWith("```")) {
        const lines = part.slice(3, -3).split("\n");
        const language = lines[0].trim() || "python";
        const code = lines.slice(1).join("\n");
        return <CodeBlock key={index} code={code} language={language} />;
      }

      // Regular text
      return (
        <p key={index} className="whitespace-pre-wrap">
          {part}
        </p>
      );
    });
  };

  if (isSystem) {
    return (
      <div className="flex justify-center py-2">
        <div className="bg-accent/50 px-4 py-2 rounded-lg text-xs text-muted-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"} mb-6`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isUser
            ? "bg-primary/10 text-primary"
            : "bg-secondary/10 text-secondary"
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Cpu className="w-4 h-4" />}
      </div>

      {/* Message Content */}
      <div className={`flex-1 max-w-3xl ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block text-left ${
            isUser
              ? "bg-primary/10 text-foreground"
              : "bg-card text-foreground"
          } px-4 py-3 rounded-lg`}
        >
          {/* 思考过程折叠区（流式时自动展开） */}
          {hasThinkingSteps && (
            <div className="mb-3">
              <button
                onClick={() => setShowThinking(!showThinking)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {showThinking || message.isStreaming ? (
                  <ChevronDown className="w-3 h-3" />
                ) : (
                  <ChevronRight className="w-3 h-3" />
                )}
                <Brain className="w-3 h-3" />
                <span>
                  {message.isStreaming ? "正在思考..." : `思考过程 (${message.thinkingSteps?.length} 步)`}
                </span>
                {message.isStreaming && (
                  <div className="flex space-x-1 ml-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse delay-75" />
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse delay-150" />
                  </div>
                )}
              </button>
              {(showThinking || message.isStreaming) && (
                <div className="mt-2 p-2 bg-background/50 rounded-lg space-y-2 max-h-64 overflow-y-auto">
                  {message.thinkingSteps?.map((step, idx) => renderThinkingStep(step, idx))}
                </div>
              )}
            </div>
          )}

          {/* 流式加载指示器（没有思考步骤时显示） */}
          {message.isStreaming && !hasThinkingSteps && (
            <div className="flex items-center gap-2 mb-2">
              <div className="flex space-x-1">
                <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                <div className="w-2 h-2 rounded-full bg-primary animate-pulse delay-75" />
                <div className="w-2 h-2 rounded-full bg-primary animate-pulse delay-150" />
              </div>
              <span className="text-xs text-muted-foreground">生成中...</span>
            </div>
          )}

          <div className="text-sm">{renderContent()}</div>

          {/* Tool Output */}
          {message.toolOutput && (
            <div className="mt-3 p-3 bg-background rounded-lg border border-border">
              <div className="text-xs font-semibold text-muted-foreground mb-1">
                Tool Output
              </div>
              <pre className="text-xs font-mono text-foreground overflow-x-auto">
                {message.toolOutput}
              </pre>
            </div>
          )}
        </div>

        {/* Feedback Buttons (Assistant only) */}
        {!isUser && onFeedback && (
          <div className="flex gap-2 mt-2 ml-1">
            <button
              onClick={() => onFeedback(message.id, "positive")}
              className="p-1 hover:bg-accent rounded transition-colors"
              title="Good response"
            >
              <ThumbsUp className="w-3.5 h-3.5 text-muted-foreground hover:text-emerald-500" />
            </button>
            <button
              onClick={() => onFeedback(message.id, "negative")}
              className="p-1 hover:bg-accent rounded transition-colors"
              title="Bad response"
            >
              <ThumbsDown className="w-3.5 h-3.5 text-muted-foreground hover:text-red-500" />
            </button>
          </div>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs text-muted-foreground mt-1 ${
            isUser ? "text-right mr-1" : "ml-1"
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}
