#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RERANK_HOME="${RERANK_HOME:-$HOME/.local/share/wechat-rerank}"
VENV_PATH="${VENV_PATH:-$RERANK_HOME/.venv}"
MODEL_NAME="${LOCAL_EMBED_MODEL:-intfloat/multilingual-e5-base}"
HOST="${LOCAL_EMBED_HOST:-127.0.0.1}"
PORT="${LOCAL_EMBED_PORT:-8766}"
API_KEY="${LOCAL_EMBED_API_KEY:-local}"
BATCH_SIZE="${LOCAL_EMBED_BATCH_SIZE:-16}"
MAX_LENGTH="${LOCAL_EMBED_MAX_LENGTH:-512}"
DEVICE="${LOCAL_EMBED_DEVICE:-auto}"

if [ ! -x "$VENV_PATH/bin/python" ]; then
  echo "missing embed venv at $VENV_PATH; run scripts/setup_local_rerank_env.sh first" >&2
  exit 1
fi

export LOCAL_EMBED_MODEL="$MODEL_NAME"
export LOCAL_EMBED_HOST="$HOST"
export LOCAL_EMBED_PORT="$PORT"
export LOCAL_EMBED_API_KEY="$API_KEY"
export LOCAL_EMBED_BATCH_SIZE="$BATCH_SIZE"
export LOCAL_EMBED_MAX_LENGTH="$MAX_LENGTH"
export LOCAL_EMBED_DEVICE="$DEVICE"

exec "$VENV_PATH/bin/python" "$REPO_ROOT/examples/local_embedding_server.py"
