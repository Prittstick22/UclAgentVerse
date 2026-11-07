"""FastAPI entrypoint. `uvicorn app.main:app --reload --port 8000`"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.container import build_state
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "app"):
        app.state.app = build_state()
    yield


app = FastAPI(title="UclAgentVerse", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) and "error" in exc.detail else {
        "error": {"code": "internal", "message": str(exc.detail), "details": {}}}
    return JSONResponse(status_code=exc.status_code, content=body)


# Serve the built frontend (Docker copies frontend/dist → app/static)
_static = get_settings().static_dir
if _static.exists():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _static / path
        return FileResponse(f if f.is_file() else _static / "index.html")
