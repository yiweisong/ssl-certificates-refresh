#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "初始化虚拟环境: $VENV"
  python3 -m venv "$VENV"
  # --only-binary: 本机 IT 加密工具会把源码编译过程读到的 .py 变成密文，
  # 导致 sdist 编译出损坏的 wheel，只允许预编译 wheel
  PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
  "$VENV/bin/pip" install --quiet -i "$PIP_INDEX" --upgrade pip
  "$VENV/bin/pip" install --quiet -i "$PIP_INDEX" --only-binary=:all: \
    -r requirements.txt
fi

exec "$PY" main.py "$@"
