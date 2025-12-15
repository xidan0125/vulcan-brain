/**
 * Unified Chat API Service
 * 统一聊天服务 - 支持 Gemini + Vulcan 本地大脑 + ReAct 工具调用 + Session 持久化
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export type ModelType = 'gemini' | 'qwen3';

export interface VulcanBrain {
  id: string;
  name: string;
  icon: string;
  description: string;
  systemPrompt?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model: ModelType;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  enable_search?: boolean;
  enable_tools?: boolean;
  agent_id?: string;
  session_id?: string;
}

export interface ChatResponse {
  content: string;
  model: string;
  finish_reason?: string;
  session_id?: string;
  timestamp: string;
}

// SSE 事件类型 - 新增 session 类型
export interface StreamEvent {
  type: 'session' | 'thinking' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error';
  content?: string;
  session_id?: string;  // session 事件专用
  id?: string;
  name?: string;
  arguments?: string;
  result?: string;
}

// Session 信息
export interface SessionInfo {
  session_id: string;
  agent_id: string;
  message_count: number;
  created_at?: string;
  updated_at?: string;
  summary?: string;
}

// 获取 auth token
function getAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('vulcan_token');
  }
  return null;
}

// 获取用户的会话列表
export async function getSessions(): Promise<SessionInfo[]> {
  const token = getAuthToken();
  if (!token) throw new Error('Unauthorized');

  const res = await fetch(`${API_BASE}/api/unified-chat/sessions`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    throw new Error('Failed to fetch sessions');
  }

  return res.json();
}

// 创建新会话
export async function createSession(agentId: string = 'general'): Promise<SessionInfo> {
  const token = getAuthToken();
  if (!token) throw new Error('Unauthorized');

  const res = await fetch(`${API_BASE}/api/unified-chat/sessions?agent_id=${agentId}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    throw new Error('Failed to create session');
  }

  return res.json();
}

// 删除会话
export async function deleteSession(sessionId: string): Promise<void> {
  const token = getAuthToken();
  if (!token) throw new Error('Unauthorized');

  const res = await fetch(`${API_BASE}/api/unified-chat/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    throw new Error('Failed to delete session');
  }
}

// 流式聊天 - 返回事件流 (支持 session)
export async function* chatStreamEvents(request: ChatRequest): AsyncGenerator<StreamEvent, void, unknown> {
  const token = getAuthToken();
  if (!token) throw new Error('Unauthorized');

  const res = await fetch(`${API_BASE}/api/unified-chat/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ ...request, stream: true }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.message || 'Stream failed');
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6)) as StreamEvent;
          yield data;
          if (data.type === 'done' || data.type === 'error') return;
        } catch (e) {
          // ignore parse errors
        }
      }
    }
  }
}

// 简化版 - 只返回文本内容 (向后兼容)
export async function* chatStream(request: ChatRequest): AsyncGenerator<string, void, unknown> {
  for await (const event of chatStreamEvents(request)) {
    if (event.type === 'token' && event.content) {
      yield event.content;
    }
    if (event.type === 'error') {
      throw new Error(event.content || 'Stream error');
    }
  }
}

// Vulcan 本地大脑列表
export const VULCAN_BRAINS: VulcanBrain[] = [
  {
    id: 'general',
    name: 'Vulcan 本地大脑',
    icon: '🧠',
    description: '通用本地 AI 助手，快速响应',
  },
  {
    id: 'production',
    name: 'Vulcan 生产专家',
    icon: '🏭',
    description: '生产流程与质量管理',
  },
  {
    id: 'logistics',
    name: 'Vulcan 物流专家',
    icon: '🚚',
    description: '物流与供应链管理',
  },
  {
    id: 'financial',
    name: 'Vulcan 财务顾问',
    icon: '💰',
    description: '财务分析与税务咨询',
  },
  {
    id: 'hr',
    name: 'Vulcan HR 顾问',
    icon: '👥',
    description: '人力资源管理',
  },
  {
    id: 'code',
    name: 'Vulcan 代码助手',
    icon: '💻',
    description: '代码生成与技术支持',
  },
];

// 工具名称映射
export const TOOL_NAMES: Record<string, string> = {
  web_search: '🔍 联网搜索',
  remember: '💾 记忆存储',
  recall: '📖 记忆回忆',
  forget: '🗑️ 记忆删除',
};

export function getToolDisplayName(name: string): string {
  return TOOL_NAMES[name] || name;
}
