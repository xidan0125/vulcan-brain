"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type PanelType = "chat" | "email" | "person" | "approval" | null;

interface PanelState {
  type: PanelType;
  id: string | null;
  title?: string;
  subtitle?: string;
}

interface InfoHubContextValue {
  // 面板状态
  panel: PanelState;
  openPanel: (type: PanelType, id: string, title?: string, subtitle?: string) => void;
  closePanel: () => void;

  // 日报缓存 (简化版，后续可扩展)
  selectedDate: string;
  setSelectedDate: (date: string) => void;
}

const InfoHubContext = createContext<InfoHubContextValue | null>(null);

export function InfoHubProvider({ children }: { children: ReactNode }) {
  const [panel, setPanel] = useState<PanelState>({
    type: null,
    id: null,
  });

  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const today = new Date();
    return today.toISOString().split("T")[0];
  });

  const openPanel = useCallback((type: PanelType, id: string, title?: string, subtitle?: string) => {
    setPanel({ type, id, title, subtitle });
  }, []);

  const closePanel = useCallback(() => {
    setPanel({ type: null, id: null });
  }, []);

  return (
    <InfoHubContext.Provider
      value={{
        panel,
        openPanel,
        closePanel,
        selectedDate,
        setSelectedDate,
      }}
    >
      {children}
    </InfoHubContext.Provider>
  );
}

export function useInfoHub() {
  const context = useContext(InfoHubContext);
  if (!context) {
    throw new Error("useInfoHub must be used within InfoHubProvider");
  }
  return context;
}
