# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend
FROM python:3.11-slim
WORKDIR /app

# Install git for shallow cloning
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY database/ /app/database/
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

ENV PYTHONPATH=/app/backend:/app
ENV PORT=8000

EXPOSE 8000

CMD ["python", "backend/run.py"]
