#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/stop-web.command"
exec "$ROOT/scripts/start-web.command"
