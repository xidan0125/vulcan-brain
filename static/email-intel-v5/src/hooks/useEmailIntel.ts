import { useQuery } from '@tanstack/react-query';
import type {
  CommandCenterData,
  RelationshipsResponse,
  GraphData,
  Company,
  ActionItem,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://192.168.31.8:8001/api';

async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  return response.json();
}

// Command Center - Today's overview
export function useCommandCenter() {
  return useQuery<CommandCenterData>({
    queryKey: ['command-center'],
    queryFn: () => fetchApi('/email-intel/command-center'),
    refetchInterval: 60000, // Refresh every minute
  });
}

// Action Items - Needs reply
export function useNeedsReply() {
  return useQuery<ActionItem[]>({
    queryKey: ['needs-reply'],
    queryFn: () => fetchApi('/email-intel/actions/needs-reply'),
    refetchInterval: 60000,
  });
}

// Action Items - Waiting on others
export function useWaitingOn() {
  return useQuery<ActionItem[]>({
    queryKey: ['waiting-on'],
    queryFn: () => fetchApi('/email-intel/actions/waiting-on'),
    refetchInterval: 60000,
  });
}

// Relationships - All contacts with health scores
export function useRelationships() {
  return useQuery<RelationshipsResponse>({
    queryKey: ['relationships'],
    queryFn: () => fetchApi('/email-intel/relationships'),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Relationship Alerts
export function useRelationshipAlerts() {
  return useQuery({
    queryKey: ['relationship-alerts'],
    queryFn: () => fetchApi('/email-intel/relationships/alerts'),
    refetchInterval: 5 * 60 * 1000, // 5 minutes
  });
}

// Company Intelligence
export function useCompanyIntel(domain: string) {
  return useQuery<Company>({
    queryKey: ['company', domain],
    queryFn: () => fetchApi(`/email-intel/companies/${encodeURIComponent(domain)}`),
    enabled: !!domain,
    staleTime: 5 * 60 * 1000,
  });
}

// All Companies
export function useCompanies() {
  return useQuery<Company[]>({
    queryKey: ['companies'],
    queryFn: () => fetchApi('/email-intel/companies'),
    staleTime: 5 * 60 * 1000,
  });
}

// Relationship Graph Data
export function useRelationshipGraph() {
  return useQuery<GraphData>({
    queryKey: ['relationship-graph'],
    queryFn: () => fetchApi('/email-intel/relationships/graph'),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Weekly Trends
export function useWeeklyTrends() {
  return useQuery({
    queryKey: ['weekly-trends'],
    queryFn: () => fetchApi('/email-intel/trends/weekly'),
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}

// Smart Search
export async function searchEmails(query: string, includeAiSummary = true) {
  const response = await fetch(`${API_BASE}/email-intel/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, include_ai_summary: includeAiSummary }),
  });
  return response.json();
}
