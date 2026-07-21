FROM python:3.13-alpine

WORKDIR /app

# Install ffmpeg and nodejs (required by yt-dlp for YouTube JS challenge)
RUN apk add --no-cache ffmpeg nodejs

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy remaining files
COPY main.py monitoring.py ./
COPY web/ ./web/
COPY channels.example.json ./channels.json

# 로그인 쿠키는 이미지에 포함하지 않고 런타임에 read-only로 마운트한
# Firefox 프로필에서 직접 읽는다.

# Expose port for web server (configurable via YT_WEB_PORT env, default 8011)
EXPOSE 8011

# Health check for yt-web container (wget available in Alpine by default)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${YT_WEB_PORT:-8011}/health || exit 1

# Default command: run web server
CMD ["uv", "run", "python", "main.py"]
