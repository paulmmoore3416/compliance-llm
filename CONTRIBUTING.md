# Contributing

Thanks for considering a contribution. This is a hackathon project; we keep the workflow lightweight.

---

## Local dev loop

The fastest way to iterate without a full ROCm box:

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Stub vLLM at http://localhost:8000 (e.g. with `vllm serve <small-model>`
# or any OpenAI-compatible server). Then:
VLLM_BASE_URL=http://localhost:8000 \
FINE_TUNED_MODEL=<your-test-model> \
uvicorn app.main:app --reload --port 8080
```

### Frontend

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8080 npm run dev
```

### Training (smoke)

You can develop training code on a CUDA box if you swap the `bnb-rocm` install for upstream `bitsandbytes`. Don't commit a CUDA-only path — keep the canonical training Dockerfile pinned to ROCm.

---

## Style

- **Python:** ruff defaults; no linter shipped in the repo, but keep imports sorted and lines ≤ 100 chars.
- **TypeScript:** strict mode is on. No `any`. Components in PascalCase, hooks in camelCase, files match.
- **No comments unless they explain WHY.** Code that needs a comment to be readable should be rewritten first.

---

## Adding a new artifact type

Three coordinated edits — see [Frontend Guide → Customizing](docs/guides/05-frontend.md#customizing).

If the new artifact requires the model to be trained on new examples (almost always), also add a builder to [`data/synthetic/build_dataset.py`](data/synthetic/build_dataset.py) and re-run training.

---

## Pull requests

- One feature per PR.
- Include a quick "tested with…" note: which command you ran, what you saw.
- If you touched training, attach the `train_loss` / `eval_loss` curves from the run.
- Update docs in the same PR if the user-facing behavior changed.
