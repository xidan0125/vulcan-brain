"use client";

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import dynamic from 'next/dynamic';
import {
  Shield, Zap, Brain, AlertTriangle,
  Network, Briefcase, ChevronRight, Activity,
  Loader2, Wand2, X, Sparkles, Target, Eye
} from 'lucide-react';

// 动态导入 recharts 避免 SSR 问题
const ResponsiveContainer = dynamic(
  () => import('recharts').then(mod => mod.ResponsiveContainer),
  { ssr: false, loading: () => <div className="h-48 bg-zinc-800/50 rounded animate-pulse" /> }
);
const RadarChart = dynamic(
  () => import('recharts').then(mod => mod.RadarChart),
  { ssr: false }
);
const Radar = dynamic(
  () => import('recharts').then(mod => mod.Radar),
  { ssr: false }
);
const PolarGrid = dynamic(
  () => import('recharts').then(mod => mod.PolarGrid),
  { ssr: false }
);
const PolarAngleAxis = dynamic(
  () => import('recharts').then(mod => mod.PolarAngleAxis),
  { ssr: false }
);

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
  task_recommendation?: {
    best_fit: { task: string; reason: string }[];
    avoid: { task: string; reason: string }[];
  };
  discoveries?: string[];
  hypotheses: { claim: string; evidence: string; confidence: number }[];
  anomalies: string[];
}

interface EmployeePersonaCardProps {
  data: EmployeeProfileData | null;
  isLoading?: boolean;
  onGenerate?: () => void;
  onClose?: () => void;
  employeeName?: string;
  employeeEmail?: string;
}

// 霓虹标签
const NeonBadge = ({ text, type = 'cyan', delay = 0 }: { text: string; type?: 'cyan' | 'purple' | 'red' | 'orange' | 'green'; delay?: number }) => {
  const colors: Record<string, string> = {
    cyan: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
    purple: "bg-violet-500/10 text-violet-300 border-violet-500/30",
    red: "bg-rose-500/10 text-rose-300 border-rose-500/30",
    orange: "bg-orange-500/10 text-orange-300 border-orange-500/30",
    green: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  };

  return (
    <motion.span
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ delay, type: "spring", stiffness: 500, damping: 25 }}
      className={`inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-medium border ${colors[type]}`}
    >
      {text}
    </motion.span>
  );
};

// 技能进度条
const SkillBar = ({ skill, value, delay }: { skill: string; value: number; delay: number }) => (
  <div className="group">
    <div className="flex justify-between text-xs mb-1.5">
      <span className="text-zinc-400 group-hover:text-white transition-colors">{skill}</span>
      <motion.span
        className="font-mono text-cyan-400"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: delay + 0.5 }}
      >
        {value}%
      </motion.span>
    </div>
    <div className="h-2 bg-zinc-800/80 rounded-full overflow-hidden border border-white/5">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 1.2, delay, ease: "easeOut" }}
        className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.5)]"
      />
    </div>
  </div>
);

// 数字滚动
const AnimatedNumber = ({ value }: { value: number }) => {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const duration = 1500;
    const steps = 30;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplay(value);
        clearInterval(timer);
      } else {
        setDisplay(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);
  return <span>{display}</span>;
};

