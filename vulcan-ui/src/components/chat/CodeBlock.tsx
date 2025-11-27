"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";

interface CodeBlockProps {
  code: string;
  language?: string;
}

export default function CodeBlock({ code, language = "python" }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-2">
      {/* Header */}
      <div className="flex items-center justify-between bg-slate-800 px-4 py-2 rounded-t-lg">
        <span className="text-xs font-mono text-muted-foreground uppercase">
          {language}
        </span>
        <button
          onClick={handleCopy}
          className="p-1.5 hover:bg-slate-700 rounded transition-colors"
          title="Copy code"
        >
          {copied ? (
            <Check className="w-4 h-4 text-emerald-500" />
          ) : (
            <Copy className="w-4 h-4 text-muted-foreground" />
          )}
        </button>
      </div>

      {/* Code Content */}
      <pre className="bg-slate-900 p-4 rounded-b-lg overflow-x-auto">
        <code className="text-sm font-mono text-foreground">
          {code}
        </code>
      </pre>
    </div>
  );
}
