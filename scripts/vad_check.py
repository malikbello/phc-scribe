"""Check the speech gate before Whisper (ADR-0031) on non-test audio: speech must pass, noise
must not.

    python scripts/vad_check.py <folder of speech WAVs>... [--tag fleurs-dev]

Speech: every WAV in the folders (for ADR-0031, the first 40 Yoruba and 20 English clips of
Google FLEURS `dev`, CC-BY 4.0, which no benchmark here uses), as is, with white noise mixed
in at 5 and 0 dB SNR, and cut to its loudest 0.5 s (a one-word answer). All must pass.
Non-speech: generated silence, hiss, white/pink/brown noise, mains hum, a fan, taps and
music-like tones, at several levels and seeds. None may pass. Folders in the frozen test
manifest are refused (ADR-0022). Needs torch and silero-vad (the API image has both).

Writes results/asr/vad-gate.<tag>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.api.asr import (  # noqa: E402
    GATE_MIN_CLIP_S,
    MIN_SPEECH_S,
    SAMPLE_RATE,
    SileroGate,
    read_wav,
)

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"
SR = SAMPLE_RATE


def refuse_frozen(folders: list[Path]) -> None:
    frozen = [f["path"] for f in json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]]
    for folder in folders:
        p = folder.resolve()
        if p.is_relative_to(ROOT) and any(
            f.startswith(p.relative_to(ROOT).as_posix()) for f in frozen
        ):
            raise SystemExit(
                f"{folder} holds frozen test data: the gate is checked on dev audio only"
            )


def db(x: np.ndarray, dbfs: float) -> np.ndarray:
    rms = float(np.sqrt(np.mean(x**2))) or 1.0
    return x * (10 ** (dbfs / 20) / rms)


def coloured(n: int, rng: np.random.Generator, exponent: float) -> np.ndarray:
    """1/f^exponent noise: 0 white, 1 pink, 2 brown."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    return np.fft.irfft(spec / f ** (exponent / 2), n)


def non_speech(seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n, t = SR * 10, np.arange(SR * 10) / SR
    hum = np.sum([np.sin(2 * np.pi * 50 * k * t) / k for k in (1, 2, 3, 5)], axis=0)
    fan = np.convolve(rng.standard_normal(n), np.ones(40) / 40, "same") * (
        1 + 0.2 * np.sin(2 * np.pi * 0.5 * t)
    )
    taps = np.zeros(n)
    for at in rng.integers(0, n - 800, 25):
        taps[at : at + 800] += np.exp(-np.arange(800) / 80) * rng.standard_normal(800)
    chord = np.sum([np.sin(2 * np.pi * f0 * t) for f0 in (261.6, 329.6, 392.0)], axis=0) * (
        0.5 + 0.5 * np.sin(2 * np.pi * 2 * t)
    )
    out = {"silence": np.zeros(n), "hiss_-60dBFS": db(rng.standard_normal(n), -60)}
    for level in (-35, -20):
        out[f"white_{level}dBFS"] = db(rng.standard_normal(n), level)
        out[f"pink_{level}dBFS"] = db(coloured(n, rng, 1), level)
        out[f"brown_{level}dBFS"] = db(coloured(n, rng, 2), level)
        out[f"hum_{level}dBFS"] = db(hum, level)
        out[f"fan_{level}dBFS"] = db(fan, level)
        out[f"taps_{level}dBFS"] = db(taps, level)
        out[f"tones_{level}dBFS"] = db(chord, level)
    return out


def loudest(x: np.ndarray, seconds: float) -> np.ndarray:
    w = int(seconds * SR)
    if len(x) <= w:
        return x
    energy = np.convolve(x**2, np.ones(w), "valid")
    i = int(np.argmax(energy))
    return x[i : i + w]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+", type=Path)
    ap.add_argument("--tag", default="dev")
    args = ap.parse_args()
    refuse_frozen(args.folders)
    gate = SileroGate()
    rng = np.random.default_rng(0)
    speech_rows, noise_rows = [], []
    for wav in sorted(p for f in args.folders for p in f.glob("*.wav")):
        x = np.asarray(read_wav(wav.read_bytes())[0])
        noise = rng.standard_normal(len(x))
        variants = {
            "clean": x,
            "snr5": x + db(noise, 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12) - 5),
            "snr0": x + db(noise, 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12)),
            "one_word_0.5s": loudest(x, 0.5),
        }
        for name, v in variants.items():
            s = gate.speech_seconds(v.astype(np.float32).tolist())
            served = len(v) / SR < GATE_MIN_CLIP_S or s >= MIN_SPEECH_S  # as the API decides
            speech_rows.append(
                {
                    "clip": wav.name,
                    "variant": name,
                    "speech_s": round(s, 2),
                    "vad_alone": s >= MIN_SPEECH_S,
                    "passes": served,
                }
            )
    for seed in range(3):
        for name, v in non_speech(seed).items():
            s = gate.speech_seconds(v.astype(np.float32).tolist())
            noise_rows.append(
                {"sound": name, "seed": seed, "speech_s": round(s, 2), "passes": s >= MIN_SPEECH_S}
            )

    def rate(rows, variant=None):
        rs = [r for r in rows if variant is None or r.get("variant") == variant]
        return f"{sum(r['passes'] for r in rs)}/{len(rs)}"

    one_word = [r for r in speech_rows if r["variant"] == "one_word_0.5s"]
    summary = {
        "tag": args.tag,
        "min_speech_s": MIN_SPEECH_S,
        "gate_min_clip_s": GATE_MIN_CLIP_S,
        "one_word_by_vad_alone": f"{sum(r['vad_alone'] for r in one_word)}/{len(one_word)}",
        "speech_passed": {
            v: rate(speech_rows, v) for v in ("clean", "snr5", "snr0", "one_word_0.5s")
        },
        "non_speech_passed": rate(noise_rows),
        "non_speech_that_passed": [r for r in noise_rows if r["passes"]],
        "speech_that_failed": [r for r in speech_rows if not r["passes"]],
        "speech": speech_rows,
        "non_speech": noise_rows,
    }
    out = ROOT / "results" / "asr" / f"vad-gate.{args.tag}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "speech_passed",
                    "non_speech_passed",
                    "non_speech_that_passed",
                    "speech_that_failed",
                )
            },
            indent=1,
        )
    )
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
