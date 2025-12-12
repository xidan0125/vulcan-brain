"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Newspaper,
  Mail,
  MessageSquare,
  FileCheck,
  Users,
  FolderKanban,
  Zap,
} from "lucide-react";

const navItems = [
  { id: "daily", label: "日报", href: "/info-hub", icon: Newspaper, exactMatch: true },
  { id: "email", label: "邮件", href: "/info-hub/email", icon: Mail },
  { id: "chat", label: "群聊", href: "/info-hub/chat", icon: MessageSquare },
  { id: "approval", label: "审批", href: "/info-hub/approval", icon: FileCheck },
  { id: "people", label: "人员", href: "/info-hub/people", icon: Users },
  { id: "projects", label: "项目", href: "/info-hub/projects", icon: FolderKanban },
  { id: "email-intel", label: "邮件情报", href: "/info-hub/email-intel", icon: Zap, highlight: true },
];

export default function InfoHubNav() {
  const pathname = usePathname();

  const isActive = (item: typeof navItems[0]) => {
    if (item.exactMatch) {
      // 日报页：只在 /info-hub 或 /info-hub/daily-report 时激活
      return pathname === "/info-hub" || pathname.startsWith("/info-hub/daily-report");
    }
    return pathname === item.href || pathname.startsWith(item.href + "/");
  };

  return (
    <nav className="flex items-center gap-1 px-4 py-2 border-b border-zinc-800 bg-zinc-950/50 overflow-x-auto">
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = isActive(item);

        return (
          <Link
            key={item.id}
            href={item.href}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
              active
                ? "bg-orange-500/10 text-orange-400 border border-orange-500/20"
                : item.highlight
                ? "text-amber-400 hover:bg-amber-500/10 border border-transparent"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-white border border-transparent"
            }`}
          >
            <Icon className="w-4 h-4" />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
