FROM python:3.12-slim

# System deps for docling (libGL) and health check (curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd -m --uid 1001 appuser

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install Python deps before copying source so this layer is cached
COPY pyproject.toml ./
RUN uv pip install --system --no-cache torch --extra-index-url https://download.pytorch.org/whl/cpu
RUN uv pip install --system --no-cache -e .

# Copy application source
COPY vectraiq/ ./vectraiq/
COPY scripts/ ./scripts/
COPY seed/ ./seed/

# Give appuser ownership
RUN chown -R appuser:appuser /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/admin/health || exit 1

CMD ["python", "scripts/serve.py"]
