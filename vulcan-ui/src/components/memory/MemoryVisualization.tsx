"use client";

import { useState, useEffect } from "react";
import {
  Users,
  Calendar,
  Brain,
  TrendingUp,
  Tag,
  MessageSquare,
} from "lucide-react";

interface UserProfile {
  name: string;
  role: string;
  expertise: string[];
  preferences: {
    key: string;
    value: string;
  }[];
  interactionCount: number;
}

interface ConversationEntry {
  id: string;
  timestamp: number;
  topic: string;
  summary: string;
  tags: string[];
  messageCount: number;
}

interface MemoryProfileResponse {
  user_id: string;
  memories: string[];
  memory_count: number;
  last_updated: string;
}

interface ConversationResponse {
  id: string;
  timestamp: string;
  preview: string;
  message_count: number;
}

interface TimelineResponse {
  conversations: ConversationResponse[];
  total_count: number;
}

export default function MemoryVisualization() {
  const [activeTab, setActiveTab] = useState<"profile" | "timeline">("profile");
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [conversations, setConversations] = useState<ConversationEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch user profile from API
  useEffect(() => {
    if (activeTab !== "profile") return;

    const fetchProfile = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('http://100.79.150.62:8001/api/memory/profile');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data: MemoryProfileResponse = await response.json();

        // Transform API data to UserProfile format
        const profile: UserProfile = {
          name: "Vulcan Brain User",
          role: "系统用户",
          expertise: ["AI Engineering", "System Architecture"],
          preferences: data.memories.map((mem) => {
            const [key, ...valueParts] = mem.split(':');
            return {
              key: key.trim(),
              value: valueParts.join(':').trim()
            };
          }),
          interactionCount: data.memory_count,
        };

        setUserProfile(profile);
        setIsLoading(false);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch profile:', err);
        setError(err.message);
        setIsLoading(false);
      }
    };

    fetchProfile();
  }, [activeTab]);

  // Fetch conversation timeline from API
  useEffect(() => {
    if (activeTab !== "timeline") return;

    const fetchTimeline = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('http://100.79.150.62:8001/api/memory/timeline');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data: TimelineResponse = await response.json();

        // Transform API data to ConversationEntry format
        const convs: ConversationEntry[] = data.conversations.map((conv) => ({
          id: conv.id,
          timestamp: new Date(conv.timestamp).getTime(),
          topic: conv.preview,
          summary: conv.preview,
          tags: ["对话记录"],
          messageCount: conv.message_count,
        }));

        setConversations(convs);
        setIsLoading(false);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch timeline:', err);
        setError(err.message);
        setIsLoading(false);
      }
    };

    fetchTimeline();
  }, [activeTab]);

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);

    if (diffInHours < 1) return "刚刚";
    if (diffInHours < 24) return `${Math.floor(diffInHours)} 小时前`;
    if (diffInHours < 48) return "昨天";
    return date.toLocaleDateString("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              <h1 className="text-2xl font-semibold">Memory System</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              用户画像与对话记忆可视化
            </p>
          </div>

          {/* Tab Switcher */}
          <div className="flex gap-1 bg-accent/50 p-1 rounded-lg">
            <button
              onClick={() => setActiveTab("profile")}
              className={`px-4 py-2 rounded-md text-sm transition-colors ${
                activeTab === "profile"
                  ? "bg-card text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Users className="w-4 h-4 inline mr-1" />
              User Profile
            </button>
            <button
              onClick={() => setActiveTab("timeline")}
              className={`px-4 py-2 rounded-md text-sm transition-colors ${
                activeTab === "timeline"
                  ? "bg-card text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Calendar className="w-4 h-4 inline mr-1" />
              Timeline
            </button>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="text-center text-muted-foreground py-8">
            Loading {activeTab === "profile" ? "profile" : "timeline"}...
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="text-center text-destructive py-8">
            ❌ Error: {error}
          </div>
        )}

        {/* Profile Tab */}
        {activeTab === "profile" && userProfile && !isLoading && (
          <div className="space-y-6">
            {/* Basic Info */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-start gap-4">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
                  <Users className="w-8 h-8 text-primary" />
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-semibold mb-1">{userProfile.name}</h2>
                  <p className="text-muted-foreground text-sm mb-3">
                    {userProfile.role}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <MessageSquare className="w-4 h-4" />
                    <span>{userProfile.interactionCount} 条记忆</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Expertise */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">Expertise Areas</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {userProfile.expertise.map((skill, index) => (
                  <span
                    key={index}
                    className="px-3 py-1.5 bg-primary/10 text-primary rounded-full text-xs font-medium"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>

            {/* Preferences */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Tag className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">Memory Records</h3>
              </div>
              <div className="space-y-3">
                {userProfile.preferences.map((pref, index) => (
                  <div key={index} className="flex items-start gap-3">
                    <div className="text-xs font-semibold text-muted-foreground min-w-[100px]">
                      {pref.key}
                    </div>
                    <div className="flex-1 text-sm">{pref.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Info Box */}
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <span className="text-primary">ℹ️</span>
                Profile Generation
              </h3>
              <p className="text-xs text-muted-foreground">
                用户画像通过 Vulcan Brain 的 Memory 模块自动提取。使用{" "}
                <code className="px-1.5 py-0.5 bg-background rounded">
                  GET /api/memory/profile
                </code>{" "}
                获取最新画像数据。
              </p>
            </div>
          </div>
        )}

        {/* Timeline Tab */}
        {activeTab === "timeline" && !isLoading && (
          <div className="space-y-4">
            {conversations.length > 0 ? (
              <>
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className="bg-card border border-border rounded-lg p-5 hover:border-primary/50 transition-colors"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-sm font-semibold">{conv.topic}</h3>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(conv.timestamp)}
                      </span>
                    </div>

                    {/* Summary */}
                    <p className="text-sm text-muted-foreground mb-3">
                      {conv.summary}
                    </p>

                    {/* Tags */}
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      {conv.tags.map((tag, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-accent text-xs rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <MessageSquare className="w-3.5 h-3.5" />
                      <span>{conv.messageCount} 条消息</span>
                    </div>
                  </div>
                ))}

                {/* Load More */}
                <button className="w-full py-3 bg-accent hover:bg-accent/80 rounded-lg text-sm transition-colors">
                  Load More Conversations
                </button>
              </>
            ) : (
              <div className="text-center text-muted-foreground py-8">
                暂无对话记录
              </div>
            )}

            {/* Info Box */}
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <span className="text-primary">ℹ️</span>
                Timeline API
              </h3>
              <p className="text-xs text-muted-foreground">
                对话历史通过{" "}
                <code className="px-1.5 py-0.5 bg-background rounded">
                  GET /api/memory/timeline
                </code>{" "}
                获取，支持分页和时间范围过滤。
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
