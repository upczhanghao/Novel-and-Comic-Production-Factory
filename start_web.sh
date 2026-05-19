#!/usr/bin/env bash
# 兼容旧入口：统一转到 FastAPI/Vue 一键启动脚本。

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT_DIR/start_api.sh" "$@"
