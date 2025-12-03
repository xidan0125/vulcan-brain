"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

// 语言类型
export type Locale = "zh-CN" | "en-US";

// 语言配置
export const locales: { code: Locale; name: string; nativeName: string }[] = [
  { code: "zh-CN", name: "Chinese (Simplified)", nativeName: "简体中文" },
  { code: "en-US", name: "English (US)", nativeName: "English" },
];

// 默认语言 - 强制中文
const DEFAULT_LOCALE: Locale = "zh-CN";
const STORAGE_KEY = "vulcan_language";

// 类型定义
type TranslationValue = string | TranslationObject;
interface TranslationObject {
  [key: string]: TranslationValue;
}
type Translations = TranslationObject;

// Context 类型
interface LanguageContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  isLoading: boolean;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

// 获取嵌套对象的值
function getNestedValue(obj: Translations, path: string): string | undefined {
  const keys = path.split(".");
  let current: TranslationValue = obj;

  for (const key of keys) {
    if (current && typeof current === "object" && key in current) {
      current = current[key];
    } else {
      return undefined;
    }
  }

  return typeof current === "string" ? current : undefined;
}

// 替换模板变量
function interpolate(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    return params[key] !== undefined ? String(params[key]) : `{${key}}`;
  });
}

// Provider 组件
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);
  const [translations, setTranslations] = useState<Translations>({});
  const [isLoading, setIsLoading] = useState(true);

  // 加载语言包
  const loadTranslations = useCallback(async (loc: Locale) => {
    setIsLoading(true);
    try {
      const module = await import(`@/i18n/locales/${loc}.json`);
      setTranslations(module.default || module);
      console.log(`[i18n] Loaded ${loc}`);
    } catch (error) {
      console.error(`[i18n] Failed to load ${loc}:`, error);
      // 回退到默认语言
      if (loc !== DEFAULT_LOCALE) {
        try {
          const fallback = await import(`@/i18n/locales/${DEFAULT_LOCALE}.json`);
          setTranslations(fallback.default || fallback);
        } catch (e) {
          console.error(`[i18n] Failed to load fallback:`, e);
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 初始化
  useEffect(() => {
    // 只从 localStorage 读取，不检测浏览器语言
    let initialLocale = DEFAULT_LOCALE;

    if (typeof window !== 'undefined') {
      const savedLocale = localStorage.getItem(STORAGE_KEY) as Locale | null;
      if (savedLocale && locales.some(l => l.code === savedLocale)) {
        initialLocale = savedLocale;
      }
    }

    setLocaleState(initialLocale);
    loadTranslations(initialLocale);
  }, [loadTranslations]);

  // 设置语言
  const setLocale = useCallback((newLocale: Locale) => {
    console.log(`[i18n] Switching to ${newLocale}`);

    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newLocale);
    }

    setLocaleState(newLocale);
    loadTranslations(newLocale);

    // 更新 HTML lang 属性
    if (typeof document !== 'undefined') {
      document.documentElement.lang = newLocale;
    }
  }, [loadTranslations]);

  // 翻译函数
  const t = useCallback((key: string, params?: Record<string, string | number>): string => {
    const value = getNestedValue(translations, key);

    if (value === undefined) {
      // 静默处理，不打印警告
      return key;
    }

    if (params) {
      return interpolate(value, params);
    }

    return value;
  }, [translations]);

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t, isLoading }}>
      {children}
    </LanguageContext.Provider>
  );
}

// Hook
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}

// 便捷的翻译 Hook
export function useTranslation() {
  const { t, locale, setLocale, isLoading } = useLanguage();
  return { t, locale, setLocale, isLoading };
}

export default LanguageContext;
