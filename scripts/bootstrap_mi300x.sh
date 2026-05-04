#!/usr/bin/env bash
# bootstrap_mi300x.sh — provision a fresh AMD Developer Cloud MI300X instance
# for the Compliance-Llama project.
#
# Idempotent. Safe to re-run.

set -euo pipefail

log() { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[bootstrap]\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Sanity: confirm we are actually on an AMD GPU host -----------------------
if ! command -v rocm-smi >/dev/null 2>&1; then
    die "rocm-smi not found. This script expects a ROCm-enabled host (e.g. AMD Developer Cloud)."
fi

log "Detected ROCm host. GPU inventory:"
rocm-smi --showproductname --showmeminfo vram | sed 's/^/    /'

# Verify gfx942 (MI300X CDNA3). The model architecture probe is what most
# downstream tooling actually keys off.
if ! rocminfo 2>/dev/null | grep -q "gfx942"; then
    log "WARNING: gfx942 not detected. The training & FP8 paths assume MI300X."
fi

# 2. Docker + ROCm device passthrough ----------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    sudo usermod -aG video "$USER"
    sudo usermod -aG render "$USER"
    log "Added $USER to docker, video, render groups. Re-login required for group changes to take effect."
fi

# 3. Project workspace --------------------------------------------------------
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/compliance-llama}"
log "Project root: $PROJECT_ROOT"

if [[ ! -d "$PROJECT_ROOT" ]]; then
    die "Project directory $PROJECT_ROOT not found. Clone the repo first."
fi

cd "$PROJECT_ROOT"

# 4. Secrets -----------------------------------------------------------------
if [[ ! -f .env ]]; then
    log "Creating .env from template — fill in HF_TOKEN before launching training."
    cp .env.example .env
fi

# 5. Pre-pull base images so the first train/serve invocation is fast --------
log "Pulling ROCm base images (this is a few GB; grab a coffee)..."
docker pull rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_2.4.0 || true
docker pull rocm/vllm:rocm6.2_vllm_0.6.3_20241015 || true

# 6. Build project images ----------------------------------------------------
log "Building Compliance-Llama training image..."
docker compose -f docker/docker-compose.yml --profile train build trainer

log "Building Compliance-Llama serving images..."
docker compose -f docker/docker-compose.yml --profile serve build vllm api

# 7. Verify GPU is visible inside the container ------------------------------
log "Smoke test: torch.cuda.is_available() inside container..."
docker run --rm \
    --device=/dev/kfd --device=/dev/dri \
    --group-add video --group-add render \
    --security-opt seccomp=unconfined --cap-add=SYS_PTRACE \
    --ipc=host \
    compliance-llama/trainer:latest \
    python -c "import torch; print('torch:', torch.__version__); print('hip available:', torch.cuda.is_available()); print('device count:', torch.cuda.device_count()); print('device 0:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'n/a')"

log "Bootstrap complete."
log "Next: edit .env, then run scripts/download_base_model.sh"
