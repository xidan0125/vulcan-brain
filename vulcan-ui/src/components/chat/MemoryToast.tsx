"use client";

import { useEffect, useState } from "react";
import { Brain, Sparkles } from "lucide-react";
import Link from "next/link";

interface MemoryToastProps {
  count: number;
  onDismiss: () => void;
}

export default function MemoryToast({ count, onDismiss }: MemoryToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (count === 0) {
      setVisible(false);
      return;
    }

    setVisible(true);
    const timer = setTimeout(() => {
      setVisible(false);
      onDismiss();
    }, 1000);

    return () => clearTimeout(timer);
  }, [count, onDismiss]);

  if (!visible || count === 0) return null;

  return (
    <div className="fixed top-20 right-6 z-50 animate-in slide-in-from-right-5 fade-in duration-300">
      <div className="bg-gradient-to-r from-violet-500/20 via-purple-500/20 to-fuchsia-500/20
                      border border-purple-500/40 rounded-xl px-4 py-3 backdrop-blur-md
                      shadow-lg shadow-purple-500/10 animate-pulse">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Brain className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-medium text-purple-300">
                已提取 {count} 条新记忆
              </span>
              <Sparkles className="w-3 h-3 text-purple-400/60" />
            </div>
            <Link
              href="/memory"
              className="text-xs text-purple-400/70 hover:text-purple-300 transition-colors"
            >
              前往记忆管理查看 →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
