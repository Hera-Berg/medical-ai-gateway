# Medical AI Gateway — backend image (Python 3.11 per spec).
# Multi-stage kept simple at scaffold stage; ML deps in later steps will benefit
# from a builder stage + wheel cache, noted inline when we add them.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; sentence-transformers/umap in later steps will add
# build-essential here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# ── Bake the FastEmbed model into the image at BUILD time ───────────────────
# Downloads ~77MB of ONNX weights into a fixed cache dir so first query at
# runtime is fast and works offline. FASTEMBED_CACHE_DIR (build) MUST match
# fastembed_cache_dir in app/config.py (runtime) or the model re-downloads.
ENV FASTEMBED_CACHE_DIR=/opt/fastembed_cache
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/opt/fastembed_cache')"

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# Healthcheck hits the liveness endpoint so docker/compose can report status.
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Stateless: safe to run as N replicas behind Nginx round-robin.
# Entrypoint runs migrations (advisory-locked) then launches uvicorn.
CMD ["./entrypoint.sh"]
