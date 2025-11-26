FROM python:3.13-slim

WORKDIR /app

# Install ffmpeg and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy remaining files
COPY main.py web_server.py ./
COPY web/ ./web/
COPY channels.example.json ./channels.json

# Expose port for web server
EXPOSE 8000

# Default command: run monitor mode
CMD ["uv", "run", "python", "main.py"]
