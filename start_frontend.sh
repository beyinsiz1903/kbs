#!/bin/bash
# Start MongoDB if not running
mkdir -p /tmp/mongodb_data
if ! pgrep -x "mongod" > /dev/null; then
    mongod --dbpath /tmp/mongodb_data --fork --logpath /tmp/mongod.log --port 27017
    echo "MongoDB started"
    sleep 2
else
    echo "MongoDB already running"
fi

# Start backend in background
cd backend
export MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
export DB_NAME="${DB_NAME:-kbs_bridge_system}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-kbs_bridge_secret_key_2024}"

# Clean up any stale uvicorn processes on port 8000
pkill -f "uvicorn server:app" 2>/dev/null || true
sleep 1

uvicorn server:app --host localhost --port 8000 &
BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID"
sleep 3

# Start frontend
cd ../frontend
PORT=5000 HOST=0.0.0.0 npm start
