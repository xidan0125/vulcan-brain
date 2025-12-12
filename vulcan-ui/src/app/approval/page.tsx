"use client";

import { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  FileCheck, Clock, CheckCircle2, XCircle,
  ChevronDown, ChevronRight,
  Calendar, User, RefreshCw
} from "lucide-react";

// ==================== Types ====================
interface Approval {
  _id: string;
  type: string;
  type_name: string;
  status: "pending" | "approved" | "rejected" | "canceled";
  applicant_id: string;
  applicant_name: string;
  form_data: {
    title?: string;
    content?: string;
    amount?: number;
    reason?: string;
    [key: string]: any;
  };
  created_at: string;
  updated_at: string;
  approval_records: Array<{
    action: string;
    operator_id: string;
    operator_name: string;
    comment?: string;
    timestamp: string;
  }>;
}

interface Stats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  by_type: Record<string, number>;
}

// ==================== API ====================
const API_BASE = "/api/approval";

async function fetchApprovals(params?: {
  status?: string;
  limit?: number;
}): Promise<{ approvals: Approval[]; count: number }> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const res = await fetch(`${API_BASE}/list?${searchParams}`);
  return res.json();
}

async function fetchStats(days: number = 7): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats?days=${days}`);
  return res.json();
}

async function approveApproval(id: string, comment: string = ""): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approver_id: "web_admin",
      approver_name: "管理员",
      comment,
    }),
  });
  return res.json();
}

async function rejectApproval(id: string, reason: string = ""): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approver_id: "web_admin",
      approver_name: "管理员",
      reason,
    }),
  });
  return res.json();
}

// ==================== Helper Functions ====================
function getStatusConfig(status: string) {
  const configs: Record<string, { color: string; bg: string; icon: any; text: string }> = {
    pending: { color: "text-amber-400", bg: "bg-amber-500/20", icon: Clock, text: "待审批" },
    approved: { color: "text-emerald-400", bg: "bg-emerald-500/20", icon: CheckCircle2, text: "已通过" },
    rejected: { color: "text-red-400", bg: "bg-red-500/20", icon: XCircle, text: "已拒绝" },
    canceled: { color: "text-zinc-400", bg: "bg-zinc-500/20", icon: XCircle, text: "已撤销" },
  };
  return configs[status] || configs.pending;
}

function formatDate(dateStr: string) {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

// ==================== Components ====================

function StatsCard({ title, value, icon: Icon, color }: {
  title: string;
  value: number;
  icon: any;
  color: string;
}) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wider">{title}</p>
          <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
        </div>
        <div className={`p-2 rounded-lg ${color.replace("text-", "bg-").replace("-400", "-500/20")}`}>
          <Icon className={`w-5 h-5 ${color}`} />
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = getStatusConfig(status);
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.color}`}>
      <Icon className="w-3.5 h-3.5" />
      {config.text}
    </span>
  );
}

