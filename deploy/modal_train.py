"""Fine-tuning and dev evaluation on Modal GPUs (ADR-0024 runs B and C).

Why Modal as well as Kaggle: the gated N-ATLaS weights need HF_TOKEN, which Kaggle only
attaches to runs started by hand from its editor. Modal attaches the `phc-scribe-api`
secret to every run, so training and evaluation can start from the command line. It also
has faster GPUs (A10G, 24 GB, bfloat16-capable). Malik's free monthly credits pay for it.

    # smoke test (constructed fixtures only; safe before the freeze)
    modal run deploy/modal_train.py::main --smoke
    # a real run, after the stage-1 freeze and build_train_set.py
    modal run deploy/modal_train.py::main --config configs/qlora.v1-weighted.yaml \
        --train-file data/train/sft.v1.jsonl --dev data/train/sft.v1.dev.items.jsonl

    # score saved adapters (and optionally base) on dev or pilot items, at LoRA scale s
    modal run deploy/modal_train.py::eval_runs --items data/bench/pilot.20261004.jsonl \
        --runs natlas-qlora-v1-weighted --scale 0.75 --tag pilot-s0.75 [--base]

Two entrypoints live here, so `modal run` needs `::main` or `::eval_runs`.
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
    .add_local_dir("tests/fixtures", f"{APP_DIR}/tests/fixtures")  # few-shot examples
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
    adapter_scale: float = 1.0,
    batch_size: int = 1,
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
        cmd += ["--adapter", f"/runs/{run_name}/adapter", "--adapter-scale", str(adapter_scale)]
    if limit:
        cmd += ["--limit", str(limit)]
    if batch_size > 1:
        cmd += ["--batch-size", str(batch_size)]
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
    # Every evaluation is kept on the volume, so a dropped client connection loses nothing.
    keep = Path("/runs") / "_eval" / name
    keep.mkdir(parents=True, exist_ok=True)
    (keep / "report.json").write_text(report.read_text())
    (keep / "pred.jsonl").write_text(pred.read_text(encoding="utf-8"), encoding="utf-8")
    if run_name:
        dest = Path("/runs") / run_name / f"dev.{name}.report.json"
        dest.write_text(report.read_text())
    runs.commit()
    hf_cache.commit()
    return {"report": json.loads(report.read_text()), "pred": pred.read_text(encoding="utf-8")}


@app.function(image=image, gpu=GPU, secrets=SECRETS, volumes=VOLUMES, timeout=2 * 3600)
def synth(prompts_jsonl: str, model: str, revision: str, attempts: int = 2) -> str:
    """ADR-0028: base N-ATLaS writes the sentences, rule checks filter them, and N-ATLaS
    classifies each kept sentence again from scratch (round trip). Returns one JSON line per
    prompt: text, rule failure, round-trip class and whether it is kept."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from bench.synth import (
        classification_messages,
        clean,
        generation_messages,
        parse_class,
        rule_check,
    )

    torch.manual_seed(20261013)
    tok = AutoTokenizer.from_pretrained(model, revision=revision)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    lm = AutoModelForCausalLM.from_pretrained(
        model, revision=revision, dtype=torch.bfloat16, device_map="cuda"
    )
    lm.eval()

    def run(batch_msgs, sample: bool, max_new: int) -> list[str]:
        enc = tok.apply_chat_template(
            batch_msgs,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            padding=True,
        ).to(lm.device)
        with torch.no_grad():
            out = lm.generate(
                **enc,
                max_new_tokens=max_new,
                do_sample=sample,
                temperature=0.8 if sample else None,
                top_p=0.95 if sample else None,
                pad_token_id=tok.pad_token_id,
            )
        return tok.batch_decode(out[:, enc["input_ids"].shape[1] :], skip_special_tokens=True)

    rows = [json.loads(x) for x in prompts_jsonl.splitlines() if x.strip()]
    pending = list(range(len(rows)))
    for attempt in range(attempts):
        for start in range(0, len(pending), 32):
            idx = pending[start : start + 32]
            texts = run([generation_messages(rows[i]) for i in idx], sample=True, max_new=70)
            for i, t in zip(idx, texts, strict=True):
                rows[i]["text"] = clean(t)
                rows[i]["rule_fail"] = rule_check(rows[i], rows[i]["text"])
                rows[i]["attempt"] = attempt
        checkable = [i for i in pending if rows[i]["rule_fail"] is None]
        for start in range(0, len(checkable), 32):
            idx = checkable[start : start + 32]
            outs = run(
                [classification_messages(rows[i], rows[i]["text"]) for i in idx],
                sample=False,
                max_new=6,
            )
            for i, o in zip(idx, outs, strict=True):
                rows[i]["class"] = parse_class(o)
        for i in pending:
            want = rows[i]["assertion"] or "none"
            rows[i]["kept"] = rows[i]["rule_fail"] is None and rows[i].get("class") == want
        pending = [i for i in pending if not rows[i]["kept"]]
        print(f"attempt {attempt}: {len(rows) - len(pending)} of {len(rows)} kept", flush=True)
    hf_cache.commit()
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


