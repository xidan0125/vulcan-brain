"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function InfoHubPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/info-hub/daily-report");
  }, [router]);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-zinc-500">跳转中...</div>
    </div>
  );
}
