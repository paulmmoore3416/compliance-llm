"""Merge LoRA adapters back into the base model and (optionally) re-quantize
to FP8 for vLLM serving on MI300X.

Why FP8? The MI300X has native FP8 (E4M3 / E5M2) tensor cores. Serving in FP8
roughly halves the VRAM footprint vs BF16 and pushes throughput considerably
without measurable quality loss for instruct-tuned 70B models.

The FP8 conversion uses AMD's Quark toolchain. For hackathon timelines we keep
the BF16 export as a strict fallback so judges can still load the model even
if Quark isn't available.

Usage:
    python -m training.src.merge_and_export \\
        --base meta-llama/Llama-3.1-70B-Instruct \\
        --adapter outputs/compliance-llama-70b-qlora/final \\
        --output models/compliance-llama-70b-merged \\
        --fp8                          # optional: also produce FP8 export
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger("compliance-llama.export")


def merge_adapters(base_model_id: str, adapter_dir: str, output_dir: str) -> str:
    logger.info("Loading base model in BF16 (no quantization for merge)")
    base = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        low_cpu_mem_usage=True,
    )

    logger.info("Attaching LoRA adapters from %s", adapter_dir)
    model = PeftModel.from_pretrained(base, adapter_dir)

    logger.info("Merging adapters into base weights")
    model = model.merge_and_unload()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logger.info("Writing merged BF16 model → %s", out)
    model.save_pretrained(out, safe_serialization=True)

    tok = AutoTokenizer.from_pretrained(adapter_dir)
    tok.save_pretrained(out)
    return str(out)


def export_fp8(merged_dir: str, fp8_output_dir: str) -> None:
    """Quantize the merged BF16 model to FP8 using AMD Quark.

    Quark is shipped via the `amd-quark` package on the ROCm developer site.
    If it's not installed we copy the BF16 weights over and warn — vLLM can
    still serve them, just with higher VRAM use.
    """
    try:
        from quark.torch import ModelQuantizer  # type: ignore
        from quark.torch.quantization.config.config import (  # type: ignore
            Config, QuantizationConfig, FP8E4M3PerTensorSpec,
        )
    except ImportError:
        logger.warning(
            "amd-quark is not installed. Skipping FP8 quantization and copying "
            "BF16 weights to %s instead. Install with: pip install amd-quark",
            fp8_output_dir,
        )
        if Path(fp8_output_dir).exists():
            shutil.rmtree(fp8_output_dir)
        shutil.copytree(merged_dir, fp8_output_dir)
        return

    fp8_spec = FP8E4M3PerTensorSpec(observer_method="min_max").to_quantization_spec()
    quant_cfg = Config(
        global_quant_config=QuantizationConfig(
            input_tensors=fp8_spec, weight=fp8_spec
        )
    )

    logger.info("Loading merged BF16 model for FP8 quantization")
    model = AutoModelForCausalLM.from_pretrained(
        merged_dir, torch_dtype=torch.bfloat16, device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(merged_dir)

    quantizer = ModelQuantizer(quant_cfg)
    model = quantizer.quantize_model(model, dataloader=None)

    Path(fp8_output_dir).mkdir(parents=True, exist_ok=True)
    quantizer.freeze(model)
    model.save_pretrained(fp8_output_dir)
    tokenizer.save_pretrained(fp8_output_dir)
    logger.info("FP8 model written → %s", fp8_output_dir)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Base model id or path")
    parser.add_argument("--adapter", required=True, help="LoRA adapter directory")
    parser.add_argument("--output", required=True, help="Output dir for merged BF16 model")
    parser.add_argument("--fp8", action="store_true", help="Also produce an FP8 export")
    parser.add_argument("--fp8-output", default=None, help="FP8 output dir (default: <output>-fp8)")
    args = parser.parse_args()

    merged_dir = merge_adapters(args.base, args.adapter, args.output)
    if args.fp8:
        fp8_dir = args.fp8_output or f"{args.output}-fp8"
        export_fp8(merged_dir, fp8_dir)


if __name__ == "__main__":
    main()
