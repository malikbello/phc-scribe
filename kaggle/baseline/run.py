"""Kaggle GPU job: base-model rungs of the baseline ladder (docs/eval-plan.md, section 2).

Runs on a Kaggle T4 notebook against the code bundle published by scripts/kaggle_push.py
(no private data is in it). Writes one predictions file and one score report per run to
/kaggle/working, so they can be pulled with `kaggle kernels output`.

N-ATLaS is gated: attach a Kaggle secret named HF_TOKEN to this notebook (Add-ons ->
Secrets). Without it, only the ungated comparator runs.
"""

import glob
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

WORK = Path("/kaggle/working")
SRC = Path(tempfile.mkdtemp())  # code lives outside /kaggle/working so outputs stay clean
REPO = SRC / "phc-scribe"

# (name, model id, mode, extra runner args). Order = priority, so the primary comparator
# finishes first.
RUNS: list[tuple[str, str, str, list[str]]] = [
    ("natlas-fewshot", "NCAIR1/N-ATLaS", "fewshot", []),
    ("llama31-fewshot", "unsloth/Llama-3.1-8B-Instruct", "fewshot", []),
    ("natlas-zeroshot", "NCAIR1/N-ATLaS", "zeroshot", []),
]
# Which items to run. "baseline": smoke + stratum G. "pilot": the 30 dev items used to set
# the guardrail margins before the freeze (docs/eval-plan.md, section 6). "prefreeze": the
# last runs before the freeze: Belebele yor_Latn for N-ATLaS and Llama-3.1 (G2 base and the
# 50% rule) and the unconstrained base comparator on the pilot items (proposal B).
# "trainprep": teacher labels for real Yoruba/Pidgin training speech (ADR-0021), then base
# N-ATLaS few-shot on the Adeola hard negatives (stratum H; a base run, allowed before the
# label freeze, ADR-0022).
# "asr": Run A of ADR-0024. N-ATLaS ASR over the training clips and the test pool's audio
# (public clip ids in data/asr/targets.v1.jsonl; no labels travel). Feeds the two-view
# training data and the "audio through N-ATLaS ASR" test condition.
# "checks": two pre-freeze settings checks (3 Oct). (1) Base N-ATLaS few-shot on the pilot
# (dev) items with the model card's repetition penalty 1.12, against the recorded run without
# it; the eval plan keeps the more generous base comparator. (2) N-ATLaS ASR with each model's
# language forced vs auto-detected, on training clips, WER against the dataset transcripts.
# "checks_asrft": "checks", then ADR-0026: fine-tune N-ATLaS ASR for Yoruba (GPU 0) and
# Pidgin (GPU 1) at the same time, then transcribe the 600-clip test pool with the base
# models (language forced) and the fine-tuned ones. One editor start for both (HF_TOKEN).
PLAN = "checks_asrft"
ITEM_SETS = {
    "baseline": ["tests/fixtures/smoke_items.jsonl", "data/bench/g.20261002.jsonl"],
    "pilot": ["data/bench/pilot.20261004.jsonl"],
    "prefreeze": ["data/bench/pilot.20261004.jsonl"],
    "trainprep": ["data/bench/h.adeola.jsonl"],
    "asr": [],
    "checks": ["data/bench/pilot.20261004.jsonl"],
    "checks_asrft": ["data/bench/pilot.20261004.jsonl"],
}[PLAN]
TEACHER = ("llama31-fewshot", "unsloth/Llama-3.1-8B-Instruct")
BELEBELE_MODELS = [("natlas", "NCAIR1/N-ATLaS"), ("llama31", "unsloth/Llama-3.1-8B-Instruct")]
if PLAN == "prefreeze":
    RUNS[:] = [("natlas-fewshot-unconstrained", "NCAIR1/N-ATLaS", "fewshot", ["--unconstrained"])]
if PLAN == "trainprep":
    RUNS[:] = [("natlas-fewshot", "NCAIR1/N-ATLaS", "fewshot", [])]
if PLAN == "asr":
    RUNS[:] = []
if PLAN in ("checks", "checks_asrft"):
    RUNS[:] = [
        ("natlas-fewshot-rp1.12", "NCAIR1/N-ATLaS", "fewshot", ["--repetition-penalty", "1.12"])
    ]
if PLAN == "pilot":
    # Dev-only check: are N-ATLaS's schema-invalid outputs cut off at the 768-token cap?
    RUNS.append(("natlas-fewshot-1536", "NCAIR1/N-ATLaS", "fewshot", ["--max-new-tokens", "1536"]))
LIMIT = int(os.environ.get("PHC_LIMIT", "0"))  # 0 = all items


