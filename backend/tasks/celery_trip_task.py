"""
Trip Planning Celery Task
Location: backend/tasks/celery_trip_task.py

v7: Added before/after TravelPreferences comparison logging in Step 2
    for testing NL preprocessing. Shows only changed fields side-by-side.

v6: Fixed _RedisBackedTripStorage — added add_restaurants() and add_activities()

v5: Passes _RedisBackedTripStorage + trip_id to orchestrator.orchestrate()

Logging: Writes to logs/agents/celery_task.log

Start worker:
    cd backend
    celery -A celery_app worker --loglevel=info --pool=solo
"""
import asyncio
import json
import traceback
from datetime import datetime

from celery_app import celery_app
from services.trip_redis_service import (
    get_trip_redis_service,
    TRIP_STATUS_PREPROCESSING,
    TRIP_STATUS_IN_PROGRESS,
    TRIP_STATUS_COMPLETED,
    TRIP_STATUS_FAILED,
    AGENT_STATUS_IN_PROGRESS,
    AGENT_STATUS_COMPLETED,
    AGENT_STATUS_FAILED,
)
from agents.preprocessor_agent import PreprocessorAgent
from agents.user_proxy_agent import TravelQUserProxy
from agents.orchestrator_agent import TravelOrchestratorAgent
from models.user_preferences import TravelPreferences
from utils.logging_config import (
    log_agent_raw, log_agent_json, log_info_raw, log_error_raw,
    setup_agent_logging,
)

# ── Task logger setup ─────────────────────────────────────────────────────
TASK_LOG = "celery_task"
setup_agent_logging(TASK_LOG, fresh_start=True)


def _log(msg: str):
    """Shortcut: log to celery_task.log."""
    log_agent_raw(msg, agent_name=TASK_LOG)


def _log_json(data, label: str = ""):
    """Shortcut: log JSON to celery_task.log."""
    log_agent_json(data, label=label, agent_name=TASK_LOG)


# v7: Helper for before/after comparison
def _get_nested_value(d: dict, dot_path: str):
    """Navigate a dot-separated path like 'flight_prefs.max_stops' into a dict."""
    keys = dot_path.split(".")
    current = d
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


