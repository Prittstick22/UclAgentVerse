# One image: build the frontend, then serve it + the API from FastAPI.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY fixtures/ /app/fixtures/
COPY docs/DATA_SOURCES.md /app/docs/DATA_SOURCES.md
RUN VITE_MOCK=0 npm run build

FROM python:3.12-slim AS recordings
WORKDIR /build
COPY demo/ ./demo/
COPY scripts/demo.py ./scripts/demo.py
RUN python -c "from pathlib import Path; from scripts.demo import prepare_bundle; prepare_bundle(destination=Path('/bundles/priya')); prepare_bundle(destination=Path('/bundles/caroline'), persona='caroline')"

FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/scripts ./scripts
COPY --from=web /app/frontend/dist ./app/static
COPY --from=recordings /bundles /opt/stead/demos
RUN mkdir -p /data
ENV SNAPSHOT_DIR=/data/snapshot STATE_DB=/data/state.sqlite RUNS_DIR=/data/runs STATIC_DIR=/app/backend/app/static
ENV DEMO_BUNDLES='{"priya":"/opt/stead/demos/priya","caroline":"/opt/stead/demos/caroline"}'
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
