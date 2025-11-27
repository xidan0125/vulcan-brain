'use client';

import React, { useEffect, useState } from 'react';
import RadarChart from './RadarChart';
import {
  getSoulStats,
  getDailyQuestions,
  submitSandboxAnswer,
  SoulStats,
  SandboxQuestion,
  SubmitAnswerResponse
} from '@/lib/api';

interface TwinDashboardProps {
  userId: string;
}

// ==================== 左栏：数字孪生 ====================
function DigitalTwinPanel({ stats, loading }: { stats: SoulStats | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 h-full animate-pulse">
        <div className="h-6 bg-gray-800 rounded w-1/3 mb-4"></div>
        <div className="h-64 bg-gray-800 rounded mb-4"></div>
        <div className="h-4 bg-gray-800 rounded w-2/3 mb-2"></div>
        <div className="h-4 bg-gray-800 rounded w-1/2"></div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-6 h-full">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-white">数字孪生</h2>
        <span className="text-xs text-gray-500">
          数据点: {stats?.data_points_collected || 0}
        </span>
      </div>

      {/* 雷达图 */}
      <div className="mb-6">
        <RadarChart
          dimensions={stats?.dimensions || {
            risk_appetite: 0.5,
            time_preference: 0.5,
            social_tendency: 0.5,
            decision_style: 0.5,
            value_priority: 0.5,
            stress_response: 0.5
          }}
          size={260}
        />
      </div>

      {/* 理解度得分 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">AI 理解度</span>
          <span className="text-2xl font-bold text-red-400">
            {Math.round((stats?.understanding_score || 0.5) * 100)}%
          </span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-red-600 to-red-400 transition-all duration-500"
            style={{ width: `${(stats?.understanding_score || 0.5) * 100}%` }}
          />
        </div>
      </div>

      {/* 连续签到 */}
      <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center">
            <span className="text-red-400 text-lg">🔥</span>
          </div>
          <div>
            <div className="text-sm text-gray-400">连续校准</div>
            <div className="text-xl font-bold text-white">{stats?.streak_days || 0} 天</div>
          </div>
        </div>
        {(stats?.streak_days || 0) >= 7 && (
          <span className="text-xs text-green-400 bg-green-400/10 px-2 py-1 rounded">
            校准完成
          </span>
        )}
      </div>

      {/* 洞察 */}
      {stats?.insights && stats.insights.length > 0 && (
        <div className="mt-4">
          <div className="text-xs text-gray-500 mb-2">AI 洞察</div>
          {stats.insights.slice(0, 2).map((insight, i) => (
            <div key={i} className="text-sm text-gray-400 py-1 border-l-2 border-red-500/50 pl-3 mb-2">
              {insight}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== 中栏：决策推演 ====================
interface QuestionCardProps {
  question: SandboxQuestion;
  onSubmit: (optionId: string) => void;
  result: SubmitAnswerResponse | null;
  submitting: boolean;
}

function QuestionCard({ question, onSubmit, result, submitting }: QuestionCardProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);

  const handleSelect = (optionId: string) => {
    if (result || submitting) return;
    setSelectedOption(optionId);
  };

  const handleSubmit = () => {
    if (!selectedOption || result || submitting) return;
    onSubmit(selectedOption);
  };

  useEffect(() => {
    if (result) {
      setShowResult(true);
    }
  }, [result]);

  const getCategoryLabel = (cat: string) => {
    const labels: Record<string, string> = {
      'HR_DECISION': '人事决策',
      'RISK_DECISION': '风险评估',
      'STRATEGY': '战略选择',
      'RESOURCE_ALLOCATION': '资源分配',
      'CRISIS_MANAGEMENT': '危机管理'
    };
    return labels[cat] || cat;
  };

  return (
    <div className="bg-gray-900 rounded-lg p-5 mb-4">
      {/* 类别标签 */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">
          {getCategoryLabel(question.category)}
        </span>
        {result && (
          <span className={`text-xs px-2 py-1 rounded ${
            result.is_match
              ? 'text-green-400 bg-green-400/10'
              : 'text-yellow-400 bg-yellow-400/10'
          }`}>
            {result.is_match ? '✓ 预测命中' : '× 预测偏差'}
          </span>
        )}
      </div>

      {/* 场景描述 */}
      <p className="text-gray-300 text-sm leading-relaxed mb-4">
        {question.scenario}
      </p>

      {/* 选项 */}
      <div className="space-y-2 mb-4">
        {question.options.map((opt) => {
          const isSelected = selectedOption === opt.id;
          const isAIPredicted = result && result.ai_predicted === opt.id;
          const isUserSelected = result && result.user_selected === opt.id;

          let borderClass = 'border-gray-700 hover:border-gray-600';
          let bgClass = 'bg-gray-800';

          if (result) {
            if (isAIPredicted && isUserSelected) {
              borderClass = 'border-green-500';
              bgClass = 'bg-green-500/10';
            } else if (isAIPredicted) {
              borderClass = 'border-red-500 border-dashed';
              bgClass = 'bg-red-500/5';
            } else if (isUserSelected) {
              borderClass = 'border-blue-500';
              bgClass = 'bg-blue-500/10';
            }
          } else if (isSelected) {
            borderClass = 'border-red-500';
            bgClass = 'bg-red-500/10';
          }

          return (
            <button
              key={opt.id}
              onClick={() => handleSelect(opt.id)}
              disabled={!!result || submitting}
              className={`w-full p-3 rounded-lg border ${borderClass} ${bgClass} text-left transition-all ${
                !result && !submitting ? 'cursor-pointer' : 'cursor-default'
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="text-gray-500 font-mono text-sm">{opt.id}</span>
                <span className="text-gray-300 text-sm flex-1">{opt.text}</span>
                {result && (
                  <div className="flex gap-1">
                    {isAIPredicted && (
                      <span className="text-xs text-red-400 bg-red-400/10 px-1.5 py-0.5 rounded">
                        AI
                      </span>
                    )}
                    {isUserSelected && (
                      <span className="text-xs text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded">
                        你
                      </span>
                    )}
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* 提交按钮 or 结果 */}
      {!result ? (
        <button
          onClick={handleSubmit}
          disabled={!selectedOption || submitting}
          className={`w-full py-3 rounded-lg font-medium transition-all ${
            selectedOption && !submitting
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-gray-800 text-gray-500 cursor-not-allowed'
          }`}
        >
          {submitting ? '提交中...' : '确认选择'}
        </button>
      ) : (
        <div className="p-3 bg-gray-800 rounded-lg">
          <div className="text-xs text-gray-500 mb-1">AI 预测理由</div>
          <p className="text-sm text-gray-400">{result.ai_reasoning}</p>
        </div>
      )}
    </div>
  );
}

function DecisionSimPanel({
  userId,
  questions,
  loading,
  onAnswerSubmit
}: {
  userId: string;
  questions: SandboxQuestion[];
  loading: boolean;
  onAnswerSubmit: () => void;
}) {
  const [results, setResults] = useState<Record<string, SubmitAnswerResponse>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  const handleSubmit = async (questionId: string, optionId: string) => {
    setSubmitting(questionId);
    try {
      const result = await submitSandboxAnswer(questionId, optionId, userId);
      setResults(prev => ({ ...prev, [questionId]: result }));
      onAnswerSubmit();
    } catch (error) {
      console.error('Submit error:', error);
    } finally {
      setSubmitting(null);
    }
  };

  if (loading) {
    return (
      <div className="h-full">
        <div className="mb-4">
          <div className="h-6 bg-gray-800 rounded w-1/4 mb-2 animate-pulse"></div>
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-gray-900 rounded-lg p-5 mb-4 animate-pulse">
            <div className="h-4 bg-gray-800 rounded w-1/4 mb-3"></div>
            <div className="h-16 bg-gray-800 rounded mb-4"></div>
            <div className="space-y-2">
              {[1, 2, 3, 4].map(j => (
                <div key={j} className="h-12 bg-gray-800 rounded"></div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  const completedCount = Object.keys(results).length;
  const totalCount = questions.length;

  return (
    <div className="h-full">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">今日决策推演</h2>
        <span className="text-sm text-gray-500">
          {completedCount}/{totalCount} 完成
        </span>
      </div>

      {/* 进度条 */}
      <div className="h-1 bg-gray-800 rounded-full mb-4 overflow-hidden">
        <div
          className="h-full bg-red-500 transition-all duration-300"
          style={{ width: `${(completedCount / totalCount) * 100}%` }}
        />
      </div>

      {/* 问题列表 */}
      <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
        {questions.map((q) => (
          <QuestionCard
            key={q.question_id}
            question={q}
            onSubmit={(optionId) => handleSubmit(q.question_id, optionId)}
            result={results[q.question_id] || null}
            submitting={submitting === q.question_id}
          />
        ))}

        {questions.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <div className="text-4xl mb-4">✅</div>
            <p>今日推演已完成</p>
            <p className="text-sm mt-2">明天再来继续校准</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== 右栏：实时资讯 ====================
function RealtimeInfoPanel() {
  // 模拟数据 - 实际应该从 API 获取
  const newsItems = [
    { title: '央行发布新政策解读', time: '2小时前', tag: '宏观' },
    { title: '科技行业估值分析报告', time: '4小时前', tag: '研报' },
    { title: '新能源产业链深度调研', time: '今天', tag: '行业' }
  ];

  return (
    <div className="bg-gray-900 rounded-lg p-6 h-full">
      <h2 className="text-lg font-semibold text-white mb-6">实时资讯</h2>

      {/* 资讯列表 */}
      <div className="space-y-4">
        {newsItems.map((item, i) => (
          <div
            key={i}
            className="p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors cursor-pointer"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded">
                {item.tag}
              </span>
              <span className="text-xs text-gray-500">{item.time}</span>
            </div>
            <p className="text-sm text-gray-300">{item.title}</p>
          </div>
        ))}
      </div>

      {/* 占位 - 可扩展区域 */}
      <div className="mt-6 p-4 border border-dashed border-gray-700 rounded-lg">
        <p className="text-xs text-gray-500 text-center">
          更多功能开发中...
        </p>
      </div>
    </div>
  );
}

// ==================== 主组件 ====================
export default function TwinDashboard({ userId }: TwinDashboardProps) {
  const [stats, setStats] = useState<SoulStats | null>(null);
  const [questions, setQuestions] = useState<SandboxQuestion[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsData, questionsData] = await Promise.all([
        getSoulStats(userId),
        getDailyQuestions(userId)
      ]);
      setStats(statsData);
      setQuestions(questionsData.questions || []);
    } catch (error) {
      console.error('Failed to fetch soul data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      fetchData();
    }
  }, [userId]);

  const handleAnswerSubmit = () => {
    // 刷新统计数据
    getSoulStats(userId).then(setStats).catch(console.error);
  };

  return (
    <div className="min-h-screen bg-black p-6">
      {/* 顶部信息 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">Soul 校准中心</h1>
        <p className="text-sm text-gray-500">
          每日 3 道决策题，持续优化 AI 对你的理解
        </p>
      </div>

      {/* 三栏布局 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* 左栏：数字孪生 */}
        <div className="lg:col-span-3">
          <DigitalTwinPanel stats={stats} loading={loading} />
        </div>

        {/* 中栏：决策推演 */}
        <div className="lg:col-span-6">
          <DecisionSimPanel
            userId={userId}
            questions={questions}
            loading={loading}
            onAnswerSubmit={handleAnswerSubmit}
          />
        </div>

        {/* 右栏：实时资讯 */}
        <div className="lg:col-span-3">
          <RealtimeInfoPanel />
        </div>
      </div>
    </div>
  );
}