class _RedisBackedTripStorage:
    """
    Adapter: TripStorageInterface backed by Redis.

    Agents call methods like add_flights(), add_hotels(), add_restaurants(),
    add_activities(), etc. This adapter writes to Redis AND updates agent
    status, so the frontend can see progress in real-time via polling.

    v6 FIX: Added add_restaurants() and add_activities() — these are what
    PlacesAgent actually calls (not add_places()). The previous version only
    had add_places(category, places) which PlacesAgent never calls.
    """

    def __init__(self, trip_id: str, redis_service):
        self.trip_id = trip_id
        self.redis = redis_service
        self._preferences = None
        self._recommendations = {}
        self._flights = []
        self._hotels = []
        self._weather = []
        self._restaurants = []
        self._activities = []
        self._places = {}
        _log(f"📦 _RedisBackedTripStorage created for {trip_id}")

    # ── Preferences ───────────────────────────────────────────────────

    def store_preferences(self, trip_id: str, preferences):
        self._preferences = preferences
        _log(f"📦 store_preferences({trip_id})")

    def get_preferences(self, trip_id: str):
        return self._preferences

    # ── Agent data (writes to Redis immediately) ──────────────────────

    def add_flights(self, trip_id: str, flights, metadata=None):
        self._flights = flights
        _log(f"✈️  add_flights({trip_id}) — {len(flights)} flights")
        self.redis.store_agent_results(trip_id, "flight", {"flights": flights, "metadata": metadata})
        self.redis.set_agent_status(trip_id, "flight", AGENT_STATUS_COMPLETED)
        _log(f"✈️  Flight: Redis → results stored + status → completed")

    def add_hotels(self, trip_id: str, hotels, metadata=None):
        self._hotels = hotels
        _log(f"🏨 add_hotels({trip_id}) — {len(hotels)} hotels")
        self.redis.store_agent_results(trip_id, "hotel", {"hotels": hotels, "metadata": metadata})
        self.redis.set_agent_status(trip_id, "hotel", AGENT_STATUS_COMPLETED)
        _log(f"🏨 Hotel: Redis → results stored + status → completed")

    def add_weather(self, trip_id: str, weather, metadata=None):
        self._weather = weather
        _log(f"🌤️  add_weather({trip_id}) — {len(weather)} forecasts")
        self.redis.store_agent_results(trip_id, "weather", {"weather": weather, "metadata": metadata})
        self.redis.set_agent_status(trip_id, "weather", AGENT_STATUS_COMPLETED)
        _log(f"🌤️  Weather: Redis → results stored + status → completed")

    def add_restaurants(self, trip_id: str, restaurants, metadata=None):
        """Store restaurant results from PlacesAgent."""
        self._restaurants = restaurants
        self._places["restaurants"] = restaurants
        _log(f"🍽️  add_restaurants({trip_id}) — {len(restaurants)} restaurants")
        self.redis.store_agent_results(
            trip_id, "restaurant",
            {"category": "restaurants", "places": restaurants, "metadata": metadata}
        )
        self.redis.set_agent_status(trip_id, "restaurant", AGENT_STATUS_COMPLETED)
        _log(f"🍽️  Restaurant: Redis → results stored + status → completed")

    def add_activities(self, trip_id: str, activities, metadata=None):
        """Store activity results from PlacesAgent."""
        self._activities = activities
        self._places["activities"] = activities
        _log(f"🎭 add_activities({trip_id}) — {len(activities)} activities")
        self.redis.store_agent_results(
            trip_id, "places",
            {"category": "activities", "places": activities, "metadata": metadata}
        )
        self.redis.set_agent_status(trip_id, "places", AGENT_STATUS_COMPLETED)
        _log(f"🎭 Activities: Redis → results stored + status → completed")

    def add_places(self, trip_id: str, category: str, places, metadata=None):
        """Generic add_places (kept for backward compat)."""
        self._places[category] = places
        agent_name = "restaurant" if category == "restaurants" else "places"
        _log(f"📍 add_places({trip_id}, {category}) — {len(places)} places")
        self.redis.store_agent_results(
            trip_id, agent_name,
            {"category": category, "places": places, "metadata": metadata}
        )
        self.redis.set_agent_status(trip_id, agent_name, AGENT_STATUS_COMPLETED)
        _log(f"📍 {category}: Redis → results stored + status → completed")

    # ── Recommendations ───────────────────────────────────────────────

    def store_recommendation(self, trip_id: str, category: str, recommended_id: str,
                             reason: str = "", metadata: dict = None):
        self._recommendations[category] = {
            "recommended_id": recommended_id,
            "reason": reason,
            "metadata": metadata or {},
            "stored_at": datetime.now().isoformat(),
        }
        _log(f"⭐ store_recommendation({trip_id}, {category}) — id={recommended_id}")

    def get_recommendations(self, trip_id: str):
        return self._recommendations

    # ── Aggregation (called by orchestrator at end) ───────────────────

    def get_all_options(self, trip_id: str):
        return {
            "flights": self._flights,
            "hotels": self._hotels,
            "weather": self._weather,
            "restaurants": self._restaurants or self._places.get("restaurants", []),
            "activities": self._activities or self._places.get("activities", []),
        }

    def get_summary(self, trip_id: str):
        opts = self.get_all_options(trip_id)
        return {
            "flights": len(opts["flights"]),
            "hotels": len(opts["hotels"]),
            "weather": len(opts["weather"]),
            "restaurants": len(opts["restaurants"]),
            "activities": len(opts["activities"]),
            "recommendations": len(self._recommendations),
        }

    def update_agent_status_message(self, trip_id: str, agent_name: str, message: str):
        """Pass-through to Redis for granular agent status messages."""
        self.redis.update_agent_status_message(
            trip_id=trip_id,
            agent_name=agent_name,
            status_message=message,
        )

    def log_api_call(self, trip_id: str, agent_name: str, api_name: str, duration: float = 0):
        _log(f"📊 API call: {agent_name} → {api_name} ({duration:.2f}s)")


# ============================================================================
# THE CELERY TASK
# ============================================================================

