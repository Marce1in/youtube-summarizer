# syntax=docker/dockerfile:1.7
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openbox \
        novnc \
        sqlite3 \
        tini \
        websockify \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project
RUN --mount=type=cache,target=/root/.cache/ms-playwright \
    playwright install chrome

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked \
    && mkdir -p /data /browser-profile \
    && chown -R pwuser:pwuser /app /data /browser-profile

USER pwuser

ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "yt_gemini", "--help"]
