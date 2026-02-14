# Backend Dockerfile
# Location: backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs/agents logs/services

EXPOSE 8000

# Default: run FastAPI (override in docker-compose for worker)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]