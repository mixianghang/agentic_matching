#!/bin/bash

# Start script for in-memory storage mode (for browser testing)
# All data will be lost when server restarts

echo "🚀 Starting Agentic Matching System (In-Memory Mode)"
echo "=================================================="
echo ""

# Unset SSLKEYLOGFILE to avoid permission errors
unset SSLKEYLOGFILE

# Use in-memory configuration
cp .env.memory .env
echo "✅ Configuration: In-Memory Storage"
echo "   - Data will be lost on server restart"
echo "   - Perfect for browser testing"
echo ""

# Check if port 8000 is in use and kill it
echo "🔍 Checking port 8000..."
PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PID" ]; then
    echo "   Found process $PID using port 8000, terminating..."
    kill -9 $PID 2>/dev/null
    sleep 1
    echo "   ✅ Port 8000 is now free"
else
    echo "   ✅ Port 8000 is available"
fi
echo ""

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Start the server
echo ""
echo "🌐 Starting server..."
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:8000"
echo ""
echo "📖 API Documentation: http://localhost:8000/docs"
echo ""
echo "⚠️  Note: All data will be lost when you stop the server!"
echo "=================================================="
echo ""

# Run the server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
