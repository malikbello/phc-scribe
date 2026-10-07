"""The /v1 API on Modal (ADR-0017). Deployed by .github/workflows/deploy-modal.yml.

- CPU container (1 core, 3 GiB): the API, the rules engine and the N-ATLaS ASR models.
  The fine-tuned N-ATLaS extractor is added as a GPU function once it is trained.
- Scales to zero: it uses credits only while requests are being served.
- Private until submission: requires_proxy_auth means every request also needs a Modal
  proxy-auth token (Modal-Key / Modal-Secret headers), on top of our own API key.
- Records live on the container disk, so they reset when it stops (fine for the demo).
"""

import modal

PRIVATE = True  # set to False on submission day (ADR-0017)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install(
        "transformers>=4.45,<6",
        "numpy>=1.26",
        "pydantic>=2.8,<3",
        "pyyaml>=6.0",
        "fastapi>=0.115",
        "httpx>=0.27",
    )
    .env(
        {
            "PYTHONPATH": "/app/serve:/app",
            "PHC_ASR": "hf",
            "PHC_EXTRACTOR": "keyword",
            "PHC_DB": "/root/phc_scribe.sqlite3",  # container disk: resets on restart
            "HF_HOME": "/cache/hf",
        }
    )
    .add_local_dir("serve", "/app/serve", ignore=["**/__pycache__"])
    .add_local_dir("bench", "/app/bench", ignore=["**/__pycache__"])
    .add_local_dir("rules", "/app/rules")
    .add_local_dir("schema", "/app/schema")
    # few-shot examples for the llama.cpp extractor's prompt (bench/prompts.py FEWSHOT_PATH)
    .add_local_file("tests/fixtures/smoke_items.jsonl", "/app/tests/fixtures/smoke_items.jsonl")
)

app = modal.App("phc-scribe-api")
hf_cache = modal.Volume.from_name("phc-scribe-hf-cache", create_if_missing=True)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("phc-scribe-api")],  # HF_TOKEN, PHC_API_KEY_HASHES
    volumes={"/cache": hf_cache},  # ASR weights survive restarts
    cpu=1,
    memory=3072,
    scaledown_window=300,
    max_containers=1,
    timeout=600,
)
@modal.asgi_app(requires_proxy_auth=PRIVATE)
def api():
    from phc_scribe.api.app import create_app

    return create_app()
