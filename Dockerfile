# One image: build the frontend, then serve it + the API from FastAPI.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY fixtures/ /fixtures/
COPY docs/DATA_SOURCES.md /docs/DATA_SOURCES.md
RUN VITE_MOCK=0 npm run build

FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/scripts ./scripts
COPY --from=web /web/dist ./app/static
ENV SNAPSHOT_DIR=/data/snapshot STATE_DB=/data/state.sqlite RUNS_DIR=/data/runs STATIC_DIR=/app/backend/app/static
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
