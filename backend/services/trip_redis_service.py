"""
Trip Redis Service — Centralized Trip Data Store
Location: backend/services/trip_redis_service.py

Manages all Redis operations for the async trip planning pipeline:
  - Trip preferences storage
  - Agent status tracking (per-agent progress)
  - Granular agent status messages (Phase 1)
  - Results storage (partial + final)
  - Preference changes from NL preprocessing

Redis Key Schema:
  trip:{trip_id}:status              → queued|preprocessing|in_progress|completed|failed
  trip:{trip_id}:preferences         → TravelPreferences JSON
  trip:{trip_id}:user_text           → raw NL text from user (or empty)
  trip:{trip_id}:preference_changes  → changes_log JSON (after preprocessor)
  trip:{trip_id}:agents              → hash {flight: pending, hotel: in_progress, ...}
  trip:{trip_id}:agent_details       → per-agent granular status messages JSON (Phase 1)
  trip:{trip_id}:results             → full results JSON (when completed)
  trip:{trip_id}:partial:{agent}     → partial results per agent
  trip:{trip_id}:error               → error message (if failed)
  trip:{trip_id}:created_at          → ISO timestamp
  trip:{trip_id}:updated_at          → ISO timestamp (last update)

All keys auto-expire after TTL_SECONDS (default: 1 hour).

Changes (Phase 1 — Granular Agent Status):
  - New Redis key: trip:{trip_id}:agent_details
  - New methods: update_agent_status_message(), set_agent_started(),
    set_agent_completed(), set_agent_error()
  - Updated: create_trip() initializes agent_details
  - Updated: get_trip_poll_response() includes agent_details
"""
import json
import redis
from typing import Dict, Any, Optional, List
from datetime import datetime

from config.settings import settings
from utils.logging_config import log_info_raw, log_error_raw

# Default TTL: 1 hour (keys auto-expire)
TTL_SECONDS = 3600

# Agent status values
AGENT_STATUS_PENDING = "pending"
AGENT_STATUS_IN_PROGRESS = "in_progress"
AGENT_STATUS_COMPLETED = "completed"
AGENT_STATUS_FAILED = "failed"

# Trip status values
TRIP_STATUS_QUEUED = "queued"
TRIP_STATUS_PREPROCESSING = "preprocessing"
TRIP_STATUS_IN_PROGRESS = "in_progress"
TRIP_STATUS_COMPLETED = "completed"
TRIP_STATUS_FAILED = "failed"

# Default agents that the orchestrator runs
DEFAULT_AGENTS = ["preprocessor", "flight", "hotel", "weather", "places", "restaurant"]


def _empty_agent_detail() -> Dict[str, Any]:
    """Default shape for a single agent's detail entry."""
    return {
        "status_message": None,
        "result_count": None,
        "started_at": None,
        "updated_at": None,
        "completed_at": None,
        "error_message": None,
    }


