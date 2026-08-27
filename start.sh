#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

# Check that the virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Python virtual environment not found."
    echo "Create it first with:"
    echo ""
    echo "  cd backend"
    echo "  python -m venv .venv"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Detect the virtual environment executable location
if [ -f "$VENV_DIR/bin/uvicorn" ]; then
    UVICORN="$VENV_DIR/bin/uvicorn"
elif [ -f "$VENV_DIR/Scripts/uvicorn.exe" ]; then
    UVICORN="$VENV_DIR/Scripts/uvicorn.exe"
else
    echo "uvicorn was not found in the virtual environment."
    echo "Install the backend dependencies with:"
    echo ""
    echo "  cd backend"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Start backend
cd "$BACKEND_DIR"
"$UVICORN" app.main:app --reload &
BACKEND_PID=$!

# Start frontend
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers."

cleanup() {
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

wait