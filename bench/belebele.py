"""G2 guardrail: Belebele `yor_Latn` accuracy (docs/eval-plan.md §6, finetuning-review §2.6).

    python -m bench.belebele --model NCAIR1/N-ATLaS --out preds/belebele.natlas.jsonl

Zero-shot multiple choice scored by next-token likelihood: the prompt shows the passage,
the question and options A-D, ends with "Answer:", and the prediction is the option
letter with the highest log-probability. One forward pass per question, no generation.
Per-item correctness is saved so base and fine-tuned models can be compared paired.
The same prompt and scoring are used for every model, before and after fine-tuning.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

DATASET = "facebook/belebele"
REVISION = "7899cdfa4e1e0d733fd77c848e2c273cb1d32be2"  # chosen 1 Oct 2026
CONFIG = "yor_Latn"
LETTERS = ("A", "B", "C", "D")


def build_prompt(row: Mapping[str, object]) -> str:
    options = "\n".join(f"{letter}. {row[f'mc_answer{i}']}" for i, letter in enumerate(LETTERS, 1))
    return (
        f"Passage: {row['flores_passage']}\n"
        f"Question: {row['question']}\n"
        f"{options}\n"
        "Answer with the letter of the correct option.\n"
        "Answer:"
    )


def gold_letter(row: Mapping[str, object]) -> str:
    return LETTERS[int(str(row["correct_answer_num"])) - 1]


def score(
    rows: Sequence[Mapping[str, object]], letter_logprobs: Callable[[str], Sequence[float]]
) -> dict:
    """Accuracy over rows; `letter_logprobs(prompt)` returns one score per letter A-D."""
    items = []
    for row in rows:
        scores = list(letter_logprobs(build_prompt(row)))
        pred = LETTERS[max(range(len(LETTERS)), key=scores.__getitem__)]
        items.append(
            {
                "id": f"{row['link']}#{row['question_number']}",
                "pred": pred,
                "gold": gold_letter(row),
            }
        )
    correct = sum(i["pred"] == i["gold"] for i in items)
    return {
        "n_items": len(items),
        "accuracy": correct / len(items) if items else None,
        "items": items,
    }


def hf_letter_scorer(model_id: str, revision: str | None = None, adapter: str | None = None):
    import torch  # pyright: ignore[reportMissingImports]
    from transformers import (  # pyright: ignore[reportMissingImports]
        AutoModelForCausalLM,
        AutoTokenizer,
    )

    tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, dtype=torch.float16, device_map="auto"
    )
    if adapter:
        from peft import PeftModel  # pyright: ignore[reportMissingImports]

        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    # " A" style tokens: the letter as it would follow "Answer:".
    letter_ids = [tok.encode(f" {letter}", add_special_tokens=False)[-1] for letter in LETTERS]

    def letter_logprobs(prompt: str) -> list[float]:
        enc = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            logits = model(**enc).logits[0, -1]
        logp = torch.log_softmax(logits.float(), dim=-1)
        return [float(logp[i]) for i in letter_ids]

    return letter_logprobs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision")
    parser.add_argument("--adapter")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    from datasets import load_dataset  # pyright: ignore[reportMissingImports]

    ds = load_dataset(DATASET, CONFIG, split="test", revision=REVISION)
    rows: list[Mapping[str, object]] = [dict(r) for r in ds][: args.limit or None]  # type: ignore[arg-type]
    result = score(rows, hf_letter_scorer(args.model, args.revision, args.adapter))
    result.update(
        {
            "dataset": DATASET,
            "config": CONFIG,
            "revision": REVISION,
            "model": args.model,
            "adapter": args.adapter,
        }
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result) + "\n")
    print(
        f"belebele {CONFIG}: accuracy {result['accuracy']:.4f}"
        f" on {result['n_items']} items -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
