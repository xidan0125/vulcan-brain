/**
 * Memory API Service v3
 * 记忆系统前端服务 - 支持提取、确认、拒绝、编辑
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// 获取 auth token
function getAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('vulcan_token');
  }
  return null;
}

// 请求头
function getHeaders(): HeadersInit {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// 待确认记忆类型
export interface PendingMemory {
  id: string;
  key: string;
  value: string;
  category: 'identity' | 'preference' | 'fact';
  confidence: number;
  context?: string;
  created_at?: string;
}

// 已确认记忆类型
export interface Memory {
  key: string;
  value: string;
  category: string;
  status: string;
}

/**
 * 从用户消息中提取记忆
 * 异步调用，不阻塞聊天
 */
export async function extractMemories(
  message: string,
  sessionId: string
): Promise<PendingMemory[]> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/extract`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!res.ok) {
      console.error('Memory extraction failed:', res.status);
      return [];
    }

    const data = await res.json();
    return (data.pending || []).map((p: any) => ({
      id: p.id || p._id,
      key: p.key,
      value: p.value,
      category: p.category || 'fact',
      confidence: p.confidence || 0.8,
      context: p.context,
      created_at: p.created_at,
    }));
  } catch (error) {
    console.error('Memory extraction error:', error);
    return [];
  }
}

/**
 * 获取待确认记忆列表
 */
export async function getPendingMemories(): Promise<PendingMemory[]> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/pending`, {
      headers: getHeaders(),
    });

    if (!res.ok) return [];

    const data = await res.json();
    return (data || []).map((p: any) => ({
      id: p.id || p._id,
      key: p.key,
      value: p.value,
      category: p.category || 'fact',
      confidence: p.confidence || 0.8,
    }));
  } catch (error) {
    console.error('Get pending memories error:', error);
    return [];
  }
}

/**
 * 确认记忆
 */
export async function confirmMemory(pendingId: string): Promise<Memory | null> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/confirm/${pendingId}`, {
      method: 'POST',
      headers: getHeaders(),
    });

    if (!res.ok) {
      console.error('Confirm memory failed:', res.status);
      return null;
    }

    return await res.json();
  } catch (error) {
    console.error('Confirm memory error:', error);
    return null;
  }
}

/**
 * 拒绝记忆
 */
export async function rejectMemory(pendingId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/reject/${pendingId}`, {
      method: 'POST',
      headers: getHeaders(),
    });

    return res.ok;
  } catch (error) {
    console.error('Reject memory error:', error);
    return false;
  }
}

/**
 * 编辑并确认记忆
 */
export async function editAndConfirmMemory(
  pendingId: string,
  newValue: string
): Promise<Memory | null> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/pending/${pendingId}`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify({ new_value: newValue }),
    });

    if (!res.ok) {
      console.error('Edit memory failed:', res.status);
      return null;
    }

    return await res.json();
  } catch (error) {
    console.error('Edit memory error:', error);
    return null;
  }
}

/**
 * 获取所有已确认记忆
 */
export async function getAllMemories(): Promise<Memory[]> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/all`, {
      headers: getHeaders(),
    });

    if (!res.ok) return [];

    return await res.json();
  } catch (error) {
    console.error('Get all memories error:', error);
    return [];
  }
}

/**
 * 获取记忆上下文（调试用）
 */
export async function getMemoryContext(): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/context`, {
      headers: getHeaders(),
    });

    if (!res.ok) return '';

    const data = await res.json();
    return data.context || '';
  } catch (error) {
    console.error('Get memory context error:', error);
    return '';
  }
}
