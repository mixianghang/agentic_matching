#!/bin/bash
# start.sh — 开发模式启动 (FastAPI + Vite dev server)
# 生产部署请使用 ./deploy.sh

set -e

echo "======================================"
echo "   智能体需求匹配系统 - 开发模式"
echo "======================================"
echo ""

# ── Python 环境 ────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python3，请先安装 Python"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

echo "🔧 激活虚拟环境..."
source venv/bin/activate

echo "📚 检查并安装 Python 依赖..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo "⚙️  创建 .env 文件..."
    cp .env.example .env
    echo ""
    echo "⚠️  请编辑 .env 文件并填入你的 OPENAI_API_KEY，然后重新运行此脚本"
    exit 1
fi

# ── Node / npm 环境 ────────────────────────────────────────────
# 加载 nvm（如果系统 PATH 里没有 node）
if ! command -v node &> /dev/null; then
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        source "$HOME/.nvm/nvm.sh"
    else
        echo "❌ 错误：未找到 node，请安装 Node.js 或 nvm"
        exit 1
    fi
fi

echo "🔧 Node $(node --version) / npm $(npm --version)"

if [ ! -d "frontend/node_modules" ]; then
    echo "📦 安装前端依赖..."
    (cd frontend && npm install --silent)
fi

# ── 清理旧进程 ─────────────────────────────────────────────────
for PORT in 8000 5173; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  端口 $PORT 已被占用，正在终止旧进程..."
        lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
        sleep 0.5
    fi
done

# ── 启动 Vite dev server (后台) ────────────────────────────────
echo ""
echo "🎨 启动 Vite 前端开发服务器 (端口 5173)..."
(cd frontend && npm run dev) &
VITE_PID=$!

# ── 启动 FastAPI ───────────────────────────────────────────────
unset SSLKEYLOGFILE
export LOG_LEVEL=${LOG_LEVEL:-INFO}
UVICORN_LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

echo "🚀 启动 FastAPI 后端 (端口 8000)..."
echo ""
echo "  前端 (热更新)：http://localhost:5173"
echo "  后端 API：     http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "======================================"
echo ""

# 打开浏览器（指向 Vite dev server）
sleep 2
if command -v open &> /dev/null; then
    open http://localhost:5173
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173
fi

# 当脚本退出时，一并杀掉 Vite
trap "kill $VITE_PID 2>/dev/null; exit" INT TERM EXIT

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 --log-level $UVICORN_LOG_LEVEL
