"use client";

import { useState, useEffect, useCallback } from "react";
import { Save, RotateCcw, Sparkles, RefreshCw } from "lucide-react";

interface SoulSettings {
  system_prompt: string;
  creativity: number;
  reasoning_depth: number;
  tool_use_preference: number;
  memory_retention: number;
  updated_at: string | null;
}

interface ConfigResponse {
  config: SoulSettings;
  is_default: boolean;
}

const API_BASE = "http://100.79.150.62:8001";

export default function SoulConfig() {
  const [settings, setSettings] = useState<SoulSettings | null>(null);
  const [isDefault, setIsDefault] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Fetch config from API
  const fetchConfig = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/api/soul/config`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data: ConfigResponse = await response.json();
      setSettings(data.config);
      setIsDefault(data.is_default);
      setError(null);
    } catch (err: any) {
      console.error("Failed to fetch config:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    if (!settings) return;

    try {
      setIsSaving(true);
      const params = new URLSearchParams({
        system_prompt: settings.system_prompt,
        creativity: settings.creativity.toString(),
        reasoning_depth: settings.reasoning_depth.toString(),
        tool_use_preference: settings.tool_use_preference.toString(),
        memory_retention: settings.memory_retention.toString(),
      });

      const response = await fetch(`${API_BASE}/api/soul/update?${params}`, {
        method: "POST",
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Save failed: ${response.status}`);
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      await fetchConfig(); // Refresh to get updated_at
    } catch (err: any) {
      console.error("Save error:", err);
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/api/soul/reset`, {
        method: "POST",
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Reset failed: ${response.status}`);
      }

      await fetchConfig();
    } catch (err: any) {
      console.error("Reset error:", err);
      setError(err.message);
      setIsLoading(false);
    }
  };

  const updateSlider = (key: keyof SoulSettings, value: number) => {
    if (!settings) return;
    setSettings((prev) => prev ? { ...prev, [key]: value } : null);
  };

  if (isLoading && !settings) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="h-full flex items-center justify-center text-destructive">
        Failed to load configuration
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              <h1 className="text-2xl font-semibold">Soul Configuration</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              定义 Agent 的核心性格和行为模式
              {isDefault && (
                <span className="ml-2 text-xs bg-accent px-2 py-0.5 rounded">
                  Using Defaults
                </span>
              )}
            </p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleReset}
              disabled={isLoading}
              className="px-4 py-2 bg-accent hover:bg-accent/80 rounded-lg transition-colors flex items-center gap-2 text-sm disabled:opacity-50"
            >
              <RotateCcw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
              Reset
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 bg-primary/10 text-primary hover:bg-primary/20 rounded-lg transition-colors flex items-center gap-2 text-sm disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saved ? "Saved!" : isSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 text-sm text-destructive">
            Error: {error}
          </div>
        )}

        {/* System Prompt */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold">System Prompt (Constitution)</label>
            <span className="text-xs text-muted-foreground">
              {settings.system_prompt.length} 字符
            </span>
          </div>
          <textarea
            value={settings.system_prompt}
            onChange={(e) =>
              setSettings((prev) => prev ? { ...prev, system_prompt: e.target.value } : null)
            }
            className="w-full h-64 bg-card border border-border rounded-lg p-4 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary/50"
            placeholder="Enter system prompt..."
          />
          <p className="text-xs text-muted-foreground">
            定义 Agent 的身份、价值观、工作方式和技能。支持使用 &lt;think&gt; 标签进行内部推理。
          </p>
        </div>

        {/* Behavior Parameters */}
        <div className="space-y-6">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs font-semibold text-muted-foreground">
              BEHAVIOR PARAMETERS
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          {/* Creativity */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold">Creativity</label>
              <span className="text-sm text-primary font-mono">
                {settings.creativity}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={settings.creativity}
              onChange={(e) => updateSlider("creativity", parseInt(e.target.value))}
              className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
            />
            <p className="text-xs text-muted-foreground">
              控制回复的创造性和多样性。高值适合头脑风暴，低值适合精确任务。
            </p>
          </div>

          {/* Reasoning Depth */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold">Reasoning Depth</label>
              <span className="text-sm text-primary font-mono">
                {settings.reasoning_depth}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={settings.reasoning_depth}
              onChange={(e) => updateSlider("reasoning_depth", parseInt(e.target.value))}
              className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
            />
            <p className="text-xs text-muted-foreground">
              推理链的深度和详细程度。高值会展示更多 &lt;think&gt; 过程。
            </p>
          </div>

          {/* Tool Use Preference */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold">Tool Use Preference</label>
              <span className="text-sm text-primary font-mono">
                {settings.tool_use_preference}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={settings.tool_use_preference}
              onChange={(e) => updateSlider("tool_use_preference", parseInt(e.target.value))}
              className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
            />
            <p className="text-xs text-muted-foreground">
              主动调用工具的倾向。高值更积极使用外部工具，低值更依赖内部知识。
            </p>
          </div>

          {/* Memory Retention */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold">Memory Retention</label>
              <span className="text-sm text-primary font-mono">
                {settings.memory_retention}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={settings.memory_retention}
              onChange={(e) => updateSlider("memory_retention", parseInt(e.target.value))}
              className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
            />
            <p className="text-xs text-muted-foreground">
              对历史对话的记忆强度。高值会更多引用历史信息，低值更独立处理每个请求。
            </p>
          </div>
        </div>

        {/* Last Updated */}
        {settings.updated_at && (
          <div className="text-xs text-muted-foreground text-right">
            Last updated: {new Date(settings.updated_at).toLocaleString("zh-CN")}
          </div>
        )}

        {/* Info Box */}
        <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <span className="text-primary">ℹ️</span>
            API Integration
          </h3>
          <p className="text-xs text-muted-foreground">
            配置通过 <code className="px-1.5 py-0.5 bg-background rounded">GET/POST /api/soul/config</code> 与后端同步。更改将在下次对话时生效。
          </p>
        </div>
      </div>
    </div>
  );
}
