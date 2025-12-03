"use client";

import { useState, useRef, useEffect } from "react";
import { Globe, Check } from "lucide-react";
import { useLanguage, locales, Locale } from "@/i18n/LanguageContext";
import { cn } from "@/lib/utils";

interface LanguageSwitcherProps {
  variant?: "default" | "compact" | "icon-only";
  className?: string;
}

export default function LanguageSwitcher({
  variant = "default",
  className
}: LanguageSwitcherProps) {
  const { locale, setLocale } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const currentLocale = locales.find(l => l.code === locale);

  const handleSelect = (code: Locale) => {
    console.log(`[LanguageSwitcher] Selected: ${code}`);
    setLocale(code);
    setIsOpen(false);
  };

  // 仅图标模式（用于侧边栏）
  if (variant === "icon-only") {
    return (
      <div ref={dropdownRef} className={cn("relative", className)}>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsOpen(!isOpen);
          }}
          className={cn(
            "w-10 h-10 rounded-md flex items-center justify-center transition-all relative group",
            "hover:bg-white/5 text-zinc-500 hover:text-zinc-300",
            isOpen && "bg-white/5 text-zinc-300"
          )}
          title="语言 / Language"
        >
          <Globe className="w-4 h-4" />
          <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800/95 border border-white/10 text-zinc-300 text-[10px] font-mono rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none tracking-wider">
            {currentLocale?.nativeName || "语言"}
          </span>
        </button>

        {isOpen && (
          <div className="absolute left-full ml-2 bottom-0 bg-zinc-900 border border-white/10 rounded-lg shadow-xl z-[100] overflow-hidden min-w-[140px]">
            {locales.map((loc) => (
              <button
                key={loc.code}
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleSelect(loc.code);
                }}
                className={cn(
                  "w-full px-3 py-2.5 text-left text-sm flex items-center gap-2 transition-colors cursor-pointer",
                  "hover:bg-white/10",
                  locale === loc.code ? "text-orange-400 bg-orange-500/10" : "text-zinc-300"
                )}
              >
                {locale === loc.code && <Check className="w-3 h-3 flex-shrink-0" />}
                <span className={locale !== loc.code ? "ml-5" : ""}>{loc.nativeName}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 紧凑模式
  if (variant === "compact") {
    return (
      <div ref={dropdownRef} className={cn("relative", className)}>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            setIsOpen(!isOpen);
          }}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded-md transition-all",
            "bg-zinc-800/50 border border-zinc-700/50 text-zinc-400 hover:text-zinc-200",
            isOpen && "border-zinc-600"
          )}
        >
          <Globe className="w-3.5 h-3.5" />
          <span className="text-xs font-mono">{locale === "zh-CN" ? "中" : "EN"}</span>
        </button>

        {isOpen && (
          <div className="absolute right-0 mt-1 bg-zinc-900 border border-white/10 rounded-lg shadow-xl z-[100] overflow-hidden min-w-[140px]">
            {locales.map((loc) => (
              <button
                key={loc.code}
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  handleSelect(loc.code);
                }}
                className={cn(
                  "w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors cursor-pointer",
                  "hover:bg-white/10",
                  locale === loc.code ? "text-orange-400" : "text-zinc-300"
                )}
              >
                {locale === loc.code && <Check className="w-3 h-3" />}
                <span className={locale !== loc.code ? "ml-5" : ""}>{loc.nativeName}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 默认模式
  return (
    <div ref={dropdownRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg transition-all w-full",
          "bg-zinc-800/50 border border-zinc-700/50 text-zinc-300 hover:border-zinc-600",
          isOpen && "border-orange-500/30"
        )}
      >
        <Globe className="w-4 h-4 text-zinc-500" />
        <span className="flex-1 text-left text-sm">{currentLocale?.nativeName}</span>
      </button>

      {isOpen && (
        <div className="absolute left-0 right-0 mt-1 bg-zinc-900 border border-white/10 rounded-lg shadow-xl z-[100] overflow-hidden">
          {locales.map((loc) => (
            <button
              key={loc.code}
              type="button"
              onClick={() => handleSelect(loc.code)}
              className={cn(
                "w-full px-3 py-2.5 text-left text-sm flex items-center gap-3 transition-colors cursor-pointer",
                "hover:bg-white/10",
                locale === loc.code ? "text-orange-400 bg-orange-500/5" : "text-zinc-300"
              )}
            >
              {locale === loc.code ? <Check className="w-4 h-4" /> : <div className="w-4 h-4" />}
              <div className="flex-1">
                <div className="font-medium">{loc.nativeName}</div>
                <div className="text-xs text-zinc-500">{loc.name}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
