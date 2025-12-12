"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  MessageSquare,
  FolderKanban,
  Mail,
  FileCheck,
  Users,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  ListTodo,
  Star,
  Clock,
  RefreshCw,
  Send,
  XCircle,
  FileText,
  TrendingUp,
  Building,
  Briefcase,
  Target,
  Eye,
  Bell,
  GitBranch,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import SlideOverPanel from "@/components/info-hub/SlideOverPanel";
import ChatPanelContent from "@/components/info-hub/ChatPanelContent";
import EmailPanelContent from "@/components/info-hub/EmailPanelContent";

// ========== 类型定义 ==========
interface ChatSummary {
  chat_id: string;
  chat_name: string;
  message_count: number;
  summary: string;
  decisions: string[];
  action_items: string[];
  risks: string[];
  topics: string[];
  activity_level: string;
  sentiment: string;
}

interface EmailAIAnalysis {
  summary: string;
  action_items: string[];
  vip_updates: string[] | string;
  urgent_matters: string[] | string;
  key_topics: string[];
  sentiment: string;
}

// Helper function to normalize string or array to array
const toArray = (value: string | string[] | undefined): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return [value];
};

interface EmailSummary {
  total: number;
  received: number;
  sent: number;
  important: number;
  external_count: number;
  top_contacts: Array<{ name: string; address: string; count: number }>;
  vip_emails: Array<{ email_id: string; subject: string; from: { name: string; address: string }; client: string }>;
  ai_analysis: EmailAIAnalysis;
}

interface ApprovalSummary {
  date: string;
  total_count: number;
  pending_count: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  summary: string;
  highlights: string[];
  pending_attention: string[];
  risks: string[];
  recommendations: string[];
}

interface ApprovalItem {
  instance_code: string;
  approval_code: string;
  approval_name: string;
  status: string;
  user_id: string;
  open_id: string;
  start_time: string;
  end_time: string | null;
  serial_number: string;
}

// ========== 项目类型定义 ==========
interface Milestone {
  title: string;
  project: string;
  due_date: string;
  status: string;
  risk_level: "low" | "medium" | "high";
}

interface LeftoverIssue {
  issue: string;
  project: string;
  owner: string;
  blocked_reason: string;
  suggested_action: string;
}

interface ResourceAllocation {
  person: string;
  projects: string[];
  task_count: number;
  workload: "low" | "medium" | "high";
  overloaded: boolean;
}

interface ProjectAttention {
  project: string;
  reason: string;
  risk_factors: string[];
  priority: "low" | "medium" | "high";
}

interface WorkloadWarning {
  person: string;
  warning: string;
  task_count: number;
  deadline_pressure: string;
}

interface CrossDeptRisk {
  risk: string;
  involved_projects: string[];
  involved_people: string[];
  mitigation: string;
}

interface ProjectAnalysis {
  milestones: Milestone[];
  leftover_issues: LeftoverIssue[];
  resource_allocation: ResourceAllocation[];
  projects_needing_attention: ProjectAttention[];
  workload_warnings: WorkloadWarning[];
  cross_department_risks: CrossDeptRisk[];
  summary: string;
}

interface ProjectSummary {
  date: string;
  generated_at: string;
  stats: {
    total_projects: number;
    total_tasks: number;
    completed_tasks: number;
    blocked_tasks: number;
    at_risk_tasks: number;
    in_progress_tasks: number;
  };
  analysis: ProjectAnalysis;
}

// V2 API 摘要类型
interface DailyReportSummary {
  chat: { count: number; chats: number; highlights: number };
  email: { count: number; urgent: number; vip: number };
  projects: { count: number; at_risk: number; blocked: number };
  approval: { count: number; pending: number };
  people: { count: number; active: number };
}

// 群聊汇总项（带来源）
interface ChatAggregatedItem {
  content: string;
  source: string;
  chat_id: string;
}

// 活跃群组
interface ActiveChat {
  name: string;
  count: number;
  chat_id: string;
}

// V2 API 响应类型
interface DailyReportV2 {
  date: string;
  generated_at: string | null;
  summary: DailyReportSummary;
  chat: {
    total_chats: number;
    total_messages: number;
    global_summary: string;
    all_risks: ChatAggregatedItem[];
    all_action_items: ChatAggregatedItem[];
    all_decisions: ChatAggregatedItem[];
    active_chats: ActiveChat[];
    summaries: ChatSummary[];
  };
  email: EmailSummary;
  projects: {
    stats?: {
      total_projects: number;
      total_tasks: number;
      completed_tasks: number;
      blocked_tasks: number;
      at_risk_tasks: number;
      in_progress_tasks: number;
    };
    analysis?: ProjectAnalysis;
    generated_at?: string;
  } | null;
  approval: {
    total: number;
    pending: number;
    by_status: Record<string, number>;
  };
  people: {
    total: number;
    active: number;
  };
}

interface DailyReport {
  date: string;
  chat: {
    total_chats: number;
    total_messages: number;
    summaries: ChatSummary[];
  };
  email: EmailSummary;
  projects: { total_count: number };
  approval: { total_count: number };
  people: { total_count: number };
}

type Dimension = "chat" | "email" | "projects" | "approval" | "people";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ========== 五维度卡片配置 ==========
const dimensionConfig = [
  { id: "chat" as Dimension, label: "聊天记录", description: "飞书群聊", icon: MessageSquare, color: "text-blue-400", bgColor: "bg-blue-500/10", borderColor: "border-blue-500/30" },
  { id: "email" as Dimension, label: "邮件", description: "Outlook", icon: Mail, color: "text-amber-400", bgColor: "bg-amber-500/10", borderColor: "border-amber-500/30" },
  { id: "projects" as Dimension, label: "项目", description: "飞书任务", icon: FolderKanban, color: "text-purple-400", bgColor: "bg-purple-500/10", borderColor: "border-purple-500/30" },
  { id: "approval" as Dimension, label: "审批", description: "飞书审批", icon: FileCheck, color: "text-emerald-400", bgColor: "bg-emerald-500/10", borderColor: "border-emerald-500/30" },
  { id: "people" as Dimension, label: "人员", description: "活跃度", icon: Users, color: "text-rose-400", bgColor: "bg-rose-500/10", borderColor: "border-rose-500/30" },
];

