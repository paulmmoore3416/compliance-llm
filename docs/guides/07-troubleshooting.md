# Troubleshooting

Concrete fixes to specific symptoms, ordered roughly by how often we see them.

---

## ROCm not detected inside container

**Symptom**

```
RuntimeError: torch.cuda.is_available() is False
```

…even though `rocm-smi` works on the host.

**Causes & fixes**

1. **Missing device passthrough.** The container needs `/dev/kfd` and `/dev/dri`:
   ```bash
   docker run --device=/dev/kfd --device=/dev/dri \
       --group-add video --group-add render \
       --security-opt seccomp=unconfined --cap-add=SYS_PTRACE \
       --ipc=host ...
   ```
   Our `docker-compose.yml` includes all of this via the `x-rocm` anchor.

2. **Wrong base image.** Confirm you're on `rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_2.4.0` — the `rocm/pytorch:latest` floating tag often points to an older ROCm.

3. **Host driver mismatch.** ROCm 6.2 needs the matching `amdgpu-dkms`. On AMD Developer Cloud images this is correct out of the box; on bare metal verify with `dpkg -l | grep amdgpu`.

4. **Group not applied.** If you just installed Docker, log out and back in so `video`/`render` group membership takes effect.

---

## `bitsandbytes` import fails inside the container

**Symptom**

```
ImportError: ... libbitsandbytes_rocm.so: cannot open shared object file
```

**Cause**

The upstream `bitsandbytes` wheel is CUDA-only. You need the AMD ROCm fork.

**Fix**

```bash
pip install --no-build-isolation \
    git+https://github.com/ROCm/bitsandbytes.git@rocm_enabled
```

Our `docker/Dockerfile.training` does this for you. If you're in a custom env, run the above manually.

---

## Training OOMs on the first forward pass

**Symptom**

```
torch.OutOfMemoryError: HIP out of memory
```

…during the first forward pass, before any gradient step.

**Causes & fixes**

1. **`prepare_model_for_kbit_training` skipped.** `train.py` calls this — confirm `model.print_trainable_parameters()` printed a sane number (~419M for `r=64`).
2. **`max_seq_length` too high.** Drop from 4096 to 2048 if you're on a non-MI300X (e.g. MI250X with 128 GB) or have less HBM available.
3. **Gradient checkpointing disabled.** Re-enable it: `gradient_checkpointing: true` in YAML.
4. **`group_by_length=false`.** Without it, padding to the longest sequence inflates memory. Turn it on.

---

## Loss is NaN / Inf

**Symptom**

Training log shows `loss: nan` after a few steps.

**Causes & fixes**

1. **`fp16: true` instead of `bf16: true`.** Llama 3.1 was trained in BF16; FP16 has too narrow a range and overflows during gradient accumulation. Always use BF16 on MI300X.
2. **`max_grad_norm` too high.** Default 0.3 in our config; if you increased it for a quick experiment, restore it.
3. **Bad data row.** Run with batch=1 and accumulation=1 to identify the offending step, then inspect `train_ds[step_idx]` for empty `text`.

---

## vLLM container exits immediately on startup

**Symptom**

`docker compose ... up vllm` returns within seconds with the container in `Exited (1)` state.

**Diagnosis**

```bash
docker logs cl-vllm | tail -100
```

Common causes:

1. **`MODEL_PATH` not mounted.** The compose file maps `${MODEL_DIR:-../models}:/models`. Confirm `models/compliance-llama-70b-fp8/` exists on the host.
2. **Model files incomplete.** Re-run `merge_and_export.py`. A truncated `.safetensors` will fail mmap.
3. **`--quantization fp8` on a BF16 model.** `launch_vllm.sh` auto-detects this; if you bypass it, pass the right flag.
4. **GPU not visible.** The same checklist as the [ROCm not detected](#rocm-not-detected-inside-container) section.

---

## vLLM throughput is half what the docs claim

**Symptom**

`benchmark.py` reports ~1500 tok/s aggregate instead of the expected 2500–3500.

**Causes & fixes**

1. **Prefix caching disabled.** `--enable-prefix-caching` is a 2–3× win for our workload (shared system prompt). Confirm it's in `launch_vllm.sh`.
2. **Concurrency too low.** Bump `--concurrency` in `benchmark.py` to 16+. Single-stream throughput is lower by design.
3. **BF16 instead of FP8.** Quark export step skipped or fell back. Check `config.json` of the model directory for `"quantization_config": {"quant_method": "fp8"}`.
4. **Triton flash attention not active.** Ensure `VLLM_USE_TRITON_FLASH_ATTN=1` is set (we set it in the serving Dockerfile).
5. **GPU memory too tight.** If you're at 99% HBM, vLLM throttles to avoid OOM. Drop `--max-num-seqs` from 128 to 64.

---

## Frontend can't talk to the API ("CORS error")

**Symptom** (browser console)

```
Access to fetch at 'http://localhost:8080/v1/generate' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**Cause**

The API's `CORS_ORIGINS` env doesn't include the frontend's origin.

**Fix**

In `.env`:

```bash
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

…then restart the API container (`docker compose ... up -d --no-deps api`).

If you deploy the frontend to a different host, add that origin too.

---

## "Stream stopped after one token"

**Symptom**

UI receives one or two tokens and then stops; no error message.

**Causes & fixes**

1. **Reverse proxy buffering.** Nginx/Caddy default buffers SSE. Set `proxy_buffering off;` (Nginx) or `flush_interval 0` (Caddy).
2. **Connection idle timeout.** vLLM keeps the SSE alive with periodic `data: {}` chunks; sse-starlette adds a `: ping` every 15s. If your proxy times out faster, raise the limit.
3. **Browser dev-tool throttling.** "Slow 3G" mode on the Network tab can make streams look stalled.

---

## Generated SOPs cite wrong clause numbers

**Symptom**

The model invents `ISO 13485 §9.3.7` (no such clause) or attributes 21 CFR 820.30 content to ISO 13485.

**This is the model behaving as expected, not a bug.** See [Compliance & Limitations → Known failure modes](06-compliance-and-limitations.md#known-failure-modes).

**Mitigations**

- Increase the synthetic dataset coverage of the affected clause cluster and retrain.
- Lower the temperature (0.0 – 0.2 max for serious use).
- Always run the generated SOP through human RA review before use.

---

## "Hugging Face download fails with 401/403"

```
huggingface_hub.utils._errors.GatedRepoError: 403 Client Error
```

**Cause**

Either the HF token isn't scoped correctly, or you haven't accepted the Llama 3.1 license.

**Fix**

1. Visit <https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct> while logged in and click "Access repository". You'll get an email confirming access.
2. Generate a token with at least the `read` scope at <https://huggingface.co/settings/tokens>.
3. `export HF_TOKEN=hf_...` and re-run `download_base_model.sh`.

---

## Anything else

Open an issue on the repo with:

- Output of `rocm-smi --showproductname`
- Output of `docker compose ... ps`
- The relevant `docker logs` excerpt
- A description of what you ran
