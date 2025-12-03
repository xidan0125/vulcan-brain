"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

// 复制按钮组件
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-400 hover:text-zinc-200 transition-all opacity-0 group-hover:opacity-100"
      title="复制代码"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      className={cn("prose prose-invert prose-sm max-w-none", className)}
      remarkPlugins={[remarkGfm]}
      components={{
        // 代码块
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || "");
          const codeString = String(children).replace(/\n$/, "");

          if (!inline && match) {
            return (
              <div className="relative group my-3">
                <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-800 border-b border-zinc-700 rounded-t-md">
                  <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider">
                    {match[1]}
                  </span>
                </div>
                <div className="relative">
                  <CopyButton text={codeString} />
                  <SyntaxHighlighter
                    style={oneDark}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{
                      margin: 0,
                      borderRadius: "0 0 0.375rem 0.375rem",
                      fontSize: "12px",
                      padding: "12px",
                      background: "#1a1a1a",
                    }}
                    {...props}
                  >
                    {codeString}
                  </SyntaxHighlighter>
                </div>
              </div>
            );
          }

          // 没有语言标记的代码块
          if (!inline) {
            return (
              <div className="relative group my-3">
                <div className="relative">
                  <CopyButton text={codeString} />
                  <pre className="bg-zinc-900 rounded-md p-3 overflow-x-auto">
                    <code className="text-xs text-zinc-300 font-mono">{children}</code>
                  </pre>
                </div>
              </div>
            );
          }

          // 行内代码
          return (
            <code
              className="px-1.5 py-0.5 bg-zinc-800 text-orange-400 text-xs font-mono rounded"
              {...props}
            >
              {children}
            </code>
          );
        },

        // 表格
        table({ children }) {
          return (
            <div className="my-4 overflow-x-auto rounded-md border border-zinc-700">
              <table className="w-full text-sm">{children}</table>
            </div>
          );
        },
        thead({ children }) {
          return <thead className="bg-zinc-800/80 border-b border-zinc-700">{children}</thead>;
        },
        th({ children }) {
          return (
            <th className="px-4 py-2 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">
              {children}
            </th>
          );
        },
        td({ children }) {
          return <td className="px-4 py-2 text-zinc-400 border-t border-zinc-800">{children}</td>;
        },
        tr({ children }) {
          return <tr className="hover:bg-zinc-800/30 transition-colors">{children}</tr>;
        },

        // 引用块
        blockquote({ children }) {
          return (
            <blockquote className="my-3 pl-4 border-l-2 border-orange-500/50 text-zinc-400 italic">
              {children}
            </blockquote>
          );
        },

        // 列表
        ul({ children }) {
          return <ul className="my-2 ml-4 space-y-1 list-disc marker:text-zinc-600">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="my-2 ml-4 space-y-1 list-decimal marker:text-zinc-500">{children}</ol>;
        },
        li({ children }) {
          return <li className="text-zinc-300 pl-1">{children}</li>;
        },

        // 标题
        h1({ children }) {
          return <h1 className="text-xl font-bold text-zinc-100 mt-6 mb-3 pb-2 border-b border-zinc-800">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-lg font-semibold text-zinc-200 mt-5 mb-2">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-base font-medium text-zinc-300 mt-4 mb-2">{children}</h3>;
        },
        h4({ children }) {
          return <h4 className="text-sm font-medium text-zinc-300 mt-3 mb-1">{children}</h4>;
        },

        // 段落
        p({ children }) {
          return <p className="my-2 text-zinc-300 leading-relaxed">{children}</p>;
        },

        // 链接
        a({ children, href }) {
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-orange-400 hover:text-orange-300 underline underline-offset-2 transition-colors"
            >
              {children}
            </a>
          );
        },

        // 粗体
        strong({ children }) {
          return <strong className="font-semibold text-zinc-100">{children}</strong>;
        },

        // 斜体
        em({ children }) {
          return <em className="italic text-zinc-400">{children}</em>;
        },

        // 删除线
        del({ children }) {
          return <del className="text-zinc-500 line-through">{children}</del>;
        },

        // 分隔线
        hr() {
          return <hr className="my-4 border-zinc-800" />;
        },

        // 图片
        img({ src, alt }) {
          return (
            <img
              src={src}
              alt={alt || ""}
              className="max-w-full h-auto rounded-md border border-zinc-800 my-3"
            />
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