class TripRedisService:
    """
    Redis-backed trip data store for async pipeline.
    Thread-safe — uses redis-py connection pool.
    """

    def __init__(self):
        redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379/0')
        self._redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        try:
            self._redis.ping()
            log_info_raw(f"✅ Redis connected: {redis_url}")
        except redis.ConnectionError as e:
            log_error_raw(f"❌ Redis connection failed: {e}")
            raise

    # ─────────────────────────────────────────────────────────────────────
    # KEY HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _key(self, trip_id: str, suffix: str) -> str:
        return f"trip:{trip_id}:{suffix}"

    def _set_json(self, key: str, data: Any, ttl: int = TTL_SECONDS):
        self._redis.set(key, json.dumps(data, default=str), ex=ttl)

    def _get_json(self, key: str) -> Optional[Any]:
        raw = self._redis.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    # ─────────────────────────────────────────────────────────────────────
    # TRIP LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────

    def create_trip(
        self,
        trip_id: str,
        preferences_dict: Dict[str, Any],
        user_text: Optional[str] = None,
        agents: Optional[List[str]] = None,
    ):
        """
        Initialize a new trip in Redis. Called by FastAPI before Celery dispatch.
        Sets status to 'queued' and initializes all agent statuses to 'pending'.
        Also initializes the agent_details structure for granular status messages.
        """
        pipe = self._redis.pipeline()

        # Trip metadata
        pipe.set(self._key(trip_id, "status"), TRIP_STATUS_QUEUED, ex=TTL_SECONDS)
        pipe.set(self._key(trip_id, "created_at"), datetime.now().isoformat(), ex=TTL_SECONDS)
        pipe.set(self._key(trip_id, "updated_at"), datetime.now().isoformat(), ex=TTL_SECONDS)

        # Preferences + user text
        pipe.set(
            self._key(trip_id, "preferences"),
            json.dumps(preferences_dict, default=str),
            ex=TTL_SECONDS,
        )
        if user_text:
            pipe.set(self._key(trip_id, "user_text"), user_text, ex=TTL_SECONDS)

        # Initialize agent statuses
        agent_list = agents or DEFAULT_AGENTS
        agent_statuses = {agent: AGENT_STATUS_PENDING for agent in agent_list}
        # If no user_text, preprocessor is automatically "completed" (nothing to do)
        if not user_text:
            agent_statuses["preprocessor"] = AGENT_STATUS_COMPLETED
        pipe.set(
            self._key(trip_id, "agents"),
            json.dumps(agent_statuses),
            ex=TTL_SECONDS,
        )

        # Phase 1: Initialize granular agent details (status messages, timestamps)
        agent_details = {}
        for agent in agent_list:
            agent_details[agent] = _empty_agent_detail()
        # If no user text, preprocessor is already done
        if not user_text:
            agent_details["preprocessor"]["status_message"] = "No refinement text — skipped"
            agent_details["preprocessor"]["completed_at"] = datetime.now().isoformat()
        pipe.set(
            self._key(trip_id, "agent_details"),
            json.dumps(agent_details),
            ex=TTL_SECONDS,
        )

        pipe.execute()
        log_info_raw(f"📦 Redis: trip {trip_id} created (agents: {agent_list})")

    # ─────────────────────────────────────────────────────────────────────
    # STATUS UPDATES
    # ─────────────────────────────────────────────────────────────────────

    def set_trip_status(self, trip_id: str, status: str):
        """Update overall trip status."""
        self._redis.set(self._key(trip_id, "status"), status, ex=TTL_SECONDS)
        self._redis.set(self._key(trip_id, "updated_at"), datetime.now().isoformat(), ex=TTL_SECONDS)

    def set_agent_status(self, trip_id: str, agent_name: str, status: str):
        """Update a single agent's status within the agents hash."""
        agents = self._get_json(self._key(trip_id, "agents")) or {}
        agents[agent_name] = status
        self._set_json(self._key(trip_id, "agents"), agents)
        self._redis.set(self._key(trip_id, "updated_at"), datetime.now().isoformat(), ex=TTL_SECONDS)

    def set_trip_error(self, trip_id: str, error_msg: str):
        """Store error message and set status to failed."""
        self._redis.set(self._key(trip_id, "error"), error_msg, ex=TTL_SECONDS)
        self.set_trip_status(trip_id, TRIP_STATUS_FAILED)

    # ─────────────────────────────────────────────────────────────────────
    # GRANULAR AGENT STATUS MESSAGES (Phase 1)
    # ─────────────────────────────────────────────────────────────────────

    def update_agent_status_message(
        self,
        trip_id: str,
        agent_name: str,
        status_message: str,
        result_count: Optional[int] = None,
    ):
        """
        Update an agent's granular status message for the frontend feed.

        Called from inside agents at each meaningful step:
          redis_service.update_agent_status_message(
              trip_id, "flight", "Scanning 44 routes from JFK, EWR, LGA"
          )

        This does NOT change the agent's overall status (pending/in_progress/completed).
        It only updates the human-readable message the frontend displays.
        """
        details = self._get_json(self._key(trip_id, "agent_details")) or {}
        now = datetime.now().isoformat()

        if agent_name not in details:
            details[agent_name] = _empty_agent_detail()

        details[agent_name]["status_message"] = status_message
        details[agent_name]["updated_at"] = now

        if result_count is not None:
            details[agent_name]["result_count"] = result_count

        self._set_json(self._key(trip_id, "agent_details"), details)

    def set_agent_started(self, trip_id: str, agent_name: str, status_message: str = "Starting..."):
        """Mark agent as started with initial message and timestamp."""
        details = self._get_json(self._key(trip_id, "agent_details")) or {}
        now = datetime.now().isoformat()

        if agent_name not in details:
            details[agent_name] = _empty_agent_detail()

        details[agent_name]["status_message"] = status_message
        details[agent_name]["started_at"] = now
        details[agent_name]["updated_at"] = now

        self._set_json(self._key(trip_id, "agent_details"), details)

    def set_agent_completed(
        self,
        trip_id: str,
        agent_name: str,
        status_message: str,
        result_count: Optional[int] = None,
    ):
        """Mark agent as completed with final message and timestamp."""
        details = self._get_json(self._key(trip_id, "agent_details")) or {}
        now = datetime.now().isoformat()

        if agent_name not in details:
            details[agent_name] = _empty_agent_detail()

        details[agent_name]["status_message"] = status_message
        details[agent_name]["updated_at"] = now
        details[agent_name]["completed_at"] = now

        if result_count is not None:
            details[agent_name]["result_count"] = result_count

        self._set_json(self._key(trip_id, "agent_details"), details)

    def set_agent_error(self, trip_id: str, agent_name: str, error_message: str):
        """Mark agent as failed with error message."""
        details = self._get_json(self._key(trip_id, "agent_details")) or {}
        now = datetime.now().isoformat()

        if agent_name not in details:
            details[agent_name] = _empty_agent_detail()

        details[agent_name]["status_message"] = f"Error: {error_message}"
        details[agent_name]["error_message"] = error_message
        details[agent_name]["updated_at"] = now

        self._set_json(self._key(trip_id, "agent_details"), details)

    # ─────────────────────────────────────────────────────────────────────
    # PREFERENCES
    # ─────────────────────────────────────────────────────────────────────

    def get_preferences(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """Get stored TravelPreferences dict."""
        return self._get_json(self._key(trip_id, "preferences"))

    def update_preferences(self, trip_id: str, preferences_dict: Dict[str, Any]):
        """Update preferences after preprocessing."""
        self._set_json(self._key(trip_id, "preferences"), preferences_dict)

    def get_user_text(self, trip_id: str) -> Optional[str]:
        """Get user's NL request text."""
        return self._redis.get(self._key(trip_id, "user_text"))

    def store_preference_changes(self, trip_id: str, changes: List[Dict[str, str]]):
        """Store the changes log from preprocessor for frontend."""
        self._set_json(self._key(trip_id, "preference_changes"), changes)

    def get_preference_changes(self, trip_id: str) -> Optional[List[Dict]]:
        """Get preference changes log."""
        return self._get_json(self._key(trip_id, "preference_changes"))

    # ─────────────────────────────────────────────────────────────────────
    # RESULTS
    # ─────────────────────────────────────────────────────────────────────

    def store_agent_results(self, trip_id: str, agent_name: str, results: Any):
        """Store partial results from a single agent (available immediately for polling)."""
        self._set_json(self._key(trip_id, f"partial:{agent_name}"), results)

    def get_agent_results(self, trip_id: str, agent_name: str) -> Optional[Any]:
        """Get partial results from a single agent."""
        return self._get_json(self._key(trip_id, f"partial:{agent_name}"))

    def store_final_results(self, trip_id: str, results: Dict[str, Any]):
        """Store the complete orchestration results."""
        self._set_json(self._key(trip_id, "results"), results)
        self.set_trip_status(trip_id, TRIP_STATUS_COMPLETED)

    def get_final_results(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """Get the complete results (only available when status=completed)."""
        return self._get_json(self._key(trip_id, "results"))

    # ─────────────────────────────────────────────────────────────────────
    # POLLING — called by GET /api/trips/{trip_id}/status
    # ─────────────────────────────────────────────────────────────────────

    def get_trip_poll_response(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """
        Build the complete poll response for the frontend.
        Returns None if trip_id doesn't exist.

        Phase 1: Now includes agent_details with granular status messages.
        """
        status = self._redis.get(self._key(trip_id, "status"))
        if not status:
            return None

        response = {
            "trip_id": trip_id,
            "status": status,
            "agents": self._get_json(self._key(trip_id, "agents")) or {},
            "agent_details": self._get_json(self._key(trip_id, "agent_details")) or {},
            "created_at": self._redis.get(self._key(trip_id, "created_at")),
            "updated_at": self._redis.get(self._key(trip_id, "updated_at")),
        }

        # Include preference changes if preprocessor has run
        pref_changes = self.get_preference_changes(trip_id)
        if pref_changes:
            response["preference_changes"] = pref_changes

        # Include error if failed
        if status == TRIP_STATUS_FAILED:
            response["error"] = self._redis.get(self._key(trip_id, "error"))

        # Include results if completed
        if status == TRIP_STATUS_COMPLETED:
            response["results"] = self.get_final_results(trip_id)

        return response

    # ─────────────────────────────────────────────────────────────────────
    # CLEANUP
    # ─────────────────────────────────────────────────────────────────────

    def delete_trip(self, trip_id: str):
        """Delete all keys for a trip (manual cleanup)."""
        pattern = f"trip:{trip_id}:*"
        keys = self._redis.keys(pattern)
        if keys:
            self._redis.delete(*keys)

    def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            return self._redis.ping()
        except Exception:
            return False


# ============================================================================
# SINGLETON
# ============================================================================

_trip_redis_service: Optional[TripRedisService] = None


def get_trip_redis_service() -> TripRedisService:
    """Get or create singleton TripRedisService."""
    global _trip_redis_service
    if _trip_redis_service is None:
        _trip_redis_service = TripRedisService()
    return _trip_redis_service