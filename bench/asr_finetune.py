"""ADR-0026: fine-tune an N-ATLaS ASR model (Whisper-Small) on WazobiaSpeech `train` speech.

    python -m bench.asr_finetune --language yo --out /kaggle/working/asr-ft/yo
    python -m bench.asr_finetune --language pcm --base openai/whisper-tiny \
        --shards 1 --max-clips 24 --epochs 1 --out /tmp/ft-smoke          # CPU smoke test

Recipe (ADR-0026, fixed before training):
- base model: `NCAIR1/Yoruba-ASR` for yo, `NCAIR1/NigerianAccentedEnglish` for pcm (gated:
  HF_TOKEN);
- data: every clip in `--shards` evenly spaced `train` shards (all domains, for acoustic
  coverage). Never `dev` or `dev_test` (the test pool; disjoint speakers, ADR-0018). The
  training clips used for the LLM's two-view data (`data/asr/targets.v1.jsonl`) are left out,
  so their ASR view stays out-of-sample. Clips longer than 30 s or with more than 440 label
  tokens are skipped (one Whisper window; no word timings exist to split them);
- held-out slice: 5% of training *speakers* (seeded hash), for the dev WER and the
  forgetting check (health vs other domains). Never the test pool;
- learning rate 1e-5, linear warm-up over 10% of steps then linear decay, AdamW, 2 epochs,
  batch 16 (8 x 2 accumulation), fp16 autocast, gradient clipping at 1.0, SpecAugment
  (time masking, p = 0.05), the model's language forced in labels and decoding.

Prints progress and WER lines (=== ASRFT ...), never transcript text. Saves the model and
processor to `--out` (safetensors), with the language forced in its generation config.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.asr_run import TARGET_RATE, resample
from bench.wazobia import DATASETS, HEALTH_DOMAIN, _shards, spread
from bench.wer import corpus_wer

BASE = {"yo": "NCAIR1/Yoruba-ASR", "pcm": "NCAIR1/NigerianAccentedEnglish"}
LANGUAGE = {"yo": "yoruba", "pcm": "english"}  # Pidgin has no Whisper language
SEED = 20261010
DEV_SHARE = 0.05
MAX_SECONDS = 30.0
MIN_SECONDS = 0.5
MAX_LABEL_TOKENS = 440  # Whisper's decoder holds 448 positions


def is_dev_speaker(speaker: str, seed: int = SEED, share: float = DEV_SHARE) -> bool:
    h = hashlib.sha256(f"{seed}:{speaker}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 2**32 < share


def read_shard(fs, path: str, skip: set[str], max_clips: int = 0) -> list[dict]:
    """Decoded 16 kHz clips (int16) from one train shard, row group by row group."""
    import numpy as np
    import pyarrow.parquet as pq
    import soundfile as sf  # pyright: ignore[reportMissingImports]

    out: list[dict] = []
    cols = ["audio_id", "audio_path", "transcript", "speaker_id", "domain"]
    with fs.open(path, "rb", block_size=2**22) as f:
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            for r in pf.read_row_group(rg, columns=cols).to_pylist():
                text = (r.get("transcript") or "").strip()
                if not text or r["audio_id"] in skip:
                    continue
                try:
                    samples, rate = sf.read(io.BytesIO(r["audio_path"]["bytes"]))
                except Exception:  # noqa: S112 (an undecodable clip is skipped, not fatal)
                    continue
                x = resample(samples, rate)
                seconds = len(x) / TARGET_RATE
                if not MIN_SECONDS <= seconds <= MAX_SECONDS:
                    continue
                out.append(
                    {
                        "audio_id": r["audio_id"],
                        "speaker": str(r.get("speaker_id") or "unknown"),
                        "health": r.get("domain") == HEALTH_DOMAIN,
                        "audio": (np.clip(x, -1, 1) * 32767).astype(np.int16),
                        "text": text,
                    }
                )
                if max_clips and len(out) >= max_clips:
                    return out
    return out


def load_clips(lang: str, shards: int, skip: set[str], max_clips: int, workers: int) -> list[dict]:
    from huggingface_hub import HfFileSystem

    repo, revision = DATASETS[lang]  # pyright: ignore[reportArgumentType]
    fs = HfFileSystem()
    paths = spread(_shards(fs, repo, revision, "train"), shards)
    per_shard = math.ceil(max_clips / len(paths)) if max_clips else 0

    def one(path: str) -> list[dict]:
        for attempt in range(4):
            try:
                return read_shard(fs, path, skip, per_shard)
            except Exception as exc:
                if attempt == 3:
                    print(f"=== ASRFT shard failed: {path.rsplit('/', 1)[-1]}: {exc!r}")
                    return []
                time.sleep(3 * 2**attempt)
        return []

    with ThreadPoolExecutor(workers) as pool:
        clips = [c for batch in pool.map(one, paths) for c in batch]
    return clips[:max_clips] if max_clips else clips


class Collator:
    def __init__(self, processor, decoder_start: int):
        self.processor = processor
        self.decoder_start = decoder_start

    def __call__(self, batch: list[dict]) -> dict:
        import numpy as np
        import torch  # pyright: ignore[reportMissingImports]

        audio = [c["audio"].astype(np.float32) / 32767 for c in batch]
        feats = self.processor.feature_extractor(
            audio, sampling_rate=TARGET_RATE, return_tensors="pt"
        ).input_features
        labels = [c["labels"] for c in batch]
        width = max(len(lab) for lab in labels)
        padded = torch.full((len(labels), width), -100, dtype=torch.long)
        for i, lab in enumerate(labels):
            padded[i, : len(lab)] = torch.tensor(lab)
        if (padded[:, 0] == self.decoder_start).all():
            padded = padded[:, 1:]  # the model prepends the start token itself
        return {"input_features": feats, "labels": padded}


def transcribe(model, processor, clips: list[dict], lang: str, batch: int = 16) -> list[str]:
    import numpy as np
    import torch  # pyright: ignore[reportMissingImports]

    device = next(model.parameters()).device
    out: list[str] = []
    model.eval()
    for i in range(0, len(clips), batch):
        audio = [c["audio"].astype(np.float32) / 32767 for c in clips[i : i + batch]]
        feats = processor.feature_extractor(
            audio, sampling_rate=TARGET_RATE, return_tensors="pt"
        ).input_features.to(device, dtype=next(model.parameters()).dtype)
        with torch.no_grad():
            ids = model.generate(
                feats, language=LANGUAGE[lang], task="transcribe", max_new_tokens=440
            )
        out += [t.strip() for t in processor.batch_decode(ids, skip_special_tokens=True)]
    return out


def dev_wer(model, processor, dev: list[dict], lang: str) -> dict[str, float | int | None]:
    hyps = transcribe(model, processor, dev, lang)
    res: dict[str, float | int | None] = {"clips": len(dev)}
    for name, keep in (("all", lambda c: True), ("health", lambda c: c["health"]),
                       ("other", lambda c: not c["health"])):  # fmt: skip
        pairs = [(c["text"], h) for c, h in zip(dev, hyps, strict=True) if keep(c)]
        wer = corpus_wer(pairs) if pairs else None
        res[f"wer_{name}"] = round(wer, 4) if wer is not None else None
        res[f"n_{name}"] = len(pairs)
    return res


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=sorted(BASE), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base", help="model to fine-tune (default: the N-ATLaS ASR model)")
    parser.add_argument("--shards", type=int, default=30)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--accumulate", type=int, default=2)
    parser.add_argument("--max-clips", type=int, default=0, help="smoke tests only")
    parser.add_argument("--max-dev", type=int, default=400)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--exclude", type=Path, default=Path("data/asr/targets.v1.jsonl"))
    args = parser.parse_args()

    import torch  # pyright: ignore[reportMissingImports]
    from transformers import (  # pyright: ignore[reportMissingImports]
        WhisperForConditionalGeneration,
        WhisperProcessor,
    )

    lang, base = args.language, args.base or BASE[args.language]
    t0 = time.time()
    skip = set()
    if args.exclude.exists():
        skip = {
            json.loads(x)["audio_id"]
            for x in args.exclude.read_text(encoding="utf-8").splitlines()
            if x.strip()
        }
    clips = load_clips(lang, args.shards, skip, args.max_clips, args.workers)
    if not clips:
        print(f"=== ASRFT {lang}: no training clips loaded")
        return 1
    dev = [c for c in clips if is_dev_speaker(c["speaker"])]
    train = [c for c in clips if not is_dev_speaker(c["speaker"])]
    if not dev:  # tiny smoke runs may have one speaker
        dev, train = train[: max(1, len(train) // 5)], train[max(1, len(train) // 5) :]
    rng = random.Random(SEED)  # noqa: S311
    rng.shuffle(dev)
    dev = dev[: args.max_dev]
    hours = sum(len(c["audio"]) for c in train) / TARGET_RATE / 3600
    print(
        f"=== ASRFT {lang} data: {len(train)} train clips ({hours:.1f} h,"
        f" {len({c['speaker'] for c in train})} speakers), {len(dev)} dev clips"
        f" ({len({c['speaker'] for c in dev})} speakers), {time.time() - t0:.0f}s",
        flush=True,
    )

    processor = WhisperProcessor.from_pretrained(base)
    processor.tokenizer.set_prefix_tokens(language=LANGUAGE[lang], task="transcribe")
    for c in train:
        c["labels"] = processor.tokenizer(c["text"]).input_ids
    before = len(train)
    train = [c for c in train if len(c["labels"]) <= MAX_LABEL_TOKENS]
    if before - len(train):
        print(f"=== ASRFT {lang}: {before - len(train)} clips skipped (labels too long)")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = WhisperForConditionalGeneration.from_pretrained(base).to(device)
    model.config.apply_spec_augment = True
    model.config.mask_time_prob = 0.05
    model.generation_config.language = LANGUAGE[lang]
    model.generation_config.task = "transcribe"
    model.generation_config.forced_decoder_ids = None
    model.config.forced_decoder_ids = None

    base_dev = dev_wer(model, processor, dev, lang)
    print(f"=== ASRFT {lang} dev base: {json.dumps(base_dev)}", flush=True)

    collate = Collator(processor, model.config.decoder_start_token_id)
    loader = torch.utils.data.DataLoader(
        train,  # pyright: ignore[reportArgumentType]
        batch_size=args.batch,
        shuffle=True,
        collate_fn=collate,
        num_workers=2 if device == "cuda" else 0,
        generator=torch.Generator().manual_seed(SEED),
    )
    steps = max(1, math.ceil(len(loader) * args.epochs / args.accumulate))
    warmup = max(1, steps // 10)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min((s + 1) / warmup, max(0.0, (steps - s) / max(1, steps - warmup)))
    )
    use_amp = device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    model.train()
    step, micro, running = 0, 0, 0.0
    while step < steps:
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                loss = model(**batch).loss / args.accumulate
            scaler.scale(loss).backward()
            running += loss.item()
            micro += 1
            if micro % args.accumulate:
                continue
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            sched.step()
            step += 1
            if step % 50 == 0 or step == steps:
                print(
                    f"=== ASRFT {lang} step {step}/{steps}: loss {running / 50:.4f},"
                    f" lr {sched.get_last_lr()[0]:.2e}, {time.time() - t0:.0f}s",
                    flush=True,
                )
                running = 0.0
            if step >= steps:
                break

    ft_dev = dev_wer(model, processor, dev, lang)
    print(f"=== ASRFT {lang} dev fine-tuned: {json.dumps(ft_dev)}", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out, safe_serialization=True)
    processor.save_pretrained(args.out)
    summary = {
        "language": lang,
        "base": base,
        "train_clips": len(train),
        "train_hours": round(hours, 2),
        "steps": steps,
        "dev_base": base_dev,
        "dev_finetuned": ft_dev,
        "seconds": round(time.time() - t0),
    }
    (args.out / "asrft-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"=== ASRFT {lang} saved to {args.out} in {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
