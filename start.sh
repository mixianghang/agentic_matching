#!/bin/bash

echo "======================================"
echo "   智能体需求匹配系统 - 一键启动"
echo "======================================"
echo ""

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python3，请先安装 Python"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📚 检查并安装依赖..."
pip install -q -r requirements.txt

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚙️ 创建 .env 文件..."
    cp .env.example .env
    echo ""
    echo "⚠️ 请编辑 .env 文件并填入你的 OPENAI_API_KEY"
    echo ""
fi

echo ""
echo "🔍 检查端口 8000 是否被占用..."

# 查找并终止占用端口的进程
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️ 端口 8000 已被占用，尝试终止旧进程..."
    lsof -Pi :8000 -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
    sleep 1
    echo "✅ 已终止旧进程"
fi

echo ""
echo "🚀 启动服务器..."
echo "📱 访问地址：http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "======================================"
echo ""

# 打开浏览器
if command -v open &> /dev/null; then
    sleep 2
    open http://localhost:8000
elif command -v xdg-open &> /dev/null; then
    sleep 2
    xdg-open http://localhost:8000
fi

# 启动服务器
unset SSLKEYLOGFILE

# 设置日志级别 (DEBUG, INFO, WARNING, ERROR)
export LOG_LEVEL=${LOG_LEVEL:-INFO}
# Uvicorn 使用小写的日志级别
UVICORN_LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

echo "📝 Log Level: $LOG_LEVEL"
echo "   Set LOG_LEVEL=DEBUG for verbose output"
echo ""

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 --log-level $UVICORN_LOG_LEVEL
