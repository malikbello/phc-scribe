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
# Several conversations at once -> one (text, prompt tokens) per conversation, in order.
BatchGenerate = Callable[[list[list[dict[str, str]]]], list[tuple[str, int]]]


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


def run_batched(
    items: Sequence[BenchItem],
    generate_batch: BatchGenerate,
    system: str,
    mode: Mode,
    batch_size: int,
    lenient: bool = False,
) -> list[Prediction]:
    """`run` with several items per generate call (committee labelling, ADR-0025).

    Items keep their input order in the output. A failed batch marks each of its items
    as an error, as a failed single generation does in `run`. Latency is the batch's
    wall time divided by its size.
    """
    preds: list[Prediction] = []
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        t0 = time.perf_counter()
        try:
            outs = generate_batch([build_messages(i.transcript, mode) for i in chunk])
            failure = None
        except Exception as e:
            outs, failure = [], f"{type(e).__name__}: {e}"
            print(f"  {system}: batch failed at {chunk[0].item_id}: {failure}", file=sys.stderr)
        per_item = round((time.perf_counter() - t0) * 1000 / len(chunk), 1)
        for k, item in enumerate(chunk):
            if failure is None:
                raw, prompt_tokens = outs[k]
                record, error = parse_record(raw, lenient)
            else:
                raw, prompt_tokens, record, error = None, None, None, failure
            preds.append(
                Prediction(
                    item_id=item.item_id,
                    system=system,
                    raw_output=raw,
                    record=record,
                    error=error,
                    latency_ms=per_item,
                    prompt_tokens=prompt_tokens,
                )
            )
        ok = sum(p.record is not None for p in preds)
        print(
            f"  {system}: {len(preds)}/{len(items)} done, {ok} schema-valid,"
            f" {per_item / 1000:.1f} s/item",
            file=sys.stderr,
            flush=True,
        )
    return preds


