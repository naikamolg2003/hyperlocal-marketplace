#!/usr/bin/env bash
# =============================================================================
# Hyperlocal Marketplace - Single-Command Developer Orchestration Script
# Spins up Docker PostgreSQL with PostGIS, runs DB initialization, launches
# FastAPI backend (port 8000), and starts Vite web frontend (port 3000) concurrently.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\033[1;36m=================================================================\033[0m"
echo -e "\033[1;36m  Hyperlocal Marketplace - Developer Stack Orchestrator          \033[0m"
echo -e "\033[1;36m=================================================================\033[0m"

# 1. Verify Docker Daemon and Container
echo -e "\n\033[1;33m[1/4] Verifying PostgreSQL PostGIS container...\033[0m"
if ! docker info > /dev/null 2>&1; then
    echo -e "\033[1;31m[ERROR] Docker daemon is not running. Please start Docker.\033[0m"
    exit 1
fi

if [ "$(docker inspect --format '{{.State.Status}}' hyperlocal-postgres 2>/dev/null)" != "running" ]; then
    echo "Starting PostgreSQL container (hyperlocal-postgres)..."
    docker compose up -d
else
    echo -e "\033[0;32mPostgreSQL container is already running.\033[0m"
fi

# Wait for DB readiness
echo "Waiting for PostgreSQL engine to accept connections..."
for i in {1..15}; do
    if docker exec hyperlocal-postgres pg_isready -U postgres -d hyperlocal_marketplace > /dev/null 2>&1; then
        echo -e "\033[0;32mPostgreSQL + PostGIS engine is ready.\033[0m"
        break
    fi
    sleep 1
done

# 2. Database Schema Initialization & Migrations
echo -e "\n\033[1;33m[2/4] Initializing database schema & extensions...\033[0m"
PYTHON_BIN="python3"
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/Scripts/python.exe"
fi

export PYTHONPATH="$SCRIPT_DIR"
$PYTHON_BIN -m backend.init_db
echo -e "\033[0;32mDatabase schema and PostGIS extensions initialized.\033[0m"

# 3. Launching Services Concurrently
echo -e "\n\033[1;33m[3/4] Launching Services Concurrently...\033[0m"
echo " - FastAPI Backend: http://localhost:8000 (Swagger: http://localhost:8000/docs)"
echo " - React Web Portal: http://localhost:3000"
echo " - Press Ctrl+C to terminate all services."

# Background PID tracking
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo -e "\n\033[1;33mShutting down background services...\033[0m"
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo -e "\033[0;32mDeveloper services stopped cleanly.\033[0m"
    exit 0
}

trap cleanup INT TERM EXIT

# Start FastAPI
$PYTHON_BIN -m uvicorn backend.main:app --port 8000 --reload &
BACKEND_PID=$!

# Start Vite Web Frontend
cd "$SCRIPT_DIR/frontend-web"
npm run dev -- --host --port 3000 &
FRONTEND_PID=$!

echo -e "\n\033[1;32m[4/4] All developer servers running! Monitor logs below:\033[0m"
echo -e "\033[1;36m-----------------------------------------------------------------\033[0m"

wait
