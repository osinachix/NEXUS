# NEXUS API - production-oriented container image (Phase 7).
#
# This is a deployment wrapper, not a second runtime: the container's only
# job is to run `uvicorn api:app`, the exact ASGI app object api.py already
# defines. All startup behavior -- configuration validation, runtime/
# checkpointer construction, rate limiter setup, agent registry -- happens
# inside api.py's existing `lifespan()`. Nothing here duplicates or
# reimplements that. See ARCHITECTURE.md's Phase 7 section for the full
# environment variable reference and README.md "Running with Docker".
#
# Two-stage build: dependencies are installed in a throwaway builder stage
# so the final image carries no compiler toolchain or pip cache.

FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements-docker.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-docker.txt

FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="nexus-api" \
      org.opencontainers.image.description="NEXUS AI Agent Runtime & Orchestration Platform - API"

# Non-root execution. No shell login, no home-directory assumptions beyond
# /app (which this user owns and the app runs from).
RUN groupadd --system nexus \
    && useradd --system --create-home --home-dir /app --gid nexus --shell /usr/sbin/nologin nexus

WORKDIR /app

COPY --from=builder /install /usr/local

# Only the backend application modules NEXUS actually needs at runtime.
# No tests/, no frontend/, no docs, no .env, no local dev artifacts -- see
# .dockerignore for what is excluded from the build context entirely.
COPY access.py agents.py api.py auth.py config.py main.py observability.py \
     pricing.py rate_limit.py run_store.py runtime.py tool_policy.py \
     tool_registry.py ./
COPY evals ./evals

RUN chown -R nexus:nexus /app
USER nexus

# Environment-driven configuration only -- nothing here is a secret, and no
# secret is ever baked into the image. NEXUS_ENVIRONMENT defaults to
# "production" for this image: config.py's load_config() will refuse to
# start at all if NEXUS_API_TOKEN is not also supplied at run time (see
# config.py) -- this image cannot silently fall back to development's
# unauthenticated mode just because a token was forgotten. Every other
# NEXUS_*/ANTHROPIC_*/LLM_*/FETCH_* variable documented in ARCHITECTURE.md's
# Phase 7 section is read the same way, at container start, from whatever
# the operator/Compose/orchestrator supplies.
ENV NEXUS_ENVIRONMENT=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Uses the existing GET /ready endpoint (checkpointer-responsive probe, no
# LLM call, no auth required) -- not a separate liveness mechanism invented
# for this container. GET /health (process-alive only) remains available
# for orchestrators that want a cheaper liveness-only probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3).status == 200 else 1)"]

# Production startup: no --reload, no dev server, no shell wrapper. The
# exact app object api.py defines.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
