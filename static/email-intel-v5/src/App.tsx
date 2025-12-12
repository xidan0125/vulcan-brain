import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  LayoutDashboard,
  Network,
  ListTodo,
  Building2,
  Search,
  Brain,
} from 'lucide-react';
import CommandCenter from './components/CommandCenter';
import RelationshipGraph from './components/RelationshipGraph';
import ActionCenter from './components/ActionCenter';
import CompanyIntel from './components/CompanyIntel';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

type TabType = 'command' | 'relationships' | 'actions' | 'companies' | 'search';

const tabs = [
  { id: 'command', label: '指挥中心', icon: LayoutDashboard },
  { id: 'relationships', label: '关系图谱', icon: Network },
  { id: 'actions', label: '行动中心', icon: ListTodo },
  { id: 'companies', label: '公司画像', icon: Building2 },
  { id: 'search', label: '智能搜索', icon: Search },
];

function AppContent() {
  const [activeTab, setActiveTab] = useState<TabType>('command');

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <header className="h-14 border-b border-zinc-800 flex items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-orange-500" />
          <span className="text-lg font-semibold">Email Intelligence</span>
          <span className="text-xs text-zinc-600 font-mono">V5.0</span>
        </div>
        <div className="text-xs text-zinc-500">
          {new Date().toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long',
          })}
        </div>
      </header>

      <div className="flex h-[calc(100vh-56px)]">
        {/* Sidebar */}
        <nav className="w-56 border-r border-zinc-800 p-3 flex flex-col">
          <div className="space-y-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                    isActive
                      ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                      : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white border border-transparent'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-orange-400' : ''}`} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Stats Summary */}
          <div className="mt-auto pt-4 border-t border-zinc-800">
            <div className="text-xs text-zinc-600 mb-2">快速统计</div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-zinc-500">
                <span>待处理邮件</span>
                <span className="text-orange-400">--</span>
              </div>
              <div className="flex justify-between text-zinc-500">
                <span>活跃联系人</span>
                <span className="text-blue-400">--</span>
              </div>
              <div className="flex justify-between text-zinc-500">
                <span>关系预警</span>
                <span className="text-red-400">--</span>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-auto">
          {activeTab === 'command' && <CommandCenter />}
          {activeTab === 'relationships' && <RelationshipGraph />}
          {activeTab === 'actions' && <ActionCenter />}
          {activeTab === 'companies' && <CompanyIntel />}
          {activeTab === 'search' && <SmartSearch />}
        </main>
      </div>
    </div>
  );
}

// Placeholder for Smart Search
function SmartSearch() {
  const [query, setQuery] = useState('');

  return (
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Smart Search</h2>
        <p className="text-sm text-zinc-500 mt-1">AI驱动的语义搜索</p>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
        <input
          type="text"
          placeholder="用自然语言搜索邮件... 例如: DBS合同续签相关的邮件"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500"
        />
      </div>

      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-zinc-500">
          <Search className="w-16 h-16 mx-auto mb-4 opacity-30" />
          <p>输入搜索内容开始</p>
          <p className="text-xs mt-2 text-zinc-600">支持语义搜索和AI摘要</p>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
