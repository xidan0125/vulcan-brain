"use client";

import { Brain, Users, Settings, Home, Cloud, MessageSquare, Target, Zap, Activity, LogOut, Presentation, Newspaper, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation, LanguageSwitcher } from "@/i18n";

interface NavItem {
  icon: React.ComponentType<{ className?: string }>;
  labelKey: string;  // i18n key
  href: string;
  highlight?: boolean;
  badge?: number;
  mobileOnly?: boolean;
  desktopOnly?: boolean;
}

// 获取阻塞任务数量
async function fetchBlockedCount(): Promise<number> {
  try {
    const res = await fetch("/api/pm/tasks");
    if (!res.ok) return 0;
    const data = await res.json();
    const tasks = data.tasks || [];
    return tasks.filter((t: any) => t.status === "blocked").length;
  } catch {
    return 0;
  }
}

export default function Sidebar() {
  const pathname = usePathname();
  const [blockedCount, setBlockedCount] = useState(0);
  const { user, logout } = useAuth();
  const { t } = useTranslation();

  useEffect(() => {
    fetchBlockedCount().then(setBlockedCount);
    const interval = setInterval(() => {
      fetchBlockedCount().then(setBlockedCount);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // 所有导航项 - 使用 i18n keys
  const allNavItems: NavItem[] = [
    { icon: FileText, labelKey: "nav.wecomReport", href: "/wecom-report", highlight: true },
    { icon: MessageSquare, labelKey: "nav.chat", href: "/chat" },
    { icon: Target, labelKey: "nav.projects", href: "/projects", badge: blockedCount },
    { icon: Brain, labelKey: "nav.soul", href: "/soul" },
    { icon: Users, labelKey: "nav.memory", href: "/memory", desktopOnly: true },
  ];

  // 移动端只显示4个核心页面
  const mobileNavItems = allNavItems.filter(item => !item.desktopOnly);

  // 桌面端显示全部
  const desktopNavItems = allNavItems.filter(item => !item.mobileOnly);

  const NavIcon = ({ item, isMobile = false }: { item: NavItem; isMobile?: boolean }) => {
    const Icon = item.icon;
    const label = t(item.labelKey);
    const isActive = pathname === item.href ||
      (item.href !== "/" && pathname.startsWith(item.href));

    if (isMobile) {
      // 移动端样式
      return (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            "flex flex-col items-center justify-center py-2 px-4 rounded-lg transition-all relative",
            isActive
              ? "text-orange-400"
              : "text-zinc-500 active:text-zinc-300",
            item.highlight && !isActive && "text-amber-500"
          )}
        >
          <div className="relative">
            <Icon className="w-5 h-5" />
            {/* Badge */}
            {item.badge && item.badge > 0 ? (
              <span className="absolute -top-1 -right-2 min-w-[16px] h-[16px] bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
                {item.badge}
              </span>
            ) : null}
          </div>
          <span className={cn(
            "text-[10px] mt-1 font-medium",
            isActive ? "text-orange-400" : "text-zinc-600"
          )}>
            {label}
          </span>
        </Link>
      );
    }

    // 桌面端样式 (保持原来的)
    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          "w-10 h-10 rounded-md flex items-center justify-center transition-all relative group",
          "hover:bg-white/5 text-zinc-500 hover:text-zinc-300",
          isActive && "bg-orange-500/10 text-orange-400 border border-orange-500/20",
          item.highlight && !isActive && "text-amber-500 hover:text-amber-400"
        )}
        title={label}
      >
        <Icon className="w-4 h-4" />

        {/* Badge - 只有阻塞数 > 0 才显示 */}
        {item.badge && item.badge > 0 ? (
          <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] bg-rose-500 text-white text-[9px] font-bold rounded-sm flex items-center justify-center px-0.5 font-mono">
            {item.badge}
          </span>
        ) : null}

        {/* Highlight pulse */}
        {item.highlight && (!item.badge || item.badge === 0) ? (
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-orange-500 rounded-sm animate-pulse" />
        ) : null}

        {/* Tooltip */}
        <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800/95 border border-white/10 text-zinc-300 text-[10px] font-mono rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none tracking-wider">
          {label.toUpperCase()}
        </span>
      </Link>
    );
  };

  return (
    <>
      {/* ===== 桌面端侧边栏 (md以上显示) ===== */}
      <div className="hidden md:flex w-16 bg-zinc-900/60 backdrop-blur-sm border-r border-white/10 flex-col items-center py-4 space-y-4">
        <Link href="/" className="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-600 rounded-md flex items-center justify-center shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-shadow">
          <Zap className="w-5 h-5 text-white" />
        </Link>

        <div className="w-6 h-px bg-white/10" />

        <nav className="flex-1 flex flex-col space-y-2">
          {desktopNavItems.map((item) => (
            <NavIcon key={item.href} item={item} isMobile={false} />
          ))}
        </nav>

        {/* 底部：语言切换 + 用户信息 + 登出 */}
        <div className="flex flex-col items-center space-y-2">
          {/* 语言切换 */}
          <LanguageSwitcher variant="icon-only" />

          {user && (
            <div className="w-10 h-10 rounded-md bg-zinc-800/50 flex items-center justify-center text-zinc-400 text-xs font-mono border border-zinc-700/50 group relative">
              {user.display_name?.[0] || user.username?.[0] || 'U'}
              <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800/95 border border-white/10 text-zinc-300 text-[10px] font-mono rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none">
                {user.display_name || user.username}
              </span>
            </div>
          )}

          <button
            onClick={logout}
            className="w-10 h-10 rounded-md flex items-center justify-center transition-all relative group hover:bg-red-500/10 text-zinc-500 hover:text-red-400"
            title={t("nav.logout")}
          >
            <LogOut className="w-4 h-4" />
            <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800/95 border border-white/10 text-zinc-300 text-[10px] font-mono rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none tracking-wider">
              {t("nav.logout").toUpperCase()}
            </span>
          </button>

          {/* PPT 演示入口 */}
          <a
            href="/presentation/"
            target="_blank"
            rel="noopener noreferrer"
            className="w-10 h-10 rounded-md flex items-center justify-center transition-all relative group hover:bg-purple-500/10 text-zinc-500 hover:text-purple-400"
            title={t("nav.presentation")}
          >
            <Presentation className="w-4 h-4" />
            <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800/95 border border-white/10 text-zinc-300 text-[10px] font-mono rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none tracking-wider">
              PPT
            </span>
          </a>

          <div className="w-6 h-px bg-white/10" />
          <span className="text-[9px] text-zinc-600 font-mono tracking-widest">V3.0</span>
        </div>
      </div>

      {/* ===== 移动端底部导航栏 (md以下显示) ===== */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-zinc-900/95 backdrop-blur-md border-t border-white/10 safe-area-bottom">
        <nav className="flex items-center justify-around px-2 py-1">
          {mobileNavItems.map((item) => (
            <NavIcon key={item.href} item={item} isMobile={true} />
          ))}
          {/* 移动端登出按钮 */}
          <button
            onClick={logout}
            className="flex flex-col items-center justify-center py-2 px-4 rounded-lg transition-all text-zinc-500 active:text-red-400"
          >
            <LogOut className="w-5 h-5" />
            <span className="text-[10px] mt-1 font-medium text-zinc-600">{t("auth.logout")}</span>
          </button>
        </nav>
      </div>
    </>
  );
}
