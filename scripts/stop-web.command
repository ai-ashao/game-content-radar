#!/bin/bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/.game-content-radar-web.pid"

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

if [ ! -f "$PID_FILE" ]; then
  echo "[Game Content Radar] No PID file. The dashboard is already stopped or was started manually."
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$PID" ]; then
  rm -f "$PID_FILE"
  echo "[Game Content Radar] Removed stale PID file."
  exit 0
fi

if kill -0 "$PID" >/dev/null 2>&1 && ! pid_is_ours "$PID"; then
  echo "[Game Content Radar] Refusing to stop unrelated process $PID; removing stale PID file."
  rm -f "$PID_FILE"
  exit 0
fi

if pid_is_ours "$PID"; then
  echo "[Game Content Radar] Stopping service $PID..."
  kill "$PID" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! kill -0 "$PID" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
  if kill -0 "$PID" >/dev/null 2>&1; then
    kill -9 "$PID" >/dev/null 2>&1 || true
  fi
fi

rm -f "$PID_FILE"
echo "[Game Content Radar] Dashboard stopped."
