FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    FINANZFUCHS_HOST=0.0.0.0 \
    FINANZFUCHS_PORT=8000 \
    FINANZFUCHS_DATA_DIR=/app/data

WORKDIR /app

# Dependencies first so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY finanzfuchs ./finanzfuchs
RUN uv sync --frozen --no-dev

# The compose file runs it as the host user that owns the data folder.
RUN useradd --system --uid 10001 finanzfuchs
USER finanzfuchs

EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "finanzfuchs.web"]