const APPROVAL_STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: any }> = {
  PENDING: { label: "待审批", color: "text-amber-400", bgColor: "bg-amber-500/10", icon: Clock },
  APPROVED: { label: "已通过", color: "text-green-400", bgColor: "bg-green-500/10", icon: CheckCircle2 },
  REJECTED: { label: "已拒绝", color: "text-red-400", bgColor: "bg-red-500/10", icon: XCircle },
  CANCELED: { label: "已撤销", color: "text-zinc-400", bgColor: "bg-zinc-500/10", icon: AlertTriangle },
};

// 项目风险等级颜色
const riskColors: Record<string, string> = {
  low: "text-green-400 bg-green-500/10",
  medium: "text-yellow-400 bg-yellow-500/10",
  high: "text-red-400 bg-red-500/10",
};

// 可折叠卡片组件
function CollapsibleSection({
  title,
  icon: Icon,
  count,
  children,
  defaultOpen = true,
  color = "purple",
}: {
  title: string;
  icon: React.ElementType;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
  color?: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const colorMap: Record<string, string> = {
    purple: "bg-purple-500/10 text-purple-400",
    red: "bg-red-500/10 text-red-400",
    blue: "bg-blue-500/10 text-blue-400",
    yellow: "bg-yellow-500/10 text-yellow-400",
    green: "bg-green-500/10 text-green-400",
    orange: "bg-orange-500/10 text-orange-400",
  };

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg ${colorMap[color]} flex items-center justify-center`}>
            <Icon className="w-4 h-4" />
          </div>
          <span className="font-medium text-white">{title}</span>
          <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full">
            {count}
          </span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-zinc-500" />
        ) : (
          <ChevronDown className="w-4 h-4 text-zinc-500" />
        )}
      </button>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// 每个 tab 的独立数据类型
interface TabData {
  date: string;
  data: DailyReportV2 | null;
  loading: boolean;
  generating: boolean;
}

function DailyReportContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tabFromUrl = searchParams.get("tab") as Dimension | null;
  const dateFromUrl = searchParams.get("date");  // 从 URL 读取日期
  const [selectedDimension, setSelectedDimension] = useState<Dimension>(
    tabFromUrl && ["email", "chat", "projects", "approval", "people"].includes(tabFromUrl)
      ? tabFromUrl
      : "email"
  );

  // 每个 tab 独立的日期和数据状态
  const [tabStates, setTabStates] = useState<Record<Dimension, TabData>>({
    chat: { date: "", data: null, loading: true, generating: false },
    email: { date: "", data: null, loading: true, generating: false },
    projects: { date: "", data: null, loading: true, generating: false },
    approval: { date: "", data: null, loading: true, generating: false },
    people: { date: "", data: null, loading: true, generating: false },
  });

  const [initialized, setInitialized] = useState(false);

  // 更新 URL 参数（tab + 当前 tab 的日期）
  const updateUrl = (tab: Dimension, date: string) => {
    const params = new URLSearchParams();
    params.set("tab", tab);
    if (date) params.set("date", date);
    router.push(`?${params.toString()}`, { scroll: false });
  };

  const handleTabChange = (tab: Dimension) => {
    setSelectedDimension(tab);
    const tabDate = tabStates[tab].date;
    updateUrl(tab, tabDate);
  };

  // 审批详情列表
  const [approvalList, setApprovalList] = useState<ApprovalItem[]>([]);
  const [approvalLoading, setApprovalLoading] = useState(false);

  // 项目生成状态
  const [projectGenerating, setProjectGenerating] = useState(false);

  // 侧滑面板状态
  const [panel, setPanel] = useState<{
    type: "chat" | "email" | null;
    id: string | null;
    title: string;
    subtitle?: string;
  }>({ type: null, id: null, title: "" });

  const openPanel = (type: "chat" | "email", id: string, title: string, subtitle?: string) => {
    setPanel({ type, id, title, subtitle });
  };

  const closePanel = () => {
    setPanel({ type: null, id: null, title: "" });
  };

  // 初始化：优先使用 URL 日期，否则获取最近有数据的日期
  useEffect(() => {
    const initAllTabs = async () => {
      try {
        // 获取每个维度最近有数据的日期
        const dimDatesRes = await fetch(`${API_BASE}/api/info-hub/daily/latest-by-dimension`);
        const dimDates = dimDatesRes.ok ? await dimDatesRes.json() : null;

        const today = new Date().toISOString().split("T")[0];
        const defaultDates: Record<Dimension, string> = {
          chat: dimDates?.chat || today,
          email: dimDates?.email || today,
          projects: dimDates?.projects || today,
          approval: dimDates?.approval || today,
          people: dimDates?.people || today,
        };

        // 如果 URL 有日期参数，当前 tab 使用 URL 日期
        const currentTab = (tabFromUrl && ["email", "chat", "projects", "approval", "people"].includes(tabFromUrl)
          ? tabFromUrl : "email") as Dimension;
        if (dateFromUrl && /^\d{4}-\d{2}-\d{2}$/.test(dateFromUrl)) {
          defaultDates[currentTab] = dateFromUrl;
        }

        // 并行获取每个 tab 各自日期的数据
        const fetchPromises = (Object.keys(defaultDates) as Dimension[]).map(async (tab) => {
          const res = await fetch(`${API_BASE}/api/info-hub/daily/v2/${defaultDates[tab]}`);
          return { tab, data: res.ok ? await res.json() : null };
        });
        const results = await Promise.all(fetchPromises);

        // 设置每个 tab 的独立日期和数据
        setTabStates(prev => {
          const newStates = { ...prev };
          results.forEach(({ tab, data }) => {
            newStates[tab] = {
              date: defaultDates[tab],
              data,
              loading: false,
              generating: false
            };
          });
          return newStates;
        });

        // 更新 URL
        updateUrl(currentTab, defaultDates[currentTab]);
      } catch (e) {
        console.error("初始化失败:", e);
        const today = new Date().toISOString().split("T")[0];
        setTabStates(prev => {
          const newStates = { ...prev };
          (Object.keys(newStates) as Dimension[]).forEach(tab => {
            newStates[tab] = { ...newStates[tab], date: today, loading: false };
          });
          return newStates;
        });
      } finally {
        setInitialized(true);
      }
    };
    initAllTabs();
  }, []);

  // 获取单个 tab 的数据
  const fetchTabData = async (tab: Dimension, targetDate: string) => {
    setTabStates(prev => ({
      ...prev,
      [tab]: { ...prev[tab], loading: true }
    }));
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/daily/v2/${targetDate}`);
      if (res.ok) {
        const data = await res.json();
        setTabStates(prev => ({
          ...prev,
          [tab]: { ...prev[tab], data, loading: false }
        }));
      }
    } catch (e) {
      console.error(`获取 ${tab} 数据失败:`, e);
      setTabStates(prev => ({
        ...prev,
        [tab]: { ...prev[tab], loading: false }
      }));
    }
  };

  // 当 tab 日期变化时获取数据
  useEffect(() => {
    if (!initialized) return;
    const currentTab = selectedDimension;
    const currentDate = tabStates[currentTab].date;
    if (currentDate) {
      fetchTabData(currentTab, currentDate);
    }
  }, [initialized, selectedDimension, tabStates[selectedDimension]?.date]);

  // 修改当前 tab 的日期（同步更新 URL）
  const setCurrentTabDate = (newDate: string) => {
    setTabStates(prev => ({
      ...prev,
      [selectedDimension]: { ...prev[selectedDimension], date: newDate }
    }));
    updateUrl(selectedDimension, newDate);
  };

  // 日期增减
  const changeDate = (days: number) => {
    const currentDate = tabStates[selectedDimension].date;
    if (!currentDate) return;
    const d = new Date(currentDate);
    d.setDate(d.getDate() + days);
    setCurrentTabDate(d.toISOString().split("T")[0]);
  };

  // 当前 tab 的数据
  const currentTabState = tabStates[selectedDimension];
  const reportV2 = currentTabState.data;
  const loading = currentTabState.loading;
  const date = currentTabState.date;

  // 获取审批详情列表（仅当切换到审批tab时）
  useEffect(() => {
    if (selectedDimension === "approval") {
      fetchApprovalList();
    }
  }, [selectedDimension]);

  // 仅获取审批列表详情（统计数据已在 V2 API 中）
  const fetchApprovalList = async () => {
    setApprovalLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/approval/list?limit=50`);
      if (res.ok) {
        const data = await res.json();
        const approvals = (data.approvals || []).map((a: any) => ({
          instance_code: a._id || a.instance_code,
          approval_code: a.approval_code,
          approval_name: a.approval_name || a.type_name || a.type,
          status: a.status?.toUpperCase() || "PENDING",
          user_id: a.user_id,
          open_id: a.open_id,
          start_time: a.start_time || a.created_at,
          end_time: a.end_time,
          serial_number: a.serial_number,
        }));
        setApprovalList(approvals);
      }
    } catch (e) {
      console.error("获取审批列表失败:", e);
    } finally {
      setApprovalLoading(false);
    }
  };

  // 生成项目简报
  const generateProjectSummary = async () => {
    setProjectGenerating(true);
    try {
      await fetch(`${API_BASE}/api/info-hub/projects/summary/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date }),
      });
      // 等待生成完成后刷新数据
      setTimeout(async () => {
        await fetchTabData("projects", date);
        setProjectGenerating(false);
      }, 5000);
    } catch (e) {
      console.error("生成项目简报失败:", e);
      setProjectGenerating(false);
    }
  };

  // 生成当前 tab 的日报
  const generating = currentTabState.generating;
  const generateReport = async () => {
    setTabStates(prev => ({
      ...prev,
      [selectedDimension]: { ...prev[selectedDimension], generating: true }
    }));
    try {
      const res = await fetch(`${API_BASE}/api/info-hub/daily/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date }),
      });
      if (res.ok) {
        // 等待后台生成，然后刷新数据
        setTimeout(async () => {
          await fetchTabData(selectedDimension, date);
          setTabStates(prev => ({
            ...prev,
            [selectedDimension]: { ...prev[selectedDimension], generating: false }
          }));
        }, 3000);
      } else {
        setTabStates(prev => ({
          ...prev,
          [selectedDimension]: { ...prev[selectedDimension], generating: false }
        }));
      }
    } catch (e) {
      console.error("生成日报失败:", e);
      setTabStates(prev => ({
        ...prev,
        [selectedDimension]: { ...prev[selectedDimension], generating: false }
      }));
    }
  };

  // 从各自 tab 的数据获取卡片数字
  const getCount = (dimId: Dimension): number => {
    const tabData = tabStates[dimId].data;
    if (!tabData?.summary) return 0;
    switch (dimId) {
      case "chat": return tabData.summary.chat.count;
      case "email": return tabData.summary.email.count;
      case "projects": return tabData.summary.projects.count;
      case "approval": return tabData.summary.approval.count;
      case "people": return tabData.summary.people.count;
      default: return 0;
    }
  };

  // 获取各自 tab 的二级信息
  const getSecondaryInfo = (dimId: Dimension): string => {
    const tabData = tabStates[dimId].data;
    if (!tabData?.summary) return "";
    switch (dimId) {
      case "chat": return tabData.summary.chat.highlights > 0 ? `${tabData.summary.chat.highlights} 重点` : "";
      case "email": return tabData.summary.email.vip > 0 ? `${tabData.summary.email.vip} VIP` : "";
      case "projects": return tabData.summary.projects.at_risk > 0 ? `${tabData.summary.projects.at_risk} 风险` : "";
      case "approval": return tabData.summary.approval.pending > 0 ? `${tabData.summary.approval.pending} 待处理` : "";
      case "people": return tabData.summary.people.active > 0 ? `${tabData.summary.people.active} 活跃` : "";
      default: return "";
    }
  };

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "-";
    try {
      return new Date(timeStr).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return timeStr;
    }
  };

  const selectedDim = dimensionConfig.find((d) => d.id === selectedDimension)!;
  const emailData = reportV2?.email;
  const emailAI = emailData?.ai_analysis;
  const projectStats = reportV2?.projects?.stats;
  const projectAnalysis = reportV2?.projects?.analysis;
  const approvalData = reportV2?.approval;
  const peopleData = reportV2?.people;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* 页面标题 - 简化版 */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">日报总览</h1>
        <p className="text-sm text-zinc-500">五维度企业数据汇总</p>
      </div>

      {/* 五维度卡片选择器 */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {dimensionConfig.map((dim) => {
          const Icon = dim.icon;
          const isSelected = selectedDimension === dim.id;
          const count = getCount(dim.id);
          const secondaryInfo = getSecondaryInfo(dim.id);
          return (
            <button key={dim.id} onClick={() => handleTabChange(dim.id)}
              className={`p-3 rounded-xl border text-center transition-all ${isSelected ? `${dim.bgColor} ${dim.borderColor} border-2` : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 cursor-pointer"}`}>
              <div className={`w-10 h-10 rounded-lg ${dim.bgColor} flex items-center justify-center mx-auto mb-2`}>
                <Icon className={`w-5 h-5 ${dim.color}`} />
              </div>
              <div className={`text-sm font-medium ${isSelected ? "text-white" : "text-zinc-300"}`}>{dim.label}</div>
              <div className="text-[10px] text-zinc-500">{dim.description}</div>
              <div className={`text-lg font-bold mt-1 ${dim.color}`}>{loading ? "-" : count}</div>
              {secondaryInfo && <div className="text-[10px] text-zinc-500 mt-0.5">{secondaryInfo}</div>}
            </button>
          );
        })}
      </div>

      {/* 内容区域 */}
      <div className="border-t border-zinc-800 pt-6">
        {/* Tab 头部：标题 + 日期 + 刷新按钮 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-lg ${selectedDim.bgColor} flex items-center justify-center`}>
              <selectedDim.icon className={`w-4 h-4 ${selectedDim.color}`} />
            </div>
            <div>
              <span className="text-sm font-medium text-white">{selectedDim.label} AI 日报</span>
              {(loading || approvalLoading) && <span className="text-xs text-zinc-600 ml-2">加载中...</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 日期选择器 */}
            <div className="flex items-center gap-1 bg-zinc-900 rounded-lg p-1">
              <button onClick={() => changeDate(-1)} className="p-1.5 hover:bg-zinc-800 rounded-md">
                <ChevronLeft className="w-3.5 h-3.5 text-zinc-400" />
              </button>
              <div className="flex items-center gap-1.5 px-2 py-1">
                <Calendar className={`w-3.5 h-3.5 ${selectedDim.color}`} />
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setCurrentTabDate(e.target.value)}
                  className="bg-transparent text-xs text-white focus:outline-none w-24"
                />
              </div>
              <button onClick={() => changeDate(1)} className="p-1.5 hover:bg-zinc-800 rounded-md">
                <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />
              </button>
            </div>
            {/* 刷新按钮 */}
            <button
              onClick={generateReport}
              disabled={generating}
              className={`flex items-center gap-1.5 px-3 py-1.5 ${selectedDim.bgColor} hover:opacity-80 border ${selectedDim.borderColor} rounded-lg text-xs ${selectedDim.color} transition-colors disabled:opacity-50`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${generating ? "animate-spin" : ""}`} />
              {generating ? "生成中..." : "刷新"}
            </button>
          </div>
        </div>

        {/* Coming Soon 维度 */}
        {false ? (
          <div className="text-center py-16 bg-zinc-900/30 rounded-xl border border-zinc-800">
            <div className={`w-16 h-16 rounded-full ${selectedDim.bgColor} flex items-center justify-center mx-auto mb-4`}>
              <selectedDim.icon className={`w-8 h-8 ${selectedDim.color}`} />
            </div>
            <h3 className="text-lg font-medium text-zinc-400 mb-2">{selectedDim.label}日报</h3>
            <p className="text-sm text-zinc-600 mb-4">即将上线</p>
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800/50 rounded-lg text-sm text-zinc-500">
              <Clock className="w-4 h-4" />Coming Soon
            </div>
          </div>
        ) : selectedDimension === "chat" ? (
          /* ===== 聊天日报 - 新布局 ===== */
          <div className="space-y-4">
            {/* 统计卡片 4个 */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: MessageSquare, label: "消息总数", value: reportV2?.chat?.total_messages || 0, color: "text-blue-400" },
                { icon: CheckCircle2, label: "决策", value: reportV2?.chat?.all_decisions?.length || 0, color: "text-green-400" },
                { icon: ListTodo, label: "待办事项", value: reportV2?.chat?.all_action_items?.length || 0, color: "text-amber-400" },
                { icon: AlertTriangle, label: "风险提醒", value: reportV2?.chat?.all_risks?.length || 0, color: "text-red-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{loading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>

            {loading ? (
              <div className="p-5 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse"><div className="h-6 w-48 bg-zinc-800 rounded mb-4" /><div className="h-20 bg-zinc-800/50 rounded" /></div>
            ) : reportV2?.chat?.total_messages ? (
              <>
                {/* AI 全局摘要 */}
                {reportV2.chat.global_summary && (
                  <div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/10">
                    <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-2"><Sparkles className="w-3 h-3" />AI 摘要</div>
                    <p className="text-sm text-zinc-300 leading-relaxed">{reportV2.chat.global_summary}</p>
                  </div>
                )}

                {/* 四宫格：风险/待办/决策/活跃群组 */}
                <div className="grid grid-cols-2 gap-4">
                  {/* 红色：风险提醒 */}
                  <div className="p-4 bg-red-500/5 rounded-lg border border-red-500/10">
                    <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-3">
                      <AlertTriangle className="w-3.5 h-3.5" />待跟进风险 ({reportV2.chat.all_risks?.length || 0})
                    </div>
                    {reportV2.chat.all_risks?.length ? (
                      <ul className="space-y-2">
                        {reportV2.chat.all_risks.slice(0, 5).map((r: {content: string; source: string; chat_id: string}, i: number) => (
                          <li key={i} className="text-sm text-zinc-300">
                            • {r.content}
                            <button onClick={() => openPanel("chat", r.chat_id, r.source, date)} className="ml-2 text-xs text-red-400/60 hover:text-red-400 cursor-pointer">[{r.source}]</button>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-xs text-zinc-600">暂无风险提醒</p>}
                  </div>

                  {/* 黄色：待办事项 */}
                  <div className="p-4 bg-amber-500/5 rounded-lg border border-amber-500/10">
                    <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-3">
                      <ListTodo className="w-3.5 h-3.5" />待办事项 ({reportV2.chat.all_action_items?.length || 0})
                    </div>
                    {reportV2.chat.all_action_items?.length ? (
                      <ul className="space-y-2">
                        {reportV2.chat.all_action_items.slice(0, 5).map((a: {content: string; source: string; chat_id: string}, i: number) => (
                          <li key={i} className="text-sm text-zinc-300">
                            • {a.content}
                            <button onClick={() => openPanel("chat", a.chat_id, a.source, date)} className="ml-2 text-xs text-amber-400/60 hover:text-amber-400 cursor-pointer">[{a.source}]</button>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-xs text-zinc-600">暂无待办事项</p>}
                  </div>

                  {/* 绿色：重要决策 */}
                  <div className="p-4 bg-green-500/5 rounded-lg border border-green-500/10">
                    <div className="flex items-center gap-2 text-xs text-green-400 font-mono mb-3">
                      <CheckCircle2 className="w-3.5 h-3.5" />重要决策 ({reportV2.chat.all_decisions?.length || 0})
                    </div>
                    {reportV2.chat.all_decisions?.length ? (
                      <ul className="space-y-2">
                        {reportV2.chat.all_decisions.slice(0, 5).map((d: {content: string; source: string; chat_id: string}, i: number) => (
                          <li key={i} className="text-sm text-zinc-300">
                            • {d.content}
                            <button onClick={() => openPanel("chat", d.chat_id, d.source, date)} className="ml-2 text-xs text-green-400/60 hover:text-green-400 cursor-pointer">[{d.source}]</button>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-xs text-zinc-600">暂无重要决策</p>}
                  </div>

                  {/* 蓝色：活跃群组 */}
                  <div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/10">
                    <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-3">
                      <Users className="w-3.5 h-3.5" />活跃群组 ({reportV2.chat.total_chats || 0})
                    </div>
                    {reportV2.chat.active_chats?.length ? (
                      <div className="space-y-2">
                        {reportV2.chat.active_chats.map((c: {name: string; count: number; chat_id: string}, i: number) => (
                          <button key={i} onClick={() => openPanel("chat", c.chat_id, c.name, `${c.count} 条消息`)} className="flex items-center justify-between p-2 bg-zinc-800/30 rounded-lg hover:bg-zinc-800/50 transition-colors w-full text-left">
                            <span className="text-sm text-zinc-300">{c.name}</span>
                            <span className="text-xs text-blue-400">{c.count} 条</span>
                          </button>
                        ))}
                      </div>
                    ) : <p className="text-xs text-zinc-600">暂无活跃群组</p>}
                  </div>
                </div>

                {/* 群聊详情折叠区 */}
                {reportV2.chat.summaries?.length > 0 && (
                  <CollapsibleSection title="群聊详情" icon={MessageSquare} count={reportV2.chat.summaries.length} color="blue" defaultOpen={false}>
                    <div className="space-y-3 mt-3">
                      {reportV2.chat.summaries.map((chat: {chat_id: string; chat_name: string; message_count: number; summary: string; topics?: string[]}, idx: number) => (
                        <div key={idx} className="p-4 bg-zinc-800/30 rounded-lg">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <MessageSquare className="w-4 h-4 text-blue-400" />
                              <span className="font-medium text-white">{chat.chat_name}</span>
                              <span className="text-xs text-zinc-500">{chat.message_count} 条</span>
                            </div>
                            <button onClick={() => openPanel("chat", chat.chat_id, chat.chat_name, `${chat.message_count} 条消息`)} className="text-xs text-zinc-500 hover:text-blue-400 cursor-pointer">查看详情 →</button>
                          </div>
                          {chat.summary && <p className="text-sm text-zinc-400">{chat.summary}</p>}
                          {chat.topics && chat.topics.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {chat.topics.map((t: string, i: number) => <span key={i} className="px-2 py-0.5 bg-blue-500/10 text-blue-300 text-xs rounded">{t}</span>)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </CollapsibleSection>
                )}
              </>
            ) : (
              <div className="text-center py-12 bg-zinc-900/30 rounded-xl border border-zinc-800">
                <MessageSquare className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
                <p className="text-zinc-500">暂无 {date} 的聊天数据</p>
                <p className="text-xs text-zinc-600 mt-2">点击「刷新」获取数据</p>
              </div>
            )}
          </div>
        ) : selectedDimension === "email" ? (
          /* ===== 邮件日报 ===== */
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: Mail, label: "收到邮件", value: emailData?.received || 0, color: "text-blue-400" },
                { icon: Send, label: "发送邮件", value: emailData?.sent || 0, color: "text-green-400" },
                { icon: Star, label: "重要邮件", value: emailData?.important || 0, color: "text-yellow-400" },
                { icon: Users, label: "外部邮件", value: emailData?.external_count || 0, color: "text-amber-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{loading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>
            <div className="p-4 bg-amber-500/5 rounded-lg border border-amber-500/10">
              <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-2"><Sparkles className="w-3 h-3" />AI 摘要</div>
              <p className="text-sm text-zinc-300 leading-relaxed">{emailAI?.summary || "暂无摘要，点击「生成日报」获取 AI 分析"}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-blue-500/5 rounded-lg border border-blue-500/10">
                <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-2"><ListTodo className="w-3 h-3" />待办事项 ({emailAI?.action_items?.length || 0})</div>
                {emailAI?.action_items?.length ? (<ul className="space-y-1">{emailAI.action_items.map((item, i) => <li key={i} className="text-xs text-zinc-400">• {item}</li>)}</ul>) : <p className="text-xs text-zinc-600">暂无待办事项</p>}
              </div>
              <div className="p-3 bg-red-500/5 rounded-lg border border-red-500/10">
                <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-2"><AlertTriangle className="w-3 h-3" />紧急事项 ({toArray(emailAI?.urgent_matters).length})</div>
                {toArray(emailAI?.urgent_matters).length ? (<ul className="space-y-1">{toArray(emailAI?.urgent_matters).map((item, i) => <li key={i} className="text-xs text-zinc-400">• {item}</li>)}</ul>) : <p className="text-xs text-zinc-600">暂无紧急事项</p>}
              </div>
              <div className="p-3 bg-yellow-500/5 rounded-lg border border-yellow-500/10">
                <div className="flex items-center gap-2 text-xs text-yellow-400 font-mono mb-2"><Star className="w-3 h-3" />重要客户 ({toArray(emailAI?.vip_updates).length})</div>
                {toArray(emailAI?.vip_updates).length ? (<ul className="space-y-1">{toArray(emailAI?.vip_updates).map((item, i) => <li key={i} className="text-xs text-zinc-400">• {item}</li>)}</ul>) : <p className="text-xs text-zinc-600">暂无 VIP 客户更新</p>}
              </div>
              <div className="p-3 bg-purple-500/5 rounded-lg border border-purple-500/10">
                <div className="text-xs text-purple-400 font-mono mb-2">关键话题 ({emailAI?.key_topics?.length || 0})</div>
                {emailAI?.key_topics?.length ? (<div className="flex flex-wrap gap-1">{emailAI.key_topics.map((topic, i) => <span key={i} className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-xs rounded">{topic}</span>)}</div>) : <p className="text-xs text-zinc-600">暂无关键话题</p>}
              </div>
            </div>
            {/* VIP 邮件列表 - 可点击跳转 */}
            {emailData?.vip_emails && emailData.vip_emails.length > 0 && (
              <div className="p-4 bg-yellow-500/5 rounded-xl border border-yellow-500/10">
                <div className="flex items-center gap-2 text-xs text-yellow-400 font-mono mb-3"><Star className="w-3 h-3" />VIP 邮件 ({emailData.vip_emails.length})</div>
                <div className="space-y-2">
                  {emailData.vip_emails.slice(0, 5).map((email, idx) => (
                    <Link key={idx} href={`/info-hub/email?email_id=${email.email_id}`} className="flex items-center justify-between p-2 bg-zinc-800/30 rounded-lg hover:bg-zinc-800/50 transition-colors">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">{email.client}</span>
                          <span className="text-sm text-zinc-300 truncate">{email.subject}</span>
                        </div>
                        <div className="text-xs text-zinc-500 mt-1">{email.from?.name || email.from?.address}</div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-zinc-600 flex-shrink-0" />
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
              <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono mb-3"><Users className="w-3 h-3" />高频联系人</div>
              {emailData?.top_contacts?.length ? (
                <div className="flex flex-wrap gap-2">
                  {emailData.top_contacts.map((contact, idx) => (
                    <Link key={idx} href={`/info-hub/email?contact=${encodeURIComponent(contact.address)}`} className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg hover:bg-zinc-800 transition-colors">
                      <div className="w-6 h-6 rounded-full bg-amber-500/10 flex items-center justify-center"><span className="text-amber-400 text-xs font-medium">{contact.name?.[0] || contact.address?.[0] || "?"}</span></div>
                      <div><div className="text-xs text-zinc-300">{contact.name || contact.address}</div><div className="text-[10px] text-zinc-600">{contact.count} 封邮件</div></div>
                    </Link>
                  ))}
                </div>
              ) : <p className="text-xs text-zinc-600">暂无联系人数据</p>}
            </div>
          </div>
        ) : selectedDimension === "projects" ? (
          /* ===== 项目日报 - 新布局 ===== */
          <div className="space-y-4">
            {/* 统计卡片 4个（精简版） */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: FolderKanban, label: "项目总数", value: projectStats?.total_projects || 0, color: "text-purple-400" },
                { icon: Clock, label: "进行中", value: projectStats?.in_progress_tasks || 0, color: "text-blue-400" },
                { icon: AlertTriangle, label: "已阻塞", value: projectStats?.blocked_tasks || 0, color: "text-red-400" },
                { icon: Bell, label: "有风险", value: projectStats?.at_risk_tasks || 0, color: "text-amber-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{loading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
              </div>
            ) : !reportV2?.projects ? (
              /* 无数据状态 */
              <div className="text-center py-16 bg-zinc-900/30 rounded-xl border border-zinc-800">
                <div className="w-16 h-16 rounded-full bg-purple-500/10 flex items-center justify-center mx-auto mb-4">
                  <FolderKanban className="w-8 h-8 text-purple-400" />
                </div>
                <h3 className="text-lg font-medium text-zinc-400 mb-2">暂无简报数据</h3>
                <p className="text-sm text-zinc-600 mb-4">点击「刷新」生成项目简报</p>
              </div>
            ) : (
              <>
                {/* AI 总结 */}
                {projectAnalysis?.summary && (
                  <div className="p-4 bg-purple-500/5 rounded-lg border border-purple-500/10">
                    <div className="flex items-center gap-2 text-xs text-purple-400 font-mono mb-2"><Sparkles className="w-3 h-3" />AI 摘要</div>
                    <p className="text-sm text-zinc-300 leading-relaxed">{projectAnalysis.summary}</p>
                  </div>
                )}

                {/* 四宫格：阻塞问题/里程碑/关注项目/负载预警 */}
                <div className="grid grid-cols-2 gap-4">
                  {/* 红色：阻塞问题 */}
                  <div className="p-4 bg-red-500/5 rounded-lg border border-red-500/10">
                    <div className="flex items-center gap-2 text-xs text-red-400 font-mono mb-3">
                      <AlertTriangle className="w-3.5 h-3.5" />阻塞问题 ({projectAnalysis?.leftover_issues?.length || 0})
                    </div>
                    {projectAnalysis?.leftover_issues?.length ? (
                      <div className="space-y-3">
                        {projectAnalysis.leftover_issues.slice(0, 3).map((issue: {issue: string; project?: string; owner: string; blocked_reason?: string; suggested_action?: string}, i: number) => (
                          <Link key={i} href={`/projects?project=${encodeURIComponent(issue.project || "")}`} className="block text-sm hover:bg-zinc-800/30 rounded p-1 -m-1 transition-colors">
                            <div className="text-zinc-300 font-medium">• {issue.issue}</div>
                            <div className="text-xs text-zinc-500 ml-3">负责: {issue.owner} {issue.project && <span className="text-red-400/60">[{issue.project}]</span>}</div>
                            {issue.suggested_action && <div className="text-xs text-green-400 ml-3">建议: {issue.suggested_action}</div>}
                          </Link>
                        ))}
                      </div>
                    ) : <p className="text-xs text-zinc-600">暂无阻塞问题</p>}
                  </div>

                  {/* 黄色：本周里程碑 */}
                  <div className="p-4 bg-amber-500/5 rounded-lg border border-amber-500/10">
                    <div className="flex items-center gap-2 text-xs text-amber-400 font-mono mb-3">
                      <Target className="w-3.5 h-3.5" />本周里程碑 ({projectAnalysis?.milestones?.length || 0})
                    </div>
                    {projectAnalysis?.milestones?.length ? (
                      <div className="space-y-2">
                        {projectAnalysis.milestones.slice(0, 4).map((m: {title: string; project: string; due_date: string; status: string; risk_level: string}, i: number) => (
                          <Link key={i} href={`/projects?project=${encodeURIComponent(m.project)}`} className="flex items-center justify-between hover:bg-zinc-800/30 rounded p-1 -m-1 transition-colors">
                            <div className="flex items-center gap-2">
                              <span className={`text-xs ${m.status === "completed" ? "text-green-400" : m.risk_level === "high" ? "text-red-400" : "text-zinc-400"}`}>
                                {m.status === "completed" ? "✓" : m.risk_level === "high" ? "⚠️" : "○"}
                              </span>
                              <span className="text-sm text-zinc-300">{m.title}</span>
                              <span className="text-xs text-amber-400/60">[{m.project}]</span>
                            </div>
                            <span className="text-xs text-zinc-500">{m.due_date}</span>
                          </Link>
                        ))}
                      </div>
                    ) : <p className="text-xs text-zinc-600">暂无里程碑</p>}
                  </div>

                  {/* 紫色：需关注项目 */}
                  <div className="p-4 bg-purple-500/5 rounded-lg border border-purple-500/10">
                    <div className="flex items-center gap-2 text-xs text-purple-400 font-mono mb-3">
                      <Eye className="w-3.5 h-3.5" />需关注项目 ({projectAnalysis?.projects_needing_attention?.length || 0})
                    </div>
                    {projectAnalysis?.projects_needing_attention?.length ? (
                      <div className="space-y-3">
                        {projectAnalysis.projects_needing_attention.slice(0, 3).map((p: {project: string; reason: string; priority: string; risk_factors?: string[]}, i: number) => (
                          <Link key={i} href={`/projects?project=${encodeURIComponent(p.project)}`} className="block text-sm hover:bg-zinc-800/30 rounded p-1 -m-1 transition-colors">
                            <div className="flex items-center gap-2">
                              <span className="text-zinc-300 font-medium">• {p.project}</span>
                              <span className={`text-xs px-1.5 py-0.5 rounded ${p.priority === "high" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400"}`}>
                                {p.priority === "high" ? "高" : "中"}
                              </span>
                            </div>
                            <div className="text-xs text-zinc-500 ml-3">{p.reason}</div>
                          </Link>
                        ))}
                      </div>
                    ) : <p className="text-xs text-zinc-600">暂无需关注项目</p>}
                  </div>

                  {/* 蓝色：负载预警 */}
                  <div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/10">
                    <div className="flex items-center gap-2 text-xs text-blue-400 font-mono mb-3">
                      <Users className="w-3.5 h-3.5" />负载预警 ({projectAnalysis?.workload_warnings?.length || 0})
                    </div>
                    {projectAnalysis?.workload_warnings?.length ? (
                      <div className="space-y-3">
                        {projectAnalysis.workload_warnings.slice(0, 3).map((w: {person: string; warning: string; task_count: number; deadline_pressure?: string}, i: number) => (
                          <div key={i} className="text-sm">
                            <div className="flex items-center gap-2">
                              <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center text-xs text-white">
                                {w.person.charAt(0)}
                              </div>
                              <span className="text-zinc-300">{w.person}</span>
                              <span className="text-xs text-red-400">{w.task_count}个任务</span>
                            </div>
                            {w.deadline_pressure && <div className="text-xs text-zinc-500 ml-8">{w.deadline_pressure}</div>}
                          </div>
                        ))}
                      </div>
                    ) : <p className="text-xs text-zinc-600">暂无负载预警</p>}
                  </div>
                </div>

                {/* 详情折叠区 */}
                <CollapsibleSection title="资源分配详情" icon={Users} count={projectAnalysis?.resource_allocation?.length || 0} color="blue" defaultOpen={false}>
                  {projectAnalysis?.resource_allocation?.length ? (
                    <div className="space-y-2 mt-3">
                      {projectAnalysis.resource_allocation.map((r: {person: string; projects?: string[]; task_count: number; overloaded?: boolean}, i: number) => (
                        <div key={i} className="flex items-center justify-between p-3 bg-zinc-800/30 rounded-lg">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center text-sm text-white">
                              {r.person.charAt(0)}
                            </div>
                            <div>
                              <div className="text-sm text-white">{r.person}</div>
                              <div className="text-xs text-zinc-500">{r.projects?.join(", ")}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-400">{r.task_count}个任务</span>
                            {r.overloaded && <span className="text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded">过载</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : <div className="text-sm text-zinc-500 mt-2">暂无资源分配数据</div>}
                </CollapsibleSection>

                {projectAnalysis?.cross_department_risks && projectAnalysis.cross_department_risks.length > 0 && (
                  <CollapsibleSection title="跨部门协作风险" icon={GitBranch} count={projectAnalysis.cross_department_risks.length} color="green" defaultOpen={false}>
                    <div className="space-y-2 mt-3">
                      {projectAnalysis.cross_department_risks.map((cr: {risk: string; involved_projects?: string[]; involved_people?: string[]; mitigation?: string}, i: number) => (
                        <div key={i} className="p-3 bg-zinc-800/30 rounded-lg">
                          <div className="text-sm text-white mb-2">{cr.risk}</div>
                          <div className="text-xs text-zinc-500">涉及: {cr.involved_projects?.join(", ")} | {cr.involved_people?.join(", ")}</div>
                          {cr.mitigation && <div className="text-xs text-green-400 mt-1">建议: {cr.mitigation}</div>}
                        </div>
                      ))}
                    </div>
                  </CollapsibleSection>
                )}

                {/* 生成时间 */}
                <div className="flex items-center justify-end pt-2">
                  <div className="text-[10px] text-zinc-600">
                    生成时间: {reportV2?.projects?.generated_at ? new Date(reportV2.projects.generated_at).toLocaleString("zh-CN") : "-"}
                  </div>
                </div>
              </>
            )}
          </div>
        ) : selectedDimension === "approval" ? (
          /* ===== 审批日报 ===== */
          <div className="space-y-4">
            {/* 统计卡片 */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: FileText, label: "总审批", value: approvalData?.total || 0, color: "text-emerald-400" },
                { icon: Clock, label: "待处理", value: approvalData?.pending || approvalData?.by_status?.PENDING || 0, color: "text-amber-400" },
                { icon: CheckCircle2, label: "已通过", value: approvalData?.by_status?.APPROVED || 0, color: "text-green-400" },
                { icon: XCircle, label: "已拒绝", value: approvalData?.by_status?.REJECTED || 0, color: "text-red-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{loading ? "-" : stat.value}</div>
                  </div>
                );
              })}
            </div>

            {/* AI 摘要 - 简化版 */}
            <div className="p-4 bg-emerald-500/5 rounded-lg border border-emerald-500/10">
              <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono mb-2"><Sparkles className="w-3 h-3" />审批概览</div>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {approvalData?.total ? `共 ${approvalData.total} 条审批记录，${approvalData.pending || 0} 条待处理` : "暂无审批数据"}
              </p>
            </div>

            {/* 按状态分布 */}
            {approvalData?.by_status && Object.keys(approvalData.by_status).length > 0 && (
              <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono mb-3"><FileCheck className="w-3 h-3" />按状态分布</div>
                <div className="grid grid-cols-4 gap-2">
                  {Object.entries(approvalData.by_status).map(([status, count]) => {
                    const config = APPROVAL_STATUS_CONFIG[status] || { label: status, color: "text-zinc-400", bgColor: "bg-zinc-500/10" };
                    return (
                      <div key={status} className={`p-2 ${config.bgColor} rounded-lg text-center`}>
                        <div className={`text-lg font-bold ${config.color}`}>{count as number}</div>
                        <div className="text-[10px] text-zinc-500">{config.label}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 审批列表 */}
            <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono"><FileText className="w-3 h-3" />最近审批 ({approvalList.length})</div>
                <Link href="/info-hub/approval" className="text-xs text-emerald-400 hover:underline">查看全部 →</Link>
              </div>
              {approvalLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-zinc-800/50 rounded-lg animate-pulse" />)}
                </div>
              ) : approvalList.length > 0 ? (
                <div className="space-y-2">
                  {approvalList.slice(0, 5).map((approval) => {
                    const statusConfig = APPROVAL_STATUS_CONFIG[approval.status] || APPROVAL_STATUS_CONFIG.PENDING;
                    const StatusIcon = statusConfig.icon;
                    return (
                      <div key={approval.instance_code} className="flex items-center justify-between p-3 bg-zinc-800/30 rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg ${statusConfig.bgColor} flex items-center justify-center`}>
                            <FileText className={`w-4 h-4 ${statusConfig.color}`} />
                          </div>
                          <div>
                            <div className="text-sm text-zinc-300">{approval.approval_name}</div>
                            <div className="text-[10px] text-zinc-600">#{approval.serial_number} · {formatTime(approval.start_time)}</div>
                          </div>
                        </div>
                        <div className={`flex items-center gap-1 px-2 py-1 rounded ${statusConfig.bgColor}`}>
                          <StatusIcon className={`w-3 h-3 ${statusConfig.color}`} />
                          <span className={`text-xs ${statusConfig.color}`}>{statusConfig.label}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileCheck className="w-10 h-10 mx-auto mb-2 text-zinc-700" />
                  <p className="text-xs text-zinc-600">暂无审批记录</p>
                </div>
              )}
            </div>
          </div>
        ) : selectedDimension === "people" ? (
          /* ===== 人员日报 ===== */
          <div className="space-y-4">
            {/* 统计卡片 */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { icon: Users, label: "总人数", value: peopleData?.total || 0, color: "text-rose-400" },
                { icon: TrendingUp, label: "活跃人员", value: peopleData?.active || 0, color: "text-green-400" },
                { icon: Building, label: "部门", value: 0, color: "text-blue-400" },
                { icon: Briefcase, label: "职能", value: 4, color: "text-purple-400" },
              ].map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div key={idx} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${stat.color}`} /><span className="text-xs text-zinc-500">{stat.label}</span></div>
                    <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                  </div>
                );
              })}
            </div>
            {/* 提示跳转到详情页 */}
            <div className="p-4 bg-rose-500/5 rounded-lg border border-rose-500/10">
              <div className="flex items-center gap-2 text-xs text-rose-400 font-mono mb-2"><Sparkles className="w-3 h-3" />人员活跃度</div>
              <p className="text-sm text-zinc-300 leading-relaxed mb-3">共 {peopleData?.total || 0} 名员工，近7日 {peopleData?.active || 0} 人有邮件活动</p>
              <Link href={`/info-hub/daily-report/people?date=${date}`} className="inline-flex items-center gap-2 px-3 py-1.5 bg-rose-500/10 text-rose-400 rounded-lg text-sm hover:bg-rose-500/20 transition-colors">
                <Users className="w-4 h-4" />查看人员详情 →
              </Link>
            </div>
          </div>

        ) : null}
      </div>

      {/* 侧滑面板 */}
      <SlideOverPanel
        open={panel.type !== null}
        onClose={closePanel}
        title={panel.title}
        subtitle={panel.subtitle}
        width="md"
        externalLink={panel.type === "chat" && panel.id ? `/info-hub/chat?chat_id=${panel.id}` : panel.type === "email" && panel.id ? `/info-hub/email?id=${panel.id}` : undefined}
      >
        {panel.type === "chat" && panel.id && (
          <ChatPanelContent chatId={panel.id} date={date} />
        )}
        {panel.type === "email" && panel.id && (
          <EmailPanelContent emailId={panel.id} />
        )}
      </SlideOverPanel>
    </div>
  );
}

// 导出组件，用 Suspense 包装
export default function DailyReportPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-black flex items-center justify-center"><div className="text-zinc-500">加载中...</div></div>}>
      <DailyReportContent />
    </Suspense>
  );
}
