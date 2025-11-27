"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";

interface AlignmentCard {
  id: string;
  scenario: string;
  optionA: string;
  optionB: string;
  correctAnswer: "A" | "B";
}

interface AlignmentDeckProps {
  cards: AlignmentCard[];
  onFeedback: (cardId: string, selected: "A" | "B", isCorrect: boolean) => void;
  onComplete: () => void;
}

export default function AlignmentDeck({ cards, onFeedback, onComplete }: AlignmentDeckProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<"A" | "B" | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [score, setScore] = useState(0);

  const currentCard = cards[currentIndex];

  const handleSelect = (option: "A" | "B") => {
    if (showResult) return;

    setSelectedAnswer(option);
    setShowResult(true);

    const isCorrect = option === currentCard.correctAnswer;
    if (isCorrect) {
      setScore(prev => prev + 1);
    }

    onFeedback(currentCard.id, option, isCorrect);

    // Auto advance after 1.5s
    setTimeout(() => {
      if (currentIndex < cards.length - 1) {
        setCurrentIndex(prev => prev + 1);
        setSelectedAnswer(null);
        setShowResult(false);
      } else {
        setCompleted(true);
        onComplete();
      }
    }, 1500);
  };

  if (completed) {
    const percentage = Math.round((score / cards.length) * 100);
    const grade = percentage >= 90 ? "S" : percentage >= 80 ? "A" : percentage >= 70 ? "B" : percentage >= 60 ? "C" : "D";

    return (
      <div className="h-full flex flex-col items-center justify-center p-6">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", duration: 0.5 }}
        >
          <Sparkles className="w-16 h-16 text-[#f97316] mb-4" />
        </motion.div>
        <h3 className="text-xl font-bold text-white mb-2">价值观对齐完成！</h3>
        <p className="text-zinc-500 text-sm mb-4">Alignment Test Complete</p>
        <div className="px-6 py-3 bg-[#f97316]/10 rounded-lg mb-2">
          <span className="text-[#f97316] font-mono text-2xl">契合度: {grade} 级</span>
        </div>
        <p className="text-zinc-400 text-sm">{score}/{cards.length} 题正确 ({percentage}%)</p>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6">
        <p className="text-zinc-400">暂无测试题目</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-bold text-white mb-1">价值观对齐测试</h2>
        <p className="text-xs text-zinc-600">Question {currentIndex + 1} of {cards.length}</p>
        <div className="mt-2 h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-[#f97316] transition-all duration-300"
            style={{ width: `${((currentIndex) / cards.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Card area */}
      <div className="flex-1 flex flex-col">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -50 }}
            className="flex-1 flex flex-col"
          >
            {/* Scenario */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5 mb-4">
              <div className="text-xs text-zinc-500 mb-3 font-mono">场景 / Scenario</div>
              <p className="text-white text-sm leading-relaxed">
                {currentCard?.scenario}
              </p>
            </div>

            {/* Options */}
            <div className="space-y-3">
              {/* Option A */}
              <button
                onClick={() => handleSelect("A")}
                disabled={showResult}
                className={`w-full text-left p-4 rounded-lg border transition-all ${
                  showResult
                    ? selectedAnswer === "A"
                      ? currentCard.correctAnswer === "A"
                        ? "bg-emerald-500/20 border-emerald-500 text-emerald-400"
                        : "bg-red-500/20 border-red-500 text-red-400"
                      : currentCard.correctAnswer === "A"
                        ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-400"
                        : "bg-zinc-900 border-zinc-800 text-zinc-400"
                    : "bg-zinc-900 border-zinc-800 hover:border-[#f97316]/50 hover:bg-zinc-800"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${
                    showResult && currentCard.correctAnswer === "A"
                      ? "bg-emerald-500 text-white"
                      : "bg-zinc-700 text-zinc-300"
                  }`}>
                    A
                  </span>
                  <span className="text-sm leading-relaxed">{currentCard?.optionA}</span>
                </div>
              </button>

              {/* Option B */}
              <button
                onClick={() => handleSelect("B")}
                disabled={showResult}
                className={`w-full text-left p-4 rounded-lg border transition-all ${
                  showResult
                    ? selectedAnswer === "B"
                      ? currentCard.correctAnswer === "B"
                        ? "bg-emerald-500/20 border-emerald-500 text-emerald-400"
                        : "bg-red-500/20 border-red-500 text-red-400"
                      : currentCard.correctAnswer === "B"
                        ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-400"
                        : "bg-zinc-900 border-zinc-800 text-zinc-400"
                    : "bg-zinc-900 border-zinc-800 hover:border-[#f97316]/50 hover:bg-zinc-800"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${
                    showResult && currentCard.correctAnswer === "B"
                      ? "bg-emerald-500 text-white"
                      : "bg-zinc-700 text-zinc-300"
                  }`}>
                    B
                  </span>
                  <span className="text-sm leading-relaxed">{currentCard?.optionB}</span>
                </div>
              </button>
            </div>

            {/* Result feedback */}
            {showResult && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`mt-4 p-3 rounded-lg text-center text-sm ${
                  selectedAnswer === currentCard.correctAnswer
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "bg-red-500/10 text-red-400"
                }`}
              >
                {selectedAnswer === currentCard.correctAnswer
                  ? "✓ 价值观一致！"
                  : `✗ 正确答案是 ${currentCard.correctAnswer}`}
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Score */}
      <div className="mt-4 text-center text-xs text-zinc-600">
        当前得分: {score}/{currentIndex + (showResult ? 1 : 0)}
      </div>
    </div>
  );
}
