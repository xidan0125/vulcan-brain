'use client';

import { Suspense } from 'react';
import DailyReportPage from './daily-report/page';

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-screen bg-zinc-950">
      <div className="animate-spin w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full" />
    </div>
  );
}

export default function InfoHubPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <DailyReportPage />
    </Suspense>
  );
}
