# Agentic Matching System

智能体需求匹配系统 — 基于智能体对话的需求匹配系统

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Vant 4 + Pinia |
| 后端 | Python + FastAPI + SQLite |
| 通信 | REST API（Vite dev proxy / dist 静态服务） |

---

## 设计文档

系统愿景、架构设计、开发路线图详见 [`design/`](design/) 目录。快速入口：
- [DESIGN.md](design/DESIGN.md) — 系统愿景、核心设计意图、架构
- [ROADMAP.md](design/ROADMAP.md) — 当前状态与开发计划

## 前置条件

- Python 3.10+
- Node.js 18+（推荐通过 [nvm](https://github.com/nvm-sh/nvm) 管理）
- 有效的 OpenAI API Key（或兼容的 LLM 服务）

---

## 开发模式

同时启动 Vite 前端开发服务器（端口 5173，支持热更新）和 FastAPI 后端（端口 8000，支持热重载）：

```bash
./start.sh
```

- 浏览器访问：**http://localhost:5173**
- Vite 自动将 `/api/*` 请求代理到后端 `localhost:8000`
- 前端代码改动即时生效，无需刷新页面

首次运行会自动创建 Python 虚拟环境并安装前后端依赖。若缺少 `.env` 文件，脚本会提示创建并退出。

### 手动启动（分步）

```bash
# 后端
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 填入 OPENAI_API_KEY
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

---

## 生产部署

构建前端静态资源，由 FastAPI 同一进程提供服务（仅需端口 8000）：

```bash
./deploy.sh
```

- 脚本会自动执行 `npm run build`，输出到 `frontend/dist/`
- FastAPI 启动后在 `/` 提供 `frontend/dist/index.html`，`/assets/` 提供 JS/CSS 包
- 可通过环境变量调整：

```bash
HOST=0.0.0.0 PORT=8000 WORKERS=2 ./deploy.sh
```

---

## 项目结构

```
agentic_matching/
├── backend/
│   ├── main.py          # FastAPI 入口（含静态文件服务）
│   ├── models.py        # 数据模型
│   ├── storage.py       # 存储层接口
│   ├── storage_sqlite.py
│   ├── agent_system.py  # 智能体系统
│   └── matching/        # 匹配算法
├── frontend/            # Vue 3 前端（开发源码）
│   ├── src/
│   │   ├── views/       # 页面：LoginView, HomeView
│   │   ├── components/  # TaskList, ChatArea, InfoPanel, MessageBubble
│   │   ├── stores/      # Pinia: auth, app
│   │   ├── api/         # Axios API 层：auth, tasks
│   │   └── router/
│   ├── dist/            # 构建输出（由 deploy.sh 生成）
│   └── vite.config.ts
├── static/
│   └── index.html       # 备用旧版前端
├── start.sh             # 开发模式启动
├── deploy.sh            # 生产部署脚本
├── start.py             # Python 跨平台启动（仅后端）
├── requirements.txt
└── .env
```

