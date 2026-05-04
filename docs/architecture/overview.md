# Architecture Overview

A condensed map of why this system is shaped the way it is. Useful for judges, future contributors, and the inevitable "why didn't you just…" follow-up questions.

---

## Design principles

1. **One GPU, one model, one service.** A single MI300X is enough to fine-tune *and* serve a 70B model. We exploit that to keep the deployment simple.
2. **Open-source path end-to-end.** No proprietary inference engine, no managed-cloud-only steps. The whole thing runs on commodity ROCm + open-source PyTorch / vLLM.
3. **Fine-tuning, not RAG.** Regulatory output has a lot of structural rules ("every requirement has a clause cite", "use this section order"). RAG plus a generic model can fake this; a fine-tune internalizes it. We bet on the latter.
4. **AMD-native, not AMD-tolerated.** FP8 quantization, gfx942-targeted flash-attention, native ROCm bnb fork. Anything that says "CUDA-only" is replaced or removed.
5. **Boring software.** FastAPI + React + httpx + ReportLab. No state library, no GraphQL, no microservices for their own sake. Hackathon-time is best spent on the model.

---

## Stack rationale

| Choice                                    | Why                                                                                                |
|-------------------------------------------|-----------------------------------------------------------------------------------------------------|
| Llama 3.1 70B Instruct                    | Best instruction-following base in the open ecosystem; 70B fits MI300X without sharding.            |
| QLoRA via PEFT                            | Lets us train on a single GPU. NF4 base + BF16 adapters is the standard recipe.                    |
| `bitsandbytes` ROCm fork                  | The only stable path to 4-bit quant on AMD as of writing.                                           |
| Llama 3.1 chat template (HF tokenizer)    | Don't reinvent ChatML; the tokenizer ships the right template.                                     |
| `target_modules`: q,k,v,o,gate,up,down    | All seven projections per block. MLP-only LoRA loses tone; attention-only LoRA loses recall.       |
| `r=64`, `lr=2e-5`, 3 epochs               | Higher rank than typical for richer structure-learning; lower LR to preserve general behavior.     |
| TRL `SFTTrainer` with packing             | Matches the data better than the bare `Trainer`; packing nearly doubles tokens/sec on small data.   |
| AMD Quark for FP8 export                  | Native MI300X FP8 path; halves VRAM and ~doubles throughput.                                       |
| vLLM ROCm                                 | Best open-source serving engine. Native FP8 and prefix caching support.                            |
| FastAPI gateway                           | Pydantic validation + SSE in 200 lines. We don't need anything heavier.                             |
| React + Tailwind                          | Same — minimal surface, fast iteration, easy demo.                                                  |
| Synthetic dataset (combinatorial)         | Reproducible, no licensing risk, expandable. Real RA docs would be better but legally fraught.     |

---

## Data flow

### Inference

```
User input ── DeviceContextPanel ─┐
                                  │
                                  ▼
                       buildRequest() in App.tsx
                                  │
                                  ▼ POST /v1/generate/stream
                              FastAPI gateway
                                  │
                       prompts.build_messages(...)
                                  │
                                  ▼ POST /v1/chat/completions stream=true
                                vLLM
                                  │
                                  ▼  HIP / MI300X
                       compliance-llama-70b (FP8)
                                  │
                                  ▼ token deltas
                          SSE event: token / done
                                  │
                                  ▼ ReadableStream parser
                          OutputPanel render (react-markdown)
```

### Fine-tuning

```
build_dataset.py → train.jsonl + eval.jsonl (JSONL)
            │
            ▼
   data.load_split() → datasets.Dataset (text-formatted via chat template)
            │
            ▼
       SFTTrainer (PEFT + LoRA on 4-bit base)
            │
            ▼
  outputs/.../final/  (LoRA adapters, ~400 MB)
            │
            ▼
   merge_and_export.py
            │
            ├── BF16 merged model  (~140 GB, fallback)
            └── FP8 merged model   (~70 GB, primary serving target)
```

---

## Trade-offs we accepted

- **Synthetic-only training data.** Real corpus would be richer but legal review takes longer than a hackathon.
- **Single MI300X.** Multi-GPU TP would give more throughput but adds complexity and is unnecessary for the demo.
- **No retrieval layer.** A clause-citation retrieval index over the actual standard texts would catch a lot of hallucinations. We considered it; punted to a v2 because (a) ISO standard texts are paywalled and (b) the fine-tune already gets 80% there. We'd add it for production.
- **No domain-aware decoder.** Constrained generation (e.g. forcing the model to only emit valid clause numbers from a registry) would eliminate hallucination but adds engine complexity. Logit processors in vLLM can do this; not in scope here.
- **No human-in-the-loop refinement.** The frontend doesn't yet support edit-and-regenerate. PDF export is one-shot.

---

## What we'd do with another month

1. **Real-clause retrieval guardrail.** Index the actual ISO/CFR texts (licensed copies) and use vLLM's logit processor API to constrain `§X.Y.Z` citations to the registered set. Eliminates the most common failure mode.
2. **Larger, jurisdiction-tagged dataset.** EU MDR + UKCA + Health Canada + PMDA + NMPA tracks, each as its own LoRA composed at inference time.
3. **Verified RA-professional review feedback loop.** Capture human edits as preference pairs and run a DPO step over the LoRA adapters.
4. **Document-version tracking.** Pin generated SOPs to specific revisions of the standards and warn when those change.
5. **Audit-trail signing.** Embed a signed manifest into the PDF export — model hash + prompt + timestamp — so a regulator can confirm what was generated and by whom.
6. **Multi-GPU TP serving for fleet deployment.** Trivial knob (`TP_SIZE=2/4/8`) but worth proper benchmarking.
7. **Eval harness.** A formal rubric ("does every requirement have a clause cite?", "does the SOP include all 8 standard sections?", "are the cited clauses real?") run on every checkpoint.
