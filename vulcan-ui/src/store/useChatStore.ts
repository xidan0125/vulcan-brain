import { create } from "zustand";
import { createSession, saveMessages, getSession, listSessions } from "@/services/chatApi";

export interface ThinkingStep {
  type: "thinking" | "code" | "tool_output";
  content: string;
  timestamp: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  isStreaming?: boolean;
  codeBlocks?: string[];
  toolOutput?: string;
  thinkingSteps?: ThinkingStep[];
}

interface ChatState {
  sessionId: string | null;
  provider: string;
  messages: Message[];
  isLoading: boolean;
  currentStreamingMessage: string;
  isSaving: boolean;
  lastSavedAt: number | null;
  unsavedCount: number;

  initSession: (provider?: string) => Promise<string>;
  loadSession: (sessionId: string) => Promise<void>;
  addMessage: (message: Omit<Message, "id" | "timestamp">) => string;
  updateLastMessage: (updater: (prev: Message) => Message) => void;
  updateStreamingMessage: (content: string) => void;
  finalizeStreamingMessage: () => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  saveToBackend: () => Promise<void>;
  autoSave: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  provider: "vulcan",
  messages: [],
  isLoading: false,
  currentStreamingMessage: "",
  isSaving: false,
  lastSavedAt: null,
  unsavedCount: 0,

  initSession: async (provider = "vulcan") => {
    try {
      const result = await createSession(provider);
      set({ 
        sessionId: result.session_id, 
        provider,
        messages: [],
        unsavedCount: 0 
      });
      console.log("[Chat] Session created:", result.session_id);
      return result.session_id;
    } catch (error) {
      console.error("[Chat] Failed to create session:", error);
      const localId = `local_${Date.now()}`;
      set({ sessionId: localId, provider });
      return localId;
    }
  },

  loadSession: async (sessionId: string) => {
    try {
      const session = await getSession(sessionId);
      const messages: Message[] = session.messages.map((m: any, idx: number) => ({
        id: `msg_${idx}_${m.timestamp || Date.now()}`,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp || Date.now(),
        isStreaming: false,
      }));
      set({ 
        sessionId, 
        provider: session.provider,
        messages,
        unsavedCount: 0 
      });
    } catch (error) {
      console.error("[Chat] Failed to load session:", error);
    }
  },

  addMessage: (message) => {
    const newMessage: Message = {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
    };
    set((state) => ({
      messages: [...state.messages, newMessage],
      unsavedCount: state.unsavedCount + 1,
    }));
    return newMessage.id;
  },

  updateLastMessage: (updater) => {
    set((state) => {
      if (state.messages.length === 0) return state;
      const lastIndex = state.messages.length - 1;
      const updatedMessage = updater(state.messages[lastIndex]);
      const newMessages = [...state.messages];
      newMessages[lastIndex] = updatedMessage;
      return { messages: newMessages };
    });
  },

  updateStreamingMessage: (content) => {
    set({ currentStreamingMessage: content });
  },

  finalizeStreamingMessage: () => {
    const { currentStreamingMessage, messages } = get();
    if (currentStreamingMessage) {
      const newMessage: Message = {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        role: "assistant",
        content: currentStreamingMessage,
        timestamp: Date.now(),
        isStreaming: false,
      };
      set({
        messages: [...messages, newMessage],
        currentStreamingMessage: "",
        unsavedCount: get().unsavedCount + 1,
      });
    }
  },

  clearMessages: () => {
    set({ messages: [], currentStreamingMessage: "", unsavedCount: 0 });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },

  saveToBackend: async () => {
    const { sessionId, messages, unsavedCount } = get();
    
    if (!sessionId || sessionId.startsWith("local_") || unsavedCount === 0) {
      return;
    }

    set({ isSaving: true });
    
    try {
      const messagesToSave = messages
        .filter(m => !m.isStreaming)
        .map(m => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        }));

      await saveMessages(sessionId, messagesToSave.slice(-unsavedCount));
      
      set({ 
        isSaving: false, 
        lastSavedAt: Date.now(),
        unsavedCount: 0 
      });
      console.log("[Chat] Messages saved:", messagesToSave.length);
    } catch (error) {
      console.error("[Chat] Failed to save messages:", error);
      set({ isSaving: false });
    }
  },

  autoSave: () => {
    const { unsavedCount } = get();
    if (unsavedCount >= 2) {
      get().saveToBackend();
    }
  },
}));
