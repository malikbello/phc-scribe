"""Kaggle GPU job: committee pre-labelling of the counted test pool (ADR-0025).

Three open models from different families (bench.committee.MEMBERS) label the 600
test-pool transcripts with the same prompt, constrained decoding and grounding as every
evaluated system. No gated model is used, so the job needs no secrets and can be started
through the API (scripts/kaggle_push.py --kernel committee).

Only public clip ids travel (data/asr/targets.v1.jsonl); the transcripts are read from the
public WazobiaSpeech dataset on Kaggle. Each member's predictions go into the log as soon
as it finishes (scripts/kaggle_log.py --slug phc-scribe-committee --save ... restores them).
"""

import glob
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

WORK = Path("/kaggle/working")
SRC = Path(tempfile.mkdtemp())
REPO = SRC / "phc-scribe"

# "smoke": every member plus the reserve on a few items, to check loading, speed and
# validity on the T4s. "full": the three members on all 600 items.
PLAN = "smoke"
SMOKE_ITEMS = 16
BATCH = 8


def unpack() -> None:
    bundles = glob.glob("/kaggle/input/**/phc-scribe.tar.gz", recursive=True)
    if bundles:
        with tarfile.open(bundles[0]) as tar:
            tar.extractall(SRC, filter="data")
        return
    # Kaggle usually unpacks the archive when it builds the dataset version.
    trees = glob.glob("/kaggle/input/**/phc-scribe/pyproject.toml", recursive=True)
    if not trees:
        sys.exit("code bundle not found under /kaggle/input: attach the phc-scribe-code dataset")
    shutil.copytree(Path(trees[0]).parent, REPO)


def sh(*args: str) -> int:
    print("+", " ".join(args), flush=True)
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'serve'}:{REPO}"}
    return subprocess.call(args, cwd=REPO, env=env)  # noqa: S603 (fixed argv)


def emit_file(path: Path) -> None:
    """Put an output file into the log (gzip + base64); kaggle_log.py --save restores it."""
    import base64
    import gzip

    data = base64.b64encode(gzip.compress(path.read_bytes())).decode()
    print(f"=== FILE {path.name} ===", flush=True)
    for i in range(0, len(data), 4000):
        print(data[i : i + 4000], flush=True)
    print("=== END FILE ===", flush=True)


def invalid_summary(pred: Path) -> None:
    import collections
    import json

    rows = [json.loads(line) for line in pred.read_text().splitlines() if line.strip()]
    bad = [r for r in rows if r.get("record") is None]
    cut = sum(1 for r in bad if r.get("raw_output") and not r["raw_output"].rstrip().endswith("}"))
    kinds = collections.Counter((r.get("error") or "")[:60] for r in bad)
    lat = sorted(r["latency_ms"] for r in rows if r.get("latency_ms"))
    med = lat[len(lat) // 2] / 1000 if lat else 0
    print(
        f"=== INVALID {pred.stem}: {len(bad)}/{len(rows)}, cut off: {cut}, median {med:.1f} s/item",
        flush=True,
    )
    for kind, n in kinds.most_common(5):
        print(f"  {n:4d}  {kind}")


def drop_cache(repo_id: str) -> None:
    """Free disk between members (four 4-bit models are ~41 GB together)."""
    cache = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{repo_id.replace('/', '--')}"
    shutil.rmtree(cache, ignore_errors=True)


def main() -> None:
    t0 = time.time()
    unpack()
    sh(sys.executable, "-m", "pip", "install", "-q", "xgrammar", "bitsandbytes")
    sh(
        sys.executable,
        "-c",
        "import torch, transformers; print('torch', torch.__version__, 'transformers',"
        " transformers.__version__, 'gpus', torch.cuda.device_count())",
    )
    sys.path[:0] = [str(REPO / "serve"), str(REPO)]
    from bench.committee import MEMBERS, RESERVE

    out = WORK / "committee"
    out.mkdir(exist_ok=True)
    items = out / "committee.items.jsonl"
    if sh(sys.executable, "-m", "bench.committee", "fetch", "--targets",
          "data/asr/targets.v1.jsonl", "--out", str(items)) != 0:  # fmt: skip
        sys.exit("run failed: committee fetch")
    members = dict(MEMBERS)
    if PLAN == "smoke":
        members[RESERVE[0]] = RESERVE[1]
    for name, (model, revision) in members.items():
        pred = out / f"committee.{name}.jsonl"
        cmd = [
            sys.executable, "-m", "bench.runners.llm", "--model", model, "--revision", revision,
            "--mode", "fewshot", "--items", str(items), "--out", str(pred),
            "--batch-size", str(BATCH),
        ]  # fmt: skip
        if PLAN == "smoke":
            cmd += ["--limit", str(SMOKE_ITEMS)]
        started = time.time()
        code = sh(*cmd)
        print(f"=== MEMBER {name}: exit {code}, {time.time() - started:.0f}s", flush=True)
        if pred.exists():
            invalid_summary(pred)
            emit_file(pred)
        drop_cache(model)
    print(f"=== COMMITTEE job done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
