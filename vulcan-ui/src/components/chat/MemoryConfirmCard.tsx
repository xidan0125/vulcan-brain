"use client";

import { useState } from "react";
import { Brain, Check, X, Edit2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface PendingMemory {
  id: string;
  key: string;
  value: string;
  category: "identity" | "preference" | "fact";
  confidence: number;
}

interface MemoryConfirmCardProps {
  memories: PendingMemory[];
  onConfirm: (id: string) => void;
  onReject: (id: string) => void;
  onEdit: (id: string, newValue: string) => void;
  onDismissAll: () => void;
}

const categoryLabels: Record<string, { label: string; color: string }> = {
  identity: { label: "身份", color: "bg-blue-500/20 text-blue-400" },
  preference: { label: "偏好", color: "bg-purple-500/20 text-purple-400" },
  fact: { label: "事实", color: "bg-green-500/20 text-green-400" },
};

export default function MemoryConfirmCard({
  memories,
  onConfirm,
  onReject,
  onEdit,
  onDismissAll,
}: MemoryConfirmCardProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  if (memories.length === 0) return null;

  const handleStartEdit = (memory: PendingMemory) => {
    setEditingId(memory.id);
    setEditValue(memory.value);
  };

  const handleSaveEdit = (id: string) => {
    if (editValue.trim()) {
      onEdit(id, editValue.trim());
    }
    setEditingId(null);
    setEditValue("");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue("");
  };

  return (
    <div className="mx-4 my-3 animate-in slide-in-from-bottom-2 duration-300">
      <div className="bg-gradient-to-r from-violet-500/10 via-purple-500/10 to-fuchsia-500/10 
                      border border-purple-500/30 rounded-xl p-4 backdrop-blur-sm">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 bg-purple-500/20 rounded-lg">
            <Brain className="w-4 h-4 text-purple-400" />
          </div>
          <span className="text-sm font-medium text-purple-300">
            Vulcan 想记住以下信息
          </span>
          <Sparkles className="w-3 h-3 text-purple-400/60" />
          <button
            onClick={onDismissAll}
            className="ml-auto text-xs text-gray-500 hover:text-gray-400 transition-colors"
          >
            全部忽略
          </button>
        </div>

        {/* Memory Items */}
        <div className="space-y-2">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="bg-black/20 rounded-lg p-3 border border-white/5"
            >
              {editingId === memory.id ? (
                /* Edit Mode */
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">{memory.key}:</span>
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="flex-1 bg-white/5 border border-white/10 rounded px-2 py-1 
                                 text-sm text-white focus:outline-none focus:border-purple-500"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveEdit(memory.id);
                        if (e.key === "Escape") handleCancelEdit();
                      }}
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={handleCancelEdit}
                      className="px-2 py-1 text-xs text-gray-400 hover:text-white transition-colors"
                    >
                      取消
                    </button>
                    <button
                      onClick={() => handleSaveEdit(memory.id)}
                      className="px-2 py-1 text-xs bg-purple-500 hover:bg-purple-600 
                                 text-white rounded transition-colors"
                    >
                      保存并确认
                    </button>
                  </div>
                </div>
              ) : (
                /* Display Mode */
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-gray-400">{memory.key}</span>
                      <span
                        className={cn(
                          "text-[10px] px-1.5 py-0.5 rounded",
                          categoryLabels[memory.category]?.color || "bg-gray-500/20 text-gray-400"
                        )}
                      >
                        {categoryLabels[memory.category]?.label || memory.category}
                      </span>
                      <span className="text-[10px] text-gray-500">
                        {Math.round(memory.confidence * 100)}%
                      </span>
                    </div>
                    <p className="text-sm text-white truncate">{memory.value}</p>
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleStartEdit(memory)}
                      className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 
                                 hover:text-white transition-colors"
                      title="编辑"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onReject(memory.id)}
                      className="p-1.5 rounded-lg hover:bg-red-500/20 text-gray-400 
                                 hover:text-red-400 transition-colors"
                      title="不用了"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onConfirm(memory.id)}
                      className="p-1.5 rounded-lg hover:bg-green-500/20 text-gray-400 
                                 hover:text-green-400 transition-colors"
                      title="确认"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
