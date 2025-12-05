#!/bin/bash
set -e

echo "Waiting for postgres..."

# Wait for postgres to be ready
until python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect(host='$DB_HOST', port='$DB_PORT', user='$DB_USER', password='$DB_PASSWORD', database='$DB_NAME'))" 2>/dev/null; do
  echo "Postgres is unavailable - sleeping"
  sleep 1
done

echo "Postgres is up - running migrations"

# Run alembic migrations
alembic upgrade head

echo "Starting application"

# Start the FastAPI application
exec uvicorn src:app --host 0.0.0.0 --port 8000
