"""
app/main.py — FastAPI application entry point.

Configures:
  - OpenAPI 3.0 documentation
  - CORS
  - Structured logging middleware
  - Database table creation on startup
  - All route handlers
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from app.api.routes import router
from app.db.database import engine
from app.db.models import Base
from app.utils.logger import log

# ── Create tables on startup ─────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Autonomous Social Media Growth Agent",
    description=(
        "A production-grade multi-agent AI system for social media content strategy, "
        "planning, and publishing. Powered by LangGraph, ChromaDB, and Groq LLM."
    ),
    version="1.0.0",
    contact={"name": "MetaUpSpace Engineering"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Health", "description": "Service health checks"},
        {"name": "Users", "description": "User management"},
        {"name": "Profile", "description": "FR-1: Profile Intelligence Agent"},
        {"name": "Competitors", "description": "FR-2: Competitive Landscape Agent"},
        {"name": "Calendar", "description": "FR-3: Content Calendar + HITL Review"},
        {"name": "Content", "description": "FR-4/5: Multi-Agent Content Generation + Review"},
        {"name": "Publish", "description": "FR-6: Content Publishing"},
        {"name": "Metrics", "description": "FR-7: Post-Publish Analytics + Adaptive Re-planning"},
        {"name": "Pipeline", "description": "Convenience: Full Pipeline Run"},
    ],
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://frontend:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000)
    log.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=elapsed,
    )
    return response

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("http.unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."},
    )

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api/v1")

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Autonomous Social Media Growth Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/api/v1/health",
    }
