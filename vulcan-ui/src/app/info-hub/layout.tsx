"use client";

import DashboardLayout from "@/components/layout/DashboardLayout";
import InfoHubNav from "@/components/info-hub/InfoHubNav";

interface InfoHubLayoutProps {
  children: React.ReactNode;
}

export default function InfoHubLayout({ children }: InfoHubLayoutProps) {
  return (
    <DashboardLayout>
      <div className="flex flex-col h-full">
        {/* 顶部导航 */}
        <InfoHubNav />

        {/* 主内容区 */}
        <div className="flex-1 overflow-auto">{children}</div>
      </div>
    </DashboardLayout>
  );
}
