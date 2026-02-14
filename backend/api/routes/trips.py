"""
Trip Search Route — Async with Redis + Celery
Location: backend/api/routes/trips.py

Endpoints:
  POST /api/trips/search     → Queue trip, return trip_id immediately (HTTP 202)
  GET  /api/trips/{id}/status → Poll agent progress + results
  POST /api/trips/{id}/itinerary → Save selections
  GET  /api/trips/health      → Health check (Redis + Celery)

Changes (v6 — Async Pipeline):
  - POST /search no longer waits for orchestration
  - Creates trip_id, builds base preferences, stores in Redis, dispatches Celery task
  - Returns HTTP 202 with trip_id in < 100ms
  - New GET /{trip_id}/status endpoint for frontend polling
  - PreprocessorAgent runs inside Celery worker (not in FastAPI process)

Flow:
  Frontend → POST /search → {trip_id, status: "queued"} (instant)
  Frontend → GET /{trip_id}/status (every 2-3s) → agent progress
  Celery   → preprocessing → orchestration → results in Redis
  Frontend → GET /{trip_id}/status → {status: "completed", results: {...}}
"""
import logging
import traceback
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from tasks.celery_trip_task import plan_trip_task

from models.trip_search_request import TripSearchRequest
from services.trip_redis_service import get_trip_redis_service
from utils.request_converter import convert_trip_request_to_preferences, validate_trip_request
from utils.logging_config import log_json_raw, log_info_raw

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["trips"])


# ============================================================================
# POST /search — Queue trip planning (returns immediately)
# ============================================================================

@router.post("/search")
async def search_trip(request: TripSearchRequest):
    """
    Queue a trip planning request. Returns immediately with trip_id.

    Steps (all synchronous, < 100ms):
      1. Generate trip_id (or reuse from request)
      2. Convert request to base TravelPreferences
      3. Store preferences + user_text in Redis
      4. Dispatch Celery task
      5. Return HTTP 202 with trip_id
    """
    logger.info("=" * 80)
    logger.info("🌐 POST /api/trips/search")
    logger.info("=" * 80)

    try:
        # ── Log incoming request ──────────────────────────────────────
        td = request.tripDetails
        log_json_raw({
            "tripId": request.tripId or "(new trip)",
            "userRequest": request.userRequest[:120] if request.userRequest else "(empty)",
            "destination": td.destination,
            "dates": f"{td.startDate} → {td.endDate}",
            "travelers": td.travelers,
            "budget": td.budget,
        }, label="📨 Incoming TripSearchRequest")

        # ── 1. Generate trip_id ───────────────────────────────────────
        trip_id = request.tripId or f"trip_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🆔 Trip ID: {trip_id}")

        # ── 2. Validate + convert to base preferences ────────────────
        request_dict = request.to_request_dict()

        is_valid, error_msg = validate_trip_request(request_dict)
        if not is_valid:
            raise ValueError(error_msg)

        travel_preferences = convert_trip_request_to_preferences(request_dict)
        preferences_dict = travel_preferences.model_dump()

        log_json_raw(preferences_dict, label="📨 Travel Preferences:")


        # ── 3. Store in Redis ─────────────────────────────────────────
        redis_service = get_trip_redis_service()
        redis_service.create_trip(
            trip_id=trip_id,
            preferences_dict=preferences_dict,
            user_text=request.userRequest if request.userRequest else None,
        )

        logger.info(f"📦 Stored in Redis: preferences + user_text")

        # ── 4. Dispatch Celery task ───────────────────────────────────
        
        plan_trip_task.delay(trip_id)

        logger.info(f"🚀 Celery task dispatched for {trip_id}")

        # ── 5. Return immediately (HTTP 202 Accepted) ────────────────
        logger.info(f"✅ 202 Accepted — returning trip_id to frontend")
        logger.info("=" * 80)

        return JSONResponse(
            status_code=202,
            content={
                "trip_id": trip_id,
                "status": "queued",
                "message": "Trip planning started. Poll /status for progress.",
                "poll_url": f"/api/trips/{trip_id}/status",
            }
        )

    except ValueError as e:
        logger.error(f"❌ 400 Bad Request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"❌ 500 Internal Server Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GET /{trip_id}/status — Poll for progress + results
# ============================================================================

@router.get("/{trip_id}/status")
async def get_trip_status(trip_id: str):
    """
    Poll trip planning progress.

    Returns current status, per-agent progress, and results when complete.

    Response shape:
    {
        "trip_id": "trip_20260214_153000",
        "status": "in_progress",           // queued|preprocessing|in_progress|completed|failed
        "agents": {
            "preprocessor": "completed",   // pending|in_progress|completed|failed
            "flight": "in_progress",
            "hotel": "completed",
            "weather": "completed",
            "places": "pending",
            "restaurant": "pending"
        },
        "preference_changes": [...],       // from preprocessor (if any)
        "created_at": "2026-02-14T15:30:00",
        "updated_at": "2026-02-14T15:30:45",
        "results": null                    // full results when status=completed
    }
    """
    try:
        redis_service = get_trip_redis_service()
        response = redis_service.get_trip_poll_response(trip_id)

        if not response:
            raise HTTPException(
                status_code=404,
                detail=f"Trip {trip_id} not found"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Status check failed for {trip_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SAVE ITINERARY
# ============================================================================

@router.post("/{trip_id}/itinerary")
async def save_itinerary(trip_id: str, itinerary: dict):
    """Explicitly save the user's itinerary selections."""
    logger.info(f"💾 POST /api/trips/{trip_id}/itinerary")
    try:
        # TODO: Persist to database
        return {
            "status": "success",
            "tripId": trip_id,
            "message": "Itinerary saved"
        }
    except Exception as e:
        logger.error(f"❌ Failed to save itinerary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GET TRIPS
# ============================================================================

@router.get("")
async def get_my_trips():
    """Return all saved trips for the current user."""
    return {"trips": []}


# ============================================================================
# HEALTH
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check including Redis and Celery status."""
    health = {
        "status": "healthy",
        "service": "TravelQ API",
        "version": "3.0.0",
        "redis": False,
        "celery": False,
    }

    # Check Redis
    try:
        redis_service = get_trip_redis_service()
        health["redis"] = redis_service.health_check()
    except Exception:
        health["redis"] = False

    # Check Celery (ping workers)
    try:
        from celery_app import celery_app
        inspector = celery_app.control.inspect()
        active = inspector.active()
        health["celery"] = active is not None and len(active) > 0
        health["celery_workers"] = list(active.keys()) if active else []
    except Exception:
        health["celery"] = False

    # Overall status
    if not health["redis"] or not health["celery"]:
        health["status"] = "degraded"

    return health