#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/_bootstrap.sh"
if ! "$ROOT/.venv/bin/python" -m heybox_content_studio --root "$ROOT" stop; then
  echo "请查看错误说明；按回车关闭。"
  read -r answer
  exit 1
fi