def unpack() -> None:
    if REPO.exists():
        return
    bundles = glob.glob("/kaggle/input/**/phc-scribe.tar.gz", recursive=True)
    if bundles:
        with tarfile.open(bundles[0]) as tar:
            tar.extractall(SRC, filter="data")
        return
    trees = glob.glob("/kaggle/input/**/phc-scribe/pyproject.toml", recursive=True)
    if not trees:
        sys.exit("code bundle not found under /kaggle/input: attach the phc-scribe-code dataset")
    shutil.copytree(Path(trees[0]).parent, REPO)


def hf_token() -> str | None:
    try:
        from kaggle_secrets import UserSecretsClient

        return UserSecretsClient().get_secret("HF_TOKEN")
    except Exception:
        return None


def sh(*args: str) -> int:
    print("+", " ".join(args), flush=True)
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'serve'}:{REPO}"}
    return subprocess.call(args, cwd=REPO, env=env)  # noqa: S603 (fixed argv)


def invalid_summary(pred: Path) -> None:
    """Print why outputs were schema-invalid, since the prediction files may not be downloadable."""
    import collections
    import json

    rows = [json.loads(line) for line in pred.read_text().splitlines() if line.strip()]
    bad = [r for r in rows if r.get("record") is None]
    cut = sum(1 for r in bad if r.get("raw_output") and not r["raw_output"].rstrip().endswith("}"))
    kinds = collections.Counter((r.get("error") or "")[:60] for r in bad)
    print(f"=== INVALID {pred.stem}: {len(bad)}/{len(rows)}, cut off (no closing brace): {cut}")
    for kind, n in kinds.most_common(5):
        print(f"  {n:4d}  {kind}")
    lens = sorted(len(r["raw_output"]) for r in rows if r.get("raw_output"))
    if lens:
        print(f"  raw output chars: median {lens[len(lens) // 2]}, max {lens[-1]}", flush=True)


def emit_file(path: Path) -> None:
    """Put a small output file into the log (gzip + base64): cloud sessions can read the
    log but not Kaggle's output files. scripts/kaggle_log.py --save writes it back out."""
    import base64
    import gzip

    data = base64.b64encode(gzip.compress(path.read_bytes())).decode()
    print(f"=== FILE {path.name} ===", flush=True)
    for i in range(0, len(data), 4000):
        print(data[i : i + 4000], flush=True)
    print("=== END FILE ===", flush=True)


def teacher(out: Path) -> None:
    """ADR-0021: Llama-3.1 few-shot labels real train-split health speech; keep only
    schema-valid, verbatim-grounded labels (bench/teacher.py)."""
    items = out / "teacher.items.jsonl"
    pred = out / "teacher.preds.jsonl"
    kept = out / "teacher.kept.jsonl"
    if sh(sys.executable, "-m", "bench.teacher", "fetch", "--out", str(items)) != 0:
        print("run failed: teacher fetch", flush=True)
        return
    name, model = TEACHER
    cmd = [sys.executable, "-m", "bench.runners.llm", "--model", model, "--mode", "fewshot"]
    cmd += ["--items", str(items), "--out", str(pred)]
    if LIMIT:
        cmd += ["--limit", str(LIMIT)]
    if sh(*cmd) != 0:
        print(f"run failed: teacher {name}", flush=True)
        return
    invalid_summary(pred)
    if (
        sh(
            *[sys.executable, "-m", "bench.teacher", "filter"],
            "--items",
            str(items),
            "--pred",
            str(pred),
            "--out",
            str(kept),
        )
        == 0
    ):
        emit_file(kept)


def asr_language_check(out: Path) -> None:
    """Forced vs auto-detected Whisper language, 30 training clips per language."""
    dest = out / "asr-language-check.jsonl"
    sh(
        sys.executable,
        "-m",
        "bench.asr_run",
        "--targets",
        "data/asr/targets.v1.jsonl",
        "--out",
        str(dest),
        "--compare-language",
        "30",
        "--workers",
        "16",
    )


def asr(out: Path) -> None:
    """ADR-0024 Run A: transcribe the target clips with the NCAIR1 ASR models."""
    dest = out / "asr.jsonl"
    code = sh(
        sys.executable,
        "-m",
        "bench.asr_run",
        "--targets",
        "data/asr/targets.v1.jsonl",
        "--out",
        str(dest),
        "--workers",
        "16",
    )
    if dest.exists():
        emit_file(dest)  # even a partial result is worth keeping
    if code != 0:
        print(f"run failed or incomplete: asr (exit {code})", flush=True)


