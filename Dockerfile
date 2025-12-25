# ByteGo Dockerfile - Multi-stage build with uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY main.py index.html ./

# Runtime stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install ca-certificates for HTTPS
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application files
COPY main.py index.html ./
COPY gunicorn.conf.py ./

# Create non-root user
RUN useradd -m -u 1000 bytego && \
    chown -R bytego:bytego /app

USER bytego

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"]

# Run with gunicorn
CMD ["/app/.venv/bin/gunicorn", "-c", "gunicorn.conf.py", "main:app"]
