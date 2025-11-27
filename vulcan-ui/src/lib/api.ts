/**
 * Vulcan Brain API Client
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// Types
export interface User {
  user_id: string;
  username: string;
  display_name: string;
  role_level: number;
  genesis_completed?: boolean;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface SoulStatus {
  user_id: string;
  genesis_completed: boolean;
  sync_rate: number;
  has_constitution: boolean;
}

export interface SoulProfile {
  user_id: string;
  display_name: string;
  soul: any;
  constitution: ConstitutionItem[];
  system_prompt_snippet: string;
}

export interface ConstitutionItem {
  id: string;
  category: 'redline' | 'core' | 'style';
  content: string;
}

// ========== Soul 数字孪生类型 ==========

export interface SoulStats {
  user_id: string;
  streak_days: number;
  last_active_date: string | null;
  understanding_score: number;
  score_history: Array<{date: string; score: number}>;
  dimensions: {
    risk_appetite: number;
    time_preference: number;
    social_tendency: number;
    decision_style: number;
    value_priority: number;
    stress_response: number;
  };
  data_points_collected: number;
  insights: string[];
}

export interface SandboxQuestion {
  question_id: string;
  scenario: string;
  category: string;
  options: Array<{
    id: string;
    text: string;
  }>;
  ai_prediction: {
    option_id: string;
    confidence: number;
    reasoning: string;
  };
}

export interface DailyQuestionsResponse {
  user_id: string;
  date: string;
  questions: SandboxQuestion[];
  streak_days: number;
  streak_warning: string | null;
}

export interface SubmitAnswerResponse {
  is_match: boolean;
  ai_predicted: string;
  user_selected: string;
  ai_reasoning: string;
  dimension_updates: Record<string, number>;
  new_understanding_score: number;
  streak_days: number;
  message: string;
}

// Helper to get auth headers
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('vulcan_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
}

// Auth APIs
export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Login failed');
  }
  return res.json();
}

export async function getMe(): Promise<User & { soul: any }> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    throw new Error('Unauthorized');
  }
  return res.json();
}

// Soul APIs
export async function getSoulStatus(): Promise<SoulStatus> {
  const res = await fetch(`${API_BASE}/api/soul/status`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to get soul status');
  return res.json();
}

export async function submitGenesis(answers: Record<number, string>): Promise<any> {
  const res = await fetch(`${API_BASE}/api/soul/genesis`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ answers })
  });
  if (!res.ok) throw new Error('Failed to submit genesis');
  return res.json();
}

export async function getConstitution(): Promise<{ user_id: string; items: ConstitutionItem[] }> {
  const res = await fetch(`${API_BASE}/api/soul/constitution`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to get constitution');
  return res.json();
}

export async function updateConstitution(items: ConstitutionItem[]): Promise<any> {
  const res = await fetch(`${API_BASE}/api/soul/constitution`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify({ items })
  });
  if (!res.ok) throw new Error('Failed to update constitution');
  return res.json();
}

export async function getSoulProfile(): Promise<SoulProfile> {
  const res = await fetch(`${API_BASE}/api/soul/profile`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to get soul profile');
  return res.json();
}

// Alignment APIs
export async function submitAlignment(
  cardId: string,
  selected: string,
  expected: string
): Promise<{ is_correct: boolean; sync_delta: number; new_sync_rate: number }> {
  const res = await fetch(
    `${API_BASE}/api/soul/alignment/submit?card_id=${cardId}&selected=${selected}&expected=${expected}`,
    { method: 'POST', headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error('Failed to submit alignment');
  return res.json();
}

// 开发调试：重置校准状态
export async function resetGenesis(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/soul/genesis/reset`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to reset genesis');
  return res.json();
}

// ========== Soul 数字孪生 API ==========

/**
 * 获取用户 Soul 统计数据（数字孪生面板）
 */
export async function getSoulStats(userId: string): Promise<SoulStats> {
  const res = await fetch(`${API_BASE}/api/soul/stats?user_id=${userId}`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to get soul stats');
  return res.json();
}

/**
 * 获取每日沙盘题目（决策推演面板）
 */
export async function getDailyQuestions(userId: string): Promise<DailyQuestionsResponse> {
  const res = await fetch(`${API_BASE}/api/soul/sandbox/daily?user_id=${userId}`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to get daily questions');
  return res.json();
}

/**
 * 提交沙盘答案
 */
export async function submitSandboxAnswer(
  questionId: string,
  selectedOptionId: string,
  userId: string
): Promise<SubmitAnswerResponse> {
  const res = await fetch(`${API_BASE}/api/soul/sandbox/submit`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      question_id: questionId,
      selected_option_id: selectedOptionId,
      user_id: userId
    })
  });
  if (!res.ok) throw new Error('Failed to submit sandbox answer');
  return res.json();
}

/**
 * 获取校准状态（用于显示"正在构建模型"提示）
 */
export async function getCalibrationStatus(userId: string): Promise<{
  in_calibration: boolean;
  calibration_progress: number;
  accuracy?: number;
  message: string;
}> {
  const res = await fetch(`${API_BASE}/api/soul/calibration?user_id=${userId}`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('Failed to get calibration status');
  return res.json();
}
