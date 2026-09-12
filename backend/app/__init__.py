"""Application factory for the Codebase Audit Platform API (FastAPI)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Config
from .routes.api import router as core_api_router, ApiError
from .services import graph_service
from .services.graph_service import DatabaseUnavailable

log = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(config_overrides: dict[str, Any] | None = None) -> FastAPI:
    app = FastAPI(
        title="Codebase Audit Platform API",
        version="2.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Allow custom config overrides
    app_config = {
        "GRAPH_BACKEND": Config.GRAPH_BACKEND,
        "COGNODB_URI": Config.COGNODB_URI,
        "COGNODB_USERNAME": Config.COGNODB_USERNAME,
        "COGNODB_PASSWORD": Config.COGNODB_PASSWORD,
    }
    if config_overrides:
        app_config.update(config_overrides)

    app.state.config = app_config

    # Initialize graph service backend
    graph_service.init_app(app_config)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Error Handlers -------------------------------------------------------

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(DatabaseUnavailable)
    async def db_error_handler(request: Request, exc: DatabaseUnavailable):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "Unable to connect to the dependency database. Please try again.",
                    "detail": str(exc),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
            )
        code = "not_found" if exc.status_code == 404 else "error"
        msg = "Resource not found." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": msg}},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        log.exception("Unhandled server error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Something went wrong. Please try again."}},
        )

    # Register core API router
    app.include_router(core_api_router)

    # Try registering additional route modules if available
    try:
        from .routes.ingest import router as ingest_router
        app.include_router(ingest_router)
    except ImportError:
        pass

    try:
        from .routes.analyze import router as analyze_router
        app.include_router(analyze_router)
    except ImportError:
        pass

    try:
        from .routes.report import router as report_router
        app.include_router(report_router)
    except ImportError:
        pass

    # Static file serving & SPA fallback
    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"error": {"code": "not_found", "message": "Resource not found."}},
                )
            candidate = FRONTEND_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        @app.get("/")
        async def root():
            return {
                "service": "Codebase Audit Platform API",
                "version": "2.0.0",
                "graph_backend": graph_service.mode(),
                "docs": "/api/docs",
                "health": "/api/health",
            }

    return app