// === 主组件 ===
export const EmployeePersonaCard = ({
  data,
  isLoading = false,
  onGenerate,
  employeeName,
  employeeEmail
}: EmployeePersonaCardProps) => {

  // 空状态
  if (!data && !isLoading) {
    return (
      <div className="w-full h-full bg-zinc-950 flex flex-col items-center justify-center p-8">
        <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center">
          <div className="relative w-24 h-24 mx-auto mb-6">
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500 to-violet-600 rounded-full blur-xl opacity-30 animate-pulse" />
            <div className="relative w-full h-full bg-zinc-900 rounded-full border border-white/10 flex items-center justify-center">
              <Brain className="w-10 h-10 text-cyan-400" />
            </div>
          </div>
          <h3 className="text-xl font-bold text-white mb-2">AI 角色分析</h3>
          <p className="text-sm text-zinc-500 mb-6 max-w-[280px]">基于邮件数据生成员工能力画像</p>
          {onGenerate && (
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={onGenerate}
              className="px-6 py-3 rounded-xl font-medium text-sm bg-gradient-to-r from-cyan-600 to-violet-600 text-white shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all flex items-center gap-2 mx-auto">
              <Wand2 size={18} />生成角色卡
            </motion.button>
          )}
        </motion.div>
      </div>
    );
  }

  // 加载状态
  if (isLoading) {
    return (
      <div className="w-full h-full bg-zinc-950 flex flex-col items-center justify-center p-8">
        <div className="relative">
          <div className="w-24 h-24 rounded-full border-2 border-cyan-500/30 border-t-cyan-500 animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Brain className="w-8 h-8 text-cyan-400 animate-pulse" />
          </div>
        </div>
        <motion.p className="text-sm text-zinc-400 mt-6" animate={{ opacity: [0.5, 1, 0.5] }} transition={{ duration: 2, repeat: Infinity }}>
          正在分析邮件数据...
        </motion.p>
        <p className="text-xs text-zinc-600 mt-2">生成深度画像中，请稍候</p>
      </div>
    );
  }

  if (!data) return null;

  // 雷达图数据
  const statsData = [
    { subject: '协调', A: 90, fullMark: 100 },
    { subject: '合规', A: data.expertise.knowledge_tags.length > 3 ? 85 : 70, fullMark: 100 },
    { subject: '技术', A: 65, fullMark: 100 },
    { subject: '分析', A: 75, fullMark: 100 },
    { subject: '人脉', A: Math.min(95, 50 + data.network.external_contacts.length * 10), fullMark: 100 },
    { subject: '沟通', A: 85, fullMark: 100 },
  ];

  const level = Math.floor((data.hypotheses[0]?.confidence || 0.5) * 50 + data.expertise.knowledge_tags.length * 3 + data.network.external_contacts.length * 2);

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
      className="w-full h-full bg-zinc-950 border border-white/10 rounded-2xl overflow-auto p-6">

      {/* 头部 */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500 to-violet-600 rounded-xl blur opacity-50 animate-pulse" />
            <div className="relative w-16 h-16 bg-zinc-900 rounded-xl border border-white/20 flex items-center justify-center">
              <span className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-white">
                {data.name.split(' ').map(n => n[0]).join('')}
              </span>
            </div>
            <div className="absolute -bottom-1 -right-1 px-1.5 py-0.5 bg-gradient-to-r from-yellow-600 to-orange-600 rounded text-[10px] font-bold text-white">
              等级 <AnimatedNumber value={level} />
            </div>
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{data.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <Shield className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-xs text-cyan-400 font-mono">{data.behavior_profile.archetype}</span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">{data.role_guess}</p>
          </div>
        </div>
      </div>

      {/* 主内容 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* 左列 */}
        <div className="space-y-5">
          {/* 雷达图 */}
          <div className="bg-zinc-900/50 rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-zinc-300">能力六维图</span>
            </div>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={statsData}>
                  <PolarGrid stroke="#3f3f46" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
                  <Radar name="能力" dataKey="A" stroke="#22d3ee" strokeWidth={2} fill="#22d3ee" fillOpacity={0.3} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 技能条 */}
          <div className="bg-zinc-900/50 rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-4 h-4 text-yellow-400" />
              <span className="text-xs font-bold text-zinc-300">技能熟练度</span>
            </div>
            <div className="space-y-4">
              {data.expertise.skills.slice(0, 4).map((skill, i) => (
                <SkillBar key={i} skill={skill} value={90 - (i * 12)} delay={i * 0.15} />
              ))}
            </div>
          </div>

          {/* 知识标签 */}
          <div className="bg-zinc-900/50 rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-bold text-zinc-300">知识领域</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.expertise.knowledge_tags.map((tag, i) => (
                <NeonBadge key={i} text={tag} type="purple" delay={0.3 + i * 0.08} />
              ))}
            </div>
          </div>
        </div>

        {/* 右列 */}
        <div className="space-y-5">
          {/* AI 洞察 */}
          <div className="bg-gradient-to-br from-zinc-900 to-zinc-950 rounded-xl border border-cyan-500/20 p-4 relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-zinc-300">AI 洞察</span>
              </div>
              <span className="text-[10px] font-mono text-cyan-500 animate-pulse">● 实时</span>
            </div>
            <div className="space-y-4">
              {data.hypotheses.slice(0, 3).map((hypo, i) => (
                <motion.div key={i} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 + i * 0.2 }}
                  className="bg-zinc-800/30 rounded-lg p-3 border border-white/5">
                  <p className="text-sm text-zinc-200 mb-2">"{hypo.claim}"</p>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${hypo.confidence * 100}%` }}
                        transition={{ duration: 1.5, delay: 0.8 + i * 0.2 }}
                        className={`h-full rounded-full ${hypo.confidence > 0.8 ? "bg-emerald-500" : hypo.confidence > 0.6 ? "bg-yellow-500" : "bg-orange-500"}`}
                      />
                    </div>
                    <span className="text-xs font-mono text-cyan-400 w-10">{(hypo.confidence * 100).toFixed(0)}%</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* 人脉网络 */}
          <div className="bg-zinc-900/50 rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Network className="w-4 h-4 text-orange-400" />
              <span className="text-xs font-bold text-zinc-300">核心人脉</span>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {data.network.key_counterparties.slice(0, 4).map((cp, i) => (
                <NeonBadge key={i} text={cp} type="orange" delay={0.4 + i * 0.1} />
              ))}
            </div>
            <div className="space-y-2">
              {data.network.external_contacts.slice(0, 3).map((contact, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 + i * 0.1 }}
                  className="flex items-center justify-between p-2 rounded-lg bg-zinc-800/30 border border-white/5 hover:border-cyan-500/30 transition-colors group">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center text-xs font-bold text-zinc-500 group-hover:text-cyan-400 transition-colors">
                      {contact.name[0]}
                    </div>
                    <div>
                      <div className="text-xs font-medium text-zinc-300">{contact.name}</div>
                      <div className="text-[10px] text-zinc-500">{contact.company}</div>
                    </div>
                  </div>
                  <ChevronRight className="w-3 h-3 text-zinc-700 group-hover:text-cyan-500 transition-colors" />
                </motion.div>
              ))}
            </div>
          </div>

          {/* 异常警告 */}
          {data.anomalies.length > 0 && (
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1 }}
              className="bg-rose-950/20 border border-rose-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span className="text-xs font-bold text-rose-300">异常检测</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.anomalies.slice(0, 4).map((anomaly, i) => (
                  <NeonBadge key={i} text={anomaly} type="red" delay={1.1 + i * 0.1} />
                ))}
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* 重新生成按钮 */}
      {onGenerate && (
        <div className="pt-4 mt-4 border-t border-white/5 flex justify-end">
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={onGenerate}
            className="px-4 py-2 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-400 hover:text-cyan-400 hover:bg-zinc-700 transition-all flex items-center gap-2 border border-white/5">
            <Wand2 size={14} />重新分析
          </motion.button>
        </div>
      )}
    </motion.div>
  );
};

export default EmployeePersonaCard;
