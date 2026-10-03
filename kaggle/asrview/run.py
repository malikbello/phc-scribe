"""Kaggle GPU job: the ASR view of the LLM's training clips, from the shipped ASR (ADR-0024
two-view data; ADR-0026 models).

The fine-tuned N-ATLaS ASR models come from the `phc-scribe-baseline` run's output (attached
as a kernel source), so nothing is uploaded and no secret is needed. The 460 training clips
(`split == "train"` in data/asr/targets.v1.jsonl) were held out of the ASR fine-tune, so
their transcripts here are out-of-sample. Output: asr-ft-train.jsonl in the log
(scripts/kaggle_log.py --slug phc-scribe-asrview --save ... restores it).
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
SRC = Path(tempfile.mkdtemp())
REPO = SRC / "phc-scribe"


def unpack() -> None:
    bundles = glob.glob("/kaggle/input/**/phc-scribe.tar.gz", recursive=True)
    if bundles:
        with tarfile.open(bundles[0]) as tar:
            tar.extractall(SRC, filter="data")
        return
    trees = glob.glob("/kaggle/input/**/phc-scribe/pyproject.toml", recursive=True)
    if not trees:
        sys.exit("code bundle not found under /kaggle/input: attach the phc-scribe-code dataset")
    shutil.copytree(Path(trees[0]).parent, REPO)


def emit_file(path: Path) -> None:
    import base64
    import gzip

    data = base64.b64encode(gzip.compress(path.read_bytes())).decode()
    print(f"=== FILE {path.name} ===", flush=True)
    for i in range(0, len(data), 4000):
        print(data[i : i + 4000], flush=True)
    print("=== END FILE ===", flush=True)


def main() -> None:
    unpack()
    models = {}
    for lang in ("yo", "pcm"):
        found = glob.glob(f"/kaggle/input/**/asr-ft/{lang}/config.json", recursive=True)
        if not found:
            sys.exit(f"fine-tuned {lang} model not found: attach the phc-scribe-baseline output")
        models[lang] = str(Path(found[0]).parent)
        print(f"=== ASRVIEW {lang} model: {models[lang]}", flush=True)
    dest = WORK / "asr-ft-train.jsonl"
    cmd = [sys.executable, "-m", "bench.asr_run", "--targets", "data/asr/targets.v1.jsonl",
           "--split", "train", "--force-language", "--out", str(dest), "--workers", "16",
           "--models", *(f"{k}={v}" for k, v in models.items())]  # fmt: skip
    print("+", " ".join(cmd), flush=True)
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'serve'}:{REPO}"}
    code = subprocess.call(cmd, cwd=REPO, env=env)  # noqa: S603 (fixed argv)
    if dest.exists():
        emit_file(dest)
    print(f"=== ASRVIEW done (exit {code})", flush=True)


if __name__ == "__main__":
    main()