@celery_app.task(
    name="plan_trip",
    bind=True,
    max_retries=1,
    default_retry_delay=10,
)
def plan_trip_task(self, trip_id: str):
    """
    Async trip planning task. Runs in Celery worker process.
    """
    _log("=" * 80)
    _log(f"🚀 CELERY TASK STARTED: plan_trip({trip_id})")
    _log(f"   Time: {datetime.now().isoformat()}")
    _log("=" * 80)

    redis_service = get_trip_redis_service()
    start_time = datetime.now()
    preproc_duration = 0.0

    try:
        # ── 1. Read from Redis ─────────────────────────────────────────
        _log("─" * 40)
        _log("STEP 1: Reading from Redis")
        _log("─" * 40)

        preferences_dict = redis_service.get_preferences(trip_id)
        if not preferences_dict:
            _log(f"❌ Preferences not found in Redis for {trip_id}")
            redis_service.set_trip_error(trip_id, "Preferences not found in Redis")
            return {"status": "failed", "error": "Preferences not found"}

        user_text = redis_service.get_user_text(trip_id)
        travel_preferences = TravelPreferences(**preferences_dict)

        _log("─" * 40)
        _log(f"✅ Loaded preferences for {trip_id}")
        _log(f"   Destination: {preferences_dict.get('destination', '?')}")
        _log(f"   Origin: {preferences_dict.get('origin', '?')}")
        _log(f"   Dates: {preferences_dict.get('departure_date', '?')} → {preferences_dict.get('return_date', '?')}")
        _log(f"   User text: \"{user_text[:200] if user_text else '(none)'}\"")
        _log_json(preferences_dict, label="📨 Original Travel Preferences:")

        

        # ── 2. Preprocessing (if user text exists) ─────────────────────
        _log("─" * 40)
        _log("STEP 2: Preprocessing")
        _log("─" * 40)

        if user_text:
            redis_service.set_trip_status(trip_id, TRIP_STATUS_PREPROCESSING)
            redis_service.set_agent_status(trip_id, "preprocessor", AGENT_STATUS_IN_PROGRESS)

            # ── v7: Capture original preferences BEFORE preprocessing ──
            original_prefs_dict = travel_preferences.model_dump()

            # _log_json(preferences_dict, label="📨 Original Travel Preferences:")

            preproc_storage = _RedisBackedTripStorage(trip_id, redis_service)
            preprocessor = PreprocessorAgent(
                trip_id=trip_id,
                trip_storage=preproc_storage,
            )

            _log("   🧠 Calling preprocessor.process()...")
            preproc_start = datetime.now()
            travel_preferences, changes_log = preprocessor.process(
                user_text=user_text,
                base_prefs=travel_preferences,
            )
            preproc_duration = (datetime.now() - preproc_start).total_seconds()
            _log(f"   🧠 Preprocessing completed in {preproc_duration:.2f}s")

            _log("─" * 40)
            _log_json(travel_preferences.model_dump(), label="📨 Merged Travel Preferences:")
            _log("─" * 40)

            if changes_log:
                redis_service.store_preference_changes(trip_id, changes_log)
                redis_service.update_preferences(trip_id, travel_preferences.model_dump())
                _log(f"   ✅ {len(changes_log)} override(s) applied")

                # ══════════════════════════════════════════════════════════
                # v7 TESTING: Side-by-side comparison of changed fields
                # ══════════════════════════════════════════════════════════
                merged_prefs_dict = travel_preferences.model_dump()

                _log("")
                _log("=" * 80)
                _log("🔍 PREFERENCE COMPARISON (Original vs NL-Merged)")
                _log("=" * 80)
                _log(f"   User text: \"{user_text}\"")
                _log("-" * 80)

                for change in changes_log:
                    field_path = change["field"]
                    action = change["action"]

                    orig_val = _get_nested_value(original_prefs_dict, field_path)
                    merged_val = _get_nested_value(merged_prefs_dict, field_path)

                    icon = {"replace": "🔄", "add": "➕", "delete": "➖"}.get(action, "❓")

                    _log(f"   {icon} [{action.upper()}] {field_path}")
                    _log(f"      ORIGINAL : {orig_val}")
                    _log(f"      MERGED   : {merged_val}")
                    _log("")

                _log("-" * 80)
                _log("   Unchanged fields omitted (all other fields identical)")
                _log("=" * 80)
                _log("")

            else:
                _log("   ℹ️  No overrides extracted")

            redis_service.set_agent_status(trip_id, "preprocessor", AGENT_STATUS_COMPLETED)
        else:
            _log("   ℹ️  No user text — skipping preprocessing")

        # ── 3. Orchestrate ─────────────────────────────────────────────
        _log("─" * 40)
        _log("STEP 3: Orchestration")
        _log("─" * 40)

        redis_service.set_trip_status(trip_id, TRIP_STATUS_IN_PROGRESS)

        trip_storage = _RedisBackedTripStorage(trip_id, redis_service)
        trip_storage.store_preferences(trip_id, travel_preferences)
        _log("   ✅ Created _RedisBackedTripStorage (v6: with add_restaurants + add_activities)")

        # Mark search agents as in_progress
        for agent_name in ["flight", "hotel", "weather", "places", "restaurant"]:
            redis_service.set_agent_status(trip_id, agent_name, AGENT_STATUS_IN_PROGRESS)
        _log("   All search agents → in_progress")

        user_proxy = TravelQUserProxy(
            name="APIUser",
            user_preferences=travel_preferences,
            human_input_mode="NEVER",
        )

        orchestrator = TravelOrchestratorAgent()

        _log(f"   🎯 orchestrate(user_proxy, trip_id={trip_id}, trip_storage=_RedisBackedTripStorage)")
        orch_start = datetime.now()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                orchestrator.orchestrate(
                    user_proxy,
                    trip_id=trip_id,
                    trip_storage=trip_storage,
                )
            )
        finally:
            loop.close()

        orch_duration = (datetime.now() - orch_start).total_seconds()
        _log(f"   ✅ Orchestration completed in {orch_duration:.2f}s")
        _log(f"   Agents used: {result.get('agents_used', [])}")

        # ── 3b: Verify Redis agent statuses ────────────────────────────
        _log("─" * 40)
        _log("STEP 3b: Verifying Redis agent statuses")
        _log("─" * 40)

        all_options = result.get("all_options", {})
        _log(f"   Flights:     {len(all_options.get('flights', []))}")
        _log(f"   Hotels:      {len(all_options.get('hotels', []))}")
        _log(f"   Restaurants: {len(all_options.get('restaurants', []))}")
        _log(f"   Activities:  {len(all_options.get('activities', []))}")
        _log(f"   Weather:     {len(all_options.get('weather', []))}")

        recs = result.get("recommendations", {})
        _log(f"   Recommendations: {list(recs.keys())}")

        # Safety net: force-complete any agents still in_progress
        poll_response = redis_service.get_trip_poll_response(trip_id)
        agent_statuses = poll_response.get("agents", {}) if poll_response else {}
        for agent_name in ["flight", "hotel", "weather", "places", "restaurant"]:
            current_status = agent_statuses.get(agent_name, "unknown")
            if current_status != AGENT_STATUS_COMPLETED:
                _log(f"   ⚠️ {agent_name} still '{current_status}' — forcing → completed")
                redis_service.set_agent_status(trip_id, agent_name, AGENT_STATUS_COMPLETED)
            else:
                _log(f"   ✅ {agent_name} → completed (updated by agent via Redis)")

        # ── 4. Store final results ─────────────────────────────────────
        _log("─" * 40)
        _log("STEP 4: Storing final results")
        _log("─" * 40)

        processing_time = (datetime.now() - start_time).total_seconds()

        final_results = {
            "status": "success",
            "trip_id": trip_id,
            "final_recommendation": result.get("final_recommendation", ""),
            "recommendations": result.get("recommendations", {}),
            "options": result.get("all_options", {}),
            "summary": result.get("summary", {}),
            "processing_time": processing_time,
            "agents_used": result.get("agents_used", []),
            "preference_changes": redis_service.get_preference_changes(trip_id),
        }

        # _log_json(final_results.get("recommendations", {}), label="Final Recommendations")
        _log_json(final_results.get("summary", {}), label="Final Summary")

        redis_service.store_final_results(trip_id, final_results)

        _log("=" * 80)
        _log(f"✅ CELERY TASK COMPLETED: {trip_id}")
        _log(f"   Total: {processing_time:.2f}s | Preproc: {preproc_duration:.2f}s | Orch: {orch_duration:.2f}s")
        _log("=" * 80)

        return {"status": "completed", "trip_id": trip_id}

    except Exception as e:
        _log("=" * 80)
        _log(f"❌ CELERY TASK FAILED: {trip_id}")
        _log(f"   Error: {str(e)}")
        _log(f"   Traceback:\n{traceback.format_exc()}")
        _log("=" * 80)

        log_error_raw(f"❌ Trip {trip_id} failed: {str(e)}")
        redis_service.set_trip_error(trip_id, str(e))
        return {"status": "failed", "trip_id": trip_id, "error": str(e)}