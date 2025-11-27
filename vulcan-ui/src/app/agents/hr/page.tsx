"use client";

import AgentChatPageLOD from "@/components/agents/AgentChatPageLOD";
import { Users } from "lucide-react";

export default function HRAgent() {
  return (
    <AgentChatPageLOD
      agentType="hr"
      agentName="HR管理"
      englishName="The HR Guardian"
      icon={<Users className="w-6 h-6" />}
      color="blue"
      placeholder="请输入人力资源问题，如：如何提升团队士气？"
    />
  );
}
