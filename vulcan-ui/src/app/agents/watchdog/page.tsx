"use client";

import AgentChatPageLOD from "@/components/agents/AgentChatPageLOD";
import { Bell } from "lucide-react";

export default function WatchdogAgent() {
  return (
    <AgentChatPageLOD
      agentType="watchdog"
      agentName="业务雷达"
      englishName="The Watchdog"
      icon={<Bell className="w-6 h-6" />}
      color="orange"
      placeholder="请输入业务监控问题，如：本周销售有异常吗？"
    />
  );
}
