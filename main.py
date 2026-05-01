"""
main.py
FastAPI application entry point.

Run development server:
  uvicorn main:app --reload --port 8000

Run production:
  uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# ── Logging setup ──────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Startup / Shutdown ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    logger.info("🚀 Starting Credit Card Sales Agent...")

    # Test DB connection
    from db.database import test_connection
    db_ok = test_connection()
    if not db_ok:
        logger.error("⚠️  Database not connected. Some features will fail.")

    # Test Redis connection
    from services.session_manager import test_redis
    redis_ok = test_redis()
    if not redis_ok:
        logger.error("⚠️  Redis not connected. Session management will fail.")

    # Pre-compile LangGraph (so first call isn't slow)
    from graph.graph_builder import sales_graph
    logger.info("✅ LangGraph compiled and ready")

    logger.info("✅ All systems go. Ready to handle calls.")
    yield
    logger.info("🛑 Shutting down...")


# ── FastAPI App ────────────────────────────────────────────────────
app = FastAPI(
    title="Credit Card Sales Agent API",
    description="AI-powered outbound sales agent using LangGraph + Groq",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────
from routes.call_routes import router as call_router
from routes.lead_routes import router as lead_router

app.include_router(call_router)
app.include_router(lead_router)


# ── Health Check ───────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    from db.database import test_connection
    from services.session_manager import test_redis, get_active_call_count
    from db.db_utils import get_daily_stats

    return {
        "status": "ok",
        "database": "connected" if test_connection() else "disconnected",
        "redis": "connected" if test_redis() else "disconnected",
        "active_calls": get_active_call_count(),
        "daily_stats": get_daily_stats(),
    }


# ── Root ───────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Credit Card Sales Agent API",
        "docs": "/docs",
        "health": "/health",
    }