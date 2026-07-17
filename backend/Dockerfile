# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage — install runtime dependencies into an isolated virtualenv.
# Build tooling (compilers) lives ONLY here so the final image stays slim.
# numpy/scipy/pandas normally ship 3.14 wheels; the toolchain is a fallback
# for any dependency that has to build from an sdist.
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
    && rm -rf /var/lib/apt/lists/*

# Everything installs into this venv, which we copy wholesale into the
# production stage — no build tools travel with it.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install the project (runtime deps only — no ".[dev]"). The build backend
# (hatchling) needs pyproject.toml + README.md + the app package present.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# ---------------------------------------------------------------------------
# Production stage — slim runtime with just the venv + app code, non-root.
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Bring over the prebuilt virtualenv and the application source.
COPY --from=build /opt/venv /opt/venv
COPY app ./app

# Run as an unprivileged user; DATA_DIR (uploads + SQLite) must be writable.
# The data dir is a mounted volume in production (see docker-compose.yml).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness for the container runtime (uses the app's own health route; python is
# already present, so no extra tooling). Traefik still routes independently.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health').read()"]

# Production server: no --reload, bind all interfaces so the frontend
# container can reach it over the shared network.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
