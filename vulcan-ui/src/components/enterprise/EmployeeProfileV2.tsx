"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User, Briefcase, Target, AlertTriangle, TrendingUp,
  Users, Building, ChevronDown, ChevronRight, Shield,
  Lightbulb, Clock, MessageSquare, Network, Award,
  AlertCircle, CheckCircle, HelpCircle, Loader2, RefreshCw
} from 'lucide-react';

// Schema V2 类型定义
export interface ProfileV2 {
  meta: {
    employee_name: string;
    analysis_scope: {
      date_range: string;
      confidence_level: string;
    };
  };
  executive_summary: {
    one_liner: string;
    inferred_role: {
      title: string;
      confidence: number;
      evidence: string;
    };
    core_value: string;
    key_strengths: string[];
    attention_flags: string[];
  };
  competency_profile: {
    domain_expertise: Array<{
      domain: string;
      proficiency: string;
      evidence_summary: string;
      example_quote: string;
    }>;
    soft_skills: {
      communication: {
        style: string;
        effectiveness: string;
        patterns: string[];
      };
      coordination: {
        capability: string;
        scope: string;
        evidence: string;
      };
      problem_solving: {
        approach: string;
        example: string;
      };
    };
  };
  work_patterns: {
    communication_habits: {
      response_style: string;
      active_periods: string;
      preferred_approach: string;
    };
    project_involvement: Array<{
      project_name: string;
      role: string;
      contribution: string;
      status: string;
    }>;
    decision_style: {
      type: string;
      evidence: string;
    };
  };
  relationship_network: {
    internal: {
      core_collaborators: Array<{
        name: string;
        inferred_relationship: string;
        interaction_nature: string;
        frequency: string;
      }>;
      cross_department: string[];
    };
    external: {
      key_contacts: Array<{
        company: string;
        contact_name: string;
        relationship_type: string;
        relationship_depth: string;
        context: string;
      }>;
    };
    network_position: string;
  };
  management_insights: {
    motivation_drivers: {
      observed_drivers: string[];
      management_approach: string;
    };
    development_suggestions: Array<{
      area: string;
      current_state: string;
      recommendation: string;
    }>;
    task_fit: {
      ideal_tasks: Array<{ task_type: string; reason: string }>;
      avoid_tasks: Array<{ task_type: string; reason: string }>;
    };
    risk_indicators: {
      turnover_risk: { level: string; signals: string[] };
      performance_concerns: { level: string; signals: string[] };
    };
  };
  discoveries: {
    interesting_findings: Array<{
      finding: string;
      significance: string;
      evidence: string;
    }>;
    hypotheses: Array<{
      claim: string;
      supporting_evidence: string;
      confidence: number;
      verification_suggestion: string;
    }>;
    anomalies: Array<{
      anomaly: string;
      possible_explanation: string;
      recommended_action: string;
    }>;
  };
  evidence_appendix?: {
    key_emails: Array<{
      subject: string;
      summary: string;
      insights: string[];
    }>;
  };
}

interface Props {
  data: ProfileV2 | null;
  isLoading: boolean;
  onRefresh?: () => void;
  employeeName?: string;
  employeeEmail?: string;
}

// 折叠Section组件
const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  badge?: React.ReactNode;
}> = ({ title, icon, defaultOpen = false, children, badge }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="text-cyan-400">{icon}</div>
          <span className="font-medium text-white">{title}</span>
          {badge}
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-4 bg-zinc-900/30">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// 风险等级Badge
const RiskBadge: React.FC<{ level: string }> = ({ level }) => {
  const getColor = (l: string) => {
    if (l === '低') return 'bg-green-500/20 text-green-400 border-green-500/30';
    if (l === '高') return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded border ${getColor(level)}`}>
      {level}
    </span>
  );
};

// 熟练度Badge
const ProficiencyBadge: React.FC<{ level: string }> = ({ level }) => {
  const getColor = (l: string) => {
    if (l === '专家') return 'bg-purple-500/20 text-purple-400';
    if (l === '熟练') return 'bg-blue-500/20 text-blue-400';
    return 'bg-zinc-500/20 text-zinc-400';
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded ${getColor(level)}`}>
      {level}
    </span>
  );
};

