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

from bench.sft import critical_char_spans, label_mask, token_weights


def encode(tok, messages: list[dict], max_len: int, critical_weight: float = 1.0) -> dict | None:
    """Token ids and labels for one example, or None if it would be truncated.

    With `critical_weight` != 1 (ADR-0024), also per-token loss weights: the tokens of each
    finding's concept and assertion count `critical_weight` times. If re-tokenising the
    rendered text does not reproduce the template's ids, the example keeps weight 1 and is
    flagged, so a tokenizer quirk can never silently mis-weight a sequence.
    """
    prompt = tok.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=True)
    full = tok.apply_chat_template(messages, tokenize=True)
    if hasattr(prompt, "input_ids"):  # transformers 5 may return a BatchEncoding
        prompt, full = prompt["input_ids"], full["input_ids"]
    if len(full) > max_len:
        return None
    ex: dict = {"input_ids": list(full), "labels": label_mask(prompt, full)}
    if critical_weight != 1.0:
        text = tok.apply_chat_template(messages, tokenize=False)
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        answer = messages[-1]["content"]
        shift = text.rfind(answer)
        if list(enc["input_ids"]) != list(full) or shift < 0:
            ex["weights"], ex["misaligned"] = [1.0] * len(full), True
        else:
            spans = critical_char_spans(answer)
            ex["weights"] = token_weights(enc["offset_mapping"], spans, critical_weight, shift)
    return ex


def collate(tok, batch: list[dict]) -> dict:
    """Pad ids, labels (-100) and weights (0) to the longest example in the batch."""
    import torch  # pyright: ignore[reportMissingImports]

    n = max(len(b["input_ids"]) for b in batch)
    pad = tok.pad_token_id

    def padded(key: str, value: float | int) -> list:
        return [b[key] + [value] * (n - len(b[key])) for b in batch]

    out = {
        "input_ids": torch.tensor(padded("input_ids", pad)),
        "attention_mask": torch.tensor(
            [[1] * len(b["input_ids"]) + [0] * (n - len(b["input_ids"])) for b in batch]
        ),
        "labels": torch.tensor(padded("labels", -100)),
    }
    if "weights" in batch[0]:
        out["weights"] = torch.tensor(padded("weights", 0.0), dtype=torch.float32)
    return out


def weighted_loss(logits, labels, weights):
    """Weighted mean of next-token cross-entropy over answer tokens:
    sum_t w_t * CE_t / sum_t w_t, with prompt and padding tokens excluded."""
    import torch.nn.functional as F  # pyright: ignore[reportMissingImports]

    logits, labels, weights = logits[:, :-1].float(), labels[:, 1:], weights[:, 1:]
    ce = F.cross_entropy(
        logits.reshape(-1, logits.size(-1)), labels.reshape(-1), ignore_index=-100, reduction="none"
    ).view_as(labels)
    w = weights * (labels != -100)
    return (ce * w).sum() / w.sum().clamp_min(1e-8)


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

    t = cfg["train"]
    critical_weight = float(t.get("critical_weight", 1.0))
    text = Path(cfg["train_file"]).read_text(encoding="utf-8")
    rows = [json.loads(line) for line in text.splitlines() if line]
    encoded = [encode(tok, r["messages"], cfg["max_seq_len"], critical_weight) for r in rows]
    data = [e for e in encoded if e is not None]
    skipped = len(encoded) - len(data)
    misaligned = sum(1 for e in data if e.pop("misaligned", False))
    print(f"{len(data)} examples ({skipped} skipped as longer than {cfg['max_seq_len']} tokens)")
    if critical_weight != 1.0:
        print(f"critical-token weight {critical_weight}; {misaligned} examples kept at weight 1")

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

    class WeightedTrainer(Trainer):
        """Trainer with the safety-weighted loss (ADR-0024); used only when weights differ."""

        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            weights = inputs.pop("weights")
            outputs = model(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"])
            loss = weighted_loss(outputs.logits, inputs["labels"], weights)
            return (loss, outputs) if return_outputs else loss

    weighted = critical_weight != 1.0
    trainer_cls = WeightedTrainer if weighted else Trainer
    collator = (
        (lambda batch: collate(tok, batch))
        if weighted
        else DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100)
    )
    # transformers 5 dropped `warmup_ratio`; its `warmup_steps` takes a float ratio instead
    import inspect

    warmup = (
        {"warmup_ratio": t["warmup_ratio"]}
        if "warmup_ratio" in inspect.signature(TrainingArguments.__init__).parameters
        else {"warmup_steps": float(t["warmup_ratio"])}
    )
    fp16 = torch.cuda.is_available()
    trainer = trainer_cls(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.out / "checkpoints"),
            num_train_epochs=t["epochs"],
            max_steps=args.max_steps,
            learning_rate=t["learning_rate"],
            per_device_train_batch_size=t["batch_size"],
            gradient_accumulation_steps=t["grad_accum"],
            **warmup,
            lr_scheduler_type=t["lr_scheduler"],
            logging_steps=t["logging_steps"],
            gradient_checkpointing=t["gradient_checkpointing"],
            fp16=fp16,
            save_strategy="no",
            report_to=[],
            seed=cfg["seed"],
            remove_unused_columns=False,  # keep `weights` for the weighted loss
        ),
        train_dataset=data,  # pyright: ignore[reportArgumentType] (a list works as a map-style dataset)
        data_collator=collator,
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
        "critical_weight": critical_weight,
        "weight_misaligned": misaligned,
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
