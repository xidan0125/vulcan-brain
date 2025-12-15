"use client";

import { useState, useEffect, useMemo } from "react";
import { ChevronDown, ChevronRight, Brain, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import MarkdownRenderer from "@/components/ui/MarkdownRenderer";

// 思考阶段模式匹配
const THINKING_PATTERNS = [
  { pattern: /分析|理解|问题|需求|意图/i, stage: "分析问题", icon: "🔍" },
  { pattern: /知识|概念|定义|原理|理论/i, stage: "检索知识", icon: "📚" },
  { pattern: /推理|因为|所以|如果|那么|考虑/i, stage: "推理论证", icon: "🧠" },
  { pattern: /步骤|方法|方案|实现|代码/i, stage: "规划方案", icon: "📝" },
  { pattern: /总结|答案|结论|最终|综上/i, stage: "组织答案", icon: "✍️" },
  { pattern: /检查|验证|确认|review/i, stage: "验证检查", icon: "✅" },
];

// 默认阶段
const DEFAULT_STAGE = { stage: "深度思考中", icon: "💭" };

interface ThinkingBlockProps {
  content: string;
  isStreaming?: boolean;
  defaultExpanded?: boolean;
}

export default function ThinkingBlock({
  content,
  isStreaming = false,
  defaultExpanded = false
}: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // 根据内容匹配当前思考阶段
  const currentStage = useMemo(() => {
    if (!content) return DEFAULT_STAGE;

    // 取最后 200 个字符来判断当前阶段
    const recentContent = content.slice(-200);

    for (const pattern of THINKING_PATTERNS) {
      if (pattern.pattern.test(recentContent)) {
        return { stage: pattern.stage, icon: pattern.icon };
      }
    }

    return DEFAULT_STAGE;
  }, [content]);

  // 统计思考内容长度
  const thinkingStats = useMemo(() => {
    const charCount = content.length;
    const lineCount = content.split('\n').length;
    return { charCount, lineCount };
  }, [content]);

  // 流式时自动展开
  useEffect(() => {
    if (isStreaming && !isExpanded) {
      // 可选：流式时自动展开
      // setIsExpanded(true);
    }
  }, [isStreaming]);

  if (!content) return null;

  return (
    <div className="mb-3 rounded-lg border border-zinc-700/50 bg-zinc-800/30 overflow-hidden">
      {/* Header - 可点击折叠 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-zinc-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-zinc-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-zinc-400" />
          )}

          <Brain className="w-4 h-4 text-purple-400" />

          <span className="text-sm text-zinc-300">
            {currentStage.icon} {currentStage.stage}
            {isStreaming && (
              <span className="ml-2 inline-flex">
                <span className="animate-pulse">...</span>
              </span>
            )}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-zinc-500">
          {!isStreaming && (
            <span>{thinkingStats.charCount} 字</span>
          )}
          {isStreaming && (
            <Sparkles className="w-3 h-3 text-purple-400 animate-pulse" />
          )}
        </div>
      </button>

      {/* Content - 可折叠 */}
      <div
        className={cn(
          "overflow-hidden transition-all duration-300",
          isExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="px-3 py-2 border-t border-zinc-700/50 max-h-[500px] overflow-y-auto">
          <div className="text-sm text-zinc-400 prose prose-invert prose-sm max-w-none">
            <MarkdownRenderer content={content} />
          </div>
        </div>
      </div>
    </div>
  );
}
