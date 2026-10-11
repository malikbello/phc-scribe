"""Service settings, read only from environment variables (never from files in git)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _hashes(raw: str) -> frozenset[str]:
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


@dataclass(frozen=True)
class Settings:
    # SHA-256 hex digests of the accepted API keys, comma-separated. The keys themselves
    # are never stored. Empty means open access, which is refused unless PHC_ENV=dev.
    api_key_hashes: frozenset[str] = field(default_factory=frozenset)
    env: str = "production"
    extractor: str = "keyword"  # keyword | llamacpp
    llamacpp_url: str = "http://127.0.0.1:8080"
    llamacpp_model: str = "phc-scribe"
    # Seconds to wait for one draft. A laptop CPU writes about 2-4 tokens a second, so a
    # full 768-token record can take several minutes; the hub queues drafts meanwhile.
    llamacpp_timeout: float = 600.0
    prompt_mode: str = "fewshot"  # the prompt the shipped model was evaluated with
    db_path: str = "phc_scribe.sqlite3"
    rate_limit_per_minute: int = 60
    max_text_chars: int = 8000
    # off | hf (the N-ATLaS ASR models, fp32) | ct2 (the same models, int8: ADR-0032 Tier 2)
    asr: str = "off"
    # Per-language overrides of the ASR model: "yo=/models/asr/yo,pcm=/models/asr/pcm".
    # The clinic hub points these at the fine-tuned models (ADR-0026), which ship.
    asr_models: str = ""
    # With asr=ct2: the int8 folders, same format. A language not listed keeps its fp32 model
    # above, so int8 can be switched on one model at a time as each passes its checks.
    asr_int8_models: str = ""
    max_audio_bytes: int = 10_000_000  # about 5 minutes of 16 kHz mono WAV
    # Voice-activity gate before Whisper (ADR-0031): on | off. With ct2 it also cuts long
    # recordings into windows at pauses.
    asr_vad: str = "on"

    @classmethod
    def from_env(cls) -> Settings:
        e = os.environ
        return cls(
            api_key_hashes=_hashes(e.get("PHC_API_KEY_HASHES", "")),
            env=e.get("PHC_ENV", "production"),
            extractor=e.get("PHC_EXTRACTOR", "keyword"),
            llamacpp_url=e.get("PHC_LLAMACPP_URL", "http://127.0.0.1:8080"),
            llamacpp_model=e.get("PHC_LLAMACPP_MODEL", "phc-scribe"),
            llamacpp_timeout=float(e.get("PHC_LLAMACPP_TIMEOUT", "600")),
            prompt_mode=e.get("PHC_PROMPT_MODE", "fewshot"),
            db_path=e.get("PHC_DB", "phc_scribe.sqlite3"),
            rate_limit_per_minute=int(e.get("PHC_RATE_LIMIT_PER_MINUTE", "60")),
            asr=e.get("PHC_ASR", "off"),
            asr_models=e.get("PHC_ASR_MODELS", ""),
            asr_int8_models=e.get("PHC_ASR_INT8_MODELS", ""),
            asr_vad=e.get("PHC_ASR_VAD", "on"),
        )

    def validate(self) -> None:
        if not self.api_key_hashes and self.env != "dev":
            raise RuntimeError("PHC_API_KEY_HASHES must be set (or PHC_ENV=dev for local use)")
        if self.extractor not in ("keyword", "llamacpp"):
            raise RuntimeError(f"unknown PHC_EXTRACTOR {self.extractor!r}")
        if self.asr not in ("off", "hf", "ct2"):
            raise RuntimeError(f"unknown PHC_ASR {self.asr!r}")
        if self.asr_vad not in ("on", "off"):
            raise RuntimeError(f"PHC_ASR_VAD must be on or off, not {self.asr_vad!r}")
        self.asr_model_overrides()  # fail at start-up, not on the first recording
        int8 = self.asr_int8_overrides()
        if self.asr == "ct2" and not int8:
            raise RuntimeError("PHC_ASR=ct2 needs PHC_ASR_INT8_MODELS naming the int8 folders")

    def asr_model_overrides(self) -> dict[str, str]:
        return _models(self.asr_models, "PHC_ASR_MODELS")

    def asr_int8_overrides(self) -> dict[str, str]:
        return _models(self.asr_int8_models, "PHC_ASR_INT8_MODELS")


def _models(value: str, name: str) -> dict[str, str]:
    from phc_scribe.api.asr import ASR_MODELS

    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in value.split(","))):
        lang, sep, model = part.partition("=")
        lang, model = lang.strip(), model.strip()
        if not sep or not model or lang not in ASR_MODELS:
            raise RuntimeError(
                f"{name} entry {part!r} must be <language>=<model>,"
                f" with language in {sorted(ASR_MODELS)}"
            )
        out[lang] = model
    return out
