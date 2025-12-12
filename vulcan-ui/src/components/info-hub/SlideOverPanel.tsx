"use client";

import { useEffect, useCallback } from "react";
import { X, ExternalLink } from "lucide-react";
import Link from "next/link";

interface SlideOverPanelProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  width?: "sm" | "md" | "lg";
  externalLink?: string;
  children: React.ReactNode;
}

const widthClasses = {
  sm: "w-80",
  md: "w-96",
  lg: "w-[480px]",
};

export default function SlideOverPanel({
  open,
  onClose,
  title,
  subtitle,
  width = "md",
  externalLink,
  children,
}: SlideOverPanelProps) {
  // ESC 键关闭
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    },
    [open, onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // 禁止背景滚动
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
      />

      {/* 面板容器 */}
      <div className="absolute inset-y-0 right-0 flex">
        <div
          className={`${widthClasses[width]} relative flex flex-col bg-zinc-950 border-l border-zinc-800 shadow-2xl transform transition-transform duration-300 ease-out`}
          style={{
            animation: "slideIn 0.3s ease-out",
          }}
        >
          {/* 头部 */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
            <div className="flex-1 min-w-0">
              <h2 className="text-sm font-medium text-white truncate">
                {title}
              </h2>
              {subtitle && (
                <p className="text-xs text-zinc-500 truncate mt-0.5">
                  {subtitle}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1 ml-3">
              {externalLink && (
                <Link
                  href={externalLink}
                  className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                  title="在新页面打开"
                >
                  <ExternalLink className="w-4 h-4" />
                </Link>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 内容区 */}
          <div className="flex-1 overflow-y-auto">{children}</div>
        </div>
      </div>

      <style jsx>{`
        @keyframes slideIn {
          from {
            transform: translateX(100%);
          }
          to {
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
