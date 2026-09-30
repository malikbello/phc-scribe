# PHC Scribe API on a Hugging Face Docker Space (free CPU). The Space is private until
# submission; scripts/deploy_space.py refuses to publish it.
FROM python:3.12-slim

RUN useradd -m -u 1000 app
WORKDIR /app

# CPU-only torch keeps the image small; transformers runs the N-ATLaS ASR models.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir "transformers>=4.45,<6" "numpy>=1.26"

COPY --chown=app pyproject.toml README.md NOTICE ./
COPY --chown=app serve serve
COPY --chown=app bench bench
COPY --chown=app rules rules
COPY --chown=app schema schema
RUN pip install --no-cache-dir -e ".[api]"

USER app
ENV HF_HOME=/home/app/.cache/huggingface \
    PHC_ASR=hf \
    PHC_EXTRACTOR=keyword \
    PHC_DB=/tmp/phc_scribe.sqlite3
EXPOSE 7860
CMD ["uvicorn", "phc_scribe.api.app:app", "--host", "0.0.0.0", "--port", "7860"]
