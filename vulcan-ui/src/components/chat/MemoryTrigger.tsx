'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Sparkles, Zap, Flame, Lightbulb, FileText } from 'lucide-react';
import { useRouter } from 'next/navigation';

// Tier 类型和配置
type MemoryTier = 'core' | 'contextual' | 'background';

interface TierCount {
  core: number;
  contextual: number;
  background: number;
}

interface MemoryTriggerProps {
  pendingCount: number;
  tierCounts?: TierCount;  // 可选的分层统计
}

const tierConfig: Record<MemoryTier, { label: string; icon: typeof Flame; color: string; bgColor: string }> = {
  core: {
    label: '核心',
    icon: Flame,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/20'
  },
  contextual: {
    label: '情境',
    icon: Lightbulb,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20'
  },
  background: {
    label: '背景',
    icon: FileText,
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/20'
  }
};

export const MemoryTrigger: React.FC<MemoryTriggerProps> = ({ pendingCount, tierCounts }) => {
  const router = useRouter();
  const [isHovered, setIsHovered] = useState(false);
  const [triggerBump, setTriggerBump] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (pendingCount > 0) {
      setTriggerBump(true);
      const timer = setTimeout(() => setTriggerBump(false), 300);
      return () => clearTimeout(timer);
    }
  }, [pendingCount]);

  // 有核心记忆时显示详情
  useEffect(() => {
    if (tierCounts?.core && tierCounts.core > 0) {
      setShowDetails(true);
      const timer = setTimeout(() => setShowDetails(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [tierCounts?.core]);

  const isVisible = pendingCount > 0;

  // 判断是否有核心记忆
  const hasCoreMemory = tierCounts?.core && tierCounts.core > 0;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className="fixed bottom-24 right-6 z-50 flex flex-col items-end gap-2"
          initial={{ scale: 0, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0, opacity: 0, y: 20 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20 }}
        >
          {/* Tier 详情浮层 */}
          <AnimatePresence>
            {(isHovered || showDetails) && tierCounts && (tierCounts.core || tierCounts.contextual || tierCounts.background) && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                className="bg-zinc-900/95 backdrop-blur-md border border-zinc-700 rounded-lg p-3 shadow-xl min-w-[160px]"
              >
                <div className="text-[10px] text-zinc-500 mb-2 font-medium">记忆分层</div>
                <div className="space-y-1.5">
                  {tierCounts.core > 0 && (
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded bg-orange-500/20 flex items-center justify-center">
                        <Flame className="w-3 h-3 text-orange-400" />
                      </div>
                      <span className="text-xs text-zinc-300 flex-1">核心</span>
                      <span className="text-xs font-medium text-orange-400">{tierCounts.core}</span>
                    </div>
                  )}
                  {tierCounts.contextual > 0 && (
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded bg-blue-500/20 flex items-center justify-center">
                        <Lightbulb className="w-3 h-3 text-blue-400" />
                      </div>
                      <span className="text-xs text-zinc-300 flex-1">情境</span>
                      <span className="text-xs font-medium text-blue-400">{tierCounts.contextual}</span>
                    </div>
                  )}
                  {tierCounts.background > 0 && (
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded bg-zinc-500/20 flex items-center justify-center">
                        <FileText className="w-3 h-3 text-zinc-400" />
                      </div>
                      <span className="text-xs text-zinc-300 flex-1">背景</span>
                      <span className="text-xs font-medium text-zinc-400">{tierCounts.background}</span>
                    </div>
                  )}
                </div>
                <div className="mt-2 pt-2 border-t border-zinc-800">
                  <div className="text-[9px] text-zinc-500">
                    {tierCounts.core > 0 ? '发现核心身份信息' : '点击查看详情'}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* 主按钮容器 */}
          <div className="relative">
            {/* 外部涟漪效果 - 核心记忆时更明显 */}
            <motion.div
              className={`absolute inset-0 rounded-full ${hasCoreMemory ? 'bg-orange-500/30' : 'bg-orange-500/20'}`}
              animate={{
                scale: [1, 1.5, 1.5],
                opacity: [0.4, 0, 0],
              }}
              transition={{
                duration: hasCoreMemory ? 1.5 : 2,
                ease: "easeInOut",
                repeat: Infinity,
                repeatDelay: hasCoreMemory ? 0.5 : 1
              }}
            />

            {/* 核心记忆时的第二层涟漪 */}
            {hasCoreMemory && (
              <motion.div
                className="absolute inset-0 rounded-full bg-orange-500/20"
                animate={{
                  scale: [1.2, 1.8, 1.8],
                  opacity: [0.3, 0, 0],
                }}
                transition={{
                  duration: 1.5,
                  ease: "easeInOut",
                  repeat: Infinity,
                  repeatDelay: 0.5,
                  delay: 0.3
                }}
              />
            )}

            {/* 核心交互按钮 */}
            <motion.button
              onClick={() => router.push('/memory')}
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
              className={`
                relative flex h-12 w-12 items-center justify-center rounded-full
                bg-zinc-900/90 backdrop-blur-md border
                ${hasCoreMemory
                  ? 'border-orange-500/50 shadow-[0_0_20px_rgba(249,115,22,0.4)]'
                  : 'border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.3)]'
                }
                transition-colors duration-300 hover:bg-zinc-800 hover:border-orange-400
                group
              `}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              animate={triggerBump ? { scale: [1, 1.2, 1] } : {}}
            >
              <div className="relative">
                <Brain
                  className={`h-5 w-5 transition-colors duration-300 ${
                    hasCoreMemory ? 'text-orange-400' : 'text-zinc-400 group-hover:text-orange-400'
                  }`}
                />

                <motion.div
                  className="absolute -top-1 -right-1 text-orange-500"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: isHovered || triggerBump || hasCoreMemory ? 1 : 0 }}
                >
                  <Sparkles size={10} fill="currentColor" />
                </motion.div>
              </div>

              {/* 徽章 - 显示数量和核心标记 */}
              <AnimatePresence>
                {pendingCount > 0 && (
                  <motion.div
                    key="badge"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    className={`absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm ring-2 ring-zinc-950 ${
                      hasCoreMemory
                        ? 'bg-gradient-to-br from-orange-500 to-red-600'
                        : 'bg-gradient-to-br from-orange-500 to-amber-600'
                    }`}
                  >
                    {pendingCount > 9 ? '9+' : pendingCount}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* 核心记忆标记 */}
              {hasCoreMemory && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute -bottom-1 -right-1 w-4 h-4 bg-orange-500 rounded-full flex items-center justify-center shadow-lg"
                >
                  <Flame className="w-2.5 h-2.5 text-white" />
                </motion.div>
              )}
            </motion.button>
          </div>

          {/* Tooltip */}
          <AnimatePresence>
            {isHovered && !showDetails && (
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="absolute right-full top-1/2 -translate-y-1/2 mr-3 whitespace-nowrap rounded-md bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 shadow-xl border border-zinc-700"
              >
                <div className="flex items-center gap-1.5">
                  <Zap size={10} className="text-orange-400" />
                  <span>
                    {pendingCount} 个新记忆点
                    {hasCoreMemory && <span className="text-orange-400 ml-1">(含核心)</span>}
                  </span>
                </div>
                <div className="absolute right-[-4px] top-1/2 -mt-1 h-2 w-2 rotate-45 border-r border-t border-zinc-700 bg-zinc-800" />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default MemoryTrigger;
