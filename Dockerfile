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

# Optional: copy cookies.txt if exists (for YouTube auth in Docker)
# If not present at build time, mount it at runtime: -v /path/to/cookies.txt:/app/cookies.txt
COPY cookies.tx[t] ./

# Expose port for web server (configurable via YT_WEB_PORT env)
EXPOSE 8088

# Health check for yt-web container (wget available in Alpine by default)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${YT_WEB_PORT:-8011}/health || exit 1

# Default command: run web server
CMD ["uv", "run", "python", "main.py"]
