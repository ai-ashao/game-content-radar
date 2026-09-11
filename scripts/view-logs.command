#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$ROOT/logs/web.log" ]; then tail -n 120 "$ROOT/logs/web.log"; else echo "还没有运行日志。"; fi
printf '\n按回车关闭。'
read -r answer
