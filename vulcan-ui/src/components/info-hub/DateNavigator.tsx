/**
 * 日期导航组件
 * 用于日报页面的日期选择
 */
import React from 'react';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';

interface DateNavigatorProps {
  date: string;
  onChange: (date: string) => void;
  className?: string;
}

export function DateNavigator({ date, onChange, className = '' }: DateNavigatorProps) {
  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    onChange(current.toISOString().split('T')[0]);
  };

  return (
    <div className={`flex items-center gap-1 bg-zinc-900 rounded-lg p-1 ${className}`}>
      <button
        onClick={() => changeDate(-1)}
        className="p-2 hover:bg-zinc-800 rounded-md transition-colors"
        aria-label="前一天"
      >
        <ChevronLeft className="w-4 h-4 text-zinc-400" />
      </button>
      <div className="flex items-center gap-2 px-3 py-1.5">
        <Calendar className="w-4 h-4 text-orange-400" />
        <input
          type="date"
          value={date}
          onChange={(e) => onChange(e.target.value)}
          className="bg-transparent text-sm text-white focus:outline-none cursor-pointer"
        />
      </div>
      <button
        onClick={() => changeDate(1)}
        className="p-2 hover:bg-zinc-800 rounded-md transition-colors"
        aria-label="后一天"
      >
        <ChevronRight className="w-4 h-4 text-zinc-400" />
      </button>
    </div>
  );
}

export default DateNavigator;