function TypeBadge({ type, typeName }: { type: string; typeName: string }) {
  const colors: Record<string, string> = {
    leave: "bg-blue-500/20 text-blue-400",
    expense: "bg-green-500/20 text-green-400",
    purchase: "bg-orange-500/20 text-orange-400",
    overtime: "bg-purple-500/20 text-purple-400",
    other: "bg-zinc-500/20 text-zinc-400",
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${colors[type] || colors.other}`}>
      {typeName}
    </span>
  );
}

// 审批操作弹窗
function ActionModal({
  isOpen,
  action,
  onClose,
  onSubmit,
  loading
}: {
  isOpen: boolean;
  action: "approve" | "reject";
  onClose: () => void;
  onSubmit: (comment: string) => void;
  loading: boolean;
}) {
  const [comment, setComment] = useState("");

  if (!isOpen) return null;

  const isApprove = action === "approve";

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className={`text-lg font-bold mb-4 ${isApprove ? "text-emerald-400" : "text-red-400"}`}>
          {isApprove ? "通过审批" : "拒绝审批"}
        </h3>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder={isApprove ? "审批意见（可选）" : "拒绝原因（可选）"}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-3 text-white text-sm resize-none h-24 focus:outline-none focus:border-zinc-600"
        />
        <div className="flex gap-3 mt-4">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-400 hover:text-white hover:border-zinc-600 transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={() => onSubmit(comment)}
            disabled={loading}
            className={`flex-1 px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 ${
              isApprove
                ? "bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"
                : "bg-red-500/20 text-red-400 hover:bg-red-500/30"
            }`}
          >
            {loading ? "处理中..." : "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}

// 审批卡片
function ApprovalCard({
  approval,
  expanded,
  onToggle,
  onApprove,
  onReject
}: {
  approval: Approval;
  expanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden hover:border-zinc-700 transition-colors">
      <div onClick={onToggle} className="p-4 cursor-pointer">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <TypeBadge type={approval.type} typeName={approval.type_name} />
              <StatusBadge status={approval.status} />
            </div>
            <h3 className="font-medium text-white truncate">
              {approval.form_data.title || `${approval.type_name}申请`}
            </h3>
            <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500">
              <span className="flex items-center gap-1">
                <User className="w-3.5 h-3.5" />
                {approval.applicant_name}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                {formatDate(approval.created_at)}
              </span>
            </div>
          </div>
          <button className="p-1 text-zinc-500">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-zinc-800 p-4 bg-zinc-800/30">
          {approval.form_data.content && (
            <div className="mb-4">
              <p className="text-xs text-zinc-500 mb-1">申请说明</p>
              <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                {approval.form_data.content}
              </p>
            </div>
          )}

          {approval.form_data.amount && (
            <div className="mb-4">
              <p className="text-xs text-zinc-500 mb-1">申请金额</p>
              <p className="text-lg font-bold text-emerald-400">
                ¥{approval.form_data.amount.toLocaleString()}
              </p>
            </div>
          )}

          {approval.approval_records && approval.approval_records.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-zinc-500 mb-2">审批记录</p>
              <div className="space-y-2">
                {approval.approval_records.map((record, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-xs">
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 ${
                      record.action === "approved" ? "bg-emerald-400" :
                      record.action === "rejected" ? "bg-red-400" : "bg-zinc-400"
                    }`} />
                    <div>
                      <span className="text-zinc-400">{record.operator_name}</span>
                      <span className={`ml-2 ${
                        record.action === "approved" ? "text-emerald-400" :
                        record.action === "rejected" ? "text-red-400" : "text-zinc-400"
                      }`}>
                        {record.action === "approved" ? "通过" :
                         record.action === "rejected" ? "拒绝" : record.action}
                      </span>
                      {record.comment && (
                        <p className="text-zinc-500 mt-0.5">{record.comment}</p>
                      )}
                      <p className="text-zinc-600 mt-0.5">{formatDate(record.timestamp)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 审批操作按钮 - 仅对待审批显示 */}
          {approval.status === "pending" && (
            <div className="flex gap-3 pt-3 border-t border-zinc-700">
              <button
                onClick={(e) => { e.stopPropagation(); onReject(); }}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <XCircle className="w-4 h-4" />
                拒绝
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onApprove(); }}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 hover:bg-emerald-500/20 transition-colors"
              >
                <CheckCircle2 className="w-4 h-4" />
                通过
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FilterBar({
  statusFilter,
  onStatusChange,
  onRefresh,
  loading
}: {
  statusFilter: string;
  onStatusChange: (status: string) => void;
  onRefresh: () => void;
  loading: boolean;
}) {
  const statuses = [
    { value: "", label: "全部" },
    { value: "pending", label: "待审批" },
    { value: "approved", label: "已通过" },
    { value: "rejected", label: "已拒绝" },
  ];

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        {statuses.map(s => (
          <button
            key={s.value}
            onClick={() => onStatusChange(s.value)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              statusFilter === s.value
                ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                : "bg-zinc-800 text-zinc-400 border border-zinc-700 hover:border-zinc-600"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
      <button
        onClick={onRefresh}
        disabled={loading}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-400 hover:text-white hover:border-zinc-600 transition-colors disabled:opacity-50"
      >
        <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        刷新
      </button>
    </div>
  );
}

// ==================== Main Page ====================
export default function ApprovalPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 弹窗状态
  const [modalOpen, setModalOpen] = useState(false);
  const [modalAction, setModalAction] = useState<"approve" | "reject">("approve");
  const [selectedApprovalId, setSelectedApprovalId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [approvalsRes, statsRes] = await Promise.all([
        fetchApprovals({ status: statusFilter || undefined, limit: 100 }),
        fetchStats(30)
      ]);
      setApprovals(approvalsRes.approvals);
      setStats(statsRes);
    } catch (error) {
      console.error("Failed to load approvals:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const handleApprove = (id: string) => {
    setSelectedApprovalId(id);
    setModalAction("approve");
    setModalOpen(true);
  };

  const handleReject = (id: string) => {
    setSelectedApprovalId(id);
    setModalAction("reject");
    setModalOpen(true);
  };

  const handleModalSubmit = async (comment: string) => {
    if (!selectedApprovalId) return;

    setActionLoading(true);
    try {
      if (modalAction === "approve") {
        await approveApproval(selectedApprovalId, comment);
      } else {
        await rejectApproval(selectedApprovalId, comment);
      }
      setModalOpen(false);
      loadData(); // 刷新列表
    } catch (error) {
      console.error("Action failed:", error);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FileCheck className="w-7 h-7 text-blue-400" />
            审批中心
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            管理和处理所有审批申请
          </p>
        </div>

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatsCard title="总计" value={stats.total} icon={FileCheck} color="text-zinc-400" />
            <StatsCard title="待审批" value={stats.pending} icon={Clock} color="text-amber-400" />
            <StatsCard title="已通过" value={stats.approved} icon={CheckCircle2} color="text-emerald-400" />
            <StatsCard title="已拒绝" value={stats.rejected} icon={XCircle} color="text-red-400" />
          </div>
        )}

        <FilterBar
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          onRefresh={loadData}
          loading={loading}
        />

        <div className="space-y-3">
          {loading && approvals.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">
              <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
              加载中...
            </div>
          ) : approvals.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">
              <FileCheck className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>暂无审批记录</p>
              <p className="text-xs mt-1">在飞书机器人中发送「发起审批」开始</p>
            </div>
          ) : (
            approvals.map(approval => (
              <ApprovalCard
                key={approval._id}
                approval={approval}
                expanded={expandedId === approval._id}
                onToggle={() => setExpandedId(expandedId === approval._id ? null : approval._id)}
                onApprove={() => handleApprove(approval._id)}
                onReject={() => handleReject(approval._id)}
              />
            ))
          )}
        </div>

        {approvals.length > 0 && (
          <div className="mt-6 text-center text-xs text-zinc-600">
            显示最近 {approvals.length} 条记录
          </div>
        )}
      </div>

      <ActionModal
        isOpen={modalOpen}
        action={modalAction}
        onClose={() => setModalOpen(false)}
        onSubmit={handleModalSubmit}
        loading={actionLoading}
      />
    </DashboardLayout>
  );
}
