#!/bin/bash
# Shared by Finder double-click launchers; no global Python installation changed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ ! -x "$ROOT/.venv/bin/python" ] || ! "$ROOT/.venv/bin/python" -c 'import sys; assert sys.version_info >= (3,11)' 2>/dev/null; then
  if [ -d "$ROOT/.venv" ]; then
    echo "现有 .venv 的 Python 低于3.11。请先备份/重建本项目虚拟环境，本脚本不会删除它。"; exit 1
  fi
  PY=""
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3,11)' 2>/dev/null; then PY="$candidate"; break; fi
  done
  if [ -z "$PY" ]; then echo "需要 Python 3.11+。安装后重新双击启动。"; exit 1; fi
  "$PY" -m venv "$ROOT/.venv"
fi
STAMP="$ROOT/.heybox-runtime/install.sha"
HASH="$("$ROOT/.venv/bin/python" -c 'import hashlib; print(hashlib.sha256(open("pyproject.toml","rb").read()).hexdigest())')"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$HASH" ] || ! "$ROOT/.venv/bin/python" -c 'import heybox_content_studio, fastapi, uvicorn, PIL, multipart' >/dev/null 2>&1; then
  echo "首次启动 / 依赖变更：正在安装本项目依赖…"
  "$ROOT/.venv/bin/python" -m pip install -e .
  mkdir -p "$ROOT/.heybox-runtime"
  printf '%s' "$HASH" > "$STAMP"
fi
