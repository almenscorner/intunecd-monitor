#!/bin/bash
set -o errexit

echo "INFO  [DB UPGRADE] Running alembic upgrade head..."
alembic upgrade head

echo "INFO  [SERVER] Starting uvicorn..."
uvicorn app.main:socket_app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers "${UVICORN_WORKERS:-2}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-nginx}"
