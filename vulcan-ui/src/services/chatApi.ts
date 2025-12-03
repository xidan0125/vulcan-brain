/**
 * Chat API Service - 对话保存功能
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Message {
  role: string;
  content: string;
  timestamp?: number;
}

interface Session {
  session_id: string;
  provider: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

// 获取 auth token
function getAuthToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("vulcan_token");
  }
  return null;
}

// 通用 fetch 封装
async function apiFetch(url: string, options: RequestInit = {}) {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      ...headers,
      ...(options.headers as Record<string, string>),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "API Error");
  }

  return response.json();
}

export async function createSession(provider: string = "vulcan", title?: string): Promise<{ session_id: string }> {
  return apiFetch("/api/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ provider, title }),
  });
}

export async function listSessions(provider?: string, limit: number = 20): Promise<{ sessions: Session[]; total: number }> {
  const params = new URLSearchParams();
  if (provider) params.append("provider", provider);
  params.append("limit", limit.toString());
  
  return apiFetch(`/api/chat/sessions?${params}`);
}

export async function getSession(sessionId: string): Promise<Session & { messages: Message[] }> {
  return apiFetch(`/api/chat/sessions/${sessionId}`);
}

export async function saveMessages(sessionId: string, messages: Message[]): Promise<{ success: boolean; saved_count: number }> {
  return apiFetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}

export async function replaceMessages(sessionId: string, messages: Message[]): Promise<{ success: boolean; message_count: number }> {
  return apiFetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: "PUT",
    body: JSON.stringify({ messages }),
  });
}

export async function deleteSession(sessionId: string): Promise<{ success: boolean }> {
  return apiFetch(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function updateSessionTitle(sessionId: string, title: string): Promise<{ success: boolean }> {
  const params = new URLSearchParams({ title });
  return apiFetch(`/api/chat/sessions/${sessionId}?${params}`, {
    method: "PATCH",
  });
}
