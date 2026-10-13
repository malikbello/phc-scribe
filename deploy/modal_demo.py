"""The judges' sandbox API (NAIC 2026): the fine-tuned N-ATLaS on a GPU behind the /v1 API.

One T4 container runs llama.cpp with the shipped Q4_K_M GGUF and the clinic hub's settings
(an 8,192-token context, the chat template from the GGUF; llama.cpp b11382, five builds from
the hub's b11387) on localhost, and the /v1 API beside it. The model itself is never
reachable from outside. Speech is the int8 N-ATLaS ASR (ADR-0032) on the container's CPU.
Its regular caller is the Tákàdá demo hub (takada-app deploy/modal_demo_hub.py); the API key
is in the Modal secret "takada-demo".

Cost gate (free credits only): one container at most, it scales to zero after one idle
minute, and the demo hub caps AI drafts per phone and per day. The workspace spend limit
($0 out of pocket) stops everything before any charge.

    modal run deploy/modal_demo.py::fetch     # once: the GGUF and int8 speech models -> volume
    modal deploy deploy/modal_demo.py         # https://malikbello--phc-scribe-api-api.modal.run
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.request

import modal

# The clinic hub builds llama.cpp b11387 for CPU; b11382 is the nearest published CUDA image.
LLAMA_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda-b11382"
MODELS = "/models"

models = modal.Volume.from_name("takada-demo-models", create_if_missing=True)
image = (
    modal.Image.from_registry(LLAMA_IMAGE, add_python="3.12")
    .entrypoint([])
    .pip_install("torch>=2.4,<3", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install(
        "transformers>=4.45,<6",
        "numpy>=1.26",
        "pydantic>=2.8,<3",
        "pyyaml>=6.0",
        "fastapi>=0.115",
        "httpx>=0.27",
        "silero-vad==6.2.3",
        "ctranslate2>=4.5,<5",
        "huggingface_hub>=0.32",
    )
    .env(
        {
            "PYTHONPATH": "/app/serve:/app",
            "PHC_EXTRACTOR": "llamacpp",
            "PHC_LLAMACPP_URL": "http://127.0.0.1:8080",
            "PHC_LLAMACPP_TIMEOUT": "300",
            "PHC_ASR": "ct2",
            "PHC_ASR_INT8_MODELS": ",".join(
                f"{k}={MODELS}/asr-int8/{k}" for k in ("en", "yo", "pcm")
            ),
            "PHC_RATE_LIMIT_PER_MINUTE": "20",
            "PHC_DB": "/root/phc_scribe.sqlite3",  # container disk: resets with it (a demo)
            "HF_HOME": f"{MODELS}/hf",
        }
    )
    .add_local_dir("serve", "/app/serve", ignore=["**/__pycache__"])
    .add_local_dir("bench", "/app/bench", ignore=["**/__pycache__"])
    .add_local_dir("rules", "/app/rules")
    .add_local_dir("schema", "/app/schema")
    .add_local_file("tests/fixtures/smoke_items.jsonl", "/app/tests/fixtures/smoke_items.jsonl")
)

# The app name gives the address: the one in the NAIC form, malikbello--phc-scribe-api-api.modal.run
# (this replaces the earlier keyword-only API there, deploy/modal_app.py).
APP = os.environ.get("PHC_DEMO_APP", "phc-scribe-api")
app = modal.App(APP)


@app.function(
    image=image,
    volumes={MODELS: models},
    secrets=[modal.Secret.from_name("phc-scribe-api")],  # HF_TOKEN: the gated model repos
    cpu=2,
    memory=4096,
    timeout=3600,
)
def fetch() -> None:
    """The fine-tuned GGUF (checked against its manifest's SHA-256) and the int8 speech models."""
    for kind in ("gguf", "int8"):
        subprocess.run(  # noqa: S603 (fixed arguments)
            [sys.executable, "-m", "phc_scribe.fetch_models", "--dest", MODELS, "--only", kind],
            check=True,
        )
    models.commit()


@app.cls(
    image=image,
    gpu="T4",
    volumes={MODELS: models},
    secrets=[modal.Secret.from_name("takada-demo")],  # PHC_API_KEY_HASHES
    cpu=2,
    memory=6144,
    scaledown_window=60,
    max_containers=1,
    timeout=900,
)
@modal.concurrent(max_inputs=4)
class Api:
    @modal.enter()
    def start_model(self) -> None:
        server = shutil.which("llama-server") or "/app/llama-server"
        args = ["-m", f"{MODELS}/takada-anc.gguf", "--host", "127.0.0.1", "--port", "8080"]
        args += ["-c", "8192", "--jinja", "--no-webui", "--parallel", "1", "-ngl", "99"]
        self.llm = subprocess.Popen([server, *args])  # noqa: S603 (fixed arguments)
        deadline = time.time() + 300
        while time.time() < deadline:
            try:
                if urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2).status == 200:
                    return
            except Exception:
                time.sleep(1)
        raise RuntimeError("llama.cpp did not become healthy in 300 s")

    @modal.exit()
    def stop_model(self) -> None:
        self.llm.terminate()

    @modal.asgi_app(label=f"{APP}-api")
    def web(self):
        from phc_scribe.api.app import create_app

        return create_app()
