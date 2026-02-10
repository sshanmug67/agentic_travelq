"""
FastAPI Application Entry Point - Agentic Travel Dashboard

This is the main FastAPI app that:
1. Registers all route handlers
2. Configures CORS
3. Sets up logging
4. Provides health checks
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from utils.logging_config import setup_logging
import logging

# Initialize logging FIRST
setup_logging(
    log_file_name="travel_dashboard",
    console_level=logging.INFO,
    enable_console=True,
    fresh_start=False
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Agentic Travel Dashboard API",
    description="Multi-agent travel planning system with flights, weather, events, and places",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers (AFTER app creation to avoid circular imports)
from api.routes import trips

# Register routers
app.include_router(trips.router)

logger.info("=" * 70)
logger.info("🚀 Agentic Travel Dashboard API")
logger.info("=" * 70)
logger.info(f"Environment: {settings.environment}")
logger.info(f"Debug mode: {settings.debug}")
logger.info(f"API Prefix: {settings.api_prefix if hasattr(settings, 'api_prefix') else '/api'}")
logger.info(f"CORS Origins: {settings.cors_origins}")
logger.info("=" * 70)


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("✅ Application startup complete")
    logger.info(f"📍 Health check: http://{settings.api_host}:{settings.api_port}/api/trips/health")
    logger.info(f"📚 API Docs: http://{settings.api_host}:{settings.api_port}/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("👋 Application shutting down...")
    from utils.logging_config import shutdown_logging
    shutdown_logging()


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