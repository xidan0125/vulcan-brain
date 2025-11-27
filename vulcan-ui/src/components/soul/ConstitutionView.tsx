"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Shield, Brain, Target, Edit3 } from "lucide-react";

interface ConstitutionItem {
  id: string;
  category: "redline" | "core" | "style";
  content: string;
}

interface ConstitutionViewProps {
  constitution: ConstitutionItem[];
  onEdit?: (item: ConstitutionItem) => void;
}

export default function ConstitutionView({ constitution, onEdit }: ConstitutionViewProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  
  const redlines = constitution.filter(c => c.category === "redline");
  const coreValues = constitution.filter(c => c.category === "core");
  const decisionStyle = constitution.filter(c => c.category === "style");
  
  const CategorySection = ({ 
    title, 
    icon: Icon, 
    items, 
    color 
  }: { 
    title: string; 
    icon: any; 
    items: ConstitutionItem[]; 
    color: string;
  }) => (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className={`text-xs font-mono font-bold ${color}`}>{title}</span>
      </div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <motion.div
            key={item.id}
            className="group relative"
            onHoverStart={() => setHoveredId(item.id)}
            onHoverEnd={() => setHoveredId(null)}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <div className="flex items-start gap-2 p-3 bg-zinc-900/50 rounded border border-zinc-800 hover:border-zinc-700 transition-colors">
              <span className="text-zinc-600 font-mono text-xs">{String(index + 1).padStart(2, '0')}</span>
              <p className="text-sm text-zinc-300 flex-1 font-mono leading-relaxed">
                {item.content}
              </p>
              {onEdit && (
                <button 
                  onClick={() => onEdit(item)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-zinc-800 rounded transition-all"
                >
                  <Edit3 className="w-3 h-3 text-zinc-500" />
                </button>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="h-full bg-[#0a0a0b] border-r border-zinc-800 p-6 overflow-y-auto">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-bold text-white mb-1">宪法石碑</h2>
        <p className="text-xs text-zinc-600">Constitution Archive</p>
      </div>
      
      {/* Constitution sections */}
      <CategorySection
        title="🔴 RED LINES"
        icon={Shield}
        items={redlines}
        color="text-red-500"
      />
      
      <CategorySection
        title="🔵 CORE VALUES"
        icon={Brain}
        items={coreValues}
        color="text-blue-500"
      />
      
      <CategorySection
        title="⚪ DECISION STYLE"
        icon={Target}
        items={decisionStyle}
        color="text-zinc-400"
      />
      
      {/* Empty state */}
      {constitution.length === 0 && (
        <div className="text-center py-12">
          <Brain className="w-12 h-12 text-zinc-800 mx-auto mb-3" />
          <p className="text-zinc-600 text-sm">宪法尚未建立</p>
          <p className="text-zinc-700 text-xs">完成创世纪 20 问后生成</p>
        </div>
      )}
    </div>
  );
}
