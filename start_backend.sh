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

# Start the FastAPI backend
cd backend
export MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
export DB_NAME="${DB_NAME:-kbs_bridge_system}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-kbs_bridge_secret_key_2024}"
uvicorn server:app --host localhost --port 8000 --reload
