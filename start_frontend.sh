#!/bin/bash
# Dev runner: backend (FastAPI) + frontend (CRA) — NO MongoDB.
# Production icin docker-compose.yml kullanin.

set -e

# Local dev data directory (Fernet-encrypted session storage)
export DATA_DIR="${DATA_DIR:-$PWD/.devdata}"
mkdir -p "$DATA_DIR"

# Generate a per-dev Fernet key once and persist it
KEY_FILE="$DATA_DIR/.devkey"
if [ -z "${SESSION_ENCRYPTION_KEY:-}" ]; then
  if [ ! -f "$KEY_FILE" ]; then
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
  fi
  export SESSION_ENCRYPTION_KEY="$(cat "$KEY_FILE")"
fi

export KBS_MODE="${KBS_MODE:-simulation}"

# Clean stale uvicorn
pkill -f "uvicorn server:app" 2>/dev/null || true
sleep 1

# Start backend
(cd backend && uvicorn server:app --host localhost --port 8000) &
BACKEND_PID=$!
echo "Backend PID=$BACKEND_PID  DATA_DIR=$DATA_DIR  KBS_MODE=$KBS_MODE"
sleep 3

# Start frontend (CRA dev server) on 5000
cd frontend
PORT=5000 HOST=0.0.0.0 npm start
