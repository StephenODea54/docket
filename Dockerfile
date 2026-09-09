FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --no-editable

FROM deps AS build
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable
ENV HOME=/opt/docket
RUN /app/.venv/bin/python -c \
    "from docket.db.db import _download_steampipe_extension; _download_steampipe_extension()"

FROM python:3.12-slim-bookworm AS runtime
ENV PATH=/app/.venv/bin:$PATH
ENV HOME=/home/docket
ENV PYTHONUNBUFFERED=1
ENV DOCKET_SERVE_HOST=0.0.0.0
ENV DOCKET_SERVE_PORT=8000
ENV DOCKET_DB_PATH=/data/docket.db
RUN useradd --create-home --uid 1000 docket && mkdir -p /data && chown docket:docket /data
WORKDIR /app
COPY --from=build --chown=docket:docket /app/.venv ./.venv
COPY --from=build --chown=docket:docket /opt/docket/.docket /home/docket/.docket
USER docket
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request as r; r.urlopen('http://127.0.0.1:8000/').status == 200 or exit(1)"
ENTRYPOINT ["docket"]
CMD ["serve"]