def hf_generator(
    model_id: str,
    *,
    load_in_4bit: bool = False,
    max_new_tokens: int = 768,
    revision: str | None = None,
    adapter: str | None = None,
    adapter_scale: float = 1.0,
    constrained: bool = True,
    repetition_penalty: float = 1.0,
) -> tuple[Generate, BatchGenerate]:
    """Greedy generation with transformers; schema-constrained with xgrammar unless told not to.

    Returns a one-conversation generator (every evaluated system uses it) and a batched one
    (left-padded, one grammar matcher per row; committee labelling only, ADR-0025).
    `repetition_penalty` 1.12 is what the N-ATLaS model card's usage example sets; 1.0 is off.
    """
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
        if adapter_scale != 1.0:
            # WiSE-FT-style interpolation (ADR-0024): W + s * dW, by scaling each LoRA layer.
            for module in model.modules():
                scaling = getattr(module, "scaling", None)
                if isinstance(scaling, dict):
                    module.scaling = {k: v * adapter_scale for k, v in scaling.items()}
    model.eval()
    # Pre-quantised 4-bit checkpoints often compute in bfloat16, which a T4 (compute
    # capability 7.5) only emulates, about 10x slower. Compute in float16 there instead.
    if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] < 8:
        for module in model.modules():
            if getattr(module, "compute_dtype", None) == torch.bfloat16:
                module.compute_dtype = torch.float16

    config = AutoConfig.from_pretrained(model_id, revision=revision)
    # Multimodal configs (Gemma 3) keep the vocabulary on the text config.
    vocab_size = getattr(config, "vocab_size", None) or config.get_text_config().vocab_size
    info = xgr.TokenizerInfo.from_huggingface(tok, vocab_size=vocab_size)
    compiler = xgr.GrammarCompiler(info)
    grammar = compiler.compile_json_schema(json.dumps(decoding_schema()))
    eos = [
        t
        for t in {tok.eos_token_id, tok.convert_tokens_to_ids("<|eot_id|>")}
        if isinstance(t, int) and t >= 0
    ]

    # Qwen3 would otherwise open a thinking block; the grammar forbids it anyway.
    template_kwargs = {"enable_thinking": False} if "qwen3" in model_id.lower() else {}

    def generate(messages: list[dict[str, str]]) -> tuple[str, int]:
        # return_dict=True gives the same shape on transformers 4.x and 5.x.
        enc = tok.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            **template_kwargs,
        ).to(model.device)
        ids, mask = enc["input_ids"], enc["attention_mask"]
        processors = [xgr.contrib.hf.LogitsProcessor(grammar)] if constrained else []  # fresh state
        with torch.no_grad():
            out = model.generate(
                ids,
                attention_mask=mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=repetition_penalty,
                logits_processor=LogitsProcessorList(processors),
                eos_token_id=eos,
                pad_token_id=tok.eos_token_id,
            )
        text = tok.decode(out[0, ids.shape[1] :], skip_special_tokens=True)
        return text.strip(), int(ids.shape[1])

    def generate_batch(batch: list[list[dict[str, str]]]) -> list[tuple[str, int]]:
        if len(batch) == 1:
            return [generate(batch[0])]
        tok.padding_side = "left"  # generation continues from the right edge
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        enc = tok.apply_chat_template(
            batch,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            padding=True,
            **template_kwargs,
        ).to(model.device)
        ids, mask = enc["input_ids"], enc["attention_mask"]
        processors = [xgr.contrib.hf.LogitsProcessor(grammar)] if constrained else []
        with torch.no_grad():
            out = model.generate(
                ids,
                attention_mask=mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=repetition_penalty,
                logits_processor=LogitsProcessorList(processors),
                eos_token_id=eos,
                pad_token_id=tok.pad_token_id,
            )
        lengths = mask.sum(dim=1).tolist()
        texts = tok.batch_decode(out[:, ids.shape[1] :], skip_special_tokens=True)
        return [(t.strip(), int(n)) for t, n in zip(texts, lengths, strict=True)]

    return generate, generate_batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision")
    parser.add_argument("--adapter", help="LoRA adapter directory to apply (fine-tuned rungs)")
    parser.add_argument(
        "--adapter-scale", type=float, default=1.0, help="s in W + s*dW (ADR-0024 scaled merge)"
    )
    parser.add_argument("--system", help="system name in reports (default: derived from model)")
    parser.add_argument("--mode", choices=["zeroshot", "fewshot", "finetuned"], default="fewshot")
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=768)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="items per generate call; >1 only for committee labelling (ADR-0025)",
    )
    parser.add_argument(
        "--unconstrained",
        action="store_true",
        help="free generation, then parse the first JSON object (supplementary comparator only)",
    )
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=1.0,
        help="1.12 = the N-ATLaS model card's setting; 1.0 = off",
    )
    args = parser.parse_args()

    items = list(read_jsonl(args.items, BenchItem))
    if args.limit:
        items = items[: args.limit]
    suffix = "-unconstrained" if args.unconstrained else ""
    if args.repetition_penalty != 1.0:
        suffix += f"-rp{args.repetition_penalty:g}"
    system = (
        args.system or f"{args.model.split('/')[-1].lower()}-{args.mode}{suffix}-{PROMPT_VERSION}"
    )
    generate, generate_batch = hf_generator(
        args.model,
        load_in_4bit=args.load_in_4bit,
        max_new_tokens=args.max_new_tokens,
        revision=args.revision,
        adapter=args.adapter,
        adapter_scale=args.adapter_scale,
        constrained=not args.unconstrained,
        repetition_penalty=args.repetition_penalty,
    )
    if args.batch_size > 1:
        # Written as it goes, so a job stopped at its time limit keeps what it has done.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("", encoding="utf-8")
        preds = []
        step = args.batch_size * 8
        for start in range(0, len(items), step):
            chunk = run_batched(
                items[start : start + step],
                generate_batch,
                system,
                args.mode,
                args.batch_size,
                lenient=args.unconstrained,
            )
            with args.out.open("a", encoding="utf-8") as f:
                for row in chunk:
                    f.write(
                        json.dumps(
                            row.model_dump(mode="json", exclude_none=True), ensure_ascii=False
                        )
                        + "\n"
                    )
            preds += chunk
    else:
        preds = run(items, generate, system, args.mode, lenient=args.unconstrained)
        write_jsonl(args.out, preds)
    ok = sum(p.record is not None for p in preds)
    print(f"wrote {len(preds)} predictions ({ok} schema-valid) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
