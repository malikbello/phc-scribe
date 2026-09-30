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
# the guardrail margins before the freeze (docs/eval-plan.md, section 6).
PLAN = "pilot"
ITEM_SETS = {
    "baseline": ["tests/fixtures/smoke_items.jsonl", "data/bench/g.20261002.jsonl"],
    "pilot": ["data/bench/pilot.20261004.jsonl"],
}[PLAN]
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


def main() -> None:
    unpack()
    sh(sys.executable, "-m", "pip", "install", "-q", "xgrammar")
    token = hf_token()
    if token:
        os.environ["HF_TOKEN"] = token
    else:
        print("HF_TOKEN secret not attached: skipping gated N-ATLaS runs", flush=True)
    out = WORK / "preds"
    out.mkdir(exist_ok=True)
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


if __name__ == "__main__":
    main()
