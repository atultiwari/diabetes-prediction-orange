#!/usr/bin/env bash
# Container entrypoint: launch FastAPI on 127.0.0.1:8000, wait for it to be
# healthy, then launch the Next.js standalone server on 0.0.0.0:3000.
# If either process dies, take the whole container down so Coolify restarts it.
set -euo pipefail

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${HOSTNAME:-0.0.0.0}"
FRONTEND_PORT="${PORT:-3000}"

log() { printf "[start.sh] %s\n" "$*"; }

cleanup() {
  log "Shutting down (signal)…"
  kill -TERM 0 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM

log "Launching uvicorn on ${BACKEND_HOST}:${BACKEND_PORT}"
(
  cd /app/backend
  exec python -m uvicorn app.main:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --proxy-headers
) &
BACKEND_PID=$!

# Wait for the backend to answer /api/health. Models take a few seconds to
# unpickle, so don't be impatient — bail out after 90s.
log "Waiting for backend health…"
for i in $(seq 1 90); do
  if curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    log "Backend is up"
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Backend died before becoming healthy"
    exit 1
  fi
  sleep 1
done

if ! curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
  log "Backend never reached health endpoint, giving up"
  kill -TERM "$BACKEND_PID" 2>/dev/null || true
  exit 1
fi

log "Launching Next.js on ${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd /app/frontend
  exec node server.js
) &
FRONTEND_PID=$!

# Wait for either to exit; first one out wins.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
EXIT_CODE=$?
log "Child process exited (code=$EXIT_CODE); shutting down siblings"
kill -TERM "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
wait 2>/dev/null || true
exit "$EXIT_CODE"
