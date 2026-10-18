#!/usr/bin/env bash
# ==============================================================================
# GraphOS All-In-One Unified Runner
# Starts both Backend (port 8000) and Frontend (port 3000) with a single command.
# Pressing Ctrl+C terminates both cleanly.
# ==============================================================================
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

# 1. Clean any orphaned processes on port 8000 or 3000
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :3000 | xargs kill -9 2>/dev/null || true

# 2. Trap SIGINT (Ctrl+C) and SIGTERM to kill background children cleanly
cleanup() {
    echo ""
    echo "🛑 Shutting down GraphOS services..."
    kill $(jobs -p) 2>/dev/null || true
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    lsof -ti :3000 | xargs kill -9 2>/dev/null || true
    echo "✅ All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "🚀 Starting GraphOS Backend (FastAPI on port 8000)..."
source .venv/bin/activate
uvicorn agent.api:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to initialize..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:8000/api/health > /dev/null; then
        echo "✅ Backend is healthy on http://localhost:8000"
        break
    fi
    sleep 1
done

echo "✨ Starting GraphOS Frontend (Next.js on port 3000)..."
cd "${ROOT_DIR}/frontend"
npm run dev
