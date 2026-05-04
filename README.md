# Compliance-Llama

> An audit-ready SOP generator for medical-device regulatory compliance, built on a QLoRA fine-tune of **Llama 3.1 70B Instruct** running on **AMD Instinct MI300X**.

[![ROCm](https://img.shields.io/badge/ROCm-6.2-ED1C24)](https://rocm.docs.amd.com/) [![PyTorch](https://img.shields.io/badge/PyTorch-2.4-EE4C2C)](https://pytorch.org/) [![vLLM](https://img.shields.io/badge/vLLM-0.6.x-7c3aed)](https://github.com/vllm-project/vllm) [![Track](https://img.shields.io/badge/AMD%20Hackathon-Track%202-black)](#)

Compliance-Llama is a domain-specialized LLM that turns a one-paragraph device description into an audit-ready Standard Operating Procedure (SOP) or QMS artifact, with explicit clause citations against **ISO 13485:2016** and **FDA 21 CFR Part 820**.

It targets the multi-billion-dollar regulatory-overhead pain point in MedTech, and it does it on **sovereign AI infrastructure**: a single AMD MI300X (192 GB HBM3) serving 70B parameters in **FP8** at interactive latency.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Architecture at a glance](#architecture-at-a-glance)
- [Quick start (TL;DR)](#quick-start-tldr)
- [Repository layout](#repository-layout)
- [Documentation index](#documentation-index)
- [Hardware & software requirements](#hardware--software-requirements)
- [Compliance disclaimer](#compliance-disclaimer)
- [License](#license)

---

## Why this exists

Bringing a medical device to market is a documentation marathon. A typical 510(k) submission is 1,000+ pages of QMS records, SOPs, design controls, and clause-by-clause justification. Drafting these is currently:

- Repetitive (every QMS rebuilds the same skeleton with minor device-specific tweaks),
- Error-prone (clause numbers drift between revisions of ISO 13485 / 21 CFR 820),
- Slow (RA teams cost $300+/hour and turn around a single SOP in days).

**Compliance-Llama compresses that workflow into seconds.** Feed in the device class, intended user, IFU, and risk profile, and get a structured SOP back — purpose, scope, responsibilities, procedure, references, revision history — with every clause cited.

Critically, the model is a **fine-tune**, not a RAG hack. A vanilla Llama happily makes up clause numbers; Compliance-Llama has been trained on the actual structure of regulatory artifacts, so its output reads like an RA professional wrote it.

## Architecture at a glance

```
   ┌──────────────────────────────┐
   │ React + TypeScript + Tailwind │   "Context Window" UI
   │   - SSE token streaming        │   - Side-by-side comparison
   │   - PDF export                 │
   └──────────────┬───────────────┘
                  │ HTTPS / SSE
   ┌──────────────▼───────────────┐
   │ FastAPI gateway              │   - Input validation (pydantic)
   │   :8080                      │   - SSE stream multiplexing
   │                              │   - PDF rendering (ReportLab)
   └──────────────┬───────────────┘
                  │ OpenAI-compat HTTP
   ┌──────────────▼───────────────┐
   │ vLLM (ROCm 6.2 build)        │   - FP8 KV cache + weights
   │   :8000                      │   - Prefix caching
   │                              │   - 128 concurrent sequences
   └──────────────┬───────────────┘
                  │ HIP / PyTorch
   ┌──────────────▼───────────────┐
   │ AMD Instinct MI300X          │   - 192 GB HBM3
   │   gfx942 (CDNA3)             │   - Native FP8 (E4M3)
   └──────────────────────────────┘
```

**Training-time** uses the same MI300X, swapping vLLM for QLoRA on top of `bitsandbytes` (ROCm fork). LoRA adapters are merged into the base model, then quantized to FP8 with AMD Quark for serving.

## Quick start (TL;DR)

On a fresh MI300X instance from AMD Developer Cloud:

```bash
git clone <your-fork>/compliance-llama && cd compliance-llama

# 1. Provision: docker, ROCm devices, base images
bash scripts/bootstrap_mi300x.sh

# 2. Configure
cp .env.example .env
# ... edit .env to add HF_TOKEN ...

# 3. Pull the base model (~140 GB, ~10–20 min on AMD DC)
bash scripts/download_base_model.sh

# 4. Generate the synthetic dataset
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m data.synthetic.build_dataset --output-dir /workspace/data/synthetic

# 5. Fine-tune (3 epochs, ~6–8 h on a single MI300X)
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m training.src.train --config /workspace/training/configs/qlora_70b.yaml

# 6. Merge LoRA + export to FP8
docker compose -f docker/docker-compose.yml --profile train run --rm trainer \
    python -m training.src.merge_and_export \
        --base meta-llama/Llama-3.1-70B-Instruct \
        --adapter /workspace/outputs/compliance-llama-70b-qlora/final \
        --output /models/compliance-llama-70b-merged \
        --fp8

# 7. Serve
docker compose -f docker/docker-compose.yml --profile serve up
# → vLLM:    http://localhost:8000
# → API:     http://localhost:8080
# → Frontend http://localhost:5173
```

Full step-by-step is in [`docs/guides/01-getting-started.md`](docs/guides/01-getting-started.md).

## Repository layout

```
compliance-llama/
├── backend/                   FastAPI gateway (SSE, PDF, comparison)
│   ├── app/
│   │   ├── main.py            Endpoints: /health /v1/generate /v1/compare /v1/export/pdf
│   │   ├── schemas.py         Pydantic models for the public API
│   │   ├── vllm_client.py     Async HTTP client for vLLM's OpenAI surface
│   │   ├── prompts.py         System prompt + chat-template builder
│   │   └── pdf.py             Markdown → PDF (ReportLab)
│   └── requirements.txt
│
├── frontend/                  React + TypeScript + Tailwind
│   └── src/
│       ├── App.tsx            Main layout + state
│       ├── components/        Header, DeviceContextPanel, OutputPanel
│       ├── lib/api.ts         Typed API client incl. SSE parser
│       └── types/api.ts       Shared types with backend
│
├── training/                  QLoRA fine-tuning (PEFT + TRL on ROCm)
│   ├── configs/qlora_70b.yaml LoRA r=64, lr=2e-5, packing=true
│   └── src/
│       ├── train.py           Entry point
│       ├── data.py            JSONL loader + chat-template formatting
│       ├── prompts.py         System prompt for training
│       └── merge_and_export.py  Merge adapters → FP8 export via Quark
│
├── data/synthetic/            "Regulatory Gold Set" generator
│   ├── build_dataset.py       Combinatorial expansion → 540+ examples
│   └── seed_examples.jsonl
│
├── serving/                   vLLM ROCm launcher + benchmark
│   ├── launch_vllm.sh         FP8 detect + tuned vLLM flags
│   ├── configs/vllm.env       Env-var defaults
│   └── benchmark.py           tok/s and TTFT measurement
│
├── docker/                    Reproducible builds
│   ├── Dockerfile.training    rocm/pytorch:6.2 + bnb-rocm fork + flash-attn
│   ├── Dockerfile.serving     rocm/vllm:6.2 + FastAPI gateway
│   ├── Dockerfile.frontend    Node 20 dev container
│   └── docker-compose.yml     Profiles: --profile train, --profile serve
│
├── scripts/
│   ├── bootstrap_mi300x.sh    One-shot AMD DC bootstrap
│   └── download_base_model.sh huggingface-cli + hf_transfer
│
└── docs/                      User & developer documentation
    ├── guides/                Step-by-step how-tos
    └── architecture/          Design notes & diagrams
```

## Documentation index

| Doc                                                                       | What it covers                                                  |
|---------------------------------------------------------------------------|------------------------------------------------------------------|
| [Getting Started](docs/guides/01-getting-started.md)                      | Provision an MI300X box → first generated SOP, end-to-end.       |
| [Fine-Tuning Guide](docs/guides/02-fine-tuning.md)                        | The QLoRA recipe: hyperparams, why we picked them, what to watch. |
| [Serving Guide](docs/guides/03-serving.md)                                | vLLM ROCm tuning, FP8 export, benchmarking, troubleshooting.     |
| [API Reference](docs/guides/04-api-reference.md)                          | Every endpoint, every field, every status code.                  |
| [Frontend Guide](docs/guides/05-frontend.md)                              | Running the UI, customizing, adding artifact types.              |
| [Compliance & Limitations](docs/guides/06-compliance-and-limitations.md)  | What this tool is and is **not**. RA professional review required. |
| [Troubleshooting](docs/guides/07-troubleshooting.md)                      | ROCm gotchas, OOMs, vLLM init issues, frontend CORS.             |
| [Architecture Notes](docs/architecture/overview.md)                       | Why these choices, what we'd do with more runway.                |

## Hardware & software requirements

**Minimum** (development & inference):
- 1× AMD Instinct MI300X (192 GB HBM3)
- ROCm 6.2 + driver
- Docker with `/dev/kfd` + `/dev/dri` passthrough
- 200 GB free disk for model weights & cache

**Tested host** (AMD Developer Cloud reference):
- Ubuntu 22.04 LTS
- ROCm 6.2.0
- Linux 5.15+ with amdgpu module
- Python 3.10 (inside container)

**For training**, the same single-MI300X box is enough thanks to QLoRA + 4-bit base weights; you do not need multi-GPU.

## Compliance disclaimer

> **Compliance-Llama is a drafting aid, not a regulatory affairs professional.** Every artifact it produces must be reviewed, edited, and signed off by qualified RA personnel before being entered into a Quality Management System or submitted to a regulator. The model can hallucinate clause numbers, conflate revisions, or omit jurisdiction-specific requirements. See [`docs/guides/06-compliance-and-limitations.md`](docs/guides/06-compliance-and-limitations.md).

## License

Code: **MIT** (see `LICENSE`).
Model weights: subject to the [Llama 3.1 Community License](https://llama.meta.com/llama3_1/license/) for the base model. Fine-tuned LoRA adapters released under the same terms.

---

Built for the AMD Hackathon —  (Fine-Tuning on AMD GPUs).
