"""Build and evaluate the shipped artefact: merged N-ATLaS, GGUF, imatrix Q4_K_M, served by
llama.cpp (ADR-0024 steps 5-6; eval plan §6a, audit C3).

    # build the Q4 model of a run (or "base" for the base model, for the 2x2)
    modal run deploy/modal_gguf.py::build_main --run natlas-qlora-v1-weighted-fs \
        --calib data/private/train/sft.v1fs.jsonl
    # evaluate it on non-test items (dev, pilot) or, after model selection, the frozen tests
    modal run deploy/modal_gguf.py::eval_main --run natlas-qlora-v1-weighted-fs --mode fewshot \
        --items data/bench/pilot.20261004.jsonl --tag pilot
    # Tier 2 (ADR-0032 step 2): 3-bit variants, scored with the Q4 on dev and pilot only
    modal run --detach deploy/modal_gguf.py::lite_spawn --run natlas-qlora-v1-weighted-fs \
        --calib data/private/train/sft.v1fs.jsonl --dev data/private/train/sft.v1.dev.items.jsonl \
        --pilot data/bench/pilot.20261004.jsonl

The importance matrix is computed on TRAINING text only (prompts and answers from the
training set), never on test items. Artefacts land on the `phc-scribe-runs` volume under
/runs/<run>/gguf/ with a manifest (llama.cpp commit, file sizes, SHA-256).
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

APP_DIR = "/app"
CUDA_ARCH = "86;89"  # A10G, L4

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "cmake", "build-essential")
    .run_commands(
        "git clone --depth 1 https://github.com/ggml-org/llama.cpp /llama.cpp",
        "cd /llama.cpp && git rev-parse HEAD > /llama.cpp/COMMIT",
        "cd /llama.cpp && cmake -B build -DGGML_CUDA=ON -DGGML_CUDA_NO_VMM=ON -DLLAMA_CURL=OFF "
        "-DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_UI=OFF "
        f"-DCMAKE_CUDA_ARCHITECTURES='{CUDA_ARCH}' "
        "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined "
        "&& cmake --build build --config Release -j 8 "
        "--target llama-server llama-quantize llama-imatrix",
    )
    .pip_install(
        "torch==2.8.0",
        "transformers>=4.56,<6",
        "peft>=0.17",
        "accelerate>=1.10",
        "sentencepiece",
        "protobuf",
        "numpy",
        "pydantic>=2.8,<3",
        "pyyaml",
        "httpx",
        "xgrammar>=0.1.25",
    )
    .run_commands("pip install /llama.cpp/gguf-py")
    .env({"PYTHONPATH": f"{APP_DIR}/serve:{APP_DIR}", "HF_HOME": "/cache/hf"})
    .add_local_dir("serve", f"{APP_DIR}/serve", ignore=["**/__pycache__"])
    .add_local_dir("bench", f"{APP_DIR}/bench", ignore=["**/__pycache__"])
    .add_local_dir("rules", f"{APP_DIR}/rules")
    .add_local_dir("schema", f"{APP_DIR}/schema")
    .add_local_dir("configs", f"{APP_DIR}/configs")
    .add_local_dir("tests/fixtures", f"{APP_DIR}/tests/fixtures")
)

app = modal.App("phc-scribe-gguf")
runs = modal.Volume.from_name("phc-scribe-runs", create_if_missing=True)
hf_cache = modal.Volume.from_name("phc-scribe-hf-cache", create_if_missing=True)
SECRETS = [modal.Secret.from_name("phc-scribe-api")]
VOLUMES = {"/runs": runs, "/cache": hf_cache}
BASE = ("NCAIR1/N-ATLaS", "e294476928aca9030e924ca27bb8e085e8581273")
BIN = "/llama.cpp/build/bin"


def _sh(*args: str) -> None:
    import subprocess

    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True)  # noqa: S603 (fixed argv)


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


@app.function(
    image=image,
    gpu="A10G",
    secrets=SECRETS,
    volumes=VOLUMES,
    timeout=4 * 3600,
)
def build(run: str, calib_text: str, scale: float = 1.0, quants: str = "Q4_K_M") -> dict:
    import shutil

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # Scratch (merged weights ~16 GB, f16 GGUF ~16 GB) on the runs volume, removed at the end.
    work = Path("/runs") / run / "gguf-work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    merged = work / "merged"
    model_id, revision = BASE
    tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
    lm = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, dtype=torch.float16)
    if run != "base":
        from peft import PeftModel

        lm = PeftModel.from_pretrained(lm, f"/runs/{run}/adapter")
        if scale != 1.0:
            for module in lm.modules():
                scaling = getattr(module, "scaling", None)
                if isinstance(scaling, dict):
                    module.scaling = {k: v * scale for k, v in scaling.items()}
        lm = lm.merge_and_unload()
    lm.save_pretrained(merged, safe_serialization=True)
    tok.save_pretrained(merged)
    del lm
    f16 = work / "model.f16.gguf"
    _sh(
        "python",
        "/llama.cpp/convert_hf_to_gguf.py",
        str(merged),
        "--outtype",
        "f16",
        "--outfile",
        str(f16),
    )
    shutil.rmtree(merged)
    calib = work / "calib.txt"
    calib.write_text(calib_text, encoding="utf-8")
    imatrix = work / "imatrix.dat"
    _sh(
        f"{BIN}/llama-imatrix",
        "-m",
        str(f16),
        "-f",
        str(calib),
        "-o",
        str(imatrix),
        "-ngl",
        "99",
        "-c",
        "512",
    )
    out_dir = Path("/runs") / run / "gguf"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = run if scale == 1.0 else f"{run}-s{scale:g}"
    manifests = {}
    for quant in quants.split(","):
        gguf = out_dir / f"{tag}.{quant}.gguf"
        _sh(f"{BIN}/llama-quantize", "--imatrix", str(imatrix), str(f16), str(gguf), quant)
        manifest = {
            "run": run,
            "scale": scale,
            "base": {"model": model_id, "revision": revision},
            "llama_cpp_commit": Path("/llama.cpp/COMMIT").read_text().strip(),
            "quant": quant,
            "imatrix_from": "training text only",
            "file": gguf.name,
            "bytes": gguf.stat().st_size,
            "sha256": _sha256(gguf),
        }
        # The shipped Q4 keeps its manifest name (serve/phc_scribe/fetch_models.py reads it).
        name = f"{tag}.manifest.json" if quant == "Q4_K_M" else f"{tag}.{quant}.manifest.json"
        (out_dir / name).write_text(json.dumps(manifest, indent=2) + "\n")
        manifests[quant] = manifest
    shutil.rmtree(work, ignore_errors=True)
    runs.commit()
    hf_cache.commit()
    return manifests["Q4_K_M"] if list(manifests) == ["Q4_K_M"] else manifests


@app.function(image=image, gpu="A10G", volumes=VOLUMES, timeout=3 * 3600)
def evaluate(
    run: str, items_jsonl: str, mode: str, system: str, scale: float = 1.0, quant: str = "Q4_K_M"
) -> dict:
    import os
    import subprocess
    import sys
    import tempfile
    import time

    import httpx

    runs.reload()
    tag = run if scale == 1.0 else f"{run}-s{scale:g}"
    q4 = Path("/runs") / run / "gguf" / f"{tag}.{quant}.gguf"
    server = subprocess.Popen(  # noqa: S603 (fixed argv)
        [
            f"{BIN}/llama-server",
            "-m",
            str(q4),
            "-ngl",
            "99",
            "-c",
            "8192",
            "--port",
            "8080",
            "--jinja",
            "--no-webui",
        ],
    )
    try:
        for _ in range(180):
            try:
                if httpx.get("http://127.0.0.1:8080/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(2)
        work = Path(tempfile.mkdtemp())
        items, pred, report = work / "items.jsonl", work / "pred.jsonl", work / "report.json"
        items.write_text(items_jsonl, encoding="utf-8")
        env = {"PYTHONPATH": f"{APP_DIR}/serve:{APP_DIR}"}
        subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "bench.runners.llamacpp",
                "--system",
                system,
                "--mode",
                mode,
                "--items",
                str(items),
                "--out",
                str(pred),
            ],
            cwd=APP_DIR,
            env={**os.environ, **env},
            check=True,
        )
        subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "bench.harness",
                "score",
                "--items",
                str(items),
                "--pred",
                str(pred),
                "--out",
                str(report),
            ],
            cwd=APP_DIR,
            env={**os.environ, **env},
            check=True,
        )
    finally:
        server.terminate()
    keep = Path("/runs") / "_eval" / system  # kept even if the client disconnects
    keep.mkdir(parents=True, exist_ok=True)
    (keep / "report.json").write_text(report.read_text())
    (keep / "pred.jsonl").write_text(pred.read_text(encoding="utf-8"), encoding="utf-8")
    runs.commit()
    return {"report": json.loads(report.read_text()), "pred": pred.read_text(encoding="utf-8")}


LITE_METRICS = ("danger_recall", "micro_f1", "false_alarm_rate", "schema_valid_rate")


@app.function(image=image, volumes=VOLUMES, timeout=12 * 3600)
def lite_pipeline(run: str, calib_text: str, sets: dict[str, str], quants: str) -> dict:
    """ADR-0032 step 2: build 3-bit variants with the same training-text imatrix, then score
    them beside the shipped Q4 (same llama.cpp, same prompt) on non-test items only."""
    built = build.remote(run, calib_text, 1.0, quants)
    calls = [
        (q, tag, evaluate.spawn(run, items, "fewshot", f"{run}-{q.lower()}-{tag}", 1.0, q))
        for q in ["Q4_K_M", *quants.split(",")]
        for tag, items in sets.items()
    ]
    summary: dict = {"run": run, "sets": {t: len(i.splitlines()) for t, i in sets.items()}}
    summary["scores"] = {}
    for q, tag, call in calls:
        overall = call.get()["report"]["overall"]
        summary["scores"].setdefault(q, {})[tag] = {k: overall[k] for k in LITE_METRICS}
    q4 = Path("/runs") / run / "gguf" / f"{run}.Q4_K_M.gguf"
    summary["bytes"] = {"Q4_K_M": q4.stat().st_size, **{q: m["bytes"] for q, m in built.items()}}
    keep = Path("/runs") / "_eval" / f"{run}-lite"
    keep.mkdir(parents=True, exist_ok=True)
    (keep / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    runs.commit()
    return summary


def _calibration(train_file: str, limit: int = 300) -> str:
    """Prompts and answers from the training set (never test items) for the importance matrix."""
    rows = [json.loads(x) for x in Path(train_file).read_text(encoding="utf-8").splitlines() if x]
    chunks = []
    for r in rows[:limit]:
        chunks.append("\n".join(m["content"] for m in r["messages"][-2:]))
    return "\n\n".join(chunks)


@app.local_entrypoint()
def build_main(run: str, calib: str, scale: float = 1.0) -> None:
    print(json.dumps(build.remote(run, _calibration(calib), scale), indent=2))


@app.local_entrypoint()
def eval_main(
    run: str,
    items: str,
    mode: str = "fewshot",
    tag: str = "pilot",
    scale: float = 1.0,
    out: str = "results/modal",
) -> None:
    system = f"{run}-q4{'' if scale == 1.0 else f'-s{scale:g}'}-{tag}"
    res = evaluate.remote(run, Path(items).read_text(encoding="utf-8"), mode, system, scale)
    dest = Path(out) / f"{run}-q4"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{tag}.report.json").write_text(json.dumps(res["report"], indent=2) + "\n")
    (dest / f"{tag}.pred.jsonl").write_text(res["pred"], encoding="utf-8")
    o = res["report"]["overall"]
    keys = ("danger_recall", "micro_f1", "false_alarm_rate", "schema_valid_rate")
    print(system, {k: o[k].get("point") for k in keys})


@app.local_entrypoint()
def eval_spawn(run: str, items: str, mode: str = "fewshot", tag: str = "pilot", scale: float = 1.0):
    """Start the evaluation and return at once (use with `modal run --detach`).

    For slow or unstable connections: the laptop's link to Modal is not held open for the
    whole run, so a dropped connection cannot stop it. Results land on the runs volume in
    /runs/_eval/<system>/ (report.json, pred.jsonl); fetch them with `modal volume get`.
    """
    system = f"{run}-q4{'' if scale == 1.0 else f'-s{scale:g}'}-{tag}"
    call = evaluate.spawn(run, Path(items).read_text(encoding="utf-8"), mode, system, scale)
    print(f"{system}: started ({call.object_id}); results in /runs/_eval/{system}/")


@app.local_entrypoint()
def lite_spawn(run: str, calib: str, dev: str, pilot: str, quants: str = "Q3_K_M,IQ3_M"):
    """Start the Tier 2 note-model check and return at once (use with `modal run --detach`).
    Results: /runs/_eval/<run>-lite/summary.json. Dev and pilot only, never a frozen set."""
    sets = {t: Path(f).read_text(encoding="utf-8") for t, f in (("dev", dev), ("pilot", pilot))}
    call = lite_pipeline.spawn(run, _calibration(calib), sets, quants)
    print(f"{run}: lite build and check started ({call.object_id}); see /runs/_eval/{run}-lite/")
