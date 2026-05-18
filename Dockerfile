# ===== Stage 1: Build dependencies in isolated environment =====
FROM python:3.12-slim as builder

WORKDIR /app

# Install Poetry 🛠️
RUN pip install --no-cache-dir poetry

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR="/tmp/poetry_cache"

# 🔥 Critical: disable virtual environment creation
RUN poetry config virtualenvs.create false

# Copy project files
COPY pyproject.toml poetry.lock ./


RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install production dependencies only
# 💼 No dev tools in final image
RUN poetry install --no-root

# ===== Stage 2: Minimal final image =====
FROM python:3.12-slim

# 🛡️ Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python*/site-packages /home/app/.local/lib/python3.12/site-packages

# Copy CLI tools (e.g. ruff, black) if any
COPY --from=builder /usr/local/bin /home/app/.local/bin

# Add user binaries to PATH
ENV PATH="/home/app/.local/bin:$PATH"

# Copy application code
# 🔄 Update paths below if your structure is different
# COPY --chown=app:app ./scripts ./scripts
COPY --chown=app:app ./app ./app
COPY --chown=app:app ./run.py .
COPY --chown=app:app ./entrypoint.sh .
# ✅ Optional: if you use src/
# COPY --chown=app:app ./src ./src
# 🔐 Optional: for local dev (never in prod!)
# COPY --chown=app:app .env .

# 🌐 Expose port (update if needed)
# EXPOSE 8000

# 🚀 Start the app!
# 🔄 Change command if needed: uvicorn, celery, python main.py, etc.
ENTRYPOINT [ "bash", "entrypoint.sh" ]
