# Fine-Tuning Guide

This document explains the **why** behind the QLoRA recipe and how to diagnose problems.

The TL;DR: 4-bit NF4 base + bf16 LoRA adapters with `r=64`, `lr=2e-5`, cosine schedule, 3 epochs, packed sequences at 4096 tokens. Single MI300X is enough.

---

## Why QLoRA?

A vanilla LoRA on Llama 3.1 70B in BF16 needs ~140 GB just for the static weights, and another ~30–60 GB for activations + optimizer state. That fits on a single MI300X (192 GB HBM3) — but only barely, and any sequence-length spike will OOM you.

**QLoRA** stores the base weights in **NF4 (4-bit normal-float)** and only the LoRA adapters in BF16. The base weights drop to ~35 GB; even with optimizer state and activations we have headroom for `seq_len=4096` and `gradient_accumulation_steps=16`.

The trade-off: QLoRA is mathematically lossy on the forward pass (4-bit dequantization for compute). Empirically the loss is well within noise for instruction-tuning. We pay a small inference cost during training in exchange for fitting on one GPU.

> The `bitsandbytes` upstream wheel is CUDA-only. We use the AMD-maintained ROCm fork: `git+https://github.com/ROCm/bitsandbytes.git@rocm_enabled`. It's installed in the training Docker image.

---

## Why these specific hyperparameters?

The config in [`training/configs/qlora_70b.yaml`](../../training/configs/qlora_70b.yaml):

| Knob                              | Value         | Why                                                                                          |
|-----------------------------------|---------------|----------------------------------------------------------------------------------------------|
| `lora.r`                          | **64**        | High rank — regulatory text is dense. Lower R underfits clause-citation patterns.            |
| `lora.lora_alpha`                 | 128           | `2 * r` — stable scaling; matches the original LoRA paper's recommendation.                  |
| `lora.target_modules`             | all 7 projections | q/k/v/o + gate/up/down. Targeting only attention loses the MLP, which holds factual recall. |
| `learning_rate`                   | **2e-5**      | Deliberately low — minimizes catastrophic forgetting of base instruction-following.          |
| `lr_scheduler_type`               | cosine        | Smooth decay to ~zero by end of epoch 3; avoids end-of-run instability.                      |
| `warmup_ratio`                    | 0.03          | ~3% of steps — enough to settle Adam moments without wasting compute.                        |
| `num_train_epochs`                | 3             | More than 3 starts to overfit our 540-example dataset; eval loss starts climbing.            |
| `per_device_train_batch_size`     | 1             | 70B + 4096 ctx is large; batching is via gradient accumulation.                              |
| `gradient_accumulation_steps`     | 16            | Effective batch = 16. Empirically the sweet spot for QLoRA on this dataset size.             |
| `gradient_checkpointing`          | true          | Trades ~30% extra time for ~40% less activation memory. Worth it for headroom.               |
| `bf16`                            | true          | MI300X is BF16-native. Don't use fp16 — Llama 3.1 was trained in BF16.                       |
| `optim`                           | paged_adamw_8bit | bnb-rocm fork supports it; halves optimizer state without quality loss.                   |
| `max_seq_length`                  | 4096          | SOPs in our dataset average ~1500 tokens; 4096 covers the long tail comfortably.             |
| `packing`                         | true          | TRL packs multiple short sequences into one 4096-token training example → ~2× throughput.   |
| `group_by_length`                 | true          | Reduces padding waste before packing kicks in.                                               |

### Why `r=64` instead of the typical `r=8` or `r=16`?

For most fine-tunes, `r=8` is plenty — you're nudging the model's tone. Here we're teaching it new structured-output behavior with hard constraints (clause numbers must be exact). Higher rank gives the model enough parameters to encode that structure as a stable attractor rather than a perturbation.

`r=64` means ~419M trainable parameters — about 0.59% of the base. Still well below "full fine-tune" territory, so it remains a LoRA in spirit and can be merged or kept as a portable adapter.

---

## Running training

Standard run:

```bash
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m training.src.train --config /workspace/training/configs/qlora_70b.yaml
```

To override a single value without editing the YAML, copy it and pass the new path:

```bash
cp training/configs/qlora_70b.yaml training/configs/qlora_70b_quick.yaml
# edit num_train_epochs: 1 for a quick smoke run
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m training.src.train --config /workspace/training/configs/qlora_70b_quick.yaml
```

### Live monitoring

The script reports to TensorBoard and (if `WANDB_API_KEY` is set) Weights & Biases.

TensorBoard:

```bash
docker compose -f docker/docker-compose.yml --profile train run --rm \
    -p 6006:6006 trainer \
    tensorboard --logdir /workspace/outputs --host 0.0.0.0
```

Then open <http://localhost:6006>.

`rocm-smi` (on the host) gives you VRAM/util:

```bash
watch -n 2 rocm-smi --showuse --showmemuse
```

You should see ~85–95% VRAM use and ~95–99% compute utilization once training is in steady state.

---

## Diagnosing training issues

### Loss never drops below ~2.0

- Check that `dataset_text_field` is `"text"` and the loaded examples actually contain rendered chat-template strings, not raw JSON. Inspect `train_ds[0]["text"]`.
- Verify the tokenizer's chat template includes the assistant turn — older HF versions need `tokenizer.chat_template` set explicitly.

### Loss spikes mid-epoch

- Almost always `max_grad_norm` is too high. Drop from `0.3` to `0.1`.
- Could also be a single bad example. Run with `--per_device_train_batch_size 1 --gradient_accumulation_steps 1` and watch which step explodes.

### OOM on the first forward pass

- You probably skipped `prepare_model_for_kbit_training`. The script does this for you — confirm it ran.
- Lower `max_seq_length` to `2048`. SOPs in our dataset rarely exceed 2K tokens.

### Loss decreases but eval is flat

- The dataset is too small *or* too uniform. Bump `--total` in `build_dataset.py` to 1500+, or extend the artifact templates with more variation.

### Eval loss climbs after epoch 1

- You're overfitting. Drop epochs to 2 or set `early_stopping_patience` (add to the YAML and pass via `EarlyStoppingCallback`).

---

## Custom datasets

The training data format is dead simple JSONL:

```json
{
  "device_context": "Device Name: ...\nDevice Class: Class II\n...",
  "instruction": "Draft a CAPA SOP per ISO 13485 §8.5.2 ...",
  "target": "# SOP-CAPA-001 ..."
}
```

Drop your file at `data/synthetic/train.jsonl` (and `eval.jsonl`) and run training. No code changes needed.

If you have **real** RA documents you can use, that's strictly better than synthetic — just be sure of the licensing.

---

## What to do with the LoRA adapters

You have three options after training:

1. **Keep them as adapters** — best for iteration. Load via `PeftModel.from_pretrained(base, adapter_dir)`. Small to share (~400 MB).
2. **Merge into base, serve in BF16** — simplest serving path. ~140 GB on disk.
3. **Merge + FP8 quantize via Quark** — best inference performance on MI300X. See [Serving Guide](03-serving.md).

Use `training/src/merge_and_export.py` for (2) and (3).
