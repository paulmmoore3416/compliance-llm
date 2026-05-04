#!/usr/bin/env bash
# Launch vLLM (ROCm build) on a single MI300X with FP8 quantization.
#
# This script is the canonical entry point used by docker-compose. It can also
# be sourced standalone when iterating on serving config without rebuilding
# the container.

set -euo pipefail

MODEL_PATH="${MODEL_PATH:-/models/compliance-llama-70b-fp8}"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# Determine quantization mode from the model directory contents. If the model
# was exported with AMD Quark, vLLM auto-detects via config.json. We still
# pass --quantization explicitly for clarity in logs.
if [[ -f "${MODEL_PATH}/config.json" ]] && grep -q "fp8" "${MODEL_PATH}/config.json"; then
    QUANT_FLAG="--quantization fp8"
else
    echo "[serve] FP8 metadata not found in ${MODEL_PATH}; falling back to BF16." >&2
    QUANT_FLAG=""
fi

# MI300X has 192 GB HBM3 — for 70B FP8 we comfortably fit a long max-model-len.
# Tensor parallel = 1 means a single GPU; bump to 2 if you have a 2-GPU node.
exec python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL_PATH}" \
    --served-model-name compliance-llama-70b \
    --host "${HOST}" \
    --port "${PORT}" \
    --tensor-parallel-size "${TP_SIZE:-1}" \
    --max-model-len "${MAX_MODEL_LEN:-8192}" \
    --max-num-seqs "${MAX_NUM_SEQS:-128}" \
    --gpu-memory-utilization "${GPU_MEM_UTIL:-0.92}" \
    --dtype "${DTYPE:-auto}" \
    ${QUANT_FLAG} \
    --trust-remote-code \
    --enable-prefix-caching \
    --disable-log-requests
