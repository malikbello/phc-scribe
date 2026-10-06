"""Model adapters behind one interface: the API is model-agnostic (architecture §2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from phc_scribe.encounter import Encounter
from phc_scribe.salvage import Repair, salvage


class ExtractorError(Exception):
    """The model backend failed or returned something that is not a record."""


@dataclass(frozen=True)
class Draft:
    """A drafted record, plus any parts removed to make the model's output valid (ADR-0029)."""

    record: Encounter
    repairs: list[Repair] = field(default_factory=list)


class Extractor(Protocol):
    name: str

    def extract(self, text: str) -> Draft: ...


class KeywordExtractor:
    """Rung 1 of the baseline ladder: keywords and regexes. Runs anywhere, no model."""

    name = "keyword-baseline-v0"

    def extract(self, text: str) -> Draft:
        from bench.baselines.keyword import extract

        return Draft(extract(text))


class LlamaCppExtractor:
    """The fine-tuned N-ATLaS GGUF behind a llama.cpp server, with the record schema as
    a decoding constraint (the same constraint the benchmark uses)."""

    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 120.0,
        mode: str = "fewshot",
        repetition_penalty: float = 1.12,
    ):
        import httpx

        self.name = f"llamacpp:{model}"
        self._client = httpx.Client(base_url=url, timeout=timeout)
        self._model = model
        self._mode = mode  # the prompt the shipped model was trained and evaluated with
        self._repetition_penalty = repetition_penalty

    def extract(self, text: str) -> Draft:
        from bench.prompts import build_messages
        from bench.runners.llamacpp import request_body

        # The exact request the benchmark's llama.cpp rung sends (evaluate what we ship).
        body = {
            "model": self._model,
            **request_body(build_messages(text, self._mode), self._repetition_penalty, 768),  # pyright: ignore[reportArgumentType]
        }
        try:
            r = self._client.post("/v1/chat/completions", json=body)
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:  # network, backend or invalid JSON
            raise ExtractorError(type(e).__name__) from e
        try:
            return Draft(Encounter.model_validate(data))
        except ValueError as e:
            record, repairs = salvage(data)
            if record is None:
                raise ExtractorError(type(e).__name__) from e
            return Draft(record, repairs)