@app.function(image=image, gpu=GPU, secrets=SECRETS, volumes=VOLUMES, timeout=2 * 3600)
def translate(rows_jsonl: str, model: str, revision: str) -> str:
    """ADR-0028 amendment: translate curated English sentences into Yoruba and Pidgin with
    N-ATLaS (greedy), back-translate to English, and keep a translation only if it passes the
    target-language rules, and the back-translation passes the English rules and still names
    the symptom."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from bench.synth import LANGS, clean, rule_check
    from bench.synth_curate import concept_named

    tok = AutoTokenizer.from_pretrained(model, revision=revision)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    lm = AutoModelForCausalLM.from_pretrained(
        model, revision=revision, dtype=torch.bfloat16, device_map="cuda"
    )
    lm.eval()

    def run(prompts: list[str]) -> list[str]:
        outs: list[str] = []
        for start in range(0, len(prompts), 32):
            msgs = [
                [
                    {"role": "system", "content": "You are a careful medical translator."},
                    {"role": "user", "content": q},
                ]
                for q in prompts[start : start + 32]
            ]
            enc = tok.apply_chat_template(
                msgs,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
                padding=True,
            ).to(lm.device)
            with torch.no_grad():
                out = lm.generate(
                    **enc, max_new_tokens=90, do_sample=False, pad_token_id=tok.pad_token_id
                )
            outs += [
                clean(t)
                for t in tok.batch_decode(
                    out[:, enc["input_ids"].shape[1] :], skip_special_tokens=True
                )
            ]
        return outs

    rows = [json.loads(x) for x in rows_jsonl.splitlines() if x.strip()]
    result = []
    for target in ("yo", "pcm"):
        name = "Yoruba" if target == "yo" else "Nigerian Pidgin"
        forward = run(
            [
                f"Translate into {LANGS[target]}. Keep the meaning exactly, including words for "
                f"'not', 'maybe', 'last pregnancy', 'very bad' or 'slight'. Reply with the "
                f"translation only.\n\n{r['text']}"
                for r in rows
            ]
        )
        back = run(
            [
                f"Translate this {name} sentence into English. Reply with the translation only."
                f"\n\n{t}"
                for t in forward
            ]
        )
        for r, t, b in zip(rows, forward, back, strict=True):
            row = {**r, "language": target, "text": t, "back": b, "source": r["text"]}
            fail = (
                rule_check(row, t)
                or (None if rule_check({**row, "language": "en"}, b) is None else "back_rules")
                or (None if concept_named(r["concept"], b) else "back_concept")
            )
            row["rule_fail"], row["kept"] = fail, fail is None
            result.append(row)
        print(
            f"{target}: kept {sum(x['kept'] for x in result if x['language'] == target)} "
            f"of {len(rows)}",
            flush=True,
        )
    hf_cache.commit()
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in result)


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
    synth_prompts: str = "",
    synth_out: str = "",
    translate_in: str = "",
    translate_out: str = "",
) -> None:
    import yaml

    config_yaml = Path(config).read_text(encoding="utf-8")
    cfg = yaml.safe_load(config_yaml)
    if translate_in:
        result = translate.remote(
            Path(translate_in).read_text(encoding="utf-8"), cfg["model"], cfg["revision"]
        )
        Path(translate_out).write_text(result, encoding="utf-8")
        rows = [json.loads(x) for x in result.splitlines() if x.strip()]
        print("translate: kept", sum(r["kept"] for r in rows), "of", len(rows), "->", translate_out)
        return
    if synth_prompts:
        result = synth.remote(
            Path(synth_prompts).read_text(encoding="utf-8"), cfg["model"], cfg["revision"]
        )
        Path(synth_out).parent.mkdir(parents=True, exist_ok=True)
        Path(synth_out).write_text(result, encoding="utf-8")
        rows = [json.loads(x) for x in result.splitlines() if x.strip()]
        print("synth: kept", sum(r["kept"] for r in rows), "of", len(rows), "->", synth_out)
        return
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
            cfg.get("eval_mode", "finetuned"),
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


@app.local_entrypoint()
def eval_runs(
    items: str,
    runs: str = "",
    base: bool = False,
    config: str = "configs/qlora.v1-weighted.yaml",
    out: str = "results/modal",
    tag: str = "pilot",
    mode: str = "finetuned",
    scale: float = 1.0,
    batch: int = 1,
) -> None:
    """Score saved adapters (comma-separated run names) and optionally the base model on any
    non-test items (dev or pilot), in parallel. `mode` is the adapters' prompt mode; `scale`
    is the LoRA scale s (ADR-0024)."""
    import yaml

    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    text = Path(items).read_text(encoding="utf-8")
    jobs = {
        r: evaluate.spawn(
            text,
            f"{r}-{tag}",
            cfg["model"],
            cfg["revision"],
            mode,
            run_name=r,
            adapter_scale=scale,
            batch_size=batch,
        )
        for r in runs.split(",")
        if r
    }
    if base:
        jobs["base"] = evaluate.spawn(
            text,
            f"natlas-fewshot-rp1.12-{tag}",
            cfg["model"],
            cfg["revision"],
            "fewshot",
            batch_size=batch,
        )
    for name, job in jobs.items():
        res = job.get()
        dest = Path(out) / name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{tag}.report.json").write_text(json.dumps(res["report"], indent=2) + "\n")
        (dest / f"{tag}.pred.jsonl").write_text(res["pred"], encoding="utf-8")
        o = res["report"]["overall"]
        keys = ("danger_recall", "micro_f1", "false_alarm_rate", "schema_valid_rate")
        print(name, {k: o[k].get("point") for k in keys})
