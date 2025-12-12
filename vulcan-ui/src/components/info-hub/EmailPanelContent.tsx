"use client";

import { useState, useEffect } from "react";
import { Mail, Calendar, User, Paperclip, Reply } from "lucide-react";

interface EmailDetail {
  email_id: string;
  subject: string;
  from: {
    name?: string;
    address?: string;
  };
  to?: Array<{ name?: string; address?: string }>;
  body?: string;
  body_preview?: string;
  received_at?: string;
  has_attachments?: boolean;
  importance?: string;
}

interface EmailPanelContentProps {
  emailId: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function EmailPanelContent({ emailId }: EmailPanelContentProps) {
  const [email, setEmail] = useState<EmailDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchEmail() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/info-hub/email/${emailId}`);
        if (!res.ok) throw new Error("Failed to fetch email");
        const data = await res.json();
        setEmail(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    if (emailId) {
      fetchEmail();
    }
  }, [emailId]);

  if (loading) {
    return (
      <div className="p-4 space-y-4">
        <div className="animate-pulse space-y-3">
          <div className="h-5 bg-zinc-800 rounded w-3/4" />
          <div className="h-3 bg-zinc-800 rounded w-1/2" />
          <div className="h-3 bg-zinc-800 rounded w-1/3" />
          <div className="h-px bg-zinc-800 my-4" />
          <div className="space-y-2">
            <div className="h-3 bg-zinc-800 rounded w-full" />
            <div className="h-3 bg-zinc-800 rounded w-full" />
            <div className="h-3 bg-zinc-800 rounded w-2/3" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!email) {
    return (
      <div className="p-4 text-center text-zinc-500 text-sm">
        邮件不存在
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 邮件头部 */}
      <div className="p-4 border-b border-zinc-800 space-y-3">
        {/* 主题 */}
        <h3 className="text-base font-medium text-white leading-snug">
          {email.subject || "(无主题)"}
        </h3>

        {/* 发件人 */}
        <div className="flex items-center gap-2 text-sm">
          <div className="w-8 h-8 rounded-full bg-amber-500/10 flex items-center justify-center">
            <span className="text-amber-400 text-xs font-medium">
              {(email.from?.name || email.from?.address || "?")[0].toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-white font-medium truncate">
              {email.from?.name || email.from?.address || "未知发件人"}
            </div>
            {email.from?.name && email.from?.address && (
              <div className="text-xs text-zinc-500 truncate">
                {email.from.address}
              </div>
            )}
          </div>
        </div>

        {/* 元信息 */}
        <div className="flex items-center gap-4 text-xs text-zinc-500">
          {email.received_at && (
            <div className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5" />
              <span>
                {new Date(email.received_at).toLocaleString("zh-CN", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          )}
          {email.has_attachments && (
            <div className="flex items-center gap-1">
              <Paperclip className="w-3.5 h-3.5" />
              <span>附件</span>
            </div>
          )}
          {email.importance === "high" && (
            <span className="px-1.5 py-0.5 bg-red-500/10 text-red-400 rounded text-[10px]">
              重要
            </span>
          )}
        </div>

        {/* 收件人 */}
        {email.to && email.to.length > 0 && (
          <div className="text-xs text-zinc-500">
            <span className="text-zinc-600">收件人：</span>
            {email.to.map((t, i) => (
              <span key={i}>
                {i > 0 && ", "}
                {t.name || t.address}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 邮件正文 */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
          {email.body || email.body_preview || "(无内容)"}
        </div>
      </div>
    </div>
  );
}
