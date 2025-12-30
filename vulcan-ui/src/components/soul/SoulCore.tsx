'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Fingerprint, X, Zap, TrendingUp, Users, Shield, Clock, Brain } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';

interface SoulDimensions {
  risk_appetite: number;
  time_horizon: number;
  strategic_drive: number;
  people_philosophy: number;
  control_style: number;
  ethical_boundary: number;
}

interface SoulData {
  sync_progress: number;
  streak_days: number;
  dimensions: SoulDimensions;
  data_points_collected: number;
}

const DIMENSION_CONFIG = {
  risk_appetite: {
    label: '风险阈值',
    left: '稳健',
    right: '激进',
    icon: TrendingUp,
    color: '#ef4444'
  },
  time_horizon: {
    label: '时间视界',
    left: '短期',
    right: '长期',
    icon: Clock,
    color: '#f97316'
  },
  strategic_drive: {
    label: '战略驱动',
    left: '防守',
    right: '进攻',
    icon: Zap,
    color: '#eab308'
  },
  people_philosophy: {
    label: '人际哲学',
    left: '独立',
    right: '协作',
    icon: Users,
    color: '#22c55e'
  },
  control_style: {
    label: '控制风格',
    left: '授权',
    right: '集中',
    icon: Brain,
    color: '#3b82f6'
  },
  ethical_boundary: {
    label: '伦理边界',
    left: '灵活',
    right: '原则',
    icon: Shield,
    color: '#a855f7'
  }
};

// SVG 六边形雷达图
const HexagonRadar = ({ dimensions }: { dimensions: SoulDimensions }) => {
  const size = 140;
  const center = size / 2;
  const maxRadius = 50;

  const keys = Object.keys(DIMENSION_CONFIG) as (keyof SoulDimensions)[];

  const getPoint = (index: number, value: number) => {
    const angle = (Math.PI / 3) * index - Math.PI / 2;
    const normalizedValue = value > 1 ? value / 100 : value; // 兼容0-100和0-1两种格式
    const radius = maxRadius * Math.min(Math.max(normalizedValue, 0), 1);
    return {
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle)
    };
  };

  const dataPoints = keys.map((key, i) => getPoint(i, dimensions[key] || 0.5));
  const dataPath = dataPoints.map((p, i) => (i === 0 ? 'M' : 'L') + ' ' + p.x + ' ' + p.y).join(' ') + ' Z';

  const bgLevels = [0.25, 0.5, 0.75, 1];

  return (
    <svg width={size} height={size} viewBox={'0 0 ' + size + ' ' + size}>
      {bgLevels.map((level, li) => {
        const points = keys.map((_, i) => getPoint(i, level));
        const path = points.map((p, i) => (i === 0 ? 'M' : 'L') + ' ' + p.x + ' ' + p.y).join(' ') + ' Z';
        return (
          <path
            key={li}
            d={path}
            fill="none"
            stroke="#27272a"
            strokeWidth="1"
            opacity={0.5}
          />
        );
      })}

      {keys.map((_, i) => {
        const end = getPoint(i, 1);
        return (
          <line
            key={i}
            x1={center}
            y1={center}
            x2={end.x}
            y2={end.y}
            stroke="#27272a"
            strokeWidth="1"
            opacity={0.3}
          />
        );
      })}

      <motion.path
        d={dataPath}
        fill="url(#soulGradient)"
        fillOpacity="0.3"
        stroke="url(#soulStroke)"
        strokeWidth="2"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      />

      {dataPoints.map((p, i) => (
        <motion.circle
          key={i}
          cx={p.x}
          cy={p.y}
          r="4"
          fill={DIMENSION_CONFIG[keys[i]].color}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: i * 0.1, duration: 0.3 }}
        />
      ))}

      <defs>
        <linearGradient id="soulGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f97316" />
          <stop offset="100%" stopColor="#ef4444" />
        </linearGradient>
        <linearGradient id="soulStroke" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f97316" />
          <stop offset="100%" stopColor="#ef4444" />
        </linearGradient>
      </defs>
    </svg>
  );
};

