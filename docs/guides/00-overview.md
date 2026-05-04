# Documentation Overview

This is the index for everything in the [`docs/`](.) tree. Skim this first.

---

## If you're a judge / first-time visitor

1. Read the [project README](../../README.md) — 5-min overview, architecture diagram, quick start.
2. Read [Compliance & Limitations](guides/06-compliance-and-limitations.md) — the most important doc in this repo. It frames what the model is and is not.
3. Skim [Architecture Overview](architecture/overview.md) — design rationale.

## If you're cloning the repo to run it

1. [Getting Started](guides/01-getting-started.md) — top to bottom, end-to-end.
2. [Implementation Guide](guides/08-implementation.md) — setting up the system in an enterprise environment.
3. [Integration Guide](guides/09-integration.md) — connecting the AI to your Quality Management System (QMS).
4. Pin [Troubleshooting](guides/07-troubleshooting.md) — bookmark before you start.

## If you're hacking on the model

1. [Fine-Tuning Guide](guides/02-fine-tuning.md) — recipe, hyperparams, how to diagnose.
2. [Serving Guide](guides/03-serving.md) — vLLM, FP8, benchmarks.
3. [Architecture Overview](architecture/overview.md) — the bigger why.

## If you're hacking on the API or UI

1. [API Reference](guides/04-api-reference.md) — every endpoint, every field.
2. [Frontend Guide](guides/05-frontend.md) — running, customizing, extending.

---

## Doc map

| File                                                                   | Audience                                  |
|------------------------------------------------------------------------|-------------------------------------------|
| [01-getting-started.md](guides/01-getting-started.md)                  | Anyone running the system end-to-end.     |
| [02-fine-tuning.md](guides/02-fine-tuning.md)                          | ML engineers tweaking the model.          |
| [03-serving.md](guides/03-serving.md)                                  | Engineers running vLLM, benchmarking.     |
| [04-api-reference.md](guides/04-api-reference.md)                      | Anyone integrating the API.               |
| [05-frontend.md](guides/05-frontend.md)                                | Frontend devs.                            |
| [06-compliance-and-limitations.md](guides/06-compliance-and-limitations.md) | RA professionals, legal, judges.    |
| [07-troubleshooting.md](guides/07-troubleshooting.md)                  | When something breaks. (It will.)         |
| [08-implementation.md](guides/08-implementation.md)                    | IT and RA professionals setting up.       |
| [09-integration.md](guides/09-integration.md)                          | Engineers integrating with a QMS.         |
| [architecture/overview.md](architecture/overview.md)                   | Designers, architects, "why?" questions.  |
