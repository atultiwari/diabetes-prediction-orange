#!/usr/bin/env bash
# Single entrypoint for local dev. Run `./dev.sh help` for the full list.
#
# Common flows:
#   ./dev.sh setup            # one-time: backend venv + frontend node_modules
#   ./dev.sh start            # run backend + frontend together (foreground)
#   ./dev.sh backend          # backend only
#   ./dev.sh frontend         # frontend only
#   ./dev.sh test             # backend pytest
#   ./dev.sh docker:up        # docker compose up --build
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
PY_BIN="$VENV_DIR/bin/python"
UV_BIN="${UV_BIN:-uv}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
PKG_MGR="${PKG_MGR:-pnpm}"

# ---- pretty logging -------------------------------------------------------

if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
  C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'
else
  C_RESET=""; C_BOLD=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""
fi

log()  { printf "%s[dev]%s %s\n" "$C_BLUE$C_BOLD" "$C_RESET" "$*"; }
ok()   { printf "%s[ok]%s  %s\n" "$C_GREEN$C_BOLD" "$C_RESET" "$*"; }
warn() { printf "%s[warn]%s %s\n" "$C_YELLOW$C_BOLD" "$C_RESET" "$*"; }
fail() { printf "%s[fail]%s %s\n" "$C_RED$C_BOLD" "$C_RESET" "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fail "Missing required tool: $1"; }

# ---- backend --------------------------------------------------------------

setup_backend() {
  need "$UV_BIN"
  log "Backend setup (Python $PYTHON_VERSION via uv)"
  cd "$BACKEND_DIR"

  "$UV_BIN" python install "$PYTHON_VERSION" >/dev/null 2>&1 || true

  if [[ ! -x "$PY_BIN" ]]; then
    log "Creating venv at $VENV_DIR"
    "$UV_BIN" venv --python "$PYTHON_VERSION" .venv
  else
    log "Reusing existing venv"
  fi

  log "Installing backend dependencies"
  "$UV_BIN" pip install --python "$PY_BIN" -e ".[dev]"
  ok "Backend ready"
}

run_backend() {
  [[ -x "$PY_BIN" ]] || fail "Backend not set up. Run: ./dev.sh setup"
  log "Starting backend on http://localhost:$BACKEND_PORT"
  cd "$BACKEND_DIR"
  QT_QPA_PLATFORM=offscreen \
    "$PY_BIN" -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT"
}

test_backend() {
  [[ -x "$PY_BIN" ]] || fail "Backend not set up. Run: ./dev.sh setup"
  log "Running backend tests"
  cd "$BACKEND_DIR"
  QT_QPA_PLATFORM=offscreen "$PY_BIN" -m pytest "$@"
}

shell_backend() {
  [[ -x "$PY_BIN" ]] || fail "Backend not set up. Run: ./dev.sh setup"
  cd "$BACKEND_DIR"
  QT_QPA_PLATFORM=offscreen "$PY_BIN"
}

# ---- frontend -------------------------------------------------------------

setup_frontend() {
  need "$PKG_MGR"
  log "Frontend setup ($PKG_MGR install)"
  cd "$FRONTEND_DIR"
  if [[ ! -f .env.local ]]; then
    cp .env.example .env.local
    ok "Wrote .env.local from .env.example"
  fi
  "$PKG_MGR" install
  ok "Frontend ready"
}

run_frontend() {
  need "$PKG_MGR"
  [[ -d "$FRONTEND_DIR/node_modules" ]] || fail "Frontend not set up. Run: ./dev.sh setup"
  log "Starting frontend on http://localhost:$FRONTEND_PORT"
  cd "$FRONTEND_DIR"
  NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:$BACKEND_PORT}" \
    "$PKG_MGR" dev --port "$FRONTEND_PORT"
}

build_frontend() {
  need "$PKG_MGR"
  cd "$FRONTEND_DIR"
  "$PKG_MGR" build
}

# ---- combined -------------------------------------------------------------

run_both() {
  [[ -x "$PY_BIN" ]] || fail "Backend not set up. Run: ./dev.sh setup"
  [[ -d "$FRONTEND_DIR/node_modules" ]] || fail "Frontend not set up. Run: ./dev.sh setup"

  local pids=()
  cleanup() {
    log "Shutting down..."
    for pid in "${pids[@]:-}"; do
      [[ -n "${pid:-}" ]] && kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
  }
  trap cleanup INT TERM EXIT

  log "Starting backend (port $BACKEND_PORT) and frontend (port $FRONTEND_PORT)"
  log "Press Ctrl-C to stop both"

  (
    cd "$BACKEND_DIR"
    QT_QPA_PLATFORM=offscreen \
      "$PY_BIN" -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" \
      2>&1 | sed -e "s/^/${C_BLUE}[backend]${C_RESET} /"
  ) &
  pids+=($!)

  (
    cd "$FRONTEND_DIR"
    NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:$BACKEND_PORT}" \
      "$PKG_MGR" dev --port "$FRONTEND_PORT" \
      2>&1 | sed -e "s/^/${C_GREEN}[frontend]${C_RESET} /"
  ) &
  pids+=($!)

  wait "${pids[@]}"
}

