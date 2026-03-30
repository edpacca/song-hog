FROM python:3.13-slim AS builder

# song-hog pyproject.toml declares requires-python>=3.14, but 3.14 has no
# stable Docker image. 3.13 runs this codebase without issue; update
# pyproject.toml's requires-python to >=3.13 to match.

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
# uv.lock is optional for song-hog; include if present
COPY uv.lock* ./

# Install dependencies (--no-dev excludes black and other dev tools)
RUN uv sync --no-dev --no-editable 2>/dev/null || uv sync --no-dev


FROM python:3.13-slim

# ffmpeg: required by ffmpeg-python for audio conversion
# curl: required by the /health healthcheck in docker-compose.yml
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
# Ensure log output reaches docker logs immediately (no buffering)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
