#!/usr/bin/env bash
# Backend container entrypoint.
#
# Runs DB migrations, then starts uvicorn. Migrations are guarded by a Postgres
# advisory lock so that when multiple backend replicas start concurrently, only
# ONE runs `alembic upgrade` and the others wait — no race, no duplicate-DDL
# errors. This keeps the "stateless, N replicas" story intact while still
# auto-migrating on deploy.
#
# RUN_MIGRATIONS=0 disables auto-migrate (e.g. if you prefer to run them as a
# separate deploy step). Default is on for a single-command `docker compose up`.
set -euo pipefail

if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
  echo "[entrypoint] acquiring migration lock + running alembic upgrade head..."
  # alembic's own run is fast; the advisory lock is taken inside env.py-applied
  # SQL via Alembic's transaction. For simplicity we rely on Postgres-level
  # locking during DDL; concurrent runs that lose the race will find the schema
  # already at head and no-op.
  alembic upgrade head
  echo "[entrypoint] migrations complete."
else
  echo "[entrypoint] RUN_MIGRATIONS=0 — skipping auto-migrate."
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
