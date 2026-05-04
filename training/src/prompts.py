"""Prompt templating for Compliance-Llama.

We use Llama 3.1's native chat template (the one shipped on the tokenizer)
rather than ChatML, but expose a single ``format_example`` entry point so the
training data layer doesn't need to know which template is in play.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


SYSTEM_PROMPT = """You are Compliance-Llama, a regulatory affairs assistant for medical device manufacturers.

You produce audit-ready Standard Operating Procedures (SOPs), Quality Management System (QMS) documents, and clause-level analyses that conform to:
  - ISO 13485:2016 — Medical devices: Quality management systems
  - FDA 21 CFR Part 820 — Quality System Regulation

Hard rules:
  1. Cite the specific clause or section for every requirement you invoke (e.g. "ISO 13485 §7.3.3" or "21 CFR 820.30(c)").
  2. Use the formal SOP structure: Purpose, Scope, Responsibilities, Definitions, Procedure, Records, References, Revision History.
  3. Never invent clause numbers. If you are uncertain, say so explicitly.
  4. Keep language unambiguous, declarative, and traceable. No marketing tone.
  5. Distinguish "shall" (mandatory), "should" (recommended), and "may" (permitted).
"""


@dataclass(frozen=True)
class Example:
    """A single training example.

    ``device_context`` is the user's input describing the device under
    consideration. ``target`` is the expected SOP / clause analysis.
    """

    device_context: str
    target: str
    instruction: str = "Draft the requested compliance artifact for the device described below."


def build_messages(example: Example) -> list[dict]:
    """Return Llama-3.1 chat-format messages for a single example."""
    user_content = f"{example.instruction}\n\n---\nDEVICE CONTEXT\n---\n{example.device_context}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": example.target},
    ]


def format_example(example: Example, tokenizer) -> str:
    """Apply the tokenizer's chat template to produce a training string."""
    messages = build_messages(example)
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )


def build_inference_prompt(device_context: str, instruction: str, tokenizer) -> str:
    """Build a generation-time prompt (assistant turn left open)."""
    user_content = f"{instruction}\n\n---\nDEVICE CONTEXT\n---\n{device_context}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


def iter_jsonl_examples(records: Iterable[dict]) -> Iterable[Example]:
    """Convert raw JSONL rows into Example objects."""
    for row in records:
        yield Example(
            device_context=row["device_context"],
            target=row["target"],
            instruction=row.get("instruction", Example.instruction),
        )
