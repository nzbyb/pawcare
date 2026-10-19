#!/bin/sh
# Container entrypoint: apply migrations before serving traffic.
set -e

echo "[entrypoint] applying database migrations..."
python -m alembic upgrade head

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
