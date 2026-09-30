"""QLoRA trainer for the fine-tuned rung (docs/architecture.md, section 6).

    python -m bench.train_qlora --config configs/qlora.v0.yaml --out runs/natlas-qlora-v0

Trains only the assistant tokens (bench.sft.label_mask) with the model's own chat
template, saves the LoRA adapter, the config and a metrics JSON. Heavy imports
(torch, transformers, peft) happen inside functions so CI never needs them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import yaml

from bench.sft import label_mask


def encode(tok, messages: list[dict], max_len: int) -> dict | None:
    """Token ids and labels for one example, or None if it would be truncated."""
    prompt = tok.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=True)
    full = tok.apply_chat_template(messages, tokenize=True)
    if hasattr(prompt, "input_ids"):  # transformers 5 may return a BatchEncoding
        prompt, full = prompt["input_ids"], full["input_ids"]
    if len(full) > max_len:
        return None
    return {"input_ids": list(full), "labels": label_mask(prompt, full)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=-1, help="for smoke tests only")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    # Optional GPU-side dependencies: not installed in CI.
    import torch  # pyright: ignore[reportMissingImports]
    from peft import (  # pyright: ignore[reportMissingImports]
        LoraConfig,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
    from transformers import (  # pyright: ignore[reportMissingImports]
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(cfg["seed"])
    tok = AutoTokenizer.from_pretrained(cfg["model"], revision=cfg.get("revision"))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    rows = [json.loads(line) for line in Path(cfg["train_file"]).read_text().splitlines() if line]
    encoded = [encode(tok, r["messages"], cfg["max_seq_len"]) for r in rows]
    data = [e for e in encoded if e is not None]
    skipped = len(encoded) - len(data)
    print(f"{len(data)} examples ({skipped} skipped as longer than {cfg['max_seq_len']} tokens)")

    kwargs: dict = {"revision": cfg.get("revision"), "device_map": "auto"}
    if cfg.get("load_in_4bit"):
        from transformers import BitsAndBytesConfig  # pyright: ignore[reportMissingImports]

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    else:
        kwargs["dtype"] = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(cfg["model"], **kwargs)
    t = cfg["train"]
    if cfg.get("load_in_4bit"):
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=t["gradient_checkpointing"]
        )
    lora = cfg["lora"]
    model = get_peft_model(
        model,
        LoraConfig(
            r=lora["r"],
            lora_alpha=lora["alpha"],
            lora_dropout=lora["dropout"],
            target_modules=lora["target_modules"],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    fp16 = torch.cuda.is_available()
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.out / "checkpoints"),
            num_train_epochs=t["epochs"],
            max_steps=args.max_steps,
            learning_rate=t["learning_rate"],
            per_device_train_batch_size=t["batch_size"],
            gradient_accumulation_steps=t["grad_accum"],
            warmup_ratio=t["warmup_ratio"],
            lr_scheduler_type=t["lr_scheduler"],
            logging_steps=t["logging_steps"],
            gradient_checkpointing=t["gradient_checkpointing"],
            fp16=fp16,
            save_strategy="no",
            report_to=[],
            seed=cfg["seed"],
        ),
        train_dataset=data,  # pyright: ignore[reportArgumentType] (a list works as a map-style dataset)
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
    )
    t0 = time.time()
    result = trainer.train()
    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out / "adapter")
    tok.save_pretrained(args.out / "adapter")
    shutil.copy(args.config, args.out / "config.yaml")
    metrics = {
        "run_name": cfg["run_name"],
        "examples": len(data),
        "skipped_too_long": skipped,
        "train_loss": result.training_loss,
        "steps": result.global_step,
        "minutes": round((time.time() - t0) / 60, 1),
        "log": trainer.state.log_history,
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"adapter -> {args.out / 'adapter'}; loss {result.training_loss:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
