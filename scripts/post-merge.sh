#!/bin/bash
# Post-merge setup for KBS Bridge.
# Idempotent. Safe to run multiple times.
set -e

echo "[post-merge] backend Python deps via uv pip install -r backend/requirements.txt"
uv pip install -r backend/requirements.txt

echo "[post-merge] frontend npm deps (if package.json exists)"
if [ -f frontend/package.json ]; then
  cd frontend && npm install --no-audit --no-fund --prefer-offline && cd -
fi

echo "[post-merge] OK"
