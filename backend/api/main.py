"""
FastAPI Application Entry Point - Agentic Travel Dashboard

IMPORTANT: Logging must be initialized FIRST, at module level,
before importing anything else that might try to use logging.
"""
import logging
import sys
from pathlib import Path

# ============================================================================
# STEP 1: Initialize logging IMMEDIATELY (before other imports)
# ============================================================================

# Add backend to path if needed
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from utils.logging_config import setup_logging

# Setup logging NOW
setup_logging(
    log_file_name="travel_dashboard",
    console_level=logging.INFO,
    enable_console=True,
    fresh_start=True
)

logger = logging.getLogger(__name__)

# ============================================================================
# STEP 2: Now import everything else
# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings

# ============================================================================
# STEP 3: Create FastAPI app
# ============================================================================

app = FastAPI(
    title="Agentic Travel Dashboard API",
    description="Multi-agent travel planning system with flights, weather, events, and places",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================================
# STEP 4: Configure CORS
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# STEP 5: Register routers
# ============================================================================

from api.routes import trips

app.include_router(trips.router)

# ============================================================================
# STEP 6: Log startup information
# ============================================================================

logger.info("=" * 70)
logger.info("🚀 Agentic Travel Dashboard API")
logger.info("=" * 70)
logger.info(f"Environment: {settings.environment}")
logger.info(f"Debug mode: {settings.debug}")
logger.info(f"CORS Origins: {settings.cors_origins}")
logger.info("=" * 70)


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("✅ Application startup complete")
    logger.info(f"📍 Health check: http://{settings.api_host}:{settings.api_port}/api/trips/health")
    logger.info(f"📚 API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    
    # Verify logs directory
    from utils.logging_config import get_log_dir
    log_dir = get_log_dir()
    logger.info(f"📁 Logs directory: {log_dir}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("👋 Application shutting down...")
    from utils.logging_config import shutdown_logging
    shutdown_logging()


# ============================================================================
# ROOT ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Agentic Travel Dashboard API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/trips/health"
    }


@app.get("/health")
async def health():
    """Global health check"""
    return {
        "status": "healthy",
        "service": "travel-dashboard-api",
        "environment": settings.environment
    }