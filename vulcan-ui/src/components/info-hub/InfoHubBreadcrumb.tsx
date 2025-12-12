"use client";

import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface InfoHubBreadcrumbProps {
  items: BreadcrumbItem[];
}

export default function InfoHubBreadcrumb({ items }: InfoHubBreadcrumbProps) {
  return (
    <nav className="flex items-center gap-1.5 text-sm mb-4">
      <Link
        href="/info-hub"
        className="flex items-center gap-1 text-zinc-500 hover:text-white transition-colors"
      >
        <Home className="w-3.5 h-3.5" />
        <span>信息中心</span>
      </Link>

      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-1.5">
          <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
          {item.href ? (
            <Link
              href={item.href}
              className="text-zinc-500 hover:text-white transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-zinc-300">{item.label}</span>
          )}
        </div>
      ))}
    </nav>
  );
}
