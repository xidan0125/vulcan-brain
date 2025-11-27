"use client";

import AgentChatPageLOD from "@/components/agents/AgentChatPageLOD";
import { TrendingUp } from "lucide-react";

export default function FinancialAgent() {
  return (
    <AgentChatPageLOD
      agentType="financial"
      agentName="财务投资"
      englishName="The Omniscient Analyst"
      icon={<TrendingUp className="w-6 h-6" />}
      color="emerald"
      placeholder="请输入财务分析问题，如：帮我计算一下投资回报率"
    />
  );
}
