"use client";

import { FolderKanban, Clock } from "lucide-react";

export default function ProjectsHistoryPage() {
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
          <FolderKanban className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">项目档案</h1>
          <p className="text-sm text-zinc-500">飞书任务项目列表</p>
        </div>
      </div>

      <div className="text-center py-20 bg-zinc-900/50 rounded-xl border border-zinc-800">
        <div className="w-16 h-16 rounded-full bg-purple-500/10 flex items-center justify-center mx-auto mb-4">
          <Clock className="w-8 h-8 text-purple-400" />
        </div>
        <h3 className="text-lg font-medium text-zinc-400 mb-2">功能开发中</h3>
        <p className="text-sm text-zinc-600">项目档案功能即将上线，敬请期待</p>
        <div className="mt-6 inline-flex items-center gap-2 px-4 py-2 bg-purple-500/10 text-purple-400 rounded-lg text-sm">
          <Clock className="w-4 h-4" />
          Coming Soon
        </div>
      </div>
    </div>
  );
}
