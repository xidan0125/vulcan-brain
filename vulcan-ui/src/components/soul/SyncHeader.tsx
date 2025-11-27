"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, Cpu, Activity } from "lucide-react";

interface SyncHeaderProps {
  syncRate: number;
  onSyncRateChange?: (delta: number) => void;
}

export default function SyncHeader({ syncRate, onSyncRateChange }: SyncHeaderProps) {
  const [displayRate, setDisplayRate] = useState(syncRate);
  const [isFlashing, setIsFlashing] = useState(false);
  
  useEffect(() => {
    if (syncRate !== displayRate) {
      setIsFlashing(true);
      // Play ding sound
      const audio = new Audio("/sounds/ding.mp3");
      audio.volume = 0.2;
      audio.play().catch(() => {});
      
      // Animate number
      const start = displayRate;
      const end = syncRate;
      const duration = 500;
      const startTime = Date.now();
      
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        setDisplayRate(start + (end - start) * progress);
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          setTimeout(() => setIsFlashing(false), 300);
        }
      };
      animate();
    }
  }, [syncRate]);

  return (
    <div className="h-20 bg-[#09090b] border-b border-zinc-800 flex items-center justify-between px-6">
      {/* Left: Security Shield */}
      <div className="flex items-center gap-3 group cursor-pointer">
        <div className="relative">
          <Shield className="w-8 h-8 text-emerald-500" />
          <div className="absolute -top-1 -right-1 w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
        </div>
        <div className="opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="text-xs text-emerald-500 font-mono">Air-Gapped</div>
          <div className="text-[10px] text-zinc-600">Local Processing Only</div>
        </div>
      </div>
      
      {/* Center: Sync Rate */}
      <div className="flex flex-col items-center">
        <div className="text-xs text-zinc-500 mb-1 font-mono">DIGITAL TWIN SYNC</div>
        <div className="flex items-center gap-2">
          <motion.div 
            className="text-4xl font-bold font-mono"
            animate={{ 
              color: isFlashing ? "#f97316" : "#ffffff",
              scale: isFlashing ? 1.1 : 1
            }}
            transition={{ duration: 0.2 }}
          >
            {displayRate.toFixed(1)}%
          </motion.div>
          
          {/* Waveform visualization */}
          <div className="flex items-end gap-0.5 h-8">
            {[...Array(12)].map((_, i) => (
              <motion.div
                key={i}
                className="w-1 bg-[#f97316] rounded-full"
                animate={{
                  height: [8, 16 + Math.random() * 16, 8],
                }}
                transition={{
                  duration: 0.8,
                  repeat: Infinity,
                  delay: i * 0.1,
                }}
              />
            ))}
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="w-48 h-1 bg-zinc-800 rounded-full mt-2 overflow-hidden">
          <motion.div 
            className="h-full bg-gradient-to-r from-[#f97316] to-[#fb923c]"
            animate={{ width: `${displayRate}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>
      
      {/* Right: Dual GPU Monitor */}
      <div className="flex items-center gap-4">
        <div className="flex flex-col items-end">
          <div className="text-xs text-zinc-500 font-mono mb-1">DUAL 5090</div>
          <div className="flex gap-2">
            {[0, 1].map((gpu) => (
              <div key={gpu} className="flex items-center gap-1">
                <Cpu className="w-4 h-4 text-zinc-600" />
                <div className="flex items-end gap-0.5">
                  {[...Array(4)].map((_, i) => (
                    <motion.div
                      key={i}
                      className="w-1 bg-[#f97316] rounded-sm"
                      animate={{
                        height: [4, 8 + Math.random() * 8, 4],
                        opacity: [0.5, 1, 0.5],
                      }}
                      transition={{
                        duration: 0.5,
                        repeat: Infinity,
                        delay: i * 0.1 + gpu * 0.2,
                      }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
