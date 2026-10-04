"""The shipped runtime as a benchmark rung: a GGUF model behind llama.cpp's server (eval plan
§6a, audit C3).

    python -m bench.runners.llamacpp --url http://127.0.0.1:8080 --system natlas-ft-q4 \
        --mode fewshot --items <items.jsonl> --out <pred.jsonl>

Same prompt (`bench.prompts.build_messages`), same JSON schema as the decoding constraint
(`decoding_schema`), greedy decoding, and the repetition penalty applied over the whole
context (`repeat_last_n` = the server context, 8192), matching Hugging Face's semantics
(eval plan §6a). Output rows are the same `Prediction` records as `bench.runners.llm`, so
`bench.harness score` reads them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench.items import BenchItem, read_jsonl, write_jsonl
from bench.runners.llm import Generate, run
from phc_scribe.encounter import decoding_schema

# The server context (llama-server -c). The chat endpoint rejects -1, so the window is the
# whole context explicitly: the penalty covers every token, as Hugging Face's does.
REPEAT_WINDOW = 8192


def request_body(
    messages: list[dict[str, str]], repetition_penalty: float, max_tokens: int
) -> dict:
    """The /v1/chat/completions body used for both evaluation and serving."""
    return {
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "repeat_penalty": repetition_penalty,
        "repeat_last_n": REPEAT_WINDOW,
        "response_format": {"type": "json_object", "schema": decoding_schema()},
    }


def server_generator(
    url: str, repetition_penalty: float, max_tokens: int, timeout: float
) -> Generate:
    import httpx

    client = httpx.Client(base_url=url, timeout=timeout)

    def generate(messages: list[dict[str, str]]) -> tuple[str, int]:
        r = client.post(
            "/v1/chat/completions", json=request_body(messages, repetition_penalty, max_tokens)
        )
        if r.status_code >= 400:  # keep the server's reason; it names the unsupported field
            raise RuntimeError(f"llama-server {r.status_code}: {r.text[:500]}")
        data = r.json()
        return data["choices"][0]["message"]["content"].strip(), int(data["usage"]["prompt_tokens"])

    return generate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--system", required=True)
    parser.add_argument("--mode", choices=["zeroshot", "fewshot", "finetuned"], default="fewshot")
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetition-penalty", type=float, default=1.12)
    parser.add_argument("--max-new-tokens", type=int, default=768)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    items = list(read_jsonl(args.items, BenchItem))
    if args.limit:
        items = items[: args.limit]
    generate = server_generator(
        args.url, args.repetition_penalty, args.max_new_tokens, args.timeout
    )
    preds = run(items, generate, args.system, args.mode)
    write_jsonl(args.out, preds)
    ok = sum(p.record is not None for p in preds)
    print(json.dumps({"predictions": len(preds), "schema_valid": ok, "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