// 维度条组件 - 修复：显示指针位置而非填充
const DimensionBar = ({
  dimension,
  value
}: {
  dimension: keyof typeof DIMENSION_CONFIG;
  value: number;
}) => {
  const config = DIMENSION_CONFIG[dimension];
  const Icon = config.icon;
  // 确保value在0-1范围内
  const rawValue = value || 0.5;
  const normalizedValue = rawValue > 1 ? rawValue / 100 : rawValue; // 兼容0-100和0-1
  const safeValue = Math.min(Math.max(normalizedValue, 0), 1);
  const position = safeValue * 100;

  return (
    <div className="flex items-center gap-2">
      <Icon className="w-3 h-3 text-zinc-500 flex-shrink-0" />
      <div className="flex-1">
        <div className="flex justify-between items-center mb-0.5">
          <span className={'text-[9px] ' + (safeValue < 0.4 ? 'text-zinc-300 font-medium' : 'text-zinc-600')}>{config.left}</span>
          <span className="text-[9px] text-zinc-400 font-medium">{config.label}</span>
          <span className={'text-[9px] ' + (safeValue > 0.6 ? 'text-zinc-300 font-medium' : 'text-zinc-600')}>{config.right}</span>
        </div>
        <div className="relative h-2 bg-zinc-800 rounded-full overflow-visible">
          {/* 中心参考线 */}
          <div className="absolute top-0 left-1/2 w-px h-full bg-zinc-600 -translate-x-1/2 z-10" />
          {/* 滑动指针 */}
          <motion.div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
            style={{ left: position + '%' }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            {/* 外圈光晕 */}
            <div
              className="absolute w-4 h-4 rounded-full -translate-x-1/2 -translate-y-1/2 opacity-30 animate-pulse"
              style={{ backgroundColor: config.color, left: '50%', top: '50%' }}
            />
            {/* 指针本体 */}
            <div
              className="w-3 h-3 rounded-full border-2 border-zinc-900 shadow-lg"
              style={{ backgroundColor: config.color }}
            />
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default function SoulCore() {
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<SoulData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchSoulData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('vulcan_token');
      const res = await fetch(API_BASE + '/api/soul/stats', {
        headers: {
          'Authorization': 'Bearer ' + token,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (err) {
      console.error('Failed to fetch soul data:', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (isOpen && !data) {
      fetchSoulData();
    }
  }, [isOpen, data]);

  // 修复：同步度限制在0-100%
  // sync_progress 可能是 0-1 (旧格式) 或 0-100+ (新格式)
  const rawSync = data ? data.sync_progress : 0;
  const syncPercent = rawSync > 1 ? Math.min(Math.round(rawSync), 100) : Math.min(Math.round(rawSync * 100), 100);

  return (
    <>
      <AnimatePresence mode="wait">
        {!isOpen && (
          <motion.button
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 z-50 group"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
          >
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-orange-500 to-red-500 animate-ping opacity-30" />
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-orange-500 to-red-500 animate-pulse opacity-20" />

            <div className="relative w-12 h-12 rounded-full bg-gradient-to-br from-orange-600 to-red-600 flex items-center justify-center shadow-lg shadow-orange-500/30 border border-orange-400/30">
              <Fingerprint className="w-6 h-6 text-white" />
            </div>

            <svg className="absolute inset-0 w-12 h-12 -rotate-90">
              <circle
                cx="24"
                cy="24"
                r="22"
                fill="none"
                stroke="rgba(249,115,22,0.2)"
                strokeWidth="2"
              />
              <circle
                cx="24"
                cy="24"
                r="22"
                fill="none"
                stroke="#f97316"
                strokeWidth="2"
                strokeLinecap="round"
                strokeDasharray={(syncPercent * 1.38) + ' 138'}
                className="transition-all duration-500"
              />
            </svg>

            <div className="absolute right-full mr-3 top-1/2 -translate-y-1/2 px-2 py-1 bg-zinc-900 border border-zinc-700 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
              <span className="text-xs text-zinc-300">数字孪生</span>
              <span className="text-xs text-orange-400 ml-2 font-mono">{syncPercent}%</span>
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              className="fixed bottom-6 right-6 z-50 w-80"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            >
              <div className="bg-[#0a0a0a]/95 backdrop-blur-xl rounded-2xl border border-zinc-800/50 shadow-2xl shadow-black/50 overflow-hidden">
                <div className="px-4 py-3 border-b border-zinc-800/50 flex items-center justify-between bg-gradient-to-r from-orange-500/5 to-red-500/5">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-600 to-red-600 flex items-center justify-center">
                      <Fingerprint className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-100">数字孪生</h3>
                      <p className="text-[10px] text-zinc-500">六维人格画像</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="p-4">
                  {loading ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="w-8 h-8 border-2 border-orange-500/30 border-t-orange-500 rounded-full animate-spin" />
                    </div>
                  ) : data ? (
                    <>
                      <div className="flex items-center justify-around mb-4 pb-4 border-b border-zinc-800/50">
                        <div className="text-center">
                          <div className="text-xl font-bold text-orange-400 font-mono">{syncPercent}%</div>
                          <div className="text-[9px] text-zinc-500">同步度</div>
                        </div>
                        <div className="text-center">
                          <div className="text-xl font-bold text-zinc-200 font-mono">{data.streak_days}</div>
                          <div className="text-[9px] text-zinc-500">连续天数</div>
                        </div>
                        <div className="text-center">
                          <div className="text-xl font-bold text-zinc-200 font-mono">{data.data_points_collected}</div>
                          <div className="text-[9px] text-zinc-500">数据点</div>
                        </div>
                      </div>

                      <div className="flex justify-center mb-4">
                        <HexagonRadar dimensions={data.dimensions} />
                      </div>

                      <div className="space-y-3">
                        {(Object.keys(DIMENSION_CONFIG) as (keyof SoulDimensions)[]).map((key) => (
                          <DimensionBar
                            key={key}
                            dimension={key}
                            value={data.dimensions[key] || 0.5}
                          />
                        ))}
                      </div>

                      <a
                        href="/soul"
                        className="mt-4 flex items-center justify-center gap-2 py-2 rounded-lg bg-zinc-800/50 border border-zinc-700/50 hover:bg-zinc-700/50 hover:border-zinc-600 transition-all text-xs text-zinc-400 hover:text-zinc-200"
                      >
                        <Zap className="w-3.5 h-3.5" />
                        前往校准中心
                      </a>
                    </>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-zinc-500">暂无数据</p>
                      <button
                        onClick={fetchSoulData}
                        className="mt-2 text-xs text-orange-400 hover:text-orange-300"
                      >
                        点击加载
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
