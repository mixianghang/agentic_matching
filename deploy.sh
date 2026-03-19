#!/bin/bash
# deploy.sh — 生产部署脚本
# 构建前端静态资源，由 FastAPI 直接提供服务（端口 8000）

set -e

echo "======================================"
echo "   智能体需求匹配系统 - 生产部署"
echo "======================================"
echo ""

# ── 参数 ───────────────────────────────────────────────────────
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}
WORKERS=${WORKERS:-1}

# ── Python 环境 ────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python3"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

echo "🔧 激活虚拟环境..."
source venv/bin/activate

echo "📚 安装 Python 依赖..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo "❌ 错误：缺少 .env 文件，请先复制 .env.example 并填入配置"
    exit 1
fi

# ── Node / npm 环境 ────────────────────────────────────────────
if ! command -v node &> /dev/null; then
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        source "$HOME/.nvm/nvm.sh"
    else
        echo "❌ 错误：未找到 node，请安装 Node.js"
        exit 1
    fi
fi

echo "🔧 Node $(node --version) / npm $(npm --version)"

# ── 构建前端 ───────────────────────────────────────────────────
echo ""
echo "🏗️  构建前端资源..."

(cd frontend && npm install --silent && npm run build)

echo "✅ 前端构建完成 → frontend/dist/"

# ── 清理旧进程 ─────────────────────────────────────────────────
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 $PORT 已被占用，正在终止旧进程..."
    lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
    sleep 0.5
fi

# ── 启动生产服务器 ─────────────────────────────────────────────
unset SSLKEYLOGFILE
export LOG_LEVEL=${LOG_LEVEL:-INFO}
UVICORN_LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

echo ""
echo "🚀 启动生产服务器..."
echo "   地址：http://$HOST:$PORT"
echo "   Workers：$WORKERS"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "======================================"
echo ""

uvicorn backend.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$UVICORN_LOG_LEVEL"
