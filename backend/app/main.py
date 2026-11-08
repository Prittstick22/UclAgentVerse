"""FastAPI entrypoint. `uvicorn app.main:app --reload --port 8000`"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.demo_guard import RateLimitMiddleware
from app.api.routes import router
from app.container import build_state, state_for_mode
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "app"):
        app.state.app = build_state()
    state_for_mode(app.state.app, "live" if app.state.app.clock.mode == "historical" else "historical")
    try:
        yield
    finally:
        for state in app.state.app.modes.values():
            if state.recording is not None:
                await state.recording.pause()


app = FastAPI(title="UclAgentVerse", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RateLimitMiddleware)   # per-IP POST limit, public demo only (#12)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def profile_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path in {"/api/mandate", "/api/profile/quiz"}:
        fields = {".".join(str(part) for part in error["loc"][1:]): error["msg"] for error in exc.errors()}
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": "Invalid request.", "details": {"fields": fields},
        }})
    return await request_validation_exception_handler(request, exc)


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
