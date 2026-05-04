"""Compliance-Llama: QLoRA fine-tuning entry point for MI300X.

Usage:
    python -m training.src.train --config training/configs/qlora_70b.yaml

The script is engineered for a single MI300X (192 GB HBM3). On smaller cards,
override ``per_device_train_batch_size`` and ``gradient_accumulation_steps``.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import torch
import yaml
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed,
)
from trl import SFTConfig, SFTTrainer

from .data import load_split

logger = logging.getLogger("compliance-llama.train")


def _load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_quant_config(cfg: dict) -> BitsAndBytesConfig:
    q = cfg["quantization"]
    return BitsAndBytesConfig(
        load_in_4bit=q["load_in_4bit"],
        bnb_4bit_quant_type=q["bnb_4bit_quant_type"],
        bnb_4bit_compute_dtype=getattr(torch, q["bnb_4bit_compute_dtype"]),
        bnb_4bit_use_double_quant=q["bnb_4bit_use_double_quant"],
    )


def _build_lora_config(cfg: dict) -> LoraConfig:
    l = cfg["lora"]
    return LoraConfig(
        r=l["r"],
        lora_alpha=l["lora_alpha"],
        lora_dropout=l["lora_dropout"],
        bias=l["bias"],
        task_type=l["task_type"],
        target_modules=l["target_modules"],
    )


def _build_sft_config(cfg: dict) -> SFTConfig:
    t = cfg["training"]
    return SFTConfig(
        output_dir=t["output_dir"],
        num_train_epochs=t["num_train_epochs"],
        per_device_train_batch_size=t["per_device_train_batch_size"],
        per_device_eval_batch_size=t["per_device_eval_batch_size"],
        gradient_accumulation_steps=t["gradient_accumulation_steps"],
        gradient_checkpointing=t["gradient_checkpointing"],
        gradient_checkpointing_kwargs=cfg["hardware"]["gradient_checkpointing_kwargs"],
        learning_rate=t["learning_rate"],
        lr_scheduler_type=t["lr_scheduler_type"],
        warmup_ratio=t["warmup_ratio"],
        weight_decay=t["weight_decay"],
        max_grad_norm=t["max_grad_norm"],
        bf16=t["bf16"],
        fp16=t["fp16"],
        optim=t["optim"],
        logging_steps=t["logging_steps"],
        save_strategy=t["save_strategy"],
        save_steps=t["save_steps"],
        save_total_limit=t["save_total_limit"],
        eval_strategy=t["eval_strategy"],
        eval_steps=t["eval_steps"],
        report_to=t["report_to"],
        seed=t["seed"],
        dataloader_num_workers=t["dataloader_num_workers"],
        remove_unused_columns=t["remove_unused_columns"],
        group_by_length=t["group_by_length"],
        ddp_find_unused_parameters=t["ddp_find_unused_parameters"],
        max_seq_length=cfg["data"]["max_seq_length"],
        packing=cfg["data"]["packing"],
        dataset_text_field="text",
    )


def main(config_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    cfg = _load_yaml(config_path)
    set_seed(cfg["training"]["seed"])

    if not torch.cuda.is_available():
        raise RuntimeError(
            "torch.cuda.is_available() is False — on ROCm this means HIP is not "
            "wired up. Verify HSA_OVERRIDE_GFX_VERSION=9.4.0 and that "
            "/dev/kfd + /dev/dri are passed into the container."
        )
    logger.info("Detected GPU: %s", torch.cuda.get_device_name(0))
    logger.info("Total HBM: %.1f GB", torch.cuda.get_device_properties(0).total_memory / 1024**3)

    base_model_id = cfg["model"]["base_model_id"]
    logger.info("Loading tokenizer for %s", base_model_id)
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_id,
        trust_remote_code=cfg["model"]["trust_remote_code"],
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    logger.info("Loading 4-bit base model (this is the heavy step — ~3-5 minutes on MI300X)")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=_build_quant_config(cfg),
        device_map=cfg["hardware"]["device_map"],
        torch_dtype=getattr(torch, cfg["model"]["torch_dtype"]),
        attn_implementation=cfg["model"]["attn_implementation"],
        trust_remote_code=cfg["model"]["trust_remote_code"],
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=cfg["training"]["gradient_checkpointing"]
    )
    lora_config = _build_lora_config(cfg)
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    logger.info("Loading datasets")
    train_ds = load_split(cfg["data"]["train_file"], tokenizer, cfg["data"]["max_seq_length"])
    eval_ds = load_split(cfg["data"]["eval_file"], tokenizer, cfg["data"]["max_seq_length"])
    logger.info("train=%d eval=%d", len(train_ds), len(eval_ds))

    sft_config = _build_sft_config(cfg)
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
        peft_config=lora_config,
    )

    logger.info("Beginning fine-tune")
    trainer.train()

    final_dir = os.path.join(cfg["training"]["output_dir"], "final")
    logger.info("Saving LoRA adapters → %s", final_dir)
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config")
    args = parser.parse_args()
    main(args.config)