# ---- docker ---------------------------------------------------------------

docker_up()    { need docker; cd "$ROOT_DIR"; docker compose up --build; }
docker_down()  { need docker; cd "$ROOT_DIR"; docker compose down; }
docker_logs()  { need docker; cd "$ROOT_DIR"; docker compose logs -f "${@:-}"; }
docker_ps()    { need docker; cd "$ROOT_DIR"; docker compose ps; }

# ---- utilities ------------------------------------------------------------

clean_backend() {
  log "Removing backend venv and caches"
  rm -rf "$VENV_DIR" "$BACKEND_DIR/.pytest_cache" "$BACKEND_DIR/orange_model_demo_backend.egg-info"
  find "$BACKEND_DIR" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  ok "Backend cleaned"
}

clean_frontend() {
  log "Removing frontend node_modules and build output"
  rm -rf "$FRONTEND_DIR/node_modules" "$FRONTEND_DIR/.next" "$FRONTEND_DIR/.env.local"
  ok "Frontend cleaned"
}

clean_all() { clean_backend; clean_frontend; }

status() {
  printf "%sRepo:%s     %s\n" "$C_BOLD" "$C_RESET" "$ROOT_DIR"
  printf "%sBackend:%s  " "$C_BOLD" "$C_RESET"
  if [[ -x "$PY_BIN" ]]; then printf "%sready%s (%s)\n" "$C_GREEN" "$C_RESET" "$("$PY_BIN" --version)"
  else printf "%snot set up%s\n" "$C_YELLOW" "$C_RESET"; fi
  printf "%sFrontend:%s " "$C_BOLD" "$C_RESET"
  if [[ -d "$FRONTEND_DIR/node_modules" ]]; then printf "%sready%s\n" "$C_GREEN" "$C_RESET"
  else printf "%snot set up%s\n" "$C_YELLOW" "$C_RESET"; fi
  printf "%sModels:%s   " "$C_BOLD" "$C_RESET"
  local count
  count=$(find "$BACKEND_DIR/models" -maxdepth 1 -name '*.pkcls' 2>/dev/null | wc -l | tr -d ' ')
  printf "%s bundled .pkcls\n" "$count"
}

usage() {
  cat <<EOF
${C_BOLD}Orange Model Demo — dev helper${C_RESET}

${C_BOLD}Usage:${C_RESET} ./dev.sh <command> [args]

${C_BOLD}Setup${C_RESET}
  setup                 Install backend deps (uv) and frontend deps ($PKG_MGR)
  setup:backend         Backend deps only
  setup:frontend        Frontend deps only

${C_BOLD}Run${C_RESET}
  start                 Run backend + frontend together (Ctrl-C stops both)
  backend               Run backend only (port $BACKEND_PORT)
  frontend              Run frontend only (port $FRONTEND_PORT)

${C_BOLD}Test / build${C_RESET}
  test [pytest args]    Run backend pytest (passes args through)
  build                 Production frontend build (next build)
  shell                 Drop into a Python REPL with backend deps loaded

${C_BOLD}Docker${C_RESET}
  docker:up             docker compose up --build
  docker:down           docker compose down
  docker:logs [svc]     Tail docker compose logs
  docker:ps             docker compose ps

${C_BOLD}Maintenance${C_RESET}
  status                Show setup status
  clean                 Remove backend venv + frontend node_modules
  clean:backend         Backend venv + caches
  clean:frontend        Frontend node_modules + .next

${C_BOLD}Env overrides${C_RESET}
  BACKEND_PORT=$BACKEND_PORT  FRONTEND_PORT=$FRONTEND_PORT
  PYTHON_VERSION=$PYTHON_VERSION  PKG_MGR=$PKG_MGR  UV_BIN=$UV_BIN
EOF
}

# ---- dispatch -------------------------------------------------------------

cmd="${1:-help}"
shift || true

case "$cmd" in
  setup)             setup_backend; setup_frontend ;;
  setup:backend)     setup_backend ;;
  setup:frontend)    setup_frontend ;;
  start|run|dev)     run_both ;;
  backend)           run_backend ;;
  frontend)          run_frontend ;;
  test)              test_backend "$@" ;;
  build)             build_frontend ;;
  shell)             shell_backend ;;
  docker:up|up)      docker_up ;;
  docker:down|down)  docker_down ;;
  docker:logs|logs)  docker_logs "$@" ;;
  docker:ps|ps)      docker_ps ;;
  status)            status ;;
  clean)             clean_all ;;
  clean:backend)     clean_backend ;;
  clean:frontend)    clean_frontend ;;
  help|-h|--help)    usage ;;
  *)                 warn "Unknown command: $cmd"; usage; exit 1 ;;
esac
