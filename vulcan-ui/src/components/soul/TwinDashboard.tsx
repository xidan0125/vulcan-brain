'use client';

import React, { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';
// 获取认证头
const getAuthHeaders = (): HeadersInit => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('vulcan_token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};


// ==================== 类型定义 ====================
interface StatsData {
  sync_progress: number;
  streak_days: number;
  dimensions: {
    risk_appetite: number;
    time_horizon: number;
    strategic_drive: number;
    people_philosophy: number;
    control_style: number;
    ethical_boundary: number;
  };
  insights: string[];
  data_points_collected: number;
  recent_topics: string[];
}

interface Question {
  question_id: string;
  category: string;
  scenario: string;
  options: { id: string; text: string }[];
  source_topic?: string;
}

interface SubmissionResult {
  is_match: boolean;
  ai_predicted?: string;
  user_selected?: string;
  ai_reasoning?: string;
  dimension_changes?: Record<string, number>;
}


interface HotTopic {
  title: string;
  summary: string;
  category: string;
  url: string;
  timestamp: string;
  source?: string;
}

// ==================== 天秤线组件 ====================
const DIMENSION_SPECTRUM: Record<string, { left: string; right: string; label: string }> = {
  risk_appetite: { left: '稳健保守', right: '激进冒险', label: '风险阈值' },
  time_horizon: { left: '短期聚焦', right: '长线布局', label: '时间视界' },
  strategic_drive: { left: '防守稳健', right: '进攻扩张', label: '战略驱动' },
  people_philosophy: { left: '独立决策', right: '协作共识', label: '人际哲学' },
  control_style: { left: '授权放手', right: '集中掌控', label: '控制风格' },
  ethical_boundary: { left: '务实灵活', right: '原则坚守', label: '伦理边界' }
};

const DIMENSION_LABELS: Record<string, string> = {
  risk_appetite: '风险阈值',
  time_horizon: '时间视界',
  strategic_drive: '战略驱动',
  people_philosophy: '人际哲学',
  control_style: '控制风格',
  ethical_boundary: '伦理边界'
};

interface BalanceScalesProps {
  dimensions: Record<string, number>;
  changes?: Record<string, number>;
  compact?: boolean;
}

const BalanceScales: React.FC<BalanceScalesProps> = ({ dimensions, changes, compact }) => {
  const dimensionKeys = Object.keys(DIMENSION_SPECTRUM);

  return (
    <div className={compact ? "space-y-2" : "space-y-4"}>
      {dimensionKeys.map((key) => {
        const spec = DIMENSION_SPECTRUM[key];
        const value = dimensions[key] ?? 0.5;
        const change = changes?.[key];
        const markerPosition = value * 100;

        return (
          <div key={key} className="relative">
            <div className="text-center mb-1">
              <span className="text-[10px] text-zinc-500 font-medium">
                {spec.label}
              </span>
              {change !== undefined && change !== 0 && (
                <span className={`ml-2 text-[9px] font-mono ${change > 0 ? 'text-green-400' : 'text-orange-400'}`}>
                  {change > 0 ? '→' : '←'} {Math.abs(Math.round(change * 100))}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1 md:gap-2">
              <div className={`hidden md:block w-16 text-right text-[9px] shrink-0 transition-colors duration-300 ${value < 0.4 ? 'text-red-400 font-medium' : 'text-zinc-600'}`}>
                {spec.left}
              </div>

              <div className="flex-1 relative h-4 md:h-5">
                <div className="absolute top-1/2 left-0 right-0 h-[2px] bg-zinc-800 -translate-y-1/2 rounded-full" />
                <div className="absolute top-1/2 left-1/2 w-[1px] h-2 md:h-2.5 bg-zinc-700 -translate-x-1/2 -translate-y-1/2" />
                <div className="absolute top-1/2 left-1/4 w-[1px] h-1 md:h-1.5 bg-zinc-800 -translate-x-1/2 -translate-y-1/2" />
                <div className="absolute top-1/2 left-3/4 w-[1px] h-1 md:h-1.5 bg-zinc-800 -translate-x-1/2 -translate-y-1/2" />
                <div
                  className="absolute top-1/2 -translate-y-1/2 transition-all duration-500 ease-out"
                  style={{ left: `${markerPosition}%` }}
                >
                  <div className="absolute w-3 h-3 md:w-4 md:h-4 bg-red-500/20 rounded-full -translate-x-1/2 -translate-y-1/2 animate-pulse" />
                  <div className="absolute w-2 h-2 md:w-2.5 md:h-2.5 bg-red-500 rounded-full -translate-x-1/2 -translate-y-1/2 border border-zinc-900 shadow-lg shadow-red-500/30" />
                </div>
              </div>

              <div className={`hidden md:block w-16 text-left text-[9px] shrink-0 transition-colors duration-300 ${value > 0.6 ? 'text-red-400 font-medium' : 'text-zinc-600'}`}>
                {spec.right}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ==================== 移动端紧凑统计 ====================
interface MobileStatsProps {
  stats: StatsData | null;
  recentChanges?: Record<string, number>;
}

const MobileStats: React.FC<MobileStatsProps> = ({ stats, recentChanges }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800/50">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          <span className="text-sm font-medium text-zinc-300">数字孪生</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-red-400 font-mono">{Math.round((stats?.sync_progress || 0) * 100)}%</span>
          <svg
            className={`w-4 h-4 text-zinc-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      <div className="flex gap-4 mt-3">
        <div className="flex-1 text-center">
          <div className="text-lg font-bold text-red-400 font-mono">{stats?.streak_days || 0}</div>
          <div className="text-[10px] text-zinc-500">连续天数</div>
        </div>
        <div className="flex-1 text-center">
          <div className="text-lg font-bold text-red-400 font-mono">{stats?.data_points_collected || 0}</div>
          <div className="text-[10px] text-zinc-500">数据点</div>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-zinc-800/50">
          <BalanceScales dimensions={stats?.dimensions || {}} changes={recentChanges} compact />

          {stats?.insights && stats.insights.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] text-zinc-500 mb-2">AI 洞察</div>
              {stats.insights.map((insight, i) => (
                <p key={i} className="text-[11px] text-zinc-400 leading-relaxed">• {insight}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ==================== 数字孪生面板 (桌面端) ====================
interface DigitalTwinPanelProps {
  stats: StatsData | null;
  loading: boolean;
  recentChanges?: Record<string, number>;
}

const DigitalTwinPanel: React.FC<DigitalTwinPanelProps> = ({ stats, loading, recentChanges }) => {
  if (loading) {
    return (
      <div className="h-full rounded-xl border border-zinc-800/50 bg-zinc-900/30 p-5 animate-pulse">
        <div className="h-4 bg-zinc-800 rounded w-20 mb-4" />
        <div className="space-y-4">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="h-8 bg-zinc-800/50 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full rounded-xl border border-zinc-800/50 bg-zinc-900/30 p-5 flex flex-col">
      <h2 className="text-sm font-medium text-zinc-300 mb-4 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
        数字孪生
      </h2>

      <div className="flex-1">
        <BalanceScales dimensions={stats?.dimensions || {}} changes={recentChanges} />
      </div>

      <div className="mt-5">
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-zinc-500">模型同步进度</span>
          <span className="text-red-400 font-mono">{Math.round((stats?.sync_progress || 0) * 100)}%</span>
        </div>
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-red-600 to-red-400 rounded-full transition-all duration-500"
            style={{ width: `${(stats?.sync_progress || 0) * 100}%` }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="bg-zinc-800/30 rounded-lg p-3">
          <div className="text-lg font-bold text-red-400 font-mono">{stats?.streak_days || 0}</div>
          <div className="text-[10px] text-zinc-500">连续天数</div>
        </div>
        <div className="bg-zinc-800/30 rounded-lg p-3">
          <div className="text-lg font-bold text-red-400 font-mono">{stats?.data_points_collected || 0}</div>
          <div className="text-[10px] text-zinc-500">数据点</div>
        </div>
      </div>

      {stats?.insights && stats.insights.length > 0 && (
        <div className="mt-4 pt-4 border-t border-zinc-800/50">
          <div className="text-[10px] text-zinc-500 mb-2">AI 洞察</div>
          {stats.insights.map((insight, i) => (
            <p key={i} className="text-[11px] text-zinc-400 leading-relaxed">• {insight}</p>
          ))}
        </div>
      )}
    </div>
  );
};

// ==================== 决策推演面板 ====================
interface DecisionPanelProps {
  questions: Question[];
  loading: boolean;
  onSubmit: (questionId: string, optionId: string) => Promise<SubmissionResult | null>;
  mobile?: boolean;
}

const DecisionPanel: React.FC<DecisionPanelProps> = ({ questions, loading, onSubmit, mobile }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmissionResult | null>(null);

  const currentQuestion = questions[currentIndex];

  const handleSelect = async (optionId: string) => {
    if (submitting || result) return;
    setSelectedOption(optionId);
    setSubmitting(true);
    const res = await onSubmit(currentQuestion.question_id, optionId);
    setResult(res);
    setSubmitting(false);
  };

  const handleNext = () => {
    setSelectedOption(null);
    setResult(null);
    setCurrentIndex(prev => Math.min(prev + 1, questions.length - 1));
  };

  if (loading) {
    return (
      <div className={`rounded-xl border border-zinc-800/50 bg-zinc-900/30 ${mobile ? 'p-4' : 'h-full p-5'} animate-pulse`}>
        <div className="h-4 bg-zinc-800 rounded w-24 mb-4" />
        <div className={`${mobile ? 'h-24' : 'h-32'} bg-zinc-800/50 rounded-lg mb-4`} />
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="h-12 bg-zinc-800/30 rounded-lg" />)}
        </div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className={`rounded-xl border border-zinc-800/50 bg-zinc-900/30 ${mobile ? 'p-4' : 'h-full p-5'} flex items-center justify-center`}>
        <div className="text-center py-8">
          <div className="text-4xl mb-3">✓</div>
          <div className="text-zinc-400">今日题目已完成</div>
          <div className="text-xs text-zinc-600 mt-1">明天再来挑战</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-zinc-800/50 bg-zinc-900/30 ${mobile ? 'p-4' : 'h-full p-5'} flex flex-col`}>
      <div className="flex items-center justify-between mb-3 md:mb-4">
        <h2 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
          <span className="text-red-500">◆</span>
          决策推演
        </h2>
        <span className="text-xs text-zinc-500">{currentIndex + 1}/{questions.length}</span>
      </div>

      <div className={`bg-zinc-800/30 rounded-lg ${mobile ? 'p-3' : 'p-4'} mb-3 md:mb-4`}>
        <div className="text-[10px] text-zinc-500 mb-2 flex items-center gap-2">
          <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded text-[9px]">
            {currentQuestion.category}
          </span>
          商业情境
        </div>
        <p className={`${mobile ? 'text-xs' : 'text-sm'} text-zinc-300 leading-relaxed`}>{currentQuestion.scenario}</p>
      </div>

      <div className="flex-1 space-y-2">
        {currentQuestion.options.map((option) => {
          const isSelected = selectedOption === option.id;
          const isDisabled = submitting || result !== null;

          return (
            <button
              key={option.id}
              onClick={() => handleSelect(option.id)}
              disabled={isDisabled}
              className={`w-full ${mobile ? 'p-3' : 'p-4'} rounded-lg border text-left transition-all duration-200 ${
                isSelected ? 'border-red-500/50 bg-red-500/10' : 'border-zinc-800/50 bg-zinc-800/20 hover:border-zinc-700 hover:bg-zinc-800/40'
              } ${isDisabled && !isSelected ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="flex items-start gap-2 md:gap-3">
                <span className={`w-5 h-5 md:w-6 md:h-6 rounded-full flex items-center justify-center text-xs font-medium shrink-0 ${
                  isSelected ? 'bg-red-500 text-white' : 'bg-zinc-700 text-zinc-400'
                }`}>
                  {option.id}
                </span>
                <span className={`${mobile ? 'text-xs' : 'text-sm'} text-zinc-300`}>{option.text}</span>
              </div>
            </button>
          );
        })}
      </div>

      {result && (
        <div className={`mt-3 md:mt-4 ${mobile ? 'p-3' : 'p-4'} bg-zinc-800/50 rounded-lg border border-zinc-700/50`}>
          <div className="text-xs text-zinc-400 mb-2">{result.ai_reasoning}</div>

          {result.dimension_changes && (
            <div className="mt-2 md:mt-3 flex flex-wrap gap-1.5 md:gap-2">
              {Object.entries(result.dimension_changes)
                .filter(([_, v]) => v !== 0)
                .map(([key, value]) => {
                  const spec = DIMENSION_SPECTRUM[key];
                  const direction = value > 0 ? spec?.right : spec?.left;
                  return (
                    <span key={key} className="px-2 py-1 rounded text-[10px] bg-zinc-700/50 text-zinc-300">
                      {DIMENSION_LABELS[key]} → {direction}
                    </span>
                  );
                })}
            </div>
          )}

          {currentIndex < questions.length - 1 && (
            <button
              onClick={handleNext}
              className="mt-3 w-full py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm transition-colors"
            >
              下一题
            </button>
          )}
        </div>
      )}

      {submitting && (
        <div className="mt-3 md:mt-4 text-center text-xs text-zinc-500">
          <span className="animate-pulse">分析中...</span>
        </div>
      )}
    </div>
  );
};

// ==================== 资讯面板 ====================
interface NewsPanelProps {
  hotTopics: HotTopic[];
  loading: boolean;
  mobile?: boolean;
}

const NewsPanel: React.FC<NewsPanelProps> = ({ hotTopics, loading, mobile }) => {
  const [expanded, setExpanded] = useState(false);
  const displayTopics = mobile && !expanded ? hotTopics.slice(0, 2) : hotTopics;

  if (loading) {
    return (
      <div className={`rounded-xl border border-zinc-800/50 bg-zinc-900/30 ${mobile ? 'p-4' : 'h-full p-5'} animate-pulse`}>
        <div className="h-4 bg-zinc-800 rounded w-20 mb-4" />
        <div className="space-y-3">
          {[1,2].map(i => <div key={i} className="h-16 bg-zinc-800/30 rounded-lg" />)}
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-zinc-800/50 bg-zinc-900/30 ${mobile ? 'p-4' : 'h-full p-5'} flex flex-col`}>
      <h2 className="text-sm font-medium text-zinc-300 mb-3 md:mb-4 flex items-center gap-2">
        <span className="text-red-500">◆</span>
        热门资讯
      </h2>

      <div className={`${mobile ? '' : 'flex-1'} space-y-2 md:space-y-3 ${mobile ? '' : 'overflow-auto'}`}>
        {displayTopics.length > 0 ? (
          displayTopics.map((topic, i) => (
            <a
              key={i}
              href={topic.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`block ${mobile ? 'p-2.5' : 'p-3'} bg-zinc-800/30 rounded-lg hover:bg-zinc-800/50 transition-colors cursor-pointer group`}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded text-[9px]">
                  {topic.category}
                </span>
                <span className="text-[9px] text-zinc-600">{topic.source}</span>
              </div>
              <p className="text-xs text-zinc-300 font-medium line-clamp-2 group-hover:text-red-400 transition-colors">
                {topic.title}
              </p>
            </a>
          ))
        ) : (
          <div className="text-center text-zinc-600 text-xs py-4 md:py-8">
            暂无热门资讯
          </div>
        )}
      </div>

      {mobile && hotTopics.length > 2 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 text-xs text-zinc-500 hover:text-zinc-300 flex items-center justify-center gap-1"
        >
          {expanded ? '收起' : `查看全部 (${hotTopics.length})`}
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      )}

      {!mobile && (
        <div className="mt-4 pt-4 border-t border-zinc-800/50">
          <div className="text-[10px] text-zinc-500 mb-2">关注标签</div>
          <div className="flex flex-wrap gap-1.5">
            {["AI", "创业", "投资", "管理", "科技"].map(tag => (
              <span key={tag} className="px-2 py-1 bg-zinc-800 rounded text-[10px] text-zinc-400 hover:text-red-400 cursor-pointer transition-colors">
                #{tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ==================== 主组件 ====================
interface TwinDashboardProps { userId?: string; }

const TwinDashboard: React.FC<TwinDashboardProps> = ({ userId: propUserId }) => {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [recentChanges, setRecentChanges] = useState<Record<string, number> | undefined>();
  const [hotTopics, setHotTopics] = useState<HotTopic[]>([]);
  const userId = propUserId || 'default_user';

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [statsRes, questionsRes, topicsRes] = await Promise.all([
          fetch(`${API_BASE}/api/soul/stats`, { headers: getAuthHeaders(), credentials: 'include' }),
          fetch(`${API_BASE}/api/soul/sandbox/daily_v2`, { headers: getAuthHeaders(), credentials: 'include' }),
          fetch(`${API_BASE}/api/soul/hot_topics`, { headers: getAuthHeaders(), credentials: 'include' })
        ]);

        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data);
        }

        if (questionsRes.ok) {
          const data = await questionsRes.json();
          setQuestions(data.questions || []);
        }

        if (topicsRes.ok) {
          const data = await topicsRes.json();
          setHotTopics(data.topics || []);
        }
      } catch (err) {
        console.error('Failed to fetch data:', err);
      }
      setLoading(false);
    };

    fetchData();
  }, [userId]);

  const handleSubmit = async (questionId: string, optionId: string): Promise<SubmissionResult | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/soul/sandbox/submit`, {
        method: 'POST',
        headers: getAuthHeaders(),
        credentials: 'include',
        body: JSON.stringify({ question_id: questionId, selected_option_id: optionId })
      });

      if (res.ok) {
        const result: SubmissionResult = await res.json();

        if (result.dimension_changes) {
          setRecentChanges(result.dimension_changes);

          setStats(prev => {
            if (!prev) return prev;
            const newDimensions = { ...prev.dimensions };
            Object.entries(result.dimension_changes || {}).forEach(([key, change]) => {
              if (key in newDimensions) {
                newDimensions[key as keyof typeof newDimensions] =
                  Math.max(0, Math.min(1, newDimensions[key as keyof typeof newDimensions] + change));
              }
            });
            return {
              ...prev,
              dimensions: newDimensions,
              sync_progress: Math.min(0.95, (prev.sync_progress || 0) + 0.005),
              data_points_collected: (prev.data_points_collected || 0) + 1
            };
          });

          setTimeout(() => setRecentChanges(undefined), 3000);
        }

        return result;
      }
    } catch (err) {
      console.error('Submit failed:', err);
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100">
      {/* ===== 移动端布局 ===== */}
      <div className="md:hidden p-4 pb-20 space-y-4">
        <div className="mb-2">
          <h1 className="text-lg font-semibold text-zinc-100">Soul 校准</h1>
          <p className="text-[11px] text-zinc-500">通过决策推演，让 AI 更懂你</p>
        </div>

        <MobileStats stats={stats} recentChanges={recentChanges} />
        <DecisionPanel questions={questions} loading={loading} onSubmit={handleSubmit} mobile />
        <NewsPanel hotTopics={hotTopics} loading={loading} mobile />
      </div>

      {/* ===== 桌面端布局 ===== */}
      <div className="hidden md:block p-6">
        <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <h1 className="text-xl font-semibold text-zinc-100">Soul 校准中心</h1>
            <p className="text-xs text-zinc-500 mt-1">通过决策推演，让 AI 更懂你</p>
          </div>

          <div className="grid grid-cols-12 gap-5" style={{ minHeight: 'calc(100vh - 140px)' }}>
            <div className="col-span-3">
              <DigitalTwinPanel stats={stats} loading={loading} recentChanges={recentChanges} />
            </div>
            <div className="col-span-6">
              <DecisionPanel questions={questions} loading={loading} onSubmit={handleSubmit} />
            </div>
            <div className="col-span-3">
              <NewsPanel hotTopics={hotTopics} loading={loading} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TwinDashboard;
