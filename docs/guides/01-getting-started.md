# Getting Started

This is the **end-to-end walk-through** — provision a fresh AMD Developer Cloud MI300X instance, fine-tune Llama 3.1 70B, serve it via vLLM, and click "Generate" in the UI.

Total wall-clock: ~10 hours, mostly the training run itself. Active hands-on time: ~30 minutes.

> **New to AMD ROCm?** The only thing you really need to know is that ROCm replaces CUDA. PyTorch's API is identical (`torch.cuda.is_available()` returns `True`, `torch.cuda.set_device(0)` works, etc.). We avoid CUDA-only code paths so the rest is just standard HF / PyTorch.

---

## 0. Prerequisites

You need:

| Item                                         | Why                                                                  |
|----------------------------------------------|----------------------------------------------------------------------|
| AMD Developer Cloud account with MI300X access | Compute. Sign up at <https://www.amd.com/en/solutions/cloud.html>.  |
| A Hugging Face account + access token        | Pull `meta-llama/Llama-3.1-70B-Instruct` (gated repo).              |
| ~250 GB disk on the cloud instance           | Model weights + cache.                                               |
| Optional: Weights & Biases account           | Observability for the training run.                                  |

Before you start the cloud instance:

1. Visit [the Llama 3.1 model card](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct) and **accept the license**. Without this, downloads will 403.
2. Generate a **read** scoped Hugging Face token at <https://huggingface.co/settings/tokens>.

---

## 1. Provision the MI300X instance

In AMD Developer Cloud, launch an MI300X VM. Pick the largest disk you can (250 GB+).

SSH in and clone this repo:

```bash
git clone https://github.com/<your-org>/compliance-llama.git ~/compliance-llama
cd ~/compliance-llama
```

Run the bootstrap script:

```bash
bash scripts/bootstrap_mi300x.sh
```

What it does:

1. Sanity-checks `rocm-smi` and `gfx942` detection.
2. Installs Docker if missing and adds you to `video` / `render` groups.
3. Pulls the ROCm base images.
4. Builds the project images (`trainer`, `vllm`, `api`, `frontend`).
5. Runs a smoke test: launches a tiny container and confirms `torch.cuda.is_available()` is `True` *inside* the container with GPU passthrough.

If the smoke test prints something like:

```
torch: 2.4.0+rocm6.2
hip available: True
device count: 1
device 0: AMD Instinct MI300X
```

…you're good. If not, jump to [Troubleshooting](07-troubleshooting.md#rocm-not-detected-inside-container).

> **Group membership note:** if this is the first time you've installed Docker on this VM, you'll need to log out and back in so your user picks up the new `docker`/`video`/`render` groups. The bootstrap script will warn you.

---

## 2. Configure secrets

```bash
cp .env.example .env
$EDITOR .env
```

Set at minimum:

```bash
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxx
```

Optionally set:

```bash
WANDB_API_KEY=...
WANDB_PROJECT=compliance-llama
```

`docker-compose.yml` reads these via `${VAR}` substitution and forwards them into the containers — never bake tokens into the image.

---

## 3. Pull the base model

```bash
set -a; source .env; set +a
bash scripts/download_base_model.sh
```

This streams `meta-llama/Llama-3.1-70B-Instruct` (~140 GB) into `./models/`. With `hf_transfer` enabled (we ship it in the image, but the host script falls back to the standard CLI) you should see ~500 MB/s on AMD DC.

Verify:

```bash
ls -lh models/Llama-3.1-70B-Instruct/*.safetensors | head
```

You should see ~30 shards totaling ~140 GB.

---

## 4. Build the training dataset

The "Regulatory Gold Set" is generated locally — no API calls, no licensing concerns.

```bash
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m data.synthetic.build_dataset \
        --output-dir /workspace/data/synthetic \
        --total 540 \
        --seed 42
```

This produces `data/synthetic/train.jsonl` (~486 examples) and `data/synthetic/eval.jsonl` (~54 examples). Each example pairs a *Device Context* (Class, IFU, Risk Profile, Intended User, Use Environment) with a *Drafted SOP* citing specific ISO 13485 / 21 CFR 820 clauses.

Spot-check the output:

```bash
head -1 data/synthetic/train.jsonl | python -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['target'][:600])"
```

You should see a properly structured SOP starting with `# SOP-…` and including `## References` with `ISO 13485:2016 §…` and `21 CFR 820.…` citations.

