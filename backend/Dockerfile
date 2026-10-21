# syntax=docker/dockerfile:1.7
# Docify backend image: one image, many roles (`docify api | worker | migrate | ...`).
# Multi-stage: uv builds a venv in the builder; the runtime has no compilers and runs as uid 10001.

ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY README.md alembic.ini ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
ARG GIT_SHA=dev
LABEL org.opencontainers.image.title="docify-backend" \
      org.opencontainers.image.source="https://github.com/docify-work/docify" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="MIT"
RUN groupadd --system --gid 10001 docify \
 && useradd --system --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin docify
COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION=${GIT_SHA} \
    LOCAL_STORAGE_DIR=/tmp/docify-storage \
    WORKER_HEARTBEAT_FILE=/tmp/worker-heartbeat
WORKDIR /app
USER 10001:10001
EXPOSE 8000 9000
ENTRYPOINT ["docify"]
CMD ["api"]
