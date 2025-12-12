/**
 * InfoHub 数据获取 Hook
 * 统一管理 InfoHub 各维度数据的获取和状态
 */
import { useState, useEffect, useCallback } from 'react';
import type { DailyReport, PersonProfile, ApprovalItem } from '@/types/info-hub';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.vsg-brain.com';

// ========== 日报 Hook ==========
interface UseDailyReportOptions {
  autoFetch?: boolean;
  date?: string;
}

interface UseDailyReportReturn {
  report: DailyReport | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  generate: (force?: boolean) => Promise<void>;
  generating: boolean;
}

export function useDailyReport(options: UseDailyReportOptions = {}): UseDailyReportReturn {
  const { autoFetch = true, date } = options;
  const [report, setReport] = useState<DailyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = date 
        ? `${API_BASE}/api/info-hub/daily/${date}`
        : `${API_BASE}/api/info-hub/daily/latest`;
      const res = await fetch(endpoint);
      if (!res.ok) throw new Error('获取日报失败');
      const data = await res.json();
      setReport(data.report);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [date]);

  const generate = useCallback(async (force = false) => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/daily/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force }),
      });
      if (!res.ok) throw new Error('生成日报失败');
      const data = await res.json();
      setReport(data.report);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setGenerating(false);
    }
  }, []);

  useEffect(() => {
    if (autoFetch) {
      fetchReport();
    }
  }, [autoFetch, fetchReport]);

  return { report, loading, error, refetch: fetchReport, generate, generating };
}

// ========== 人员列表 Hook ==========
interface UsePeopleListOptions {
  autoFetch?: boolean;
  department?: string;
  function?: string;
  activeOnly?: boolean;
}

interface UsePeopleListReturn {
  people: PersonProfile[];
  total: number;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function usePeopleList(options: UsePeopleListOptions = {}): UsePeopleListReturn {
  const { autoFetch = true, department, function: func, activeOnly } = options;
  const [people, setPeople] = useState<PersonProfile[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPeople = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (department) params.set('department', department);
      if (func) params.set('function', func);
      if (activeOnly) params.set('active_only', 'true');
      
      const res = await fetch(`${API_BASE}/api/info-hub/people/list?${params}`);
      if (!res.ok) throw new Error('获取人员列表失败');
      const data = await res.json();
      setPeople(data.people);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [department, func, activeOnly]);

  useEffect(() => {
    if (autoFetch) {
      fetchPeople();
    }
  }, [autoFetch, fetchPeople]);

  return { people, total, loading, error, refetch: fetchPeople };
}

// ========== 审批列表 Hook ==========
interface UseApprovalListOptions {
  autoFetch?: boolean;
  status?: string;
  approvalType?: string;
  limit?: number;
}

interface UseApprovalListReturn {
  approvals: ApprovalItem[];
  count: number;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useApprovalList(options: UseApprovalListOptions = {}): UseApprovalListReturn {
  const { autoFetch = true, status, approvalType, limit = 50 } = options;
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (approvalType) params.set('approval_type', approvalType);
      params.set('limit', String(limit));
      
      const res = await fetch(`${API_BASE}/api/info-hub/approval/list?${params}`);
      if (!res.ok) throw new Error('获取审批列表失败');
      const data = await res.json();
      setApprovals(data.approvals);
      setCount(data.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [status, approvalType, limit]);

  useEffect(() => {
    if (autoFetch) {
      fetchApprovals();
    }
  }, [autoFetch, fetchApprovals]);

  return { approvals, count, loading, error, refetch: fetchApprovals };
}

// ========== 聊天列表 Hook ==========
interface UseChatListOptions {
  autoFetch?: boolean;
}

interface UseChatListReturn {
  chats: Array<{ chat_id: string; chat_name: string; total_messages: number }>;
  count: number;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useChatList(options: UseChatListOptions = {}): UseChatListReturn {
  const { autoFetch = true } = options;
  const [chats, setChats] = useState<Array<{ chat_id: string; chat_name: string; total_messages: number }>>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchChats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/chat/list`);
      if (!res.ok) throw new Error('获取聊天列表失败');
      const data = await res.json();
      setChats(data.chats);
      setCount(data.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoFetch) {
      fetchChats();
    }
  }, [autoFetch, fetchChats]);

  return { chats, count, loading, error, refetch: fetchChats };
}
