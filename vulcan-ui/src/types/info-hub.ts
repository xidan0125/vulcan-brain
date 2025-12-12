/**
 * InfoHub 类型定义
 * 与后端 api/info_hub/schemas 保持同步
 */

// ========== 通用类型 ==========
export interface DimensionStats {
  total: number;
  highlight_count: number;
  risk_count: number;
}

export interface AIAnalysis {
  summary: string;
  action_items: string[];
  risks: string[];
  highlights: string[];
  sentiment: 'positive' | 'neutral' | 'negative';
}

// ========== 聊天维度 ==========
export interface ChatAIAnalysis extends AIAnalysis {
  topics: string[];
  decisions: string[];
}

export interface ChatSummary {
  chat_id: string;
  chat_name: string;
  message_count: number;
  summary: string;
  decisions: string[];
  action_items: string[];
  risks: string[];
  topics: string[];
  activity_level: 'high' | 'medium' | 'low';
  sentiment: string;
}

export interface ChatDimensionData {
  total_chats: number;
  total_messages: number;
  total_decisions: number;
  total_action_items: number;
  total_risks: number;
  summaries: ChatSummary[];
}

// ========== 邮件维度 ==========
export interface EmailContact {
  name: string;
  address: string;
  count: number;
}

export interface EmailAIAnalysis extends AIAnalysis {
  vip_updates: string[];
  urgent_matters: string[];
  key_topics: string[];
}

export interface EmailDimensionData {
  total: number;
  received: number;
  sent: number;
  important: number;
  external_count: number;
  top_contacts: EmailContact[];
  ai_analysis: EmailAIAnalysis;
}

// ========== 人员维度 ==========
export interface DepartmentStats {
  department: string;
  count: number;
  active_count: number;
}

export interface FunctionStats {
  function: string;
  count: number;
}

export interface PeopleDimensionData {
  total_count: number;
  active_count: number;
  department_count: number;
  function_count: number;
  by_department: DepartmentStats[];
  by_function: FunctionStats[];
}

export interface PersonProfile {
  user_id: string;
  name: string;
  email: string;
  department: string;
  function: string;
  projects: string[];
  ms365_job_title?: string;
  email_sent_total: number;
  email_received_total: number;
  last_active?: string;
  daily_activity: Record<string, { email_sent: number; email_received: number; total: number }>;
}

// ========== 审批维度 ==========
export interface ApprovalAIAnalysis extends AIAnalysis {
  pending_attention: string[];
  recommendations: string[];
}

export interface ApprovalItem {
  instance_code: string;
  approval_code: string;
  approval_name: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELED';
  user_id: string;
  open_id: string;
  start_time: string;
  end_time?: string;
  serial_number: string;
}

export interface ApprovalDimensionData {
  total_count: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  ai_analysis: ApprovalAIAnalysis;
}

// ========== 项目维度 ==========
export interface ProjectDimensionData {
  total_count: number;
  in_progress: number;
  completed: number;
  blocked: number;
}

// ========== 日报概览 ==========
export interface DimensionOverview {
  chat: {
    total_messages: number;
    total_decisions: number;
    total_risks: number;
  };
  email: {
    total: number;
    important: number;
    external: number;
  };
  people: {
    total_count: number;
    active_count: number;
  };
  approval: {
    total_count: number;
    pending_count: number;
  };
  project: {
    total_count: number;
    in_progress: number;
  };
}

// ========== 日报主结构 ==========
export interface DailyReport {
  date: string;
  generated_at?: string;
  chat: ChatDimensionData;
  email: EmailDimensionData;
  people: PeopleDimensionData;
  approval: ApprovalDimensionData;
  project: ProjectDimensionData;
  overview: DimensionOverview;
}

// ========== API 响应 ==========
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface DailyReportResponse {
  report: DailyReport;
}
