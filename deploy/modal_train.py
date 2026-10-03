"""Fine-tuning and dev evaluation on Modal GPUs (ADR-0024 runs B and C).

Why Modal as well as Kaggle: the gated N-ATLaS weights need HF_TOKEN, which Kaggle only
attaches to runs started by hand from its editor. Modal attaches the `phc-scribe-api`
secret to every run, so training and evaluation can start from the command line. It also
has faster GPUs (A10G, 24 GB, bfloat16-capable). Malik's free monthly credits pay for it.

    # smoke test (constructed fixtures only; safe before the freeze)
    modal run deploy/modal_train.py --smoke
    # a real run, after the stage-1 freeze and build_train_set.py
    modal run deploy/modal_train.py --config configs/qlora.v1-weighted.yaml \
        --train-file data/train/sft.v1.jsonl --dev data/train/sft.v1.dev.items.jsonl

Runs are saved on the `phc-scribe-runs` volume as /runs/<run_name>/{adapter, metrics.json,
dev reports}. Training data travels as function arguments into Malik's own Modal account
and is never baked into an image.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import modal

GPU = "A10G"
APP_DIR = "/app"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.8.0",
        "transformers>=4.56,<6",
        "peft>=0.17",
        "bitsandbytes>=0.47",
        "accelerate>=1.10",
        "xgrammar>=0.1.25",
        "numpy>=1.26",
        "pydantic>=2.8,<3",
        "pyyaml>=6.0",
    )
    .env({"PYTHONPATH": f"{APP_DIR}/serve:{APP_DIR}", "HF_HOME": "/cache/hf"})
    .add_local_dir("serve", f"{APP_DIR}/serve", ignore=["**/__pycache__"])
    .add_local_dir("bench", f"{APP_DIR}/bench", ignore=["**/__pycache__"])
    .add_local_dir("rules", f"{APP_DIR}/rules")
    .add_local_dir("schema", f"{APP_DIR}/schema")
    .add_local_dir("configs", f"{APP_DIR}/configs")
)

app = modal.App("phc-scribe-train")
runs = modal.Volume.from_name("phc-scribe-runs", create_if_missing=True)
hf_cache = modal.Volume.from_name("phc-scribe-hf-cache", create_if_missing=True)
SECRETS = [modal.Secret.from_name("phc-scribe-api")]  # HF_TOKEN
VOLUMES = {"/runs": runs, "/cache": hf_cache}


def _sh(*args: str) -> None:
    import subprocess

    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=APP_DIR, check=True)  # noqa: S603 (fixed argv)


@app.function(image=image, gpu=GPU, secrets=SECRETS, volumes=VOLUMES, timeout=4 * 3600)
def train(config_yaml: str, train_jsonl: str, max_steps: int = -1, suffix: str = "") -> dict:
    import yaml

    cfg = yaml.safe_load(config_yaml)
    data = Path(APP_DIR) / cfg["train_file"]
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text(train_jsonl, encoding="utf-8")
    cfg_path = Path(tempfile.mkdtemp()) / "config.yaml"
    cfg_path.write_text(config_yaml, encoding="utf-8")
    out = Path("/runs") / (cfg["run_name"] + suffix)
    _sh(
        "python",
        "-m",
        "bench.train_qlora",
        "--config",
        str(cfg_path),
        "--out",
        str(out),
        "--max-steps",
        str(max_steps),
    )
    runs.commit()
    hf_cache.commit()
    return json.loads((out / "metrics.json").read_text())


@app.function(image=image, gpu=GPU, secrets=SECRETS, volumes=VOLUMES, timeout=4 * 3600)
def evaluate(
    items_jsonl: str,
    name: str,
    model: str,
    revision: str,
    mode: str,
    run_name: str = "",
    repetition_penalty: float = 1.12,
    limit: int = 0,
) -> dict:
    """Score base (run_name empty) or fine-tuned (/runs/<run_name>/adapter) on dev items."""
    runs.reload()
    work = Path(tempfile.mkdtemp())
    items = work / "items.jsonl"
    items.write_text(items_jsonl, encoding="utf-8")
    pred = work / "pred.jsonl"
    cmd = [
        "python",
        "-m",
        "bench.runners.llm",
        "--model",
        model,
        "--revision",
        revision,
        "--mode",
        mode,
        "--items",
        str(items),
        "--out",
        str(pred),
        "--system",
        name,
        "--repetition-penalty",
        str(repetition_penalty),
    ]
    if run_name:
        cmd += ["--adapter", f"/runs/{run_name}/adapter"]
    if limit:
        cmd += ["--limit", str(limit)]
    _sh(*cmd)
    report = work / "report.json"
    _sh(
        "python",
        "-m",
        "bench.harness",
        "score",
        "--items",
        str(items),
        "--pred",
        str(pred),
        "--out",
        str(report),
    )
    if run_name:
        dest = Path("/runs") / run_name / f"dev.{name}.report.json"
        dest.write_text(report.read_text())
        runs.commit()
    hf_cache.commit()
    return {"report": json.loads(report.read_text()), "pred": pred.read_text(encoding="utf-8")}


def _smoke_data() -> tuple[str, str]:
    """SFT rows and items from the constructed smoke fixtures (never test data)."""
    import sys

    sys.path[:0] = ["serve", "."]
    from bench.items import BenchItem, read_jsonl
    from bench.sft import example

    items = list(read_jsonl(Path("tests/fixtures/smoke_items.jsonl"), BenchItem))
    rows = "".join(json.dumps(example(i), ensure_ascii=False) + "\n" for i in items)
    raw = "".join(i.model_dump_json(exclude_none=True) + "\n" for i in items[:4])
    return rows, raw


@app.local_entrypoint()
def main(
    config: str = "configs/qlora.v1-weighted.yaml",
    train_file: str = "",
    dev: str = "",
    smoke: bool = False,
    base: bool = True,
    out: str = "results/modal",
) -> None:
    import yaml

    config_yaml = Path(config).read_text(encoding="utf-8")
    cfg = yaml.safe_load(config_yaml)
    if smoke:
        train_rows, dev_items = _smoke_data()
        metrics = train.remote(config_yaml, train_rows, max_steps=3, suffix="-smoke")
        print("train metrics:", json.dumps(metrics))
        res = evaluate.remote(
            dev_items,
            "smoke-ft",
            cfg["model"],
            cfg["revision"],
            "finetuned",
            run_name=cfg["run_name"] + "-smoke",
        )
        print("smoke eval:", json.dumps(res["report"]["overall"].get("schema_valid_rate")))
        return
    if not train_file or not dev:
        raise SystemExit("--train-file and --dev are required (or --smoke)")
    metrics = train.remote(config_yaml, Path(train_file).read_text(encoding="utf-8"))
    print("train metrics:", json.dumps(metrics))
    dev_items = Path(dev).read_text(encoding="utf-8")
    jobs = {
        "ft": evaluate.spawn(
            dev_items,
            f"{cfg['run_name']}-dev",
            cfg["model"],
            cfg["revision"],
            "finetuned",
            run_name=cfg["run_name"],
        )
    }
    if base:
        jobs["base"] = evaluate.spawn(
            dev_items, "natlas-fewshot-rp1.12-dev", cfg["model"], cfg["revision"], "fewshot"
        )
    dest = Path(out) / cfg["run_name"]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    for key, job in jobs.items():
        res = job.get()
        (dest / f"dev.{key}.report.json").write_text(json.dumps(res["report"], indent=2) + "\n")
        o = res["report"]["overall"]
        keys = ("danger_recall", "micro_f1", "false_alarm_rate", "schema_valid_rate")
        print(key, {k: o[k].get("point") for k in keys})
