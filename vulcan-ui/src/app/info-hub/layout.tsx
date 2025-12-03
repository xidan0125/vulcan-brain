"use client";
import { usePathname } from "next/navigation";
import Link from "next/link";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Newspaper,
  MessageSquare,
  Mail,
  Users,
  FolderKanban,
  FileCheck,
} from "lucide-react";
interface InfoHubLayoutProps {
  children: React.ReactNode;
}
const navItems = [
  {
    id: "daily-report",
    href: "/info-hub/daily-report",
    icon: Newspaper,
    label: "日报总览",
    description: "五维度汇总",
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
  },
  {
    id: "chat",
    href: "/info-hub/chat",
    icon: MessageSquare,
    label: "聊天分析",
    description: "飞书群聊",
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
  },
  {
    id: "email",
    href: "/info-hub/email",
    icon: Mail,
    label: "邮件分析",
    description: "Microsoft 365",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
  },
  {
    id: "people",
    href: "/info-hub/people",
    icon: Users,
    label: "人员管理",
    description: "员工活跃度",
    color: "text-rose-400",
    bgColor: "bg-rose-500/10",
  },
  {
    id: "projects",
    href: "/info-hub/projects",
    icon: FolderKanban,
    label: "项目管理",
    description: "飞书任务",
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
    status: "coming",
  },
  {
    id: "approval",
    href: "/info-hub/approval",
    icon: FileCheck,
    label: "审批动态",
    description: "飞书审批",
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
  },
];
export default function InfoHubLayout({ children }: InfoHubLayoutProps) {
  const pathname = usePathname();
  const isActive = (href: string) => {
    if (href === "/info-hub/daily-report") {
      return pathname === "/info-hub/daily-report" || pathname.startsWith("/info-hub/daily-report/");
    }
    return pathname === href;
  };
  return (
    <DashboardLayout>
      <div className="flex h-full">
        {/* 二级侧边栏 - 固定展开 */}
        <div className="w-52 flex-shrink-0 border-r border-white/5 bg-zinc-950/50">
          {/* 侧边栏头部 */}
          <div className="h-12 flex items-center px-4 border-b border-white/5">
            <span className="text-xs font-mono text-zinc-400 tracking-wider">
              INFO HUB
            </span>
          </div>
          {/* 导航列表 */}
          <nav className="p-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              const isComing = item.status === "coming";
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                    active
                      ? "bg-orange-500/10 border border-orange-500/20"
                      : isComing
                      ? "opacity-40 cursor-not-allowed hover:opacity-50"
                      : "hover:bg-white/5 border border-transparent"
                  }`}
                  onClick={(e) => isComing && e.preventDefault()}
                >
                  <div
                    className={`w-8 h-8 rounded-md flex items-center justify-center ${
                      active ? "bg-orange-500/20" : item.bgColor
                    }`}
                  >
                    <Icon
                      className={`w-4 h-4 ${active ? "text-orange-400" : item.color}`}
                    />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-sm font-medium ${
                          active ? "text-orange-400" : "text-zinc-300"
                        }`}
                      >
                        {item.label}
                      </span>
                      {isComing && (
                        <span className="text-[8px] text-zinc-600 font-mono bg-zinc-800/50 px-1.5 py-0.5 rounded">
                          SOON
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-zinc-600">{item.description}</span>
                  </div>
                </Link>
              );
            })}
          </nav>
          {/* 底部信息 */}
          <div className="absolute bottom-4 left-0 right-0 px-4">
            <div className="text-[10px] text-zinc-700 font-mono text-center">
              五维度信息中心
            </div>
          </div>
        </div>
        {/* 主内容区 */}
        <div className="flex-1 overflow-auto">{children}</div>
      </div>
    </DashboardLayout>
  );
}
