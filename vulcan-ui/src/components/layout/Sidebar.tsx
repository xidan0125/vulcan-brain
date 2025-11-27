"use client";

import { Brain, Database, Users, Settings, Home, Cloud, Target, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import Link from "next/link";

interface NavItem {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href: string;
  highlight?: boolean;
  badge?: number;
}

const navItems: NavItem[] = [
  { icon: Home, label: "Home", href: "/" },
  { icon: Cloud, label: "Gemini", href: "/gemini", highlight: true },
  { icon: Target, label: "War Room", href: "/projects", badge: 2 },
  { icon: Brain, label: "Soul", href: "/soul" },
  { icon: Database, label: "Knowledge", href: "/knowledge" },
  { icon: Users, label: "Memory", href: "/memory" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-16 bg-zinc-900/60 backdrop-blur-sm border-r border-white/10 flex flex-col items-center py-4 space-y-4">
      {/* Logo - 更硬朗的方形设计 */}
      <Link href="/" className="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-600 rounded-md flex items-center justify-center shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-shadow">
        <Zap className="w-5 h-5 text-white" />
      </Link>

      {/* Separator - 更细更精致 */}
      <div className="w-6 h-px bg-white/10" />

      {/* Nav Items */}
      <nav className="flex-1 flex flex-col space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));

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
              title={item.label}
            >
              <Icon className="w-4 h-4" />

              {/* Badge 红点 */}
              {item.badge && item.badge > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] bg-rose-500 text-white text-[9px] font-bold rounded-sm flex items-center justify-center px-0.5 font-mono">
                  {item.badge}
                </span>
              )}

              {/* Highlight pulse (无 badge 时显示) */}
              {item.highlight && !item.badge && (
                <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-orange-500 rounded-sm animate-pulse" />
              )}

              {/* Tooltip on hover */}
              <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800/95 border border-white/10 text-zinc-300 text-[10px] font-mono rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none tracking-wider">
                {item.label.toUpperCase()}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom: 简化的版本标识 */}
      <div className="flex flex-col items-center space-y-1">
        <span className="text-[9px] text-zinc-600 font-mono tracking-widest">V3.0</span>
      </div>
    </div>
  );
}
