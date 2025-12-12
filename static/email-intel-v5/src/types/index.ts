// Email Intelligence V5 Types

// ==================== Contact & Company ====================
export interface Contact {
  id: string;
  name: string;
  email: string;
  company?: string;
  company_id?: string;
  role?: string;
  health_score: number;
  health_trend: 'improving' | 'stable' | 'declining';
  last_contact: string;
  total_emails: number;
  email_count: number; // alias for graph compatibility
  emails_30d: number;
  avg_response_time_hours?: number;
  tags?: string[];
}

export interface Company {
  id: string;
  name: string;
  domains: string[];
  relation_type: 'client' | 'vendor' | 'partner' | 'government' | 'internal' | 'unknown';
  health_score: number;
  total_emails: number;
  emails_30d: number;
  contact_count: number;
  first_contact?: string;
  last_contact?: string;
  contacts?: Contact[];
}

// ==================== Action Items ====================
export interface ActionItem {
  id: string;
  type: 'needs_reply' | 'waiting_on' | 'follow_up';
  priority: 'high' | 'medium' | 'low';
  priority_score: number;

  email_id: string;
  thread_id?: string;
  subject: string;
  snippet?: string;

  from: {
    name: string;
    email: string;
    company?: string;
  };

  created_at: string;
  due_date?: string;
  days_waiting: number;

  ai_summary?: string;
}

// ==================== Command Center ====================
export interface CommandCenterData {
  urgent_count: number;
  waiting_count: number;
  opportunity_count: number;

  urgent_actions: ActionItem[];
  relationship_alerts: RelationshipAlert[];
  weekly_trends: WeeklyTrends;
}

export interface RelationshipAlert {
  id: string;
  type: 'cooling' | 'inactive' | 'risk' | 'opportunity';
  severity: 'high' | 'medium' | 'low';
  contact?: Contact;
  company?: Company;
  message: string;
  days_since_contact?: number;
  suggested_action?: string;
}

export interface WeeklyTrends {
  emails_sent: number;
  emails_received: number;
  avg_response_time: number;
  response_time_trend: 'improving' | 'stable' | 'declining';
  active_contacts: number;
  new_contacts: number;
}

// ==================== Relationship Graph ====================
export interface GraphNode {
  id: string;
  name: string;
  type: 'person' | 'company' | 'internal';
  email?: string;
  company?: string;
  health_score: number;
  email_count: number;
  importance: number;
  color?: string;
  // Force graph positioning (set by d3)
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  value: number;
  relation_type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// ==================== API Responses ====================
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface RelationshipsResponse {
  contacts: Contact[];
  companies: Company[];
  total_contacts: number;
  total_companies: number;
}

export interface ActionsResponse {
  needs_reply: ActionItem[];
  waiting_on: ActionItem[];
  follow_ups: ActionItem[];
}
