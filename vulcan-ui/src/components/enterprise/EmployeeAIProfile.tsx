"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  Brain,
  Network,
  Target,
  AlertTriangle,
  Sparkles,
  Briefcase,
  Lightbulb,
  Fingerprint,
  Loader2,
  Wand2,
  X
} from 'lucide-react';

// --- 类型定义 ---
export interface EmployeeProfileData {
  name: string;
  role_guess: string;
  expertise: {
    knowledge_tags: string[];
    skills: string[];
  };
  network: {
    external_contacts: { name: string; company: string; relationship: string }[];
    internal_contacts: { name: string; interaction_type: string }[];
    key_counterparties: string[];
  };
  behavior_profile: {
    archetype: string;
    communication_style: string;
    work_patterns: string[];
  };
  task_recommendation: {
    best_fit: { task: string; reason: string }[];
    avoid: { task: string; reason: string }[];
  };
  discoveries: string[];
  hypotheses: { claim: string; evidence: string; confidence: number }[];
  anomalies: string[];
}

// --- 子组件 ---

// 可折叠区块
const Section = ({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  accentColor = "cyan"
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  accentColor?: "cyan" | "violet" | "rose" | "emerald" | "amber";
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const colorMap = {
    cyan: "text-cyan-400 group-hover:text-cyan-300",
    violet: "text-violet-400 group-hover:text-violet-300",
    rose: "text-rose-400 group-hover:text-rose-300",
    emerald: "text-emerald-400 group-hover:text-emerald-300",
    amber: "text-amber-400 group-hover:text-amber-300",
  };

  return (
    <div className="mb-4 border border-white/5 bg-zinc-900/30 rounded-xl overflow-hidden backdrop-blur-sm transition-colors hover:border-white/10">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 group cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className={`p-1.5 rounded-lg bg-white/5 ${colorMap[accentColor]}`}>
            <Icon size={16} />
          </div>
          <span className="text-sm font-semibold text-zinc-200 tracking-wide uppercase">
            {title}
          </span>
        </div>
        <ChevronDown
          size={16}
          className={`text-zinc-500 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            <div className="px-4 pb-5 pt-0 border-t border-white/5">
              <div className="pt-4 space-y-4">
                {children}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// 标签
const Tag = ({ text, type = "default" }: { text: string, type?: "knowledge" | "skill" | "pattern" | "default" }) => {
  const styles = {
    knowledge: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20",
    skill: "bg-blue-500/10 text-blue-300 border-blue-500/20",
    pattern: "bg-zinc-800 text-zinc-300 border-zinc-700",
    default: "bg-zinc-800 text-zinc-300 border-zinc-700"
  };

  return (
    <span className={`
      inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium border
      transition-all hover:scale-105 cursor-default ${styles[type]}
    `}>
      {text}
    </span>
  );
};

// 置信度进度条
const ConfidenceBar = ({ value }: { value: number }) => {
  const percentage = Math.round(value * 100);
  const colorClass = percentage > 80 ? 'from-emerald-500 to-teal-400' :
                     percentage > 60 ? 'from-cyan-500 to-blue-400' :
                     'from-amber-500 to-orange-400';

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-zinc-500 font-mono">CONFIDENCE</span>
        <span className="text-zinc-300 font-mono">{percentage}%</span>
      </div>
      <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 1, ease: "easeOut" }}
          className={`h-full bg-gradient-to-r ${colorClass} rounded-full`}
        />
      </div>
    </div>
  );
};

// --- 主组件 ---
interface EmployeeAIProfileProps {
  data: EmployeeProfileData | null;
  isLoading?: boolean;
  onGenerate?: () => void;
  onClose?: () => void;
  employeeName?: string;
  employeeEmail?: string;
}

export const EmployeeAIProfile = ({
  data,
  isLoading = false,
  onGenerate,
  onClose,
  employeeName,
  employeeEmail
}: EmployeeAIProfileProps) => {

  // 空状态：没有画像数据
  if (!data && !isLoading) {
    return (
      <div className="w-full h-full bg-zinc-950 text-zinc-100 flex flex-col border-l border-white/5">
        {/* 头部 */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">{employeeName || "员工画像"}</h2>
            <p className="text-sm text-zinc-500">{employeeEmail}</p>
          </div>
          {onClose && (
            <button onClick={onClose} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
              <X size={18} className="text-zinc-400" />
            </button>
          )}
        </div>

        {/* 空状态内容 */}
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-500/20 to-cyan-500/20 flex items-center justify-center mb-6">
            <Brain size={40} className="text-violet-400" />
          </div>
          <h3 className="text-xl font-bold text-zinc-200 mb-2">AI 员工画像</h3>
          <p className="text-sm text-zinc-500 text-center mb-6 max-w-[280px]">
            基于邮件数据，AI 将分析该员工的专业能力、人脉网络、行为模式和任务适配度
          </p>
          {onGenerate && (
            <button
              onClick={onGenerate}
              className="px-6 py-3 rounded-xl font-medium text-sm bg-gradient-to-r from-violet-600 to-cyan-600 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 hover:scale-105 transition-all duration-300 flex items-center gap-2"
            >
              <Wand2 size={18} />
              生成 AI 画像
            </button>
          )}
        </div>
      </div>
    );
  }

  // 加载状态
  if (isLoading) {
    return (
      <div className="w-full h-full bg-zinc-950 text-zinc-100 flex flex-col border-l border-white/5">
        <div className="p-6 border-b border-white/10">
          <h2 className="text-lg font-bold text-white">{employeeName || "生成中..."}</h2>
          <p className="text-sm text-zinc-500">{employeeEmail}</p>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-500/20 to-cyan-500/20 animate-pulse" />
            <Loader2 size={32} className="absolute inset-0 m-auto text-cyan-400 animate-spin" />
          </div>
          <p className="text-sm text-zinc-400 mt-6 animate-pulse">正在分析邮件数据...</p>
          <p className="text-xs text-zinc-600 mt-2">这可能需要 1-2 分钟</p>
        </div>
      </div>
    );
  }

  // 正常显示画像
  // TypeScript guard - data is guaranteed to exist at this point
  if (!data) return null;

  return (
    <div className="w-full h-full bg-zinc-950 text-zinc-100 flex flex-col border-l border-white/5 shadow-2xl overflow-hidden font-sans">

      {/* 顶部：个人信息头 */}
      <div className="relative p-6 border-b border-white/10 bg-gradient-to-b from-zinc-900 to-zinc-950 z-10 shrink-0">
        {/* 装饰性光效 */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent opacity-50" />

        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-14 h-14 rounded-full bg-zinc-800 border-2 border-white/10 flex items-center justify-center overflow-hidden">
                <span className="text-xl font-bold text-zinc-500">{data?.name?.charAt(0) || "?"}</span>
              </div>
              <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-zinc-950 rounded-full flex items-center justify-center border border-white/10">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
              </div>
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">{data.name}</h1>
              <div className="flex items-center gap-2 mt-1">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 uppercase tracking-wider">
                  AI Predicted
                </span>
              </div>
              <span className="text-sm text-zinc-400">{data.role_guess}</span>
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
              <X size={18} className="text-zinc-400" />
            </button>
          )}
        </div>
      </div>

      {/* 滚动内容区域 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2" style={{ scrollbarWidth: 'thin', scrollbarColor: '#3f3f46 transparent' }}>

        {/* Section 1: 行为画像 (核心) */}
        <div className="mb-6 mt-2 text-center">
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-2 font-mono">Behavioral Archetype</div>
          <h2 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 drop-shadow-lg">
            {data.behavior_profile.archetype}
          </h2>
          <p className="text-sm text-zinc-400 mt-2 italic">&ldquo;{data.behavior_profile.communication_style}&rdquo;</p>

          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {data.behavior_profile.work_patterns.map((pattern, i) => (
              <Tag key={i} text={pattern} type="pattern" />
            ))}
          </div>
        </div>

        {/* Section 2: AI 洞察 */}
        {data.discoveries.length > 0 && (
          <Section title="AI Discoveries" icon={Sparkles} accentColor="violet">
            <div className="space-y-3">
              {data.discoveries.map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="relative p-3 rounded-lg bg-violet-500/5 border border-violet-500/20 hover:bg-violet-500/10 transition-colors"
                >
                  <div className="absolute left-0 top-3 bottom-3 w-0.5 bg-violet-500 rounded-r-full shadow-[0_0_8px_rgba(139,92,246,0.5)]" />
                  <p className="text-sm text-zinc-200 pl-2 leading-relaxed">{item}</p>
                </motion.div>
              ))}
            </div>
          </Section>
        )}

        {/* Section 3: 假设与置信度 */}
        {data.hypotheses.length > 0 && (
          <Section title="Hypotheses" icon={Brain} accentColor="cyan">
            <div className="space-y-5">
              {data.hypotheses.map((hypo, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-start gap-2">
                    <Lightbulb size={14} className="text-yellow-500 mt-0.5 shrink-0" />
                    <p className="text-sm font-medium text-zinc-200">{hypo.claim}</p>
                  </div>
                  <p className="text-xs text-zinc-500 pl-6 border-l border-zinc-800 ml-1.5">{hypo.evidence}</p>
                  <div className="pl-6">
                    <ConfidenceBar value={hypo.confidence} />
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Section 4: 专业能力 */}
        <Section title="Expertise Matrix" icon={Fingerprint} accentColor="cyan">
          <div className="space-y-4">
            <div>
              <h4 className="text-xs text-zinc-500 mb-2 font-mono uppercase">Domain Knowledge</h4>
              <div className="flex flex-wrap gap-2">
                {data.expertise.knowledge_tags.map((tag, i) => (
                  <Tag key={i} text={tag} type="knowledge" />
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs text-zinc-500 mb-2 font-mono uppercase">Skills</h4>
              <div className="flex flex-wrap gap-2">
                {data.expertise.skills.map((skill, i) => (
                  <Tag key={i} text={skill} type="skill" />
                ))}
              </div>
            </div>
          </div>
        </Section>

        {/* Section 5: 任务推荐 */}
        <Section title="Task Fit" icon={Target} accentColor="emerald">
          <div className="grid gap-3">
            <div className="space-y-2">
              <span className="text-xs font-bold text-emerald-500 uppercase tracking-wider flex items-center gap-1">
                <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full" /> Best Fit
              </span>
              {data.task_recommendation.best_fit.map((item, i) => (
                <div key={i} className="p-3 rounded bg-zinc-900 border border-zinc-800">
                  <div className="text-sm font-medium text-zinc-200">{item.task}</div>
                  <div className="text-xs text-zinc-500 mt-1">{item.reason}</div>
                </div>
              ))}
            </div>

            {data.task_recommendation.avoid.length > 0 && (
              <div className="space-y-2 mt-2">
                <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1">
                  <div className="w-1.5 h-1.5 bg-zinc-600 rounded-full" /> Avoid
                </span>
                {data.task_recommendation.avoid.map((item, i) => (
                  <div key={i} className="p-3 rounded bg-zinc-900/50 border border-zinc-800/50 opacity-70">
                    <div className="text-sm font-medium text-zinc-400">{item.task}</div>
                    <div className="text-xs text-zinc-600 mt-1">{item.reason}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Section>

        {/* Section 6: 异常检测 */}
        {data.anomalies.length > 0 && (
          <Section title="Anomalies" icon={AlertTriangle} accentColor="rose" defaultOpen={false}>
            <div className="space-y-2">
              {data.anomalies.map((anomaly, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/10">
                  <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-red-200/80">{anomaly}</p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Section 7: 关系网络 */}
        <Section title="Network" icon={Network} accentColor="cyan" defaultOpen={false}>
          <div className="space-y-4">
            {data.network.external_contacts.length > 0 && (
              <div>
                <h4 className="text-xs text-zinc-500 mb-2 font-mono uppercase">External Contacts</h4>
                <ul className="space-y-2">
                  {data.network.external_contacts.slice(0, 5).map((c, i) => (
                    <li key={i} className="flex justify-between items-center text-sm p-2 rounded hover:bg-white/5 transition-colors">
                      <div>
                        <span className="text-zinc-200 block">{c.name}</span>
                        <span className="text-xs text-zinc-500">{c.company}</span>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                        {c.relationship}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.network.key_counterparties.length > 0 && (
              <div>
                <h4 className="text-xs text-zinc-500 mb-2 font-mono uppercase">Key Partners</h4>
                <div className="flex flex-wrap gap-2">
                  {data.network.key_counterparties.map((company, i) => (
                    <Tag key={i} text={company} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </Section>
      </div>

      {/* 底部操作栏 */}
      <div className="p-4 border-t border-white/10 bg-zinc-950 z-10 shrink-0">
        <button className="w-full py-3 rounded-lg font-medium text-sm bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 hover:scale-[1.02] transition-all duration-300 flex items-center justify-center gap-2">
          <Briefcase size={16} />
          分配项目任务
        </button>
      </div>
    </div>
  );
};

export default EmployeeAIProfile;
