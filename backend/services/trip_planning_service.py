"""
Trip Planning Service
Location: backend/services/trip_planning_service.py

Changes (v5):
  - NL Preprocessing: If userRequest text exists, PreprocessorAgent parses it
    and merges overrides into TravelPreferences before dispatching to orchestrator.
  - PreprocessorAgent is a proper agent (extends TravelQBaseAgent) with LLM,
    logging, and conversation tracking — not a utility function.
  - plan_trip() accepts optional user_request_text parameter.
  - preference_changes returned in result for frontend summary bar updates.

Changes (v4):
  - plan_trip() accepts the request dict directly from to_request_dict()
  - Removed TripRequest intermediary — data flows straight to converter

Flow (v5):
    TripSearchRequest → to_request_dict() ─┐
                        userRequest ────────┼→ plan_trip()
                                            │     ├→ convert to TravelPreferences (base)
                                            │     ├→ PreprocessorAgent.process() (if user text)
                                            │     ├→ merge overrides into preferences
                                            │     └→ orchestrate with merged preferences
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from agents.user_proxy_agent import TravelQUserProxy
from agents.orchestrator_agent import TravelOrchestratorAgent
from agents.preprocessor_agent import PreprocessorAgent
from utils.request_converter import convert_trip_request_to_preferences, validate_trip_request
from utils.logging_config import log_info_raw, log_json_raw, log_error_raw


class TripPlanningService:

    async def plan_trip(
        self,
        request_dict: Dict[str, Any],
        user_request_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Plan trip from a request dict, optionally applying NL overrides.

        Args:
            request_dict: Dict from TripSearchRequest.to_request_dict()
            user_request_text: Raw text from "Refine Your Search" box (optional).
                              If provided, PreprocessorAgent parses it and merges
                              overrides into the base TravelPreferences.

        Returns:
            Result dict with trip_id, all_options, recommendations,
            and preference_changes (if user text was processed).
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

            # ── Convert to base TravelPreferences ──────────────────────
            travel_preferences = convert_trip_request_to_preferences(request_dict)

            log_json_raw(
                travel_preferences.model_dump(),
                label="travel_preferences (base — from summary bar + preferences panel)",
                include_borders=True
            )

            # ── NL Preprocessing (v5) ──────────────────────────────────
            # If user typed text, run PreprocessorAgent to parse and merge
            # overrides BEFORE dispatching to the orchestrator.
            # ────────────────────────────────────────────────────────────
            changes_log: List[Dict[str, str]] = []

            if user_request_text and user_request_text.strip():
                log_info_raw(f"💬 User request text detected: \"{user_request_text[:200]}\"")
                log_info_raw("   🧠 Creating PreprocessorAgent...")

                preprocessor = PreprocessorAgent(
                    trip_id="preprocessing",
                    trip_storage=_NullTripStorage(),
                )

                travel_preferences, changes_log = preprocessor.process(
                    user_text=user_request_text,
                    base_prefs=travel_preferences
                )

                if changes_log:
                    log_json_raw(
                        travel_preferences.model_dump(),
                        label="travel_preferences (MERGED — after NL overrides)",
                        include_borders=True
                    )
                    log_info_raw(f"   ✅ {len(changes_log)} preference(s) overridden by user text")
                else:
                    log_info_raw("   ℹ️  No overrides extracted from user text")
            else:
                log_info_raw("ℹ️  No user request text — using base preferences as-is")

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
                "processing_time": f"{processing_time:.2f}s",
                "nl_overrides_applied": len(changes_log),
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
                "agents_used": result["agents_used"],
                # v5: Changes log for frontend summary bar updates
                "preference_changes": changes_log if changes_log else None,
            }

        except Exception as e:
            log_error_raw(f"❌ Trip planning failed: {str(e)}")
            raise Exception(f"Trip planning failed: {str(e)}")


# ============================================================================
# Null Storage — lightweight stub for PreprocessorAgent
# ============================================================================
# The PreprocessorAgent runs BEFORE the orchestrator creates trip_storage.
# This stub satisfies the TripStorageInterface so the agent can initialize
# without errors. API call logging is a no-op; real storage comes later
# when the orchestrator creates InMemoryTripStorage for the search agents.
# ============================================================================

class _NullTripStorage:
    """
    No-op implementation of TripStorageInterface.
    Used by PreprocessorAgent which runs before real storage is created.
    """
    def log_api_call(self, **kwargs):
        pass

    def get_preferences(self, trip_id: str):
        return None

    def store_preferences(self, trip_id: str, preferences=None):
        pass

    def add_flights(self, **kwargs):
        pass

    def add_hotels(self, **kwargs):
        pass

    def store_recommendation(self, **kwargs):
        pass

    def __getattr__(self, name):
        """Catch-all for any other storage method calls."""
        return lambda *args, **kwargs: None


trip_planning_service = TripPlanningService()