FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.0

COPY . .

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
