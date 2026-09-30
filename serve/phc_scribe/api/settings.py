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
    db_path: str = "phc_scribe.sqlite3"
    rate_limit_per_minute: int = 60
    max_text_chars: int = 8000

    @classmethod
    def from_env(cls) -> Settings:
        e = os.environ
        return cls(
            api_key_hashes=_hashes(e.get("PHC_API_KEY_HASHES", "")),
            env=e.get("PHC_ENV", "production"),
            extractor=e.get("PHC_EXTRACTOR", "keyword"),
            llamacpp_url=e.get("PHC_LLAMACPP_URL", "http://127.0.0.1:8080"),
            llamacpp_model=e.get("PHC_LLAMACPP_MODEL", "phc-scribe"),
            db_path=e.get("PHC_DB", "phc_scribe.sqlite3"),
            rate_limit_per_minute=int(e.get("PHC_RATE_LIMIT_PER_MINUTE", "60")),
        )

    def validate(self) -> None:
        if not self.api_key_hashes and self.env != "dev":
            raise RuntimeError("PHC_API_KEY_HASHES must be set (or PHC_ENV=dev for local use)")
        if self.extractor not in ("keyword", "llamacpp"):
            raise RuntimeError(f"unknown PHC_EXTRACTOR {self.extractor!r}")
