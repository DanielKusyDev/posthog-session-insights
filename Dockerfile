# Build
FROM python:3.11-slim as builder

RUN pip install --no-cache-dir poetry==2.1.4
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false
RUN poetry install -n --no-root --with dev

# Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ /app/src/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/

# Copy entrypoint script and fix line endings
COPY entrypoint.sh /app/
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh # sed needed on windows

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["/app/entrypoint.sh"]
