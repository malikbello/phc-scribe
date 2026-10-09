# The /v1 API as a container, for the Takada clinic hub (takada-app deploy/compose/hub.yml)
# and any other self-hosted run. Same code and dependencies as the Modal image
# (deploy/modal_app.py), on the CPU.
#
#   docker build -f deploy/api.Dockerfile -t phc-scribe-api:local .
#
# Models are never baked in: they come from a mounted volume (HF_HOME, PHC_ASR_MODELS, and the
# GGUF served by a separate llama.cpp container), so the image has no N-ATLaS weights in it
# and runs offline with HF_HUB_OFFLINE=1. Runs as a non-root user; records go to /data.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install "torch>=2.4,<3" --index-url https://download.pytorch.org/whl/cpu \
 && pip install \
      "transformers>=4.45,<6" \
      "numpy>=1.26" \
      "pydantic>=2.8,<3" \
      "pyyaml>=6.0" \
      "fastapi>=0.115" \
      "httpx>=0.27" \
      "uvicorn>=0.30" \
      "silero-vad==6.2.3"

# /models exists and belongs to scribe in the image, so a new named volume mounted there
# inherits that owner. Without it the volume is root-owned and fetch_models fails with
# "Permission denied: '/models/hf'" (found on the first laptop hub install, 9 Oct).
RUN useradd --create-home --uid 10001 scribe && mkdir /data /models && chown scribe /data /models
WORKDIR /app
COPY serve serve
COPY bench bench
COPY rules rules
COPY schema schema
# The few-shot prompt's examples (bench/prompts.py FEWSHOT_PATH): the shipped model was
# trained and evaluated with this prompt, so the drafting step cannot run without them.
COPY tests/fixtures/smoke_items.jsonl tests/fixtures/smoke_items.jsonl

ENV PYTHONPATH=/app/serve:/app \
    PHC_DB=/data/phc_scribe.sqlite3 \
    PHC_EXTRACTOR=keyword \
    PHC_ASR=off

USER scribe
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=4)"
CMD ["uvicorn", "phc_scribe.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
