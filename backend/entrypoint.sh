#!/usr/bin/env bash
set -euo pipefail

if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
  echo "[entrypoint] acquiring migration lock + running alembic upgrade head..."
  alembic upgrade head
  echo "[entrypoint] migrations complete."
else
  echo "[entrypoint] RUN_MIGRATIONS=0 — skipping auto-migrate."
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
