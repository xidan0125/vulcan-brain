"use client";

import { useState, useCallback } from "react";
import { motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { GENESIS_QUESTIONS, GenesisQuestion } from "@/data/genesisQuestions";

interface GenesisWizardProps {
  onComplete: (answers: Record<number, string>) => void;
}

export default function GenesisWizard({ onComplete }: GenesisWizardProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [exitX, setExitX] = useState(0);

  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const cardOpacity = useTransform(x, [-200, -100, 0, 100, 200], [0.5, 1, 1, 1, 0.5]);

  // A/B 选项高亮：拖动时增强对应方向的选项
  const optionAScale = useTransform(x, [-150, 0, 50], [1.1, 1, 0.95]);
  const optionBScale = useTransform(x, [-50, 0, 150], [0.95, 1, 1.1]);
  const optionAOpacity = useTransform(x, [-150, 0, 100], [1, 0.7, 0.4]);
  const optionBOpacity = useTransform(x, [-100, 0, 150], [0.4, 0.7, 1]);

  const currentQuestion = GENESIS_QUESTIONS[currentIndex];
  const progress = ((currentIndex) / GENESIS_QUESTIONS.length) * 100;

  const handleSwipe = useCallback((direction: "left" | "right") => {
    const answer = direction === "left"
      ? currentQuestion.optionA.value
      : currentQuestion.optionB.value;

    setAnswers(prev => ({ ...prev, [currentQuestion.id]: answer }));
    setExitX(direction === "left" ? -300 : 300);

    // Play swoosh sound
    const audio = new Audio("/sounds/swoosh.mp3");
    audio.volume = 0.3;
    audio.play().catch(() => {});

    setTimeout(() => {
      if (currentIndex < GENESIS_QUESTIONS.length - 1) {
        setCurrentIndex(prev => prev + 1);
        setExitX(0);
      } else {
        // Complete - play ding sound
        const dingAudio = new Audio("/sounds/ding.mp3");
        dingAudio.play().catch(() => {});
        onComplete({ ...answers, [currentQuestion.id]: answer });
      }
    }, 200);
  }, [currentIndex, currentQuestion, answers, onComplete]);

  const handleDragEnd = useCallback((_: any, info: { offset: { x: number } }) => {
    if (info.offset.x < -100) {
      handleSwipe("left");
    } else if (info.offset.x > 100) {
      handleSwipe("right");
    }
  }, [handleSwipe]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") handleSwipe("left");
    if (e.key === "ArrowRight") handleSwipe("right");
  }, [handleSwipe]);

  // 点击选项直接选择
  const handleOptionClick = (option: "A" | "B") => {
    handleSwipe(option === "A" ? "left" : "right");
  };

  return (
    <div
      className="fixed inset-0 bg-[#09090b] flex flex-col items-center justify-center"
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      {/* Breathing light effect */}
      <div
        className="absolute inset-0 flex items-center justify-center pointer-events-none"
        style={{ opacity: 0.1 + (progress / 100) * 0.3 }}
      >
        <div className="w-96 h-96 rounded-full bg-[#f97316] blur-[100px] animate-pulse" />
      </div>

      {/* Header */}
      <div className="absolute top-8 left-0 right-0 text-center">
        <h1 className="text-2xl font-bold text-white mb-2">创世纪 20 问</h1>
        <p className="text-zinc-500 text-sm">The Genesis 20 - 灵魂校准协议</p>
      </div>

      {/* Category badge */}
      <div className="absolute top-24 px-4 py-1 rounded-full bg-zinc-800 text-zinc-400 text-xs font-mono">
        {currentQuestion?.category.toUpperCase()}
      </div>

      {/* Main content area with options */}
      <div className="relative flex items-center justify-center gap-8">
        {/* Option A - Left side - 始终可见 */}
        <motion.button
          onClick={() => handleOptionClick("A")}
          style={{ scale: optionAScale, opacity: optionAOpacity }}
          className="w-32 py-4 rounded-xl bg-red-500/20 border-2 border-red-500/50 hover:border-red-500 hover:bg-red-500/30 transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <div className="text-red-400 font-bold text-lg mb-1">A</div>
          <div className="text-red-300 text-sm px-2 leading-tight">
            {currentQuestion?.optionA.label}
          </div>
        </motion.button>

        {/* Card */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            className="relative w-[380px] h-[280px] cursor-grab active:cursor-grabbing"
            style={{ x, rotate, opacity: cardOpacity }}
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            onDragEnd={handleDragEnd}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1, x: 0 }}
            exit={{ x: exitX, opacity: 0, transition: { duration: 0.2 } }}
          >
            {/* Card content */}
            <div className="w-full h-full bg-zinc-900 border border-zinc-700 rounded-xl p-6 flex flex-col justify-center shadow-2xl">
              <div className="text-[#f97316] text-xs font-mono mb-4">
                Q{currentIndex + 1}/20
              </div>
              <p className="text-white text-lg leading-relaxed">
                {currentQuestion?.scenario}
              </p>
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Option B - Right side - 始终可见 */}
        <motion.button
          onClick={() => handleOptionClick("B")}
          style={{ scale: optionBScale, opacity: optionBOpacity }}
          className="w-32 py-4 rounded-xl bg-blue-500/20 border-2 border-blue-500/50 hover:border-blue-500 hover:bg-blue-500/30 transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <div className="text-blue-400 font-bold text-lg mb-1">B</div>
          <div className="text-blue-300 text-sm px-2 leading-tight">
            {currentQuestion?.optionB.label}
          </div>
        </motion.button>
      </div>

      {/* Instructions */}
      <div className="absolute bottom-32 text-zinc-500 text-sm">
        点击选项 或 拖动卡片选择
      </div>
      <div className="absolute bottom-24 text-zinc-600 text-xs">
        键盘快捷键: ← A | B →
      </div>

      {/* Progress bar */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 w-64">
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-[#f97316]"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
        <div className="text-center mt-2 text-zinc-500 text-xs font-mono">
          {currentIndex}/{GENESIS_QUESTIONS.length}
        </div>
      </div>
    </div>
  );
}
