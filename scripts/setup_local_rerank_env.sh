#!/usr/bin/env bash
set -euo pipefail

RERANK_HOME="${RERANK_HOME:-$HOME/.local/share/wechat-rerank}"
VENV_PATH="${VENV_PATH:-$RERANK_HOME/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -n "${TORCH_CHANNEL:-}" ]; then
  TORCH_CHANNEL="$TORCH_CHANNEL"
elif [ -f "/etc/nv_tegra_release" ] && [ "$(uname -m)" = "aarch64" ]; then
  TORCH_CHANNEL="jetson-cu126"
else
  TORCH_CHANNEL="cpu"
fi

if [ "$TORCH_CHANNEL" = "jetson-cu126" ]; then
  TORCH_INDEX="${JETSON_TORCH_INDEX:-https://pypi.jetson-ai-lab.io/jp6/cu126}"
  TORCH_VERSION="${JETSON_TORCH_VERSION:-2.10.0}"
else
  TORCH_INDEX="${CPU_TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"
  TORCH_VERSION="${CPU_TORCH_VERSION:-2.11.0+cpu}"
fi

mkdir -p "$RERANK_HOME"
if [ ! -x "$VENV_PATH/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

"$VENV_PATH/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_PATH/bin/python" -m pip uninstall -y \
  torch torchvision torchaudio triton \
  nvidia-cublas nvidia-cudnn nvidia-cusolver nvidia-cusparse \
  nvidia-cufft nvidia-curand nvidia-cuda-runtime \
  cuda-toolkit cuda-bindings cuda-pathfinder >/dev/null 2>&1 || true
"$VENV_PATH/bin/python" -m pip install --index-url "$TORCH_INDEX" "torch==$TORCH_VERSION"
"$VENV_PATH/bin/python" -m pip install \
  "transformers>=4.46,<5" \
  "fastapi" \
  "uvicorn[standard]" \
  "sentencepiece" \
  "safetensors"

echo "local rerank env ready: $VENV_PATH"
echo "torch source: $TORCH_INDEX torch==$TORCH_VERSION"
echo "torch channel: $TORCH_CHANNEL"
