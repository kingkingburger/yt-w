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

# cookies.txt는 이미지에 포함시키지 않는다 — 공개 라이브는 pot-provider의 PO Token만으로
# 접근 가능하고, 멤버십/비공개가 필요하면 런타임에 볼륨 마운트로 주입하면 된다.
# 과거 COPY cookies.tx[t]는 빌드 타임 쿠키를 이미지에 박아 재배포해도 낡은 쿠키가
# 따라다녔다.

# Expose port for web server (configurable via YT_WEB_PORT env, default 8011)
EXPOSE 8011

# Health check for yt-web container (wget available in Alpine by default)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${YT_WEB_PORT:-8011}/health || exit 1

# Default command: run web server
CMD ["uv", "run", "python", "main.py"]
