"""
FastAPI Application - Main entry point.
"""

import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from .routes import (
    health_router, status_router, portfolio_router, orders_router,
    risk_router, strategy_router, system_router, metrics_router,
    capabilities_router
)
from .middleware import LoggingMiddleware, RateLimitMiddleware, AuthMiddleware

logger = logging.getLogger(__name__)


# Configuration
class Settings:
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", "60"))


settings = Settings()


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting API server...")
    # Initialize connections, etc.
    yield
    logger.info("Shutting down API server...")
    # Cleanup


# --- App ---
app = FastAPI(
    title="Trading System API",
    description="API for the Adaptive Crypto Portfolio Research / Optimization Engine",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, calls_per_minute=settings.RATE_LIMIT)
app.add_middleware(AuthMiddleware, excluded_paths=["/health", "/docs", "/redoc", "/openapi.json"])


# --- Exception Handlers ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "timestamp": datetime.now().isoformat(),
            "status": exc.status_code,
            "error": exc.detail,
            "path": request.url.path
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "timestamp": datetime.now().isoformat(),
            "status": 422,
            "error": "Validation Error",
            "details": exc.errors(),
            "path": request.url.path
        }
    )


# --- Routes ---
app.include_router(health_router, prefix="/api/v1")
app.include_router(status_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")
app.include_router(strategy_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(capabilities_router, prefix="/api/v1")


@app.get("/")
async def root():
    # Serve the UI dashboard
    static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    index_path = os.path.join(static_path, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"name": "Trading System API", "version": "2.0.0", "docs": "/docs", "ui": "/static/index.html"}


@app.get("/static/{path:path}")
async def serve_static(path: str):
    """Serve static files."""
    static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', path)
    if os.path.exists(static_path) and os.path.isfile(static_path):
        return FileResponse(static_path)
    raise StarletteHTTPException(status_code=404, detail="File not found")


def run(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(app, host=host, port=port, log_level="info")
