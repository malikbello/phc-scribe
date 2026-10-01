"""WazobiaSpeech (EqualyzAI / Data Science Nigeria, CC-BY-4.0) text access (ADR-0018).

Reads only the text columns of the parquet shards over HTTP range requests, so the audio
is never downloaded. Used by scripts/fetch_wazobia.py (test pool) and bench/teacher.py
(training clips, on Kaggle).
"""

from __future__ import annotations

from pathlib import Path

from bench.items import Language
from bench.label_queue import SourceRow

# Our language code -> dataset repo. Revisions pinned when the cards were read
# (1 Oct 2026, 08:12 UTC). CC-BY-4.0 confirmed on both cards at these revisions.
DATASETS: dict[Language, tuple[str, str]] = {
    "yo": ("Africanvoice/yoruba_african_voices", "353ea9f10a1f67cda131ebb90f3205114be8ae58"),
    "pcm": ("Africanvoice/naija_african_voices", "2bb56186c314ea1f9c83951af3ae55b1703580a3"),
}
HEALTH_DOMAIN = "HE"


def _shards(fs, repo: str, revision: str, split: str) -> list[str]:
    ref = f"datasets/{repo}@{revision}"
    names = [str(p) for p in fs.ls(f"{ref}/data", detail=False)]
    return sorted(p for p in names if Path(p).name.startswith(f"{split}-"))


def spread(paths: list[str], k: int | None) -> list[str]:
    """k shards spaced evenly over the sorted list (all of them if k is None or larger)."""
    if not k or k >= len(paths):
        return list(paths)
    return [paths[(i * len(paths)) // k] for i in range(k)]


def read_health_rows(
    lang: Language, split: str, max_shards: int | None = None, workers: int = 8
) -> list[SourceRow]:
    from concurrent.futures import ThreadPoolExecutor

    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    repo, revision = DATASETS[lang]
    fs = HfFileSystem()
    paths = spread(_shards(fs, repo, revision, split), max_shards)
    if not paths:
        raise FileNotFoundError(f"no {split} shards for {repo}")

    def read(path: str) -> list[dict]:
        with fs.open(path, "rb", block_size=2**20) as f:
            table = pq.ParquetFile(f).read(
                columns=["transcript", "audio_id", "speaker_id", "domain"]
            )
        return table.to_pylist()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        tables = list(pool.map(read, paths))
    rows: list[SourceRow] = []
    for rec in (r for t in tables for r in t):
        if rec.get("domain") != HEALTH_DOMAIN:
            continue
        rows.append(
            SourceRow(
                source="wazobia",
                source_id=str(rec["audio_id"]),
                speaker_id=str(rec.get("speaker_id") or "unknown"),
                language=lang,
                split=split,
                transcript=str(rec.get("transcript") or ""),
            )
        )
    return rows


def speaker_overlap(lang: Language, test_splits: list[str], workers: int = 16) -> int:
    """Number of speakers in both the train split and the test pool, over all shards."""
    from concurrent.futures import ThreadPoolExecutor

    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    repo, revision = DATASETS[lang]
    fs = HfFileSystem()

    def speakers_in(path: str) -> set[str]:
        with fs.open(path, "rb", block_size=2**20) as f:
            col = pq.ParquetFile(f).read(columns=["speaker_id"]).column(0)
        return {str(s) for s in col.to_pylist()}

    def speakers(splits: list[str]) -> set[str]:
        paths = [p for split in splits for p in _shards(fs, repo, revision, split)]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return set().union(*pool.map(speakers_in, paths))

    return len(speakers(["train"]) & speakers(test_splits))
