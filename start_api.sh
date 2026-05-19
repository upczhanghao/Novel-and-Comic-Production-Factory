#!/usr/bin/env bash
# start_api.sh - 一键启动 NovelWriter FastAPI + Vue 前端
# 用法：
#   ./start_api.sh              # 生产模式：安装依赖、构建前端、启动 7860
#   ./start_api.sh --dev        # 开发模式：后端热重载 + Vite 前端
#   ./start_api.sh --skip-build # 生产模式但跳过前端构建

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MODE="prod"
SKIP_BUILD="${NOVELWRITER_SKIP_BUILD:-0}"
for arg in "$@"; do
  case "$arg" in
    --dev) MODE="dev" ;;
    --skip-build) SKIP_BUILD="1" ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg"
      exit 1
      ;;
  esac
done

HOST="${NOVELWRITER_HOST:-127.0.0.1}"
PORT="${NOVELWRITER_PORT:-7860}"
FRONTEND_PORT="${NOVELWRITER_FRONTEND_PORT:-5173}"
PYTHON_BIN="${NOVELWRITER_PYTHON:-}"

find_python() {
  if [ -n "$PYTHON_BIN" ]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "未找到 NOVELWRITER_PYTHON=$PYTHON_BIN"; exit 1; }
    echo "$PYTHON_BIN"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    echo "未找到 Python，请先安装 Python 3.11+" >&2
    exit 1
  fi
}

ensure_python_env() {
  local py
  py="$(find_python)"
  if [ "${NOVELWRITER_USE_SYSTEM_PYTHON:-0}" != "1" ]; then
    if [ ! -x ".venv/bin/python" ]; then
      echo "创建虚拟环境 .venv ..."
      "$py" -m venv .venv
    fi
    py=".venv/bin/python"
  fi

  echo "Python: $("$py" --version)"
  "$py" -m pip install --upgrade pip >/dev/null

  local marker=".novelwriter.requirements.sha256"
  if [ "${NOVELWRITER_USE_SYSTEM_PYTHON:-0}" != "1" ]; then
    marker=".venv/.requirements.sha256"
  fi
  local current_hash
  current_hash="$("$py" - <<'PY'
import hashlib, pathlib
path = pathlib.Path("requirements.txt")
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
)"
  if ! "$py" -c "import fastapi, uvicorn" >/dev/null 2>&1 || [ ! -f "$marker" ] || [ "$(cat "$marker" 2>/dev/null)" != "$current_hash" ]; then
    echo "安装/更新 Python 依赖 ..."
    "$py" -m pip install -r requirements.txt
    mkdir -p "$(dirname "$marker")"
    printf "%s" "$current_hash" > "$marker"
  fi

  PYTHON_BIN="$py"
}

ensure_frontend_deps() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "未找到 npm，请先安装 Node.js 18+"
    exit 1
  fi
  if [ ! -d "frontend/node_modules" ]; then
    echo "安装前端依赖 ..."
    (cd frontend && { [ -f package-lock.json ] && npm ci || npm install; })
  fi
}

frontend_needs_build() {
  [ "$SKIP_BUILD" = "1" ] && return 1
  [ "${NOVELWRITER_FORCE_BUILD:-0}" = "1" ] && return 0
  [ ! -f "frontend/dist/index.html" ] && return 0
  find frontend/src frontend/package.json frontend/package-lock.json frontend/vite.config.ts -type f -newer frontend/dist/index.html 2>/dev/null | grep -q .
}

build_frontend_if_needed() {
  ensure_frontend_deps
  if frontend_needs_build; then
    echo "构建前端 ..."
    (cd frontend && npm run build)
  else
    echo "前端 dist 已是最新，跳过构建。"
  fi
}

ensure_runtime_files() {
  mkdir -p output styles prompts vectorstore
  [ -f projects.json ] || printf '{"active_project":"","projects":{}}\n' > projects.json
  [ -f xp_presets.json ] || printf '[]\n' > xp_presets.json
}

start_prod() {
  echo "=== 生产模式：启动 http://${HOST}:${PORT} ==="
  ensure_python_env
  ensure_runtime_files
  build_frontend_if_needed
  exec "$PYTHON_BIN" -m uvicorn api_server:app --host "$HOST" --port "$PORT"
}

start_dev() {
  echo "=== 开发模式：后端 http://${HOST}:${PORT} + 前端 http://127.0.0.1:${FRONTEND_PORT} ==="
  ensure_python_env
  ensure_runtime_files
  ensure_frontend_deps

  "$PYTHON_BIN" -m uvicorn api_server:app --host "$HOST" --port "$PORT" --reload &
  BACKEND_PID=$!
  (cd frontend && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT") &
  FRONTEND_PID=$!

  cleanup() {
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM
  wait
}

if [ "$MODE" = "dev" ]; then
  start_dev
else
  start_prod
fi
