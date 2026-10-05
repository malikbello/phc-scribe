"""G2 guardrail (eval plan §6): Belebele `yor_Latn`, base N-ATLaS vs the selected fine-tune.

    modal run deploy/modal_belebele.py --run natlas-qlora-v1-weighted-fs

Scores both models in parallel on the same 900 questions (zero-shot letter likelihood,
`bench/belebele.py`), then the 95% paired bootstrap CI of the accuracy difference. G2 passes
if the lower bound is at least -m, with m = 3 points (fixed 1 Oct). Writes
results/frozen/belebele.<name>.json and results/frozen/g2.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

APP_DIR = "/app"
MARGIN = 0.03  # m, eval plan §6 (measured 1 Oct: min(3 points, half the gain over Llama-3.1))
BASE = ("NCAIR1/N-ATLaS", "e294476928aca9030e924ca27bb8e085e8581273")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.8.0",
        "transformers>=4.56,<6",
        "peft>=0.17",
        "accelerate>=1.10",
        "datasets>=3.0",
        "numpy>=1.26",
        "pydantic>=2.8,<3",
        "pyyaml>=6.0",
    )
    .env({"PYTHONPATH": f"{APP_DIR}/serve:{APP_DIR}", "HF_HOME": "/cache/hf"})
    .add_local_dir("serve", f"{APP_DIR}/serve", ignore=["**/__pycache__"])
    .add_local_dir("bench", f"{APP_DIR}/bench", ignore=["**/__pycache__"])
    .add_local_dir("rules", f"{APP_DIR}/rules")
    .add_local_dir("schema", f"{APP_DIR}/schema")
)
app = modal.App("phc-scribe-belebele")
runs = modal.Volume.from_name("phc-scribe-runs", create_if_missing=True)
hf_cache = modal.Volume.from_name("phc-scribe-hf-cache", create_if_missing=True)


@app.function(
    image=image,
    gpu="A10G",
    secrets=[modal.Secret.from_name("phc-scribe-api")],
    volumes={"/runs": runs, "/cache": hf_cache},
    timeout=2 * 3600,
)
def belebele(run: str = "") -> dict:
    import subprocess
    import sys
    import tempfile

    out = Path(tempfile.mkdtemp()) / "belebele.json"
    cmd = [
        sys.executable,
        "-m",
        "bench.belebele",
        "--model",
        BASE[0],
        "--revision",
        BASE[1],
        "--out",
        str(out),
    ]
    if run:
        cmd += ["--adapter", f"/runs/{run}/adapter"]
    subprocess.run(cmd, cwd=APP_DIR, check=True)  # noqa: S603 (fixed argv)
    result = json.loads(out.read_text())
    keep = Path("/runs") / "_eval" / f"belebele-{run or 'base'}"
    keep.mkdir(parents=True, exist_ok=True)
    (keep / "result.json").write_text(json.dumps(result))
    runs.commit()
    hf_cache.commit()
    return result


@app.local_entrypoint()
def main(run: str, out: str = "results/frozen") -> None:
    import sys

    sys.path[:0] = ["serve", "."]
    from bench.stats import Ratio, paired_bootstrap_diff

    jobs = {"base": belebele.spawn(""), run: belebele.spawn(run)}
    results = {name: job.get() for name, job in jobs.items()}
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    for name, res in results.items():
        (dest / f"belebele.{name}.json").write_text(json.dumps(res, indent=1) + "\n")
    base, ft = results["base"]["items"], results[run]["items"]
    if len(base) != len(ft):
        raise SystemExit("different item counts")
    base_ok = [float(i["pred"] == i["gold"]) for i in base]
    ft_ok = [float(i["pred"] == i["gold"]) for i in ft]
    diff = paired_bootstrap_diff(
        Ratio.of(base_ok, [1.0] * len(base_ok)), Ratio.of(ft_ok, [1.0] * len(ft_ok))
    )
    g2 = {
        "base_accuracy": results["base"]["accuracy"],
        "finetuned_accuracy": results[run]["accuracy"],
        "difference": {"point": diff.point, "low": diff.low, "high": diff.high},
        "margin_m": MARGIN,
        "passes": diff.low >= -MARGIN,
        "n_items": len(base),
    }
    (dest / "g2.json").write_text(json.dumps(g2, indent=2) + "\n")
    print(json.dumps(g2, indent=2))
