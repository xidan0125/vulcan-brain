"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence, useMotionValue, useTransform } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { submitGenesis, getSoulStatus, resetGenesis } from "@/lib/api";
import { GENESIS_QUESTIONS } from "@/data/genesisQuestions";

// ==================== Types ====================
interface TraitScores {
  risk_tendency: number;
  control_level: number;
  people_focus: number;
  ethics_priority: number;
}

// ==================== 入口阶段 ====================
function CalibrationEntry({ onStart }: { onStart: () => void }) {
  const [booting, setBooting] = useState(true);
  const [bootLines, setBootLines] = useState<string[]>([]);

  const bootSequence = [
    "VULCAN NEURAL CORE v3.1.0",
    "Initializing quantum processors...",
    "Loading decision matrix...",
    "Scanning executive profile...",
    "PROFILE NOT FOUND",
    "",
    "System requires calibration.",
    "Requesting decision preference mapping..."
  ];

  useEffect(() => {
    let idx = 0;
    const timer = setInterval(() => {
      if (idx < bootSequence.length) {
        setBootLines(prev => [...prev, bootSequence[idx]]);
        idx++;
      } else {
        clearInterval(timer);
        setTimeout(() => setBooting(false), 800);
      }
    }, 200);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
      <div className="max-w-2xl w-full px-8">
        {/* Boot Sequence */}
        <div className="mb-12 font-mono text-sm">
          {bootLines.filter(Boolean).map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className={`mb-1 ${
                line?.includes("NOT FOUND") ? "text-amber-500" :
                line?.includes("requires") || line?.includes("Requesting") ? "text-orange-400" :
                "text-zinc-500"
              }`}
            >
              {line?.startsWith("VULCAN") ? (
                <span className="text-orange-500 font-bold">{line}</span>
              ) : line ? (
                <>
                  <span className="text-zinc-600 mr-2">&gt;</span>
                  {line}
                </>
              ) : null}
            </motion.div>
          ))}
        </div>

        {/* Start Button */}
        <AnimatePresence>
          {!booting && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center"
            >
              <p className="text-zinc-400 mb-8 text-lg">
                Vulcan 需要了解您的决策偏好以提供精准建议
              </p>
              <button
                onClick={onStart}
                className="px-8 py-4 bg-gradient-to-r from-orange-500 to-red-500 text-white font-medium rounded-lg hover:from-orange-600 hover:to-red-600 transition-all shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30"
              >
                开始系统校准
              </button>
              <p className="text-zinc-600 text-sm mt-4">
                约需 3-5 分钟 · 20 个决策场景
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ==================== 问答卡片 ====================
function QuestionCard({
  question,
  index,
  total,
  onAnswer,
  traitScores
}: {
  question: typeof GENESIS_QUESTIONS[0];
  index: number;
  total: number;
  onAnswer: (value: string) => void;
  traitScores: TraitScores;
}) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const opacity = useTransform(x, [-200, -100, 0, 100, 200], [0.5, 0.8, 1, 0.8, 0.5]);

  const [dragDirection, setDragDirection] = useState<"left" | "right" | null>(null);

  const handleDragEnd = useCallback((_: any, info: { offset: { x: number } }) => {
    if (Math.abs(info.offset.x) > 100) {
      const value = info.offset.x > 0 ? question.optionB.value : question.optionA.value;
      onAnswer(value);
    }
    setDragDirection(null);
  }, [question, onAnswer]);

  const categoryColors: Record<string, string> = {
    Strategy: "text-blue-400",
    People: "text-emerald-400",
    Ethics: "text-purple-400",
    Control: "text-amber-400"
  };

  return (
    <div className="flex h-screen pb-24">
      {/* Left Panel - Option A Hint */}
      <div className={`w-32 flex items-center justify-center transition-opacity ${
        dragDirection === "left" ? "opacity-100" : "opacity-30"
      }`}>
        <div className="text-center">
          <div className="w-12 h-12 rounded-full bg-orange-500/20 flex items-center justify-center mx-auto mb-2">
            <span className="text-orange-400 text-xl">←</span>
          </div>
          <p className="text-sm text-orange-400 font-medium max-w-[100px]">{question.optionA.label}</p>
        </div>
      </div>

      {/* Center - Card */}
      <div className="flex-1 flex items-center justify-center">
        <motion.div
          drag="x"
          dragConstraints={{ left: 0, right: 0 }}
          style={{ x, rotate, opacity }}
          onDrag={(_, info) => {
            setDragDirection(info.offset.x > 20 ? "right" : info.offset.x < -20 ? "left" : null);
          }}
          onDragEnd={handleDragEnd}
          className="w-full max-w-lg cursor-grab active:cursor-grabbing"
        >
          <div className="bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-8 shadow-2xl">
            {/* Progress */}
            <div className="flex items-center justify-between mb-6">
              <span className={`text-xs font-medium uppercase tracking-wider ${categoryColors[question.category] || 'text-zinc-400'}`}>
                {question.category}
              </span>
              <span className="text-xs text-zinc-500 font-mono">
                {String(index + 1).padStart(2, "0")} / {total}
              </span>
            </div>

            {/* Scenario */}
            <h2 className="text-lg text-white font-medium leading-relaxed mb-8">
              {question.scenario}
            </h2>

            {/* Options */}
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => onAnswer(question.optionA.value)}
                className="p-4 rounded-xl border border-zinc-700 hover:border-orange-500/50 hover:bg-orange-500/5 transition-all text-left group"
              >
                <span className="text-orange-400 text-sm font-mono mb-2 block">A</span>
                <span className="text-zinc-300 text-sm group-hover:text-white transition-colors">
                  {question.optionA.label}
                </span>
              </button>
              <button
                onClick={() => onAnswer(question.optionB.value)}
                className="p-4 rounded-xl border border-zinc-700 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-all text-left group"
              >
                <span className="text-cyan-400 text-sm font-mono mb-2 block">B</span>
                <span className="text-zinc-300 text-sm group-hover:text-white transition-colors">
                  {question.optionB.label}
                </span>
              </button>
            </div>

            {/* Drag Hint */}
            <p className="text-center text-zinc-600 text-xs mt-6">
              拖拽卡片或点击选项
            </p>
          </div>
        </motion.div>
      </div>

      {/* Right Panel - Option B Hint */}
      <div className={`w-32 flex items-center justify-center transition-opacity ${
        dragDirection === "right" ? "opacity-100" : "opacity-30"
      }`}>
        <div className="text-center">
          <div className="w-12 h-12 rounded-full bg-cyan-500/20 flex items-center justify-center mx-auto mb-2">
            <span className="text-cyan-400 text-xl">→</span>
          </div>
          <p className="text-sm text-cyan-400 font-medium max-w-[100px]">{question.optionB.label}</p>
        </div>
      </div>
    </div>
  );
}

