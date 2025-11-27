import { create } from 'zustand';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  isStreaming?: boolean;
  codeBlocks?: string[];
  toolOutput?: string;
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  currentStreamingMessage: string;

  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => string;
  updateLastMessage: (updater: (prev: Message) => Message) => void;
  updateStreamingMessage: (content: string) => void;
  finalizeStreamingMessage: () => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  currentStreamingMessage: '',

  addMessage: (message) => {
    const newMessage: Message = {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
    };
    set((state) => ({
      messages: [...state.messages, newMessage],
    }));
    return newMessage.id;
  },

  // ✅ 新增：更新最后一条消息（用于流式追加）
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
        role: 'assistant',
        content: currentStreamingMessage,
        timestamp: Date.now(),
        isStreaming: false,
      };
      set({
        messages: [...messages, newMessage],
        currentStreamingMessage: '',
      });
    }
  },

  clearMessages: () => {
    set({ messages: [], currentStreamingMessage: '' });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },
}));
