"use client";

import AgentChatPageLOD from "@/components/agents/AgentChatPageLOD";
import { PenTool } from "lucide-react";

export default function GhostwriterAgent() {
  return (
    <AgentChatPageLOD
      agentType="ghostwriter"
      agentName="替身写作"
      englishName="The Ghostwriter"
      icon={<PenTool className="w-6 h-6" />}
      color="purple"
      placeholder="请输入写作需求，如：帮我写一封年会总结邮件"
    />
  );
}
