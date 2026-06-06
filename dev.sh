#!/usr/bin/env bash
# Loudrr-FastAPI Local Dev (bash/macOS/Linux variant)
# Run:  ./dev.sh
#
# Mirrors dev.ps1 but for bash environments. Uses `tmux` if available for one
# multiplexed window, else falls back to backgrounding each service and
# capturing logs to /tmp/loudrr-fastapi/*.log.
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$PROJECT_ROOT/backend"
FRONTEND="$PROJECT_ROOT/frontend"
VENV_PY="$PROJECT_ROOT/.venv/bin/python"   # adjust if venv lives at backend/.venv

# --- 0. Check Docker ---
if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon not running. Start Docker Desktop and re-run." >&2
    exit 1
fi

# --- 1. Bring up postgres + redis ---
echo "[1/5] Bringing up Postgres + Redis..."
(cd "$BACKEND" && docker compose up -d db redis >/dev/null)

# --- 2. Wait for postgres ---
echo "[2/5] Waiting for Postgres :5432..."
until nc -z localhost 5432 2>/dev/null || (echo > /dev/tcp/127.0.0.1/5432) 2>/dev/null; do
    sleep 1
done
echo "  Postgres up."

# --- 3. Launch services ---
if command -v tmux >/dev/null 2>&1; then
    echo "[3/5] Launching services in tmux session 'loudrr'..."
    tmux kill-session -t loudrr 2>/dev/null || true
    tmux new-session -d -s loudrr -n backend "cd '$BACKEND' && '$VENV_PY' -m uvicorn app.main:app --port 8000 --reload"
    tmux new-window  -t loudrr   -n worker  "cd '$BACKEND' && '$VENV_PY' -m arq app.tasks.worker.WorkerSettings"
    tmux new-window  -t loudrr   -n next    "cd '$FRONTEND' && npm run dev"
    tmux new-window  -t loudrr   -n shell   "cd '$PROJECT_ROOT' && exec bash"
    echo "  Attach with:  tmux attach -t loudrr"
else
    echo "[3/5] tmux not found — launching in background, logging to /tmp/loudrr-fastapi/"
    mkdir -p /tmp/loudrr-fastapi
    (cd "$BACKEND"  && "$VENV_PY" -m uvicorn app.main:app --port 8000 --reload          >/tmp/loudrr-fastapi/backend.log 2>&1) &
    (cd "$BACKEND"  && "$VENV_PY" -m arq app.tasks.worker.WorkerSettings                >/tmp/loudrr-fastapi/worker.log  2>&1) &
    (cd "$FRONTEND" && npm run dev                                                       >/tmp/loudrr-fastapi/next.log    2>&1) &
    echo "  Tail backend: tail -f /tmp/loudrr-fastapi/backend.log"
fi

echo ""
echo "URLs:"
echo "  Backend:         http://localhost:8000"
echo "  API docs:        http://localhost:8000/docs"
echo "  Admin dashboard: http://localhost:3000/admin"
echo "  Mini-app:        http://localhost:3000/app"
echo ""
echo "Stop with: ./dev-stop.sh (or tmux kill-session -t loudrr)"
