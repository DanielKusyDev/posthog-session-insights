#!/bin/bash
# entrypoint.sh

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting FastAPI server..."
exec uvicorn app:app --host 0.0.0.0 --port 8000