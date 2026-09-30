"""Model adapters behind one interface: the API is model-agnostic (architecture §2)."""

from __future__ import annotations

import json
from typing import Protocol

from phc_scribe.encounter import Encounter, decoding_schema


class ExtractorError(Exception):
    """The model backend failed or returned something that is not a record."""


class Extractor(Protocol):
    name: str

    def extract(self, text: str) -> Encounter: ...


class KeywordExtractor:
    """Rung 1 of the baseline ladder: keywords and regexes. Runs anywhere, no model."""

    name = "keyword-baseline-v0"

    def extract(self, text: str) -> Encounter:
        from bench.baselines.keyword import extract

        return extract(text)


class LlamaCppExtractor:
    """The fine-tuned N-ATLaS GGUF behind a llama.cpp server, with the record schema as
    a decoding constraint (the same constraint the benchmark uses)."""

    def __init__(self, url: str, model: str, timeout: float = 120.0):
        import httpx

        self.name = f"llamacpp:{model}"
        self._client = httpx.Client(base_url=url, timeout=timeout)
        self._model = model

    def extract(self, text: str) -> Encounter:
        from bench.prompts import build_messages

        body = {
            "model": self._model,
            "messages": build_messages(text, "finetuned"),
            "temperature": 0,
            "response_format": {"type": "json_object", "schema": decoding_schema()},
        }
        try:
            r = self._client.post("/v1/chat/completions", json=body)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return Encounter.model_validate(json.loads(content))
        except Exception as e:  # network, backend or schema failure
            raise ExtractorError(type(e).__name__) from e
