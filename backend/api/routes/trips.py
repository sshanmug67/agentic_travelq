"""
Trip Search Route — Accepts Frontend Payload As-Is
Location: backend/api/routes/trips.py

Single POST /api/trips/search endpoint that handles:
  1. New trip requests        (tripId is null)
  2. Trip refinements         (tripId set, userRequest or preferences changed)
  3. Selection saves          (tripId set, currentItinerary changed)
  4. Combined refine + save   (tripId set, multiple things changed)

Changes (v4):
  - Removed TripRequest intermediary — passes request dict directly to service
  - Old: to_request_dict() → TripRequest(**dict) → plan_trip(TripRequest)
    ❌ TripRequest silently dropped cuisine_prefs, interested_carriers, etc.
  - New: to_request_dict() → plan_trip(dict)
    ✅ All data flows through to the converter

Logging: Uses standard Python logging via logging.getLogger(__name__).
"""
import logging
import traceback

from fastapi import APIRouter, HTTPException

from models.trip import TripResponse
from models.trip_search_request import TripSearchRequest
from services.trip_planning_service import trip_planning_service
from utils.logging_config import log_json_raw, log_info_raw

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["trips"])


# ============================================================================
# MAIN ENDPOINT
# ============================================================================

@router.post("/search", response_model=TripResponse)
async def search_trip(request: TripSearchRequest):
    """
    Unified trip search / update endpoint.

    The frontend always sends the same shape. The backend decides what to do:

      tripId is null → Full new search
      tripId is set  → Compare against stored state, act on what changed
    """
    logger.info("=" * 80)
    logger.info("🌐 POST /api/trips/search")
    logger.info("=" * 80)

    try:
        # ── Log incoming request summary ──────────────────────────────
        td = request.tripDetails
        log_json_raw({
            "tripId": request.tripId or "(new trip)",
            "is_new_trip": request.is_new_trip,
            "userRequest": request.userRequest[:120] if request.userRequest else "(empty)",
            "tripDetails": {
                "origin": td.origin or "(not set)",
                "destination": td.destination,
                "dates": f"{td.startDate} → {td.endDate}",
                "travelers": td.travelers,
                "budget": td.budget,
            },
            "preferences": {
                "airlines": request.preferred_airlines or [],
                "cuisines": request.preferred_cuisines or [],
                "activities": request.preferred_activities or [],
            },
            "has_selections": request.has_selections,
        }, label="📨 Incoming TripSearchRequest")

        # ── Route to the right handler ──────────────────────────────────
        if request.is_new_trip:
            logger.info("🆕 New trip — running full search")
            log_info_raw("🆕 New trip — running full search")
            result = await _handle_new_trip(request)
        else:
            logger.info(f"🔄 Existing trip {request.tripId} — determining changes")
            log_info_raw(f"🔄 Existing trip {request.tripId} — determining changes")
            result = await _handle_existing_trip(request)

        response = TripResponse(**result)

        logger.info("✅ 200 OK")
        logger.info("=" * 80)
        return response

    except ValueError as e:
        logger.error(f"❌ 400 Bad Request: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"❌ 500 Internal Server Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HANDLERS
# ============================================================================

async def _handle_new_trip(request: TripSearchRequest) -> dict:
    """
    Brand-new trip. Run full planning pipeline.

    Passes the request dict directly to trip_planning_service — no TripRequest
    intermediary that would silently drop fields like cuisine_prefs.
    """
    request_dict = request.to_request_dict()

    logger.info("📤 Delegating to TripPlanningService (new trip)")
    logger.info(f"   origin={request_dict.get('origin')}, "
                f"dest={request_dict.get('destination')}, "
                f"dates={request_dict.get('departure_date')}→{request_dict.get('return_date')}")

    result = await trip_planning_service.plan_trip(request_dict)
    return result


async def _handle_existing_trip(request: TripSearchRequest) -> dict:
    """
    Existing trip — determine what changed and act accordingly.

    TODO: Implement differential logic once trip state storage exists.
    For now, treat every existing-trip request as a full re-plan.
    """
    request_dict = request.to_request_dict()

    logger.info(f"📤 Delegating to TripPlanningService (existing trip: {request.tripId})")
    result = await trip_planning_service.plan_trip(request_dict)
    return result


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
    # TODO: Fetch from database
    return {"trips": []}


# ============================================================================
# HEALTH
# ============================================================================

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "TravelQ API",
        "version": "2.0.0"
    }