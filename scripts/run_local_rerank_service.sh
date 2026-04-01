#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RERANK_HOME="${RERANK_HOME:-$HOME/.local/share/wechat-rerank}"
VENV_PATH="${VENV_PATH:-$RERANK_HOME/.venv}"
MODEL_NAME="${LOCAL_RERANK_MODEL:-Alibaba-NLP/gte-multilingual-reranker-base}"
HOST="${LOCAL_RERANK_HOST:-127.0.0.1}"
PORT="${LOCAL_RERANK_PORT:-8765}"
API_KEY="${LOCAL_RERANK_API_KEY:-local}"
BATCH_SIZE="${LOCAL_RERANK_BATCH_SIZE:-8}"
MAX_LENGTH="${LOCAL_RERANK_MAX_LENGTH:-1024}"
DEVICE="${LOCAL_RERANK_DEVICE:-auto}"

if [ ! -x "$VENV_PATH/bin/python" ]; then
  echo "missing rerank venv at $VENV_PATH; run scripts/setup_local_rerank_env.sh first" >&2
  exit 1
fi

export LOCAL_RERANK_MODEL="$MODEL_NAME"
export LOCAL_RERANK_HOST="$HOST"
export LOCAL_RERANK_PORT="$PORT"
export LOCAL_RERANK_API_KEY="$API_KEY"
export LOCAL_RERANK_BATCH_SIZE="$BATCH_SIZE"
export LOCAL_RERANK_MAX_LENGTH="$MAX_LENGTH"
export LOCAL_RERANK_DEVICE="$DEVICE"

exec "$VENV_PATH/bin/python" "$REPO_ROOT/examples/local_rerank_server.py"