export const EmployeeProfileV2: React.FC<Props> = ({
  data,
  isLoading,
  onRefresh,
  employeeName,
  employeeEmail
}) => {
  // Loading状态
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mb-4" />
        <p className="text-zinc-400">正在分析员工邮件数据...</p>
        <p className="text-zinc-600 text-sm mt-2">预计需要1-2分钟</p>
      </div>
    );
  }

  // 无数据状态
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <User className="w-12 h-12 text-zinc-700 mb-4" />
        <p className="text-zinc-400 mb-4">暂无画像数据</p>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-4 py-2 bg-cyan-500/20 text-cyan-400 rounded-lg hover:bg-cyan-500/30 transition-colors flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            生成画像
          </button>
        )}
      </div>
    );
  }

  const { executive_summary, competency_profile, work_patterns, relationship_network, management_insights, discoveries } = data;

  return (
    <div className="space-y-4 p-4">
      {/* 头部：Executive Summary */}
      <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/20 rounded-xl p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-white">{data.meta?.employee_name || employeeName}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-cyan-400">{executive_summary?.inferred_role?.title}</span>
              <span className="text-zinc-600">|</span>
              <span className="text-zinc-500 text-sm">置信度 {Math.round((executive_summary?.inferred_role?.confidence || 0) * 100)}%</span>
            </div>
          </div>
          {onRefresh && (
            <button onClick={onRefresh} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
              <RefreshCw className="w-4 h-4 text-zinc-500" />
            </button>
          )}
        </div>

        {/* 一句话定位 */}
        <p className="text-white/90 text-lg leading-relaxed mb-4 border-l-2 border-cyan-500 pl-3">
          {executive_summary?.one_liner}
        </p>

        {/* 核心价值 */}
        <div className="bg-zinc-900/50 rounded-lg p-3 mb-4">
          <div className="text-xs text-zinc-500 mb-1">核心价值</div>
          <p className="text-zinc-300 text-sm">{executive_summary?.core_value}</p>
        </div>

        {/* 强项 & 注意事项 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-green-400 mb-2 flex items-center gap-1">
              <CheckCircle className="w-3 h-3" /> 关键强项
            </div>
            <div className="space-y-1">
              {executive_summary?.key_strengths?.map((s, i) => (
                <div key={i} className="text-sm text-zinc-300 flex items-start gap-2">
                  <span className="text-green-400 mt-1">•</span> {s}
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-amber-400 mb-2 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" /> 需要关注
            </div>
            <div className="space-y-1">
              {executive_summary?.attention_flags?.map((s, i) => (
                <div key={i} className="text-sm text-zinc-300 flex items-start gap-2">
                  <span className="text-amber-400 mt-1">•</span> {s}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 能力画像 */}
      <Section title="能力画像" icon={<Award className="w-4 h-4" />} defaultOpen={true}>
        <div className="space-y-4">
          <div className="text-xs text-zinc-500 mb-2">专业领域</div>
          {competency_profile?.domain_expertise?.map((exp, i) => (
            <div key={i} className="bg-zinc-800/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-medium">{exp.domain}</span>
                <ProficiencyBadge level={exp.proficiency} />
              </div>
              <p className="text-zinc-400 text-sm mb-2">{exp.evidence_summary}</p>
              {exp.example_quote && (
                <div className="text-xs text-zinc-500 italic border-l-2 border-zinc-700 pl-2">
                  &quot;{exp.example_quote}&quot;
                </div>
              )}
            </div>
          ))}

          <div className="text-xs text-zinc-500 mt-4 mb-2">软技能</div>
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">沟通能力</div>
              <div className="text-white text-sm">{competency_profile?.soft_skills?.communication?.style}</div>
              <div className="text-xs text-cyan-400 mt-1">效果: {competency_profile?.soft_skills?.communication?.effectiveness}</div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">协调能力</div>
              <div className="text-white text-sm">{competency_profile?.soft_skills?.coordination?.scope}</div>
              <div className="text-xs text-cyan-400 mt-1">{competency_profile?.soft_skills?.coordination?.capability}</div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">问题解决</div>
              <div className="text-white text-sm">{competency_profile?.soft_skills?.problem_solving?.approach}</div>
            </div>
          </div>
        </div>
      </Section>

      {/* 工作模式 */}
      <Section title="工作模式" icon={<Clock className="w-4 h-4" />}>
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">响应风格</div>
              <div className="text-white text-sm">{work_patterns?.communication_habits?.response_style}</div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">活跃时段</div>
              <div className="text-white text-sm">{work_patterns?.communication_habits?.active_periods}</div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">决策风格</div>
              <div className="text-white text-sm">{work_patterns?.decision_style?.type}</div>
            </div>
          </div>

          <div className="text-xs text-zinc-500 mt-4 mb-2">参与项目</div>
          <div className="space-y-2">
            {work_patterns?.project_involvement?.map((proj, i) => (
              <div key={i} className="flex items-center justify-between bg-zinc-800/50 rounded-lg p-3">
                <div>
                  <span className="text-white">{proj.project_name}</span>
                  <span className="text-zinc-500 text-sm ml-2">- {proj.contribution}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-cyan-400">{proj.role}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${proj.status === '进行中' ? 'bg-blue-500/20 text-blue-400' : 'bg-green-500/20 text-green-400'}`}>
                    {proj.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* 关系网络 */}
      <Section title="关系网络" icon={<Network className="w-4 h-4" />}>
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-zinc-500">网络定位:</span>
            <span className="text-sm text-cyan-400">{relationship_network?.network_position}</span>
          </div>

          <div className="text-xs text-zinc-500 mb-2">内部协作</div>
          <div className="space-y-2">
            {relationship_network?.internal?.core_collaborators?.map((c, i) => (
              <div key={i} className="flex items-center justify-between bg-zinc-800/50 rounded-lg p-2">
                <span className="text-white">{c.name}</span>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-zinc-400">{c.inferred_relationship}</span>
                  <span className="text-cyan-400">{c.interaction_nature}</span>
                  <span className="text-zinc-500">{c.frequency}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="text-xs text-zinc-500 mt-4 mb-2">外部联系</div>
          <div className="space-y-2">
            {relationship_network?.external?.key_contacts?.map((c, i) => (
              <div key={i} className="bg-zinc-800/50 rounded-lg p-2">
                <div className="flex items-center justify-between">
                  <span className="text-white">{c.company}</span>
                  <span className="text-xs text-cyan-400">{c.relationship_type}</span>
                </div>
                <div className="text-xs text-zinc-500 mt-1">{c.context}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* 管理建议 */}
      <Section
        title="管理建议"
        icon={<Target className="w-4 h-4" />}
        badge={
          management_insights?.risk_indicators?.turnover_risk?.level === '高' ? (
            <span className="ml-2 px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded">离职风险高</span>
          ) : null
        }
      >
        <div className="space-y-4">
          {/* 管理方式 */}
          <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-lg p-3">
            <div className="text-xs text-cyan-400 mb-1">建议管理方式</div>
            <p className="text-white text-sm">{management_insights?.motivation_drivers?.management_approach}</p>
          </div>

          {/* 风险指标 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">离职风险</span>
                <RiskBadge level={management_insights?.risk_indicators?.turnover_risk?.level || '低'} />
              </div>
              <div className="space-y-1">
                {management_insights?.risk_indicators?.turnover_risk?.signals?.map((s, i) => (
                  <div key={i} className="text-xs text-zinc-400">• {s}</div>
                ))}
              </div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">绩效风险</span>
                <RiskBadge level={management_insights?.risk_indicators?.performance_concerns?.level || '低'} />
              </div>
              <div className="space-y-1">
                {management_insights?.risk_indicators?.performance_concerns?.signals?.map((s, i) => (
                  <div key={i} className="text-xs text-zinc-400">• {s}</div>
                ))}
              </div>
            </div>
          </div>

          {/* 任务匹配 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-green-400 mb-2">适合任务</div>
              {management_insights?.task_fit?.ideal_tasks?.map((t, i) => (
                <div key={i} className="text-sm text-zinc-300 mb-1">
                  <span className="text-green-400 mr-1">✓</span> {t.task_type}
                </div>
              ))}
            </div>
            <div>
              <div className="text-xs text-red-400 mb-2">避免任务</div>
              {management_insights?.task_fit?.avoid_tasks?.map((t, i) => (
                <div key={i} className="text-sm text-zinc-300 mb-1">
                  <span className="text-red-400 mr-1">✗</span> {t.task_type}
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* 发现与假设 */}
      <Section title="发现与假设" icon={<Lightbulb className="w-4 h-4" />}>
        <div className="space-y-4">
          {discoveries?.interesting_findings?.map((f, i) => (
            <div key={i} className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-white text-sm mb-1">{f.finding}</div>
              <div className="text-xs text-cyan-400">{f.significance}</div>
            </div>
          ))}

          {discoveries?.hypotheses && discoveries.hypotheses.length > 0 && (
            <>
              <div className="text-xs text-zinc-500 mt-4 mb-2">待验证假设</div>
              {discoveries.hypotheses.map((h, i) => (
                <div key={i} className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-white text-sm">{h.claim}</span>
                    <span className="text-xs text-amber-400">置信度 {Math.round(h.confidence * 100)}%</span>
                  </div>
                  <div className="text-xs text-zinc-400">验证方式: {h.verification_suggestion}</div>
                </div>
              ))}
            </>
          )}

          {discoveries?.anomalies && discoveries.anomalies.length > 0 && (
            <>
              <div className="text-xs text-zinc-500 mt-4 mb-2">异常发现</div>
              {discoveries.anomalies.map((a, i) => (
                <div key={i} className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <div className="text-white text-sm mb-1">{a.anomaly}</div>
                  <div className="text-xs text-zinc-400">建议: {a.recommended_action}</div>
                </div>
              ))}
            </>
          )}
        </div>
      </Section>

      {/* 分析范围 */}
      <div className="text-xs text-zinc-600 text-center mt-4">
        分析范围: {data.meta?.analysis_scope?.date_range} | 置信度: {data.meta?.analysis_scope?.confidence_level}
      </div>
    </div>
  );
};

export default EmployeeProfileV2;