def main() -> None:
    unpack()
    sh(sys.executable, "-m", "pip", "install", "-q", "xgrammar")
    token = hf_token()
    if token:
        os.environ["HF_TOKEN"] = token
    elif PLAN in ("pilot", "prefreeze", "trainprep", "asr", "checks", "checks_asrft"):
        # The pilot exists to measure N-ATLaS; fail fast instead of spending GPU time without it.
        sys.exit("HF_TOKEN secret not attached: attach it (Add-ons -> Secrets) and re-run")
    else:
        print("HF_TOKEN secret not attached: skipping gated N-ATLaS runs", flush=True)
    out = WORK / "preds"
    out.mkdir(exist_ok=True)
    if PLAN == "trainprep":
        teacher(out)
    if PLAN == "asr":
        asr(out)
    if PLAN in ("checks", "checks_asrft"):
        asr_language_check(out)
    if PLAN == "prefreeze":
        for name, model in BELEBELE_MODELS:
            dest = out / f"belebele.{name}.json"
            if (
                sh(sys.executable, "-m", "bench.belebele", "--model", model, "--out", str(dest))
                == 0
            ):
                import json

                res = json.loads(dest.read_text())
                print(
                    f"=== BELEBELE {name}: accuracy {res['accuracy']:.4f}"
                    f" on {res['n_items']} items",
                    flush=True,
                )
    for name, model, mode, extra in RUNS:
        if model.startswith("NCAIR1/") and not token:
            continue
        for items in ITEM_SETS:
            tag = Path(items).stem.split(".")[0].replace("_items", "")
            pred = out / f"{name}.{tag}.jsonl"
            cmd = [
                sys.executable,
                "-m",
                "bench.runners.llm",
                "--model",
                model,
                "--mode",
                mode,
                "--items",
                items,
                "--out",
                str(pred),
                *extra,
            ]
            if LIMIT:
                cmd += ["--limit", str(LIMIT)]
            if sh(*cmd) != 0:
                print(f"run failed: {name} on {items}", flush=True)
                continue
            invalid_summary(pred)
            sh(
                sys.executable,
                "-m",
                "bench.harness",
                "score",
                "--items",
                items,
                "--pred",
                str(pred),
                "--out",
                str(out / f"{name}.{tag}.report.json"),
            )
            # Output files may not be downloadable everywhere; the log always is.
            report = out / f"{name}.{tag}.report.json"
            if report.exists():
                print(f"=== REPORT {name}.{tag} ===\n{report.read_text()}", flush=True)


def asr_finetune(out: Path) -> None:
    """ADR-0026: one language per GPU in parallel, then the test pool with base and
    fine-tuned models (both with the language forced, so the comparison is paired)."""
    import json

    ft = WORK / "asr-ft"
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'serve'}:{REPO}"}
    procs = {}
    for gpu, lang in enumerate(("yo", "pcm")):
        log = open(out / f"asrft.{lang}.log", "w")  # noqa: SIM115 (closed below)
        cmd = [sys.executable, "-m", "bench.asr_finetune", "--language", lang,
               "--out", str(ft / lang)]  # fmt: skip
        print("+", " ".join(cmd), f"(GPU {gpu})", flush=True)
        procs[lang] = (
            subprocess.Popen(  # noqa: S603 (fixed argv)
                cmd,
                cwd=REPO,
                env={**env, "CUDA_VISIBLE_DEVICES": str(gpu)},
                stdout=log,
                stderr=subprocess.STDOUT,
            ),
            log,
        )
    for lang, (proc, log) in procs.items():
        code = proc.wait()
        log.close()
        text = (out / f"asrft.{lang}.log").read_text(errors="replace")
        for line in text.splitlines():
            if line.startswith("=== ASRFT") or "Error" in line:
                print(line, flush=True)
        print(f"=== ASRFT {lang} exit {code}", flush=True)
        summary = ft / lang / "asrft-summary.json"
        if summary.exists():
            print(f"=== ASRFT {lang} summary {json.dumps(json.loads(summary.read_text()))}")
    for name, models in (
        ("asr-base-forced", []),
        (
            "asr-ft-forced",
            [f"{lang}={ft / lang}" for lang in ("yo", "pcm") if (ft / lang).exists()],
        ),
    ):
        if name == "asr-ft-forced" and not models:
            print("run failed: no fine-tuned ASR model to evaluate", flush=True)
            continue
        dest = out / f"{name}.jsonl"
        sh(sys.executable, "-m", "bench.asr_run", "--targets", "data/asr/targets.v1.jsonl",
           "--split", "dev_pool", "--force-language", "--out", str(dest), "--workers", "16",
           *(["--models", *models] if models else []))  # fmt: skip
        if dest.exists():
            emit_file(dest)


if __name__ == "__main__":
    main()
    if PLAN == "checks_asrft":
        asr_finetune(WORK / "preds")