> **Want to grow the dataset?** The generator is deterministic; bump `--total` to expand the combinatorial sweep, or extend `ARTIFACT_BUILDERS` in [`data/synthetic/build_dataset.py`](../../data/synthetic/build_dataset.py) with additional SOP templates.

---

## 5. Fine-tune

The whole training config lives in [`training/configs/qlora_70b.yaml`](../../training/configs/qlora_70b.yaml). Defaults are sensible for a single MI300X.

```bash
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m training.src.train --config /workspace/training/configs/qlora_70b.yaml
```

What to expect:

| Phase                       | Duration                  | What's happening                                          |
|-----------------------------|---------------------------|-----------------------------------------------------------|
| Tokenizer load              | seconds                   | HF cache hit                                              |
| 4-bit base model load       | 3–5 minutes               | Quantizing 70B from BF16 to NF4 across HBM                |
| Adapter initialization      | seconds                   | LoRA modules wired into 7 projection layers per block     |
| Training (3 epochs, 540 ex) | ~6–8 hours                | gradient_accumulation_steps=16 → effective batch 16       |
| Saving                      | ~1 minute                 | LoRA adapters only — ~400 MB                              |

You'll see lines like:

```
2026-05-04 12:34:56 | INFO | compliance-llama.train | Detected GPU: AMD Instinct MI300X
2026-05-04 12:34:56 | INFO | compliance-llama.train | Total HBM: 191.9 GB
trainable params: 419,430,400 || all params: 70,973,034,496 || trainable%: 0.5910
{'loss': 1.834, 'learning_rate': 1.97e-05, 'epoch': 0.06}
```

The loss should monotonically decrease. If it spikes hard or plateaus above 1.5, see [Fine-Tuning Guide → Diagnosing](02-fine-tuning.md#diagnosing-training-issues).

When it finishes, the LoRA adapters land at:

```
outputs/compliance-llama-70b-qlora/final/
├── adapter_config.json
├── adapter_model.safetensors
└── tokenizer.json
```

---

## 6. Merge & export to FP8

vLLM serves the merged model, not raw adapters. We also re-quantize to FP8 to halve the VRAM footprint (and exploit the MI300X's native FP8 cores).

```bash
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m training.src.merge_and_export \
        --base meta-llama/Llama-3.1-70B-Instruct \
        --adapter /workspace/outputs/compliance-llama-70b-qlora/final \
        --output /models/compliance-llama-70b-merged \
        --fp8 \
        --fp8-output /models/compliance-llama-70b-fp8
```

If `amd-quark` isn't installed, the script falls back to copying the BF16 weights — vLLM will still serve them, just at higher VRAM use.

---

## 7. Serve

```bash
docker compose -f docker/docker-compose.yml --profile serve up
```

This brings up three containers:

| Container | Port  | What it is                                    |
|-----------|-------|-----------------------------------------------|
| `cl-vllm` | 8000  | vLLM OpenAI-compatible API on the MI300X.     |
| `cl-api`  | 8080  | FastAPI gateway (SSE, PDF, validation).       |
| `cl-frontend` | 5173 | React UI.                                  |

Health check:

```bash
curl -s http://localhost:8080/health | jq
# { "status": "ok", "vllm_reachable": true, "fine_tuned_model": "compliance-llama-70b" }
```

Open <http://localhost:5173> in your browser. Fill in the device context (the form pre-populates with a CGM example) and click **Generate**.

You should see tokens streaming in within ~1 second of clicking, and a complete SOP within ~10–20 seconds.

---

## 8. (Optional) Side-by-side comparison

Want to demo the value of fine-tuning? Spin up a second vLLM instance pointed at the *un-tuned* base model and configure the API:

```bash
# In a second terminal, with vLLM running for the base model on port 8001
export BASE_LLAMA_URL=http://localhost:8001
docker compose -f docker/docker-compose.yml --profile serve up --no-deps api
```

Now in the UI, **Compare with base Llama 3.1** is enabled — clicking it produces both outputs side-by-side. The difference is dramatic: base Llama hallucinates clause numbers, Compliance-Llama cites them correctly.

---

## What's next

- [Fine-Tuning Guide](02-fine-tuning.md) — knobs you can turn, how to diagnose loss curves.
- [Serving Guide](03-serving.md) — vLLM tuning, FP8 details, benchmarking.
- [Compliance & Limitations](06-compliance-and-limitations.md) — **read this before showing output to anyone in RA**.
