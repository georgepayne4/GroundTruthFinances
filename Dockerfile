# GroundTruth Financial Planning Platform
# Multi-stage build: frontend assets + Python API runtime

# --- Stage 1: Build frontend ---
FROM node:20-alpine AS frontend
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --production=false
COPY web/ ./
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.12-slim AS runtime

# WeasyPrint system dependencies (for PDF export)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary gunicorn

# Application code
COPY engine/ ./engine/
COPY api/ ./api/
COPY config/ ./config/
COPY main.py ./

# Frontend static assets from stage 1
COPY --from=frontend /app/web/dist ./web/dist

# Create outputs directory
RUN mkdir -p outputs

# Non-root user
RUN useradd -r -s /bin/false groundtruth && chown -R groundtruth:groundtruth /app
USER groundtruth

EXPOSE 8000

# Production uvicorn: 4 workers, 120s timeout, graceful 30s shutdown
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--timeout-keep-alive", "120", \
     "--timeout-graceful-shutdown", "30", \
     "--log-level", "info"]
