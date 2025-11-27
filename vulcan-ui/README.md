# Vulcan Brain - Operations Center UI

**Status**: Phase 1, 2 & 3 Complete ✅

## 🏗️ Architecture

### Tech Stack
- **Framework**: Next.js 16 (App Router, Turbopack)
- **Styling**: Tailwind CSS (Dark Mode, Cyberpunk Professional)
- **UI Components**: Custom components + Lucide Icons
- **State Management**: Zustand (to be implemented)
- **Markdown**: react-markdown + syntax highlighting

### Design Philosophy
- **Theme**: "Cyberpunk Professional"
- **Colors**: 
  - Background: `slate-950`
  - Primary: Neon Cyan (`hsl(180 100% 50%)`)
  - Secondary: Amber (`hsl(45 100% 51%)`)
- **Fonts**: 
  - UI: Inter
  - Code: JetBrains Mono

## 📁 Project Structure

```
vulcan-ui/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout (dark mode)
│   │   ├── page.tsx            # Home page (Chat)
│   │   └── globals.css         # Global styles
│   ├── components/
│   │   ├── layout/
│   │   │   ├── DashboardLayout.tsx  # ⭐ 三栏式布局
│   │   │   ├── Sidebar.tsx          # 左侧导航栏
│   │   │   └── Inspector.tsx        # 右侧检查器
│   │   ├── chat/               # Chat 组件 (TBD)
│   │   ├── soul/               # Soul 配置 (TBD)
│   │   ├── knowledge/          # 知识库 (TBD)
│   │   ├── memory/             # 记忆可视化 (TBD)
│   │   └── ui/                 # 基础 UI 组件
│   ├── lib/
│   │   └── utils.ts            # cn() 工具函数
│   ├── store/                  # Zustand stores (TBD)
│   └── types/                  # TypeScript 类型定义
├── public/                     # 静态资源
├── tailwind.config.ts          # Tailwind 配置（暗色主题）
├── tsconfig.json               # TypeScript 配置
└── next.config.ts              # Next.js 配置
```

## ✅ Completed Features (Phase 1, 2 & 3)

### Phase 1: Project Initialization
- ✅ Next.js 15.5.6 + TypeScript setup
- ✅ Tailwind CSS v3.4.0 with dark mode
- ✅ Custom color scheme (Cyberpunk Professional)
- ✅ Fonts configured (Inter + JetBrains Mono)
- ✅ All dependencies installed

### Phase 2: Layout Architecture
- ✅ **DashboardLayout**: Three-column layout
- ✅ **Sidebar**: Left navigation (Chat, Soul, Knowledge, Memory, Settings)
- ✅ **Inspector**: Right panel (collapsible) with:
  - System State (GPU status, 36GB/72GB VRAM, token rate)
  - Thinking Process (CoT logs)
  - Performance Metrics (TTFT, latency)
  - Context Window info

### Phase 3: Feature Pages & State Management
- ✅ **Chat Interface**:
  - ChatWindow with streaming simulation
  - MessageBubble component (user/assistant/system roles)
  - CodeBlock component with syntax highlighting
  - Feedback buttons (thumbs up/down)
  - Zustand state management (useChatStore)
- ✅ **Soul Configuration**:
  - System Prompt editor (constitution)
  - Behavior sliders (Creativity, Reasoning Depth, Tool Use, Memory Retention)
  - Save/Reset functionality
- ✅ **Knowledge Base**:
  - File upload interface (PDF, TXT, MD, DOC, DOCX)
  - Document list with status (processing/ready)
  - Search and filtering
  - Delete functionality
- ✅ **Memory Visualization**:
  - User Profile tab (expertise, preferences, interaction count)
  - Timeline tab (conversation history with tags)
  - Auto-generated insights

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Open http://localhost:3000
```

## 🎯 Next Steps (Phase 4+)

- [ ] Backend API Integration
  - Connect to FastAPI streaming endpoint `/api/chat/stream`
  - Implement actual SSE connection for Chat
  - Hook up Soul/Knowledge/Memory API endpoints
- [ ] Real-time System Metrics
  - Connect Inspector to live GPU/VRAM data
  - Display actual thinking process from backend
  - Show real performance metrics
- [ ] Settings Page
  - User preferences
  - Theme customization
  - System configuration

## 🔗 Backend Integration

Backend: `vulcan_brain_v2` (Python + LlamaIndex)
- **API Specification**: See `API_SPEC.md` for complete endpoint documentation
- **Streaming Chat**: POST `/api/chat/stream` (SSE protocol)
- **Event Types**: token, code, tool_output, final_answer, error
- **System Status**: GET `/api/system/status` (GPU, VRAM, tokens/s)
- **Soul Config**: GET/POST `/api/soul/config` and `/api/soul/update`
- **Knowledge**: POST `/api/knowledge/upload`, GET `/api/knowledge/list`
- **Memory**: GET `/api/memory/profile`, GET `/api/memory/timeline`

### Priority Implementation Order:
1. **P0**: `/api/chat/stream` - Core chat functionality
2. **P1**: `/api/system/status` - Inspector metrics
3. **P2**: `/api/memory/*` - User profile & timeline
4. **P3**: `/api/knowledge/*` - Document management
5. **P4**: `/api/soul/*` - Configuration

---

## 📸 Current Features (with Mock Data)

All four main modules are fully functional with mock data:

1. **Chat**: Stream-style conversation with code blocks and feedback
2. **Soul**: System prompt editor with behavior parameter sliders
3. **Knowledge**: Document upload/management with processing status
4. **Memory**: User profile extraction and conversation timeline

The UI is **production-ready** and awaiting backend API implementation.

---

**Agent B** - Frontend Construction
**Date**: 2025-11-20
**Sprint**: Phase 1-3 Complete
