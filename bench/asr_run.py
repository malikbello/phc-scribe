"""Run A (ADR-0024): N-ATLaS ASR over WazobiaSpeech clips, on Kaggle.

    python -m bench.asr_run --targets data/asr/targets.v1.jsonl --out preds/asr.jsonl

Targets are public clip ids only ({audio_id, language, split}); no labels and no private
text travel to Kaggle. For each split the job opens the parquet shards over HTTP, reads the
`audio_id` column, and downloads the audio only for the row groups that hold a target, so it
never pulls whole splits (each shard is ~500 MB). Audio is decoded (WAV, 48 kHz), resampled
to 16 kHz and transcribed with the NCAIR1 model for its language (serve/phc_scribe/api/asr.py:
Yoruba-ASR for yo, NigerianAccentedEnglish for pcm). The NCAIR1 models are gated: HF_TOKEN.

Writes one JSON line per clip: audio_id, language, split, model, text, seconds. Prints counts
and timing only, never transcript text.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import gcd
from pathlib import Path

from bench.wazobia import DATASETS, _shards, spread

TARGET_RATE = 16_000
# Training clips were sampled from 40 evenly spaced shards (bench.teacher fetch); test-pool
# clips may come from any shard of their split.
TRAIN_SHARDS = 40
# A target's split names the shards to search. The test pool (ADR-0018) is dev + dev_test,
# and the label queue does not record which of the two a clip came from.
SPLITS = {"train": ["train"], "dev_pool": ["dev", "dev_test"]}


def resample(samples, rate: int, target: int = TARGET_RATE):
    import numpy as np
    from scipy.signal import resample_poly  # pyright: ignore[reportMissingImports]

    x = np.asarray(samples, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)  # stereo -> mono
    if rate == target:
        return x
    g = gcd(rate, target)
    return resample_poly(x, target // g, rate // g).astype(np.float32)


def shard_hits(fs, path: str, wanted: set[str]) -> list[tuple[str, bytes, str]]:
    """(audio_id, encoded audio, the dataset's human transcript) for every wanted clip in one
    shard, reading only the row groups that contain one."""
    import pyarrow.parquet as pq

    with fs.open(path, "rb", block_size=2**20) as f:
        pf = pq.ParquetFile(f)
        ids = pf.read(columns=["audio_id"]).column(0).to_pylist()
        hit_rows = {i for i, a in enumerate(ids) if a in wanted}
        if not hit_rows:
            return []
        out, start = [], 0
        for rg in range(pf.num_row_groups):
            n = pf.metadata.row_group(rg).num_rows
            if any(start <= i < start + n for i in hit_rows):
                cols = ["audio_id", "audio_path", "transcript"]
                table = pf.read_row_group(rg, columns=cols).to_pylist()
                out += [
                    (r["audio_id"], r["audio_path"]["bytes"], r["transcript"] or "")
                    for r in table
                    if r["audio_id"] in wanted
                ]
            start += n
        return out


def shard_hits_retrying(
    fs, path: str, wanted: set[str], attempts: int = 4
) -> list[tuple[str, bytes, str]]:
    """shard_hits with exponential backoff: a transient HTTP or read error on one shard must
    not end the run. A shard that keeps failing is reported, and its clips count as missing."""
    for attempt in range(attempts):
        try:
            return shard_hits(fs, path, wanted)
        except Exception as exc:  # network and parquet errors vary
            if attempt == attempts - 1:
                name = path.rsplit("/", 1)[-1]
                print(
                    f"=== ASR shard failed after {attempts} tries: {name}: {type(exc).__name__}",
                    flush=True,
                )
                return []
            time.sleep(2**attempt * 3)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="for smoke tests only")
    parser.add_argument(
        "--force-language", action="store_true", help="force each model's Whisper language"
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=[],
        metavar="LANG=PATH",
        help="replace a language's model, e.g. yo=/kaggle/working/asr-ft/yo (ADR-0026)",
    )
    parser.add_argument(
        "--split", choices=sorted(SPLITS), help="only the targets of this split (default: all)"
    )
    parser.add_argument(
        "--compare-language",
        type=int,
        default=0,
        metavar="N",
        help="check: N training clips per language, transcribed with and without the forced"
        " language; prints WER against the dataset's transcripts",
    )
    args = parser.parse_args()

    import soundfile as sf  # pyright: ignore[reportMissingImports]
    from huggingface_hub import HfFileSystem

    from phc_scribe.api.asr import ASR_MODELS, HfWhisperTranscriber

    targets = [
        json.loads(line) for line in args.targets.read_text(encoding="utf-8").splitlines() if line
    ]
    if args.compare_language:
        per: dict[str, int] = defaultdict(int)
        picked = []
        for t in targets:
            if t["split"] == "train" and per[t["language"]] < args.compare_language:
                per[t["language"]] += 1
                picked.append(t)
        targets = picked
    if args.split:
        targets = [t for t in targets if t["split"] == args.split]
    if args.limit:
        targets = targets[: args.limit]
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for t in targets:
        groups[(t["language"], t["split"])].add(t["audio_id"])

    fs = HfFileSystem()
    from bench.wer import edit_errors

    overrides = dict(m.split("=", 1) for m in args.models)
    asr = HfWhisperTranscriber(
        models={**ASR_MODELS, **overrides}, force_language=args.force_language
    )
    errs: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    t0 = time.time()
    audio_seconds = 0.0
    with args.out.open("w", encoding="utf-8") as out, ThreadPoolExecutor(args.workers) as pool:
        for (lang, split), wanted in sorted(groups.items()):
            repo, revision = DATASETS[lang]  # pyright: ignore[reportArgumentType]
            paths = [p for s in SPLITS[split] for p in _shards(fs, repo, revision, s)]
            if split == "train":
                paths = spread(paths, TRAIN_SHARDS)
            model = asr.model_for(lang)
            found = 0
            for hits in pool.map(lambda p, w=wanted: shard_hits_retrying(fs, p, w), paths):
                for audio_id, data, reference in hits:
                    if audio_id in done:
                        continue
                    samples, rate = sf.read(io.BytesIO(data))
                    x = resample(samples, rate)
                    audio_seconds += len(x) / TARGET_RATE
                    row: dict = {
                        "audio_id": audio_id,
                        "language": lang,
                        "split": split,
                        "model": model,
                        "forced_language": args.force_language,
                        "reference": reference,
                        "seconds": round(len(x) / TARGET_RATE, 2),
                    }
                    if args.compare_language:
                        modes = {"auto": False, "forced": True}
                    else:
                        modes = {"forced" if args.force_language else "auto": None}
                    for mode, force in modes.items():
                        text = asr.transcribe(x, lang, force=force)  # pyright: ignore[reportArgumentType]
                        row["text" if force is None else f"text_{mode}"] = text
                        e, n = edit_errors(reference, text)
                        errs[(lang, mode)][0] += e
                        errs[(lang, mode)][1] += n
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    done.add(audio_id)
                    found += 1
            print(
                f"=== ASR {lang}/{split}: {found} of {len(wanted)} clips from {len(paths)} shards"
                f" ({time.time() - t0:.0f}s elapsed)",
                flush=True,
            )
    for (lang, mode), (e, n) in sorted(errs.items()):
        if n:
            print(f"=== WER {lang} {mode}: {e / n:.3f} over {n} reference words", flush=True)
    missing = len(targets) - len(done)
    print(
        f"=== ASR done: {len(done)} clips, {audio_seconds / 60:.1f} min of audio,"
        f" {missing} missing,"
        f" {time.time() - t0:.0f}s",
        flush=True,
    )
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
