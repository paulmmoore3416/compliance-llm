"""Dataset loading & formatting for Compliance-Llama fine-tuning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from datasets import Dataset

from .prompts import Example, format_example, iter_jsonl_examples


def _read_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Training file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_split(jsonl_path: str | Path, tokenizer, max_seq_length: int) -> Dataset:
    """Load a JSONL file and pre-format every example into a single ``text`` column.

    TRL's ``SFTTrainer`` will tokenize this column, optionally with packing.
    """
    raw = _read_jsonl(jsonl_path)
    examples = list(iter_jsonl_examples(raw))

    formatter = _make_formatter(tokenizer)
    formatted = [{"text": formatter(ex)} for ex in examples]

    return Dataset.from_list(formatted)


def _make_formatter(tokenizer) -> Callable[[Example], str]:
    def fmt(ex: Example) -> str:
        return format_example(ex, tokenizer)
    return fmt
