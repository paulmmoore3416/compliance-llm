# Serving Guide

How Compliance-Llama is served at inference time, and how to tune it.

---

## The pipeline

```
   merged BF16 model           AMD Quark             vLLM ROCm
       (140 GB)        ───►     FP8 export    ───►    runtime    ───► OpenAI HTTP API
                              (~70 GB on disk)       (MI300X)
```

There are three reasons we go through Quark + FP8 rather than just serving BF16:

1. **VRAM** — FP8 weights are half the size, leaving more HBM for KV cache and concurrent sequences.
2. **Throughput** — MI300X has native FP8 (E4M3 / E5M2) tensor cores. We're using silicon that BF16 leaves idle.
3. **Quality preservation** — for instruction-tuned 70B models, FP8 loss is in the noise floor of evaluation. We've measured no measurable regression on our SOP-quality rubric.

If `amd-quark` is not installed (it's gated/limited-distribution at time of writing), `merge_and_export.py` falls back to BF16. vLLM will serve it; you just lose ~40% throughput.

---

## Launching vLLM

The canonical entrypoint is [`serving/launch_vllm.sh`](../../serving/launch_vllm.sh). It auto-detects FP8 metadata in `config.json` and adds `--quantization fp8` accordingly.

Manual invocation:

```bash
docker run --rm \
    --device=/dev/kfd --device=/dev/dri \
    --group-add video --group-add render \
    --security-opt seccomp=unconfined --cap-add=SYS_PTRACE \
    --ipc=host --shm-size=32g \
    -v $(pwd)/models:/models \
    -p 8000:8000 \
    rocm/vllm:rocm6.2_vllm_0.6.3_20241015 \
    python -m vllm.entrypoints.openai.api_server \
        --model /models/compliance-llama-70b-fp8 \
        --served-model-name compliance-llama-70b \
        --tensor-parallel-size 1 \
        --max-model-len 8192 \
        --max-num-seqs 128 \
        --gpu-memory-utilization 0.92 \
        --quantization fp8 \
        --enable-prefix-caching
```

### Key flags explained

| Flag                              | Default     | What it does                                                                       |
|-----------------------------------|-------------|------------------------------------------------------------------------------------|
| `--tensor-parallel-size`          | 1           | Single MI300X. Set to 2/4/8 on multi-GPU nodes; weights split across GPUs.         |
| `--max-model-len`                 | 8192        | Hard ceiling on prompt + output tokens per sequence. 8K is plenty for SOPs.        |
| `--max-num-seqs`                  | 128         | Concurrent sequences. With 192 GB HBM3 you can push much higher; 128 is comfortable. |
| `--gpu-memory-utilization`        | 0.92        | Fraction of HBM vLLM is allowed to use. Higher = more KV cache, less safety margin. |
| `--enable-prefix-caching`         | on          | Caches the system prompt KV. Massive win for our use case — same system prompt every request. |
| `--quantization fp8`              | auto        | Enables FP8 paths. Required if model was Quark-exported.                            |
| `--disable-log-requests`          | on          | Reduces log noise during demo.                                                     |

### Memory budget on MI300X

A rough budget for FP8 70B at 8K context:

- Weights:                 ~70 GB
- KV cache (128 seqs × 8K): ~80 GB (FP8 KV)
- Activations / scratch:   ~10 GB
- **Total:**               ~160 GB / 192 GB → 84% utilization, comfortable.

Bumping `--max-num-seqs` to 256 and `--max-model-len` to 16384 fits, but starts to flirt with edge cases.

---

## Benchmarking

We ship [`serving/benchmark.py`](../../serving/benchmark.py). After bringing up vLLM:

```bash
python serving/benchmark.py --base-url http://localhost:8000 \
    --requests 64 --concurrency 16 --max-tokens 512
```

Expected on a single MI300X with FP8 + prefix caching, our model:

- **Output tokens/sec:** 2,500–3,500 (aggregate, all concurrent requests)
- **Per-stream tokens/sec:** 60–90
- **TTFT median:** 0.3–0.6 s
- **TTFT p99:** 1.0–1.8 s

If you're materially below these numbers, the [Troubleshooting](07-troubleshooting.md) doc has a vLLM-specific section.

> **Why prefix caching matters so much here.** Every Compliance-Llama request shares the same ~280-token system prompt. With `--enable-prefix-caching` vLLM hashes the prefix and reuses its KV across requests — the second user's TTFT drops by ~250–400 ms because we skip prompt prefill for the system prompt.

---

## Running a "base vs fine-tuned" comparison demo

Two vLLM containers, one binding the fine-tune, one binding the base model:

```bash
# Terminal A — fine-tuned
MODEL_PATH=/models/compliance-llama-70b-fp8 PORT=8000 bash serving/launch_vllm.sh

# Terminal B — base
MODEL_PATH=/models/Llama-3.1-70B-Instruct PORT=8001 bash serving/launch_vllm.sh
```

Then start the API with `BASE_LLAMA_URL` set:

```bash
docker compose -f docker/docker-compose.yml --profile serve up api
# (with BASE_LLAMA_URL=http://host.docker.internal:8001 in .env)
```

The frontend automatically enables the **Compare with base Llama 3.1** button when the comparison endpoint is reachable.

> **Tip for the demo video:** the value-of-fine-tuning is most visible on questions that *require* a specific clause number. "Draft a Risk Management SOP citing ISO 14971 §7" is a great prompt — base Llama will give you a generic risk doc, Compliance-Llama gives you the actual structure with correct sub-clauses.

---

## Multi-GPU scaling

If you have a 2x or 8x MI300X box, you can use tensor parallelism for higher throughput:

```bash
TP_SIZE=2 bash serving/launch_vllm.sh
```

vLLM will shard the model across GPUs. **Throughput roughly doubles** with TP=2, and the per-stream latency stays the same. Use TP > 1 only if you need the throughput — for a single-stream demo it's wasteful.

---

## Updating the served model

After a new fine-tune:

1. `merge_and_export.py` produces a new directory under `models/`.
2. Edit `MODEL_PATH` in `.env` (or `docker/docker-compose.yml`).
3. `docker compose ... up -d --no-deps vllm` restarts only the vLLM container.

vLLM cold-start with FP8 70B is ~90 seconds. The healthcheck in `docker-compose.yml` has `start_period: 600s` so dependent containers wait.

---

## Hardening for production (not in scope for the hackathon, but…)

- Put a real reverse proxy (Caddy, Nginx) in front of the API; terminate TLS there.
- Add rate-limiting per IP — vLLM is happy to chew through your GPU minutes.
- Persist generation logs to a database; SOPs are auditable artifacts and should be reproducible.
- Sign every generated PDF with a timestamp + model hash to support audit trails.
- Add a real auth layer; pydantic validation is **input** validation, not authentication.
