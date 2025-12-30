'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * 认知中心 - 已废弃，重定向到 /soul
 */
export default function CognitiveCenterPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/soul');
  }, [router]);

  return (
    <div className="h-screen bg-[#050505] flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border border-orange-500/50 border-t-orange-500 rounded-md animate-spin mx-auto mb-4" />
        <p className="text-zinc-600 text-xs font-mono tracking-wider">REDIRECTING...</p>
      </div>
    </div>
  );
}
