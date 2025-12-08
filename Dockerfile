# Build
FROM python:3.11-slim as builder

RUN pip install --no-cache-dir poetry==2.1.4
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false
RUN poetry install -n --no-root

# Runtime
FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ /app/app/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/
COPY entrypoint.sh /app/

# Fix line endings and make executable
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["/app/entrypoint.sh"]