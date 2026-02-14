"""
Trip Planning Service
Location: backend/services/trip_planning_service.py

Changes (v4):
  - plan_trip() now accepts the request dict directly from to_request_dict()
  - Removed TripRequest intermediary — data flows straight to converter
  - No more silent field dropping by Pydantic
  
  Old flow (data loss):
    TripSearchRequest → to_request_dict() → TripRequest(**dict) → model_dump() → converter
    ❌ TripRequest didn't have cuisine_prefs, interested_carriers, etc. → silently dropped
  
  New flow (direct):
    TripSearchRequest → to_request_dict() → converter → TravelPreferences
    ✅ All fields pass through — no intermediary to drop them
"""
from typing import Dict, Any
from datetime import datetime

from agents.user_proxy_agent import TravelQUserProxy
from agents.orchestrator_agent import TravelOrchestratorAgent
from utils.request_converter import convert_trip_request_to_preferences, validate_trip_request
from utils.logging_config import log_info_raw, log_json_raw, log_error_raw


class TripPlanningService:

    async def plan_trip(self, request_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan trip from a request dict.

        Args:
            request_dict: Dict from TripSearchRequest.to_request_dict()
                          Contains all fields including cuisine_prefs, interested_carriers, etc.

        Returns:
            Result dict with trip_id, all_options, recommendations, etc.
        """
        start_time = datetime.now()

        log_info_raw("=" * 80)
        log_info_raw("📋 TripPlanningService: Starting trip planning")
        log_info_raw("=" * 80)

        try:
            log_json_raw(request_dict, label="request_dict", include_borders=True)

            # ── Validate ───────────────────────────────────────────────
            is_valid, error_msg = validate_trip_request(request_dict)
            if not is_valid:
                raise ValueError(error_msg)

            # ── Convert directly to TravelPreferences (no TripRequest middleman) ─
            travel_preferences = convert_trip_request_to_preferences(request_dict)

            log_json_raw(travel_preferences.model_dump(), label="travel_preferences", include_borders=True)

            # ── Create user proxy ──────────────────────────────────────
            user_proxy = TravelQUserProxy(
                name="APIUser",
                user_preferences=travel_preferences,
                human_input_mode="NEVER"
            )

            # ── Create orchestrator ────────────────────────────────────
            orchestrator = TravelOrchestratorAgent()

            # ── Orchestrate (handles storage internally) ───────────────
            result = await orchestrator.orchestrate(user_proxy)

            processing_time = (datetime.now() - start_time).total_seconds()

            log_info_raw("=" * 80)
            log_info_raw("✅ Trip planning completed successfully")
            log_json_raw({
                "trip_id": result["trip_id"],
                "flights_reviewed": len(result["all_options"]["flights"]),
                "hotels_reviewed": len(result["all_options"]["hotels"]),
                "recommendations": result.get("recommendations", {}),
                "processing_time": f"{processing_time:.2f}s"
            }, label="Results Summary")
            log_info_raw("=" * 80)

            return {
                "status": "success",
                "trip_id": result["trip_id"],
                "final_recommendation": result["final_recommendation"],
                "recommendations": result.get("recommendations", {}),
                "options": result["all_options"],
                "summary": result["summary"],
                "processing_time": processing_time,
                "agents_used": result["agents_used"]
            }

        except Exception as e:
            log_error_raw(f"❌ Trip planning failed: {str(e)}")
            raise Exception(f"Trip planning failed: {str(e)}")


trip_planning_service = TripPlanningService()