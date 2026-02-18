# backend/Dockerfile
# TravelQ FastAPI Backend — Production Image
# ============================================

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN mkdir -p /logs && \
    adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app /logs
USER appuser

# Expose port
EXPOSE 8000

# Default: run FastAPI with Gunicorn + Uvicorn workers
# main.py is at backend/main.py → inside container it's /app/main.py → "main:app"
# Override in docker-compose for Celery worker
CMD ["gunicorn", "main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
