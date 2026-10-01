"""Model rungs 2-5 of the baseline ladder: a Hugging Face causal LM with the same
prompt and the same JSON-schema-constrained decoding for every model.

    python -m bench.runners.llm --model NCAIR1/N-ATLaS --mode fewshot \
        --items data/bench/g.20261002.jsonl --out preds/natlas-fewshot.g.jsonl [--load-in-4bit]

Constrained decoding uses xgrammar's Hugging Face logits processor with the published
decoding schema (phc_scribe.encounter.decoding_schema), so every output parses as JSON
of the right shape. Scoring (bench.harness score) then re-validates and grounds the
record, exactly as for the keyword baseline.

Heavy imports (torch, transformers, xgrammar) happen inside functions so the rest of
the package, and CI, never need them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from bench.items import BenchItem, Prediction, read_jsonl, write_jsonl
from bench.prompts import PROMPT_VERSION, Mode, build_messages
from phc_scribe.encounter import Encounter, decoding_schema

Generate = Callable[[list[dict[str, str]]], tuple[str, int]]  # messages -> (text, prompt tokens)


def extract_json(text: str) -> str:
    """The first complete top-level JSON object in free text (code fences and prose ignored).

    Used only for unconstrained generation (the supplementary comparator, proposal B in
    docs/research/finetuning-review.md); constrained output is parsed as is.
    """
    start = text.find("{")
    if start < 0:
        return text
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def parse_record(raw: str, lenient: bool = False) -> tuple[Encounter | None, str | None]:
    """Parse model output into a record; schema violations become an error, not a crash."""
    try:
        return Encounter.model_validate(json.loads(extract_json(raw) if lenient else raw)), None
    except Exception as e:  # invalid JSON or schema violation: scored as schema-invalid
        return None, f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"


def run(
    items: Sequence[BenchItem], generate: Generate, system: str, mode: Mode, lenient: bool = False
) -> list[Prediction]:
    preds: list[Prediction] = []
    for n, item in enumerate(items, 1):
        t0 = time.perf_counter()
        try:
            raw, prompt_tokens = generate(build_messages(item.transcript, mode))
            record, error = parse_record(raw, lenient)
        except Exception as e:
            raw, prompt_tokens, record, error = None, None, None, f"{type(e).__name__}: {e}"
            if not any(p.error and p.raw_output is None for p in preds):
                print(f"  {system}: generation failed on {item.item_id}: {error}", file=sys.stderr)
        preds.append(
            Prediction(
                item_id=item.item_id,
                system=system,
                raw_output=raw,
                record=record,
                error=error,
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                prompt_tokens=prompt_tokens,
            )
        )
        if n % 10 == 0 or n == len(items):
            ok = sum(p.record is not None for p in preds)
            print(
                f"  {system}: {n}/{len(items)} done, {ok} schema-valid", file=sys.stderr, flush=True
            )
    return preds


def hf_generator(
    model_id: str,
    *,
    load_in_4bit: bool = False,
    max_new_tokens: int = 768,
    revision: str | None = None,
    adapter: str | None = None,
    constrained: bool = True,
) -> Generate:
    """Greedy generation with transformers; schema-constrained with xgrammar unless told not to."""
    # Optional GPU-side dependencies: not installed in CI.
    import torch  # pyright: ignore[reportMissingImports]
    import xgrammar as xgr  # pyright: ignore[reportMissingImports]
    from transformers import (  # pyright: ignore[reportMissingImports]
        AutoConfig,
        AutoModelForCausalLM,
        AutoTokenizer,
        LogitsProcessorList,
    )

    tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
    kwargs: dict = {"revision": revision, "device_map": "auto"}
    if load_in_4bit:
        from transformers import BitsAndBytesConfig  # pyright: ignore[reportMissingImports]

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16
        )
    else:
        kwargs["dtype"] = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
    if adapter:
        from peft import PeftModel  # pyright: ignore[reportMissingImports]

        model = PeftModel.from_pretrained(model, adapter)
    model.eval()

    vocab_size = AutoConfig.from_pretrained(model_id, revision=revision).vocab_size
    info = xgr.TokenizerInfo.from_huggingface(tok, vocab_size=vocab_size)
    compiler = xgr.GrammarCompiler(info)
    grammar = compiler.compile_json_schema(json.dumps(decoding_schema()))
    eos = [
        t
        for t in {tok.eos_token_id, tok.convert_tokens_to_ids("<|eot_id|>")}
        if isinstance(t, int) and t >= 0
    ]

    def generate(messages: list[dict[str, str]]) -> tuple[str, int]:
        # return_dict=True gives the same shape on transformers 4.x and 5.x.
        enc = tok.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(model.device)
        ids, mask = enc["input_ids"], enc["attention_mask"]
        processors = [xgr.contrib.hf.LogitsProcessor(grammar)] if constrained else []  # fresh state
        with torch.no_grad():
            out = model.generate(
                ids,
                attention_mask=mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                logits_processor=LogitsProcessorList(processors),
                eos_token_id=eos,
                pad_token_id=tok.eos_token_id,
            )
        text = tok.decode(out[0, ids.shape[1] :], skip_special_tokens=True)
        return text.strip(), int(ids.shape[1])

    return generate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision")
    parser.add_argument("--adapter", help="LoRA adapter directory to apply (fine-tuned rungs)")
    parser.add_argument("--system", help="system name in reports (default: derived from model)")
    parser.add_argument("--mode", choices=["zeroshot", "fewshot", "finetuned"], default="fewshot")
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=768)
    parser.add_argument(
        "--unconstrained",
        action="store_true",
        help="free generation, then parse the first JSON object (supplementary comparator only)",
    )
    args = parser.parse_args()

    items = list(read_jsonl(args.items, BenchItem))
    if args.limit:
        items = items[: args.limit]
    suffix = "-unconstrained" if args.unconstrained else ""
    system = (
        args.system or f"{args.model.split('/')[-1].lower()}-{args.mode}{suffix}-{PROMPT_VERSION}"
    )
    generate = hf_generator(
        args.model,
        load_in_4bit=args.load_in_4bit,
        max_new_tokens=args.max_new_tokens,
        revision=args.revision,
        adapter=args.adapter,
        constrained=not args.unconstrained,
    )
    preds = run(items, generate, system, args.mode, lenient=args.unconstrained)
    write_jsonl(args.out, preds)
    ok = sum(p.record is not None for p in preds)
    print(f"wrote {len(preds)} predictions ({ok} schema-valid) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
