#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -x ".venv/bin/python" ]; then
  echo "[Game Content Radar] Creating local Python environment..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import game_content_radar, fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[Game Content Radar] Installing / updating dependencies..."
  .venv/bin/python -m pip install -e .
fi

echo "[Game Content Radar] Opening http://127.0.0.1:8787"
exec .venv/bin/game-radar web --config config/codex.yaml
