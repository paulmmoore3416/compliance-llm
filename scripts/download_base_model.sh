#!/usr/bin/env bash
# Pull Llama 3.1 70B Instruct into the local model cache.
#
# Requires a HF token with access to meta-llama/Llama-3.1-70B-Instruct
# (gated repo — accept the license on the model card first).

set -euo pipefail

: "${HF_TOKEN:?HF_TOKEN must be set. Edit .env and source it.}"

MODEL_ID="${MODEL_ID:-meta-llama/Llama-3.1-70B-Instruct}"
TARGET_DIR="${MODEL_DIR:-./models}/$(basename "$MODEL_ID")"

mkdir -p "$TARGET_DIR"

echo "[download] $MODEL_ID -> $TARGET_DIR"

# hf_transfer + the snapshot CLI is the fastest path; falls back to plain
# huggingface_hub if hf_transfer is not installed.
HF_HUB_ENABLE_HF_TRANSFER=1 \
huggingface-cli download "$MODEL_ID" \
    --local-dir "$TARGET_DIR" \
    --local-dir-use-symlinks False \
    --token "$HF_TOKEN"

echo "[download] Done. ~140 GB at $TARGET_DIR"