// ==================== 实时参数面板 ====================
function TraitPanel({ scores }: { scores: TraitScores }) {
  const traits = [
    { key: "risk_tendency", label: "风险偏好", color: "from-orange-500 to-red-500" },
    { key: "control_level", label: "控制力度", color: "from-amber-500 to-orange-500" },
    { key: "people_focus", label: "人才重视", color: "from-emerald-500 to-teal-500" },
    { key: "ethics_priority", label: "道德优先", color: "from-purple-500 to-indigo-500" },
  ] as const;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-zinc-900/95 backdrop-blur-sm border-t border-zinc-800 py-4 px-8 z-50">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">决策参数实时变化</span>
        </div>
        <div className="grid grid-cols-4 gap-6">
          {traits.map(({ key, label, color }) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-zinc-400">{label}</span>
                <span className="text-zinc-500 font-mono">{Math.round(scores[key])}%</span>
              </div>
              <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full bg-gradient-to-r ${color} rounded-full`}
                  initial={{ width: "50%" }}
                  animate={{ width: `${scores[key]}%` }}
                  transition={{ type: "spring", damping: 20 }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ==================== 完成页面 ====================
function CalibrationComplete({
  scores,
  onContinue,
  onReset
}: {
  scores: TraitScores;
  onContinue: () => void;
  onReset: () => void;
}) {
  const [resetting, setResetting] = useState(false);

  const getProfileLabel = (score: number) => {
    if (score >= 70) return "高";
    if (score >= 40) return "中";
    return "低";
  };

  const profileSummary = {
    risk: getProfileLabel(scores.risk_tendency),
    control: getProfileLabel(scores.control_level),
    people: getProfileLabel(scores.people_focus),
    ethics: getProfileLabel(scores.ethics_priority)
  };

  const handleReset = async () => {
    if (resetting) return;
    setResetting(true);
    try {
      await resetGenesis();
      localStorage.removeItem('vulcan_genesis_complete');
      localStorage.removeItem('vulcan_genesis_answers');
      onReset();
    } catch (error) {
      console.error('Reset failed:', error);
      alert('重置失败，请重试');
    }
    setResetting(false);
  };

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-lg w-full px-8 text-center"
      >
        {/* Success Icon */}
        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center mx-auto mb-8 shadow-lg shadow-orange-500/30">
          <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-white mb-4">
          系统校准完成
        </h1>
        <p className="text-zinc-400 mb-8">
          Vulcan 已学习您的决策偏好，将据此提供个性化建议
        </p>

        {/* Quick Profile Summary */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 mb-8">
          <h3 className="text-sm text-zinc-500 uppercase tracking-wider mb-4">决策画像概览</h3>
          <div className="grid grid-cols-2 gap-4 text-left">
            <div>
              <span className="text-zinc-500 text-sm">风险偏好</span>
              <p className="text-white font-medium">{profileSummary.risk}</p>
            </div>
            <div>
              <span className="text-zinc-500 text-sm">控制力度</span>
              <p className="text-white font-medium">{profileSummary.control}</p>
            </div>
            <div>
              <span className="text-zinc-500 text-sm">人才重视</span>
              <p className="text-white font-medium">{profileSummary.people}</p>
            </div>
            <div>
              <span className="text-zinc-500 text-sm">道德优先</span>
              <p className="text-white font-medium">{profileSummary.ethics}</p>
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex flex-col gap-3">
          <button
            onClick={onContinue}
            className="px-8 py-4 bg-gradient-to-r from-orange-500 to-red-500 text-white font-medium rounded-lg hover:from-orange-600 hover:to-red-600 transition-all shadow-lg shadow-orange-500/20"
          >
            进入系统
          </button>

          {/* Reset Button - for testing */}
          <button
            onClick={handleReset}
            disabled={resetting}
            className="px-6 py-2 text-zinc-500 hover:text-zinc-300 text-sm transition-colors disabled:opacity-50"
          >
            {resetting ? '重置中...' : '重新校准 (测试用)'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ==================== Main Page ====================
export default function CalibrationPage() {
  const [phase, setPhase] = useState<"entry" | "questions" | "complete">("entry");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [traitScores, setTraitScores] = useState<TraitScores>({
    risk_tendency: 50,
    control_level: 50,
    people_focus: 50,
    ethics_priority: 50
  });
  const [submitting, setSubmitting] = useState(false);

  const { user, loading, isAuthenticated, genesisCompleted, refreshCalibrationStatus } = useAuth();
  const router = useRouter();

  // 追踪是否是"刚完成校准"的状态（此时不应该跳转）
  const [justCompleted, setJustCompleted] = useState(false);

  // 如果已完成校准且不是刚完成的，跳转首页（防止已校准用户再次访问）
  useEffect(() => {
    if (!loading && genesisCompleted && phase === "entry" && !justCompleted) {
      router.push('/');
    }
  }, [loading, genesisCompleted, phase, justCompleted, router]);

  // 未登录则跳转登录
  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login');
    }
  }, [loading, isAuthenticated, router]);

  // 计算特质分数变化
  const calculateTraitDelta = (value: string): Partial<TraitScores> => {
    const traitMap: Record<string, Partial<TraitScores>> = {
      // Strategy - 风险相关
      risk_seeking: { risk_tendency: 8 },
      risk_averse: { risk_tendency: -8 },
      speed_first: { risk_tendency: 5 },
      quality_first: { risk_tendency: -3 },
      short_term_survival: { risk_tendency: 3 },
      long_term_vision: { risk_tendency: -2 },
      proactive_change: { risk_tendency: 4 },
      delayed_change: { risk_tendency: -4 },
      aggressive_growth: { risk_tendency: 6 },
      organic_growth: { risk_tendency: -6 },

      // People - 人才相关
      talent_over_culture: { people_focus: -5 },
      culture_over_talent: { people_focus: 8 },
      loyalty_first: { people_focus: 4 },
      performance_first: { people_focus: -4 },
      flexible_rules: { control_level: -5 },
      strict_rules: { control_level: 8 },
      wolf_culture: { control_level: 6, people_focus: -3 },
      nurturing_culture: { control_level: -4, people_focus: 5 },
      flat_hierarchy: { control_level: -5 },
      strict_hierarchy: { control_level: 6 },

      // Ethics - 道德相关
      pragmatic: { ethics_priority: -8 },
      principled: { ethics_priority: 8 },
      result_oriented: { ethics_priority: -5 },
      integrity_first: { ethics_priority: 6 },
      profit_driven: { ethics_priority: -6 },
      privacy_first: { ethics_priority: 7 },
      aggressive_pr: { ethics_priority: -4 },
      transparent_pr: { ethics_priority: 5 },
      move_fast: { ethics_priority: -3, risk_tendency: 4 },
      wait_and_see: { ethics_priority: 4, risk_tendency: -3 },

      // Control - 控制相关
      soft_report: { control_level: -3 },
      data_first_report: { control_level: 4 },
      micromanagement: { control_level: 8 },
      result_management: { control_level: -6 },
      full_transparency: { control_level: -4 },
      selective_transparency: { control_level: 5 },
      welcome_dissent: { control_level: -5 },
      respect_authority: { control_level: 6 },
      options_style: { control_level: -3 },
      directive_style: { control_level: 4 },
    };
    return traitMap[value] || {};
  };

  const handleAnswer = async (value: string) => {
    const questionId = GENESIS_QUESTIONS[currentIndex].id;
    const newAnswers = { ...answers, [questionId]: value };
    setAnswers(newAnswers);

    // 更新特质分数
    const delta = calculateTraitDelta(value);
    setTraitScores(prev => ({
      risk_tendency: Math.max(0, Math.min(100, prev.risk_tendency + (delta.risk_tendency || 0))),
      control_level: Math.max(0, Math.min(100, prev.control_level + (delta.control_level || 0))),
      people_focus: Math.max(0, Math.min(100, prev.people_focus + (delta.people_focus || 0))),
      ethics_priority: Math.max(0, Math.min(100, prev.ethics_priority + (delta.ethics_priority || 0))),
    }));

    // 下一题或完成
    if (currentIndex < GENESIS_QUESTIONS.length - 1) {
      setTimeout(() => setCurrentIndex(prev => prev + 1), 300);
    } else {
      // 提交到后端
      setSubmitting(true);
      try {
        await submitGenesis(newAnswers);
        await refreshCalibrationStatus();
        localStorage.setItem('vulcan_genesis_complete', 'true');
      } catch (error) {
        console.error('Failed to submit genesis:', error);
        localStorage.setItem('vulcan_genesis_complete', 'true');
        localStorage.setItem('vulcan_genesis_answers', JSON.stringify(newAnswers));
      }
      setSubmitting(false);
      setJustCompleted(true);  // 标记为"刚完成"，防止跳转
      setPhase("complete");
    }
  };

  const handleContinue = () => {
    router.push('/');
  };

  // 重置校准，重新开始
  const handleReset = () => {
    setPhase("entry");
    setCurrentIndex(0);
    setAnswers({});
    setTraitScores({
      risk_tendency: 50,
      control_level: 50,
      people_focus: 50,
      ethics_priority: 50
    });
  };

  // Loading states
  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (submitting) {
    return (
      <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-zinc-400">正在生成决策画像...</p>
        </div>
      </div>
    );
  }

  // Render phases
  switch (phase) {
    case "entry":
      return <CalibrationEntry onStart={() => setPhase("questions")} />;

    case "questions":
      return (
        <div className="min-h-screen bg-[#09090b]">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentIndex}
              initial={{ opacity: 0, x: 100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
            >
              <QuestionCard
                question={GENESIS_QUESTIONS[currentIndex]}
                index={currentIndex}
                total={GENESIS_QUESTIONS.length}
                onAnswer={handleAnswer}
                traitScores={traitScores}
              />
            </motion.div>
          </AnimatePresence>
          <TraitPanel scores={traitScores} />
        </div>
      );

    case "complete":
      return <CalibrationComplete scores={traitScores} onContinue={handleContinue} onReset={handleReset} />;
  }
}
