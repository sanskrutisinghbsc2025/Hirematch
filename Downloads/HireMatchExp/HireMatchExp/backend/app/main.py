
from contextlib import asynccontextmanager
import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.deps import get_database, get_config
from backend.app.api.routes import (
    analytics,
    candidates,
    comparison,
    criteria,
    health,
    jobs,
    models,
    reports,
    screening,
    sessions,
    settings,
    simulator,
)
from core.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing HireMatch API server...")
    cfg = get_config()
    db = get_database()
    logger.info(f"Database initialized at: {cfg.db_path}")
    logger.info(f"Storage directory: {cfg.storage_dir}")
    yield
    logger.info("HireMatch API server shutting down gracefully.")


app = FastAPI(
    title="HireMatch AI Screening Engine",
    description=(
        "Production-grade REST API backend for HireMatch — AI-powered multi-layer "
        "resume screening, deterministic criteria evaluation, and recruitment analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(health.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(criteria.router, prefix="/api")
app.include_router(screening.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(comparison.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(simulator.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/")
def root():
    return {
        "service": "HireMatch AI Screening API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "api_prefix": "/api",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error occurred.",
            "error_type": type(exc).__name__,
            "path": request.url.path,
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
