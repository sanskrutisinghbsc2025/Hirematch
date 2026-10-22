#!/usr/bin/env bash

echo "==================================================="
echo "            HireMatch Platform Launcher"
echo "==================================================="
echo ""

# Activate virtual environment if present
if [ -f ".venv/Scripts/activate" ]; then
    echo "[1/3] Activating virtual environment (.venv)..."
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "[1/3] Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "[1/3] Using system Python..."
fi

echo "[2/3] Starting FastAPI Backend on http://127.0.0.1:8000..."
python -m uvicorn backend.app.main:app --port 8000 --reload &
BACKEND_PID=$!

echo "[3/3] Starting Next.js Frontend on http://localhost:3000..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================================="
echo "  HireMatch is running!"
echo "  - Frontend Web UI:  http://localhost:3000"
echo "  - Backend API Docs: http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to terminate both servers."
echo "==================================================="

trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM
wait
