#!/bin/bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${RADAR_WEB_PORT:-8787}"
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}"
CONFIG="${RADAR_WEB_CONFIG:-config/codex.yaml}"
PID_FILE="$ROOT/.game-content-radar-web.pid"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/web.log"
mkdir -p "$LOG_DIR"

health_check() {
  "$ROOT/.venv/bin/python" - "$URL/api/health" >/dev/null 2>&1 <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=0.7) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raise SystemExit(0 if payload.get("ok") and payload.get("version") == "0.3.0" else 1)
except Exception:
    raise SystemExit(1)
PY
}

pid_is_ours() {
  PID_TO_CHECK="$1"
  case "$PID_TO_CHECK" in
    ''|*[!0-9]*) return 1 ;;
  esac
  kill -0 "$PID_TO_CHECK" >/dev/null 2>&1 || return 1
  PROCESS_COMMAND="$(ps -p "$PID_TO_CHECK" -o command= 2>/dev/null || true)"
  case "$PROCESS_COMMAND" in
    *"$ROOT/.venv/bin/game-radar web"*) return 0 ;;
    *) return 1 ;;
  esac
}

open_dashboard() {
  if command -v open >/dev/null 2>&1; then
    open "$URL"
  else
    "$ROOT/.venv/bin/python" - "$URL" <<'PY' >/dev/null 2>&1 &
import sys, webbrowser
webbrowser.open(sys.argv[1])
PY
  fi
}

echo "[Game Content Radar] Preparing local dashboard..."

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  python3 -m venv "$ROOT/.venv"
fi

if ! "$ROOT/.venv/bin/python" -c "import game_content_radar, fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[Game Content Radar] Installing dependencies..."
  "$ROOT/.venv/bin/python" -m pip install -e "$ROOT"
fi

if health_check; then
  echo "[Game Content Radar] Dashboard is already running at $URL"
  open_dashboard
  exit 0
fi

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if pid_is_ours "$OLD_PID"; then
    echo "[Game Content Radar] Waiting for existing process $OLD_PID..."
    for _ in $(seq 1 20); do
      if health_check; then
        open_dashboard
        exit 0
      fi
      sleep 0.5
    done
    echo "[Game Content Radar] Existing process is unhealthy. Restarting it."
    kill "$OLD_PID" >/dev/null 2>&1 || true
    sleep 1
  elif [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" >/dev/null 2>&1; then
    echo "[Game Content Radar] Refusing to stop unrelated process $OLD_PID; removing stale PID file."
  fi
  rm -f "$PID_FILE"
fi

echo "[Game Content Radar] Starting background service..."
nohup "$ROOT/.venv/bin/game-radar" web \
  --root "$ROOT" \
  --config "$CONFIG" \
  --host "$HOST" \
  --port "$PORT" \
  --no-browser \
  >> "$LOG_FILE" 2>&1 </dev/null &
PID=$!
echo "$PID" > "$PID_FILE"

for _ in $(seq 1 40); do
  if health_check; then
    echo "[Game Content Radar] Ready: $URL"
    echo "[Game Content Radar] Log: $LOG_FILE"
    open_dashboard
    exit 0
  fi
  if ! kill -0 "$PID" >/dev/null 2>&1; then
    echo "[Game Content Radar] Service exited during startup."
    echo "--- Last log lines ---"
    tail -n 30 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 0.5
done

echo "[Game Content Radar] Startup timed out."
echo "--- Last log lines ---"
tail -n 30 "$LOG_FILE" 2>/dev/null || true
kill "$PID" >/dev/null 2>&1 || true
rm -f "$PID_FILE"
exit 1
