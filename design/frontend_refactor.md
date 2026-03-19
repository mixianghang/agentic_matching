# Frontend Refactor: Vue 3 + Vite Architecture

## Overview

Replace the monolithic `static/index.html` (2000+ lines of mixed HTML/CSS/JS) with a proper
Vue 3 + Vite single-page application. The Python FastAPI backend remains unchanged.

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  frontend/  (Vue 3 + Vite + TypeScript + Vant)  │   │
│  │  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │   │
│  │  │ Stores  │  │  Views   │  │   Components   │  │   │
│  │  │ (Pinia) │  │(LoginView│  │ TaskList       │  │   │
│  │  │ auth.ts │  │ HomeView)│  │ ChatArea       │  │   │
│  │  │ app.ts  │  └──────────┘  │ InfoPanel      │  │   │
│  │  └────┬────┘                │ MessageBubble  │  │   │
│  │       │ api/ layer          └────────────────┘  │   │
│  │       │ (axios + interceptors)                   │   │
│  └───────┼──────────────────────────────────────────┘   │
└──────────┼──────────────────────────────────────────────┘
           │ /api/*  (proxy in dev, direct in prod)
┌──────────┼──────────────────────────────────────────────┐
│  backend/│ (Python FastAPI — unchanged)                  │
│  ┌───────▼────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │   main.py      │  │ agent_system │  │  storage    │  │
│  │  (REST routes) │  │  + demand    │  │  (SQLite)   │  │
│  └────────────────┘  └──────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
frontend/
├── index.html              # HTML entry point (minimal, just mounts #app)
├── package.json            # Vue 3, Vite, Vant, Pinia, Vue Router, Axios
├── vite.config.ts          # Build config + dev proxy → :8000
├── tsconfig.json
├── .env.example
└── src/
    ├── main.ts             # App bootstrap
    ├── App.vue             # Root component (just <router-view>)
    ├── router/
    │   └── index.ts        # Routes: /login, /home (auth guard)
    ├── api/
    │   ├── index.ts        # Axios instance + auth/error interceptors
    │   ├── auth.ts         # login(), register()
    │   └── tasks.ts        # tasks CRUD, sendMessage(), getMatches(), getDemandProgress()
    ├── stores/
    │   ├── auth.ts         # Pinia: token, user, login(), logout()
    │   └── app.ts          # Pinia: tasks[], currentTask, sendMessage(), etc.
    ├── views/
    │   ├── LoginView.vue   # Login / register tabs
    │   └── HomeView.vue    # 3-column shell (responsive: 1-column on mobile)
    └── components/
        ├── TaskList.vue        # Left sidebar — task cards + new-task button
        ├── ChatArea.vue        # Center — messages + text input
        ├── InfoPanel.vue       # Right — demand values, progress, match results
        └── MessageBubble.vue   # Single chat message (user or agent)
```

## Key Design Decisions

### 1. No Node.js BFF Layer
MyVillage has a NestJS middleware, but our FastAPI already provides all the API routes.
A BFF layer would add complexity without value here. The Vite dev server proxies
`/api/*` directly to FastAPI on port 8000.

### 2. Pinia for State
- `auth` store: user identity + JWT token (persisted to localStorage)
- `app` store: tasks list, currently-selected task, messages, demand progress, matches

All API calls live in store actions — components never call `api/` directly.
This keeps components declarative and testable.

### 3. Vant 4 UI Library
Follows MyVillage. Vant is designed for mobile-first / WeChat miniapp patterns:
- `van-form`, `van-field` for inputs
- `van-nav-bar` for mobile page headers
- `van-cell-group`, `van-cell` for info lists
- `van-tabbar` for bottom navigation on mobile
- `van-tag` for status badges

### 4. Responsive Layout Strategy
- **Desktop (≥768px)**: 3-column flexbox layout (320px sidebar | flex-1 chat | 320px info)
- **Mobile (<768px)**: Single active panel at a time. `mobilePanel` state in HomeView
  controls which CSS class is applied, showing/hiding panels. Bottom tabs allow switching.
  Back arrow in ChatArea → returns to task list.

### 5. Mobile / WeChat Miniapp Friendly Patterns
- No `window.alert()` / `window.prompt()` — use `van-toast` / `van-dialog`
- `max-width: 480px` on `#app` for mobile-width feel
- `viewport` meta with `maximum-scale=1.0` prevents zoom on input focus
- Touch-friendly button sizes (≥44px tap targets)

## Data Flow

```
User types message
  → ChatArea emits input
    → app.sendMessage(content) [store action]
      → tasksApi.sendMessage(taskId, content)  [API call]
        → POST /api/messages/
          → FastAPI DemandDefinitionEngineV2
        ← { message: AgentMessage }
      → push agent message to currentTask.messages
      → tasksApi.get(taskId)  [refresh task metadata]
      → tasksApi.getDemandProgress(taskId)  [refresh side panel]
        → renderInfoPanel updates automatically via reactive state
```

## Dev Setup

```bash
# Terminal 1: Python backend
cd /path/to/agentic_matching
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Vue frontend
cd frontend
npm install
npm run dev   # starts on :5173, proxies /api → :8000
```

## Production Build

```bash
cd frontend && npm run build   # outputs to frontend/dist/
```

`backend/main.py` is updated to serve `frontend/dist` if it exists (falls back to
`static/` for backward compatibility).

## File Count vs. Old Architecture

| Old | New |
|-----|-----|
| 1 file (index.html, 1500 LOC) | 16 focused files (avg ~80 LOC each) |
| No type safety | TypeScript throughout |
| Vanilla DOM manipulation | Vue 3 reactivity |
| Global variables | Pinia stores (typed, devtools-friendly) |
| No separation of concerns | API / Store / View / Component layers |
