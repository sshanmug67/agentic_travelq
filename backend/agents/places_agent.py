"""
Structured Daily Plan — PlacesAgent v9.5 (Retry + Smart Planner)
Location: backend/agents/places_agent.py

Changes (v9.5 — Retry + Smart Planner):
  - _search_text_with_retry(): retry wrapper for Google Places text search
    with up to 2 retries + linear backoff on transient 500 errors
  - _fetch_restaurants_async(): uses retry wrapper + broader backfill
    queries when pool is still short after primary searches
  - _fetch_activities_async(): uses retry wrapper on all text search calls
  - _run_planner(): dynamic RULES — when venue pool < slots needed,
    instructs LLM to spread repeats across non-consecutive days instead
    of block-copying day groups

Changes (v9.4 — Scalable Writers + Dedicated Nuggets):
  - Writers now scale dynamically: ceil(num_days / 3) writers, each ≤3 days
    * 1-3 days → 1 writer
    * 4-6 days → 2 writers
    * 7-9 days → 3 writers
    * 10+ days → 4+ writers
  - Writers ONLY write day narratives (emit_day) — no nugget responsibility
  - Nuggets are a DEDICATED parallel LLM call that runs alongside day writers
    * Always runs, guaranteed output, not dependent on writers
  - Fixed: rating None crash (safe None check before formatting)
  - Fixed: empty writer hallucination (writers never called with 0 days)

Changes (v9.3 — Three-Phase Pipeline):
  - Phase 2 now has 3 LLM calls instead of 1
  - Planner sees ALL venues + ALL weather → perfect global coordination

Changes (v9.2.1):
  - Streaming tool calls, per-day agent feed messages, nugget fallback

Changes (v9.1):
  - Compact narratives (1-2 sentences), max_tokens=2500

Changes (v9):
  - Structured JSON daily plan with enrichment and icon resolution
"""
import math
import time
import json
import re
import asyncio
import textwrap
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.google_places_service import get_google_places_service
from services.weather_service import get_weather_service
from models.trip import Place, Weather

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai

from utils.icon_mapper import get_cuisine_icon, get_activity_icon, get_weather_icon


# ═══════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS — emit_day used by Writers, emit_nuggets kept for fallback
# ═══════════════════════════════════════════════════════════════════════════

EMIT_DAY_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_day",
        "description": (
            "Store one completed day of the travel plan. "
            "Call this exactly once per day, in sequential order. "
            "Each call must contain exactly 4 time slots: morning, lunch, afternoon, dinner."
        ),
        "parameters": {
            "type": "object",
            "required": ["day", "date", "title", "intro", "slots"],
            "properties": {
                "day": {"type": "integer", "description": "Day number (1, 2, 3...)"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "title": {"type": "string", "description": "Creative, evocative title for the day"},
                "intro": {"type": "string", "description": "1-2 engaging sentences addressing the traveler. Reference the weather and set expectations for the day ahead. Second person voice."},
                "slots": {
                    "type": "array",
                    "description": "Exactly 4 time slots: morning, lunch, afternoon, dinner",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "required": ["time", "venue_name", "type", "category", "narrative"],
                        "properties": {
                            "time": {"type": "string", "enum": ["morning", "lunch", "afternoon", "dinner"]},
                            "venue_name": {"type": "string", "description": "EXACT venue name from assignments"},
                            "type": {"type": "string", "enum": ["activity", "restaurant"]},
                            "category": {"type": "string", "description": "Venue category or cuisine type"},
                            "narrative": {"type": "string", "description": "Exactly 2 engaging sentences. Sentence 1: what makes THIS specific venue unique or famous (signature dish, famous exhibit, architectural feature). Sentence 2: why it's a great match for this traveler's interests. Second person voice (you/your)."},
                        },
                    },
                },
            },
        },
    },
}

EMIT_NUGGETS_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_nuggets",
        "description": "Store travel info nuggets. Call ONCE, after all days are emitted.",
        "parameters": {
            "type": "object",
            "required": ["nuggets"],
            "properties": {
                "nuggets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "title", "content", "color"],
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "content": {"type": "string", "description": "1-2 concise sentences"},
                            "color": {"type": "string", "enum": ["sky", "purple", "orange", "green", "emerald"]},
                        },
                    },
                },
            },
        },
    },
}


class PlacesAgent(TravelQBaseAgent):
    """
    Places Agent v9.5 — Retry + Smart Planner.

    Phase 1: Parallel API fetches (weather + restaurants + activities)
      - v9.5: Text search calls use retry wrapper for transient 500 errors
      - v9.5: Broader backfill queries when pool is still short
    Phase 2: Three-phase LLM pipeline:
      - Planner: assigns venues to slots for ALL days (~4s)
        - v9.5: Dynamic rules handle small pools gracefully
      - N Writers (parallel): ceil(num_days/3) writers, each ≤3 days
      - Nuggets (parallel with writers): dedicated LLM call, guaranteed output
    """

    CATEGORY_TYPES = {
        "restaurants": ["restaurant", "cafe", "bar"],
        "attractions": ["tourist_attraction", "museum", "art_gallery"],
        "shopping": ["shopping_mall", "department_store", "market"],
        "nature": ["park", "botanical_garden", "hiking_area"],
        "culture": ["museum", "art_gallery", "performing_arts_theater"],
        "entertainment": ["movie_theater", "amusement_park", "casino"],
    }
    INDOOR_TYPES = {
        "museum", "art_gallery", "performing_arts_theater", "movie_theater",
        "shopping_mall", "department_store", "casino", "spa", "aquarium",
        "bowling_alley", "cafe", "restaurant", "bar", "bakery",
    }
    OUTDOOR_TYPES = {
        "park", "botanical_garden", "hiking_area", "zoo", "beach",
        "campground", "tourist_attraction", "amusement_park", "stadium",
        "golf_course", "marina",
    }

    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """You are a Travel Planning Expert who creates comprehensive, weather-aware
day-by-day itineraries combining weather, restaurants, activities, and local events."""

        super().__init__(
            name="PlacesAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="PlacesAgent",
            system_message=system_message,
            description="Finds restaurants, attractions, and points of interest",
            **kwargs,
        )
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        self.google_places = get_google_places_service()
        self.weather_service = get_weather_service()
        log_agent_raw("Places Agent v9.5 initialized (retry + smart planner)", agent_name="PlacesAgent")

    # ─────────────────────────────────────────────────────────────────────
    # STATUS HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, message: str, agent_name: str = "places"):
        try:
            self.trip_storage.update_agent_status_message(self.trip_id, agent_name, message)
        except Exception as e:
            log_agent_raw(f"Status update failed ({agent_name}): {e}", agent_name="PlacesAgent")

    def _update_weather_status(self, msg): self._update_status(msg, "weather")
    def _update_restaurant_status(self, msg): self._update_status(msg, "restaurant")
    def _update_activity_status(self, msg): self._update_status(msg, "places")
    def _update_planner_status(self, msg):
        self._update_status(msg, "restaurant")
        self._update_status(msg, "places")

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_all_interests(prefs) -> List[str]:
        return prefs.activity_prefs.preferred_interests + prefs.activity_prefs.interested_interests

    @staticmethod
    def _get_all_cuisines(prefs) -> List[str]:
        return prefs.restaurant_prefs.preferred_cuisines + prefs.restaurant_prefs.interested_cuisines

    def _calculate_trip_days(self, prefs) -> int:
        try:
            return max((datetime.strptime(prefs.return_date, "%Y-%m-%d") - datetime.strptime(prefs.departure_date, "%Y-%m-%d")).days, 1)
        except (ValueError, AttributeError):
            return 5

    # ─── v9.5: Retry wrapper for transient Google API failures ───────
    MAX_SEARCH_RETRIES = 2
    SEARCH_RETRY_DELAY = 1.0  # seconds

    def _search_text_with_retry(self, **kwargs) -> list:
        """
        Wrapper around google_places.search_places_by_text() with retry
        logic for transient 500 errors.

        Google Places API occasionally returns 500 on text search — these
        are transient and succeed on retry. Without this, ~50% of searches
        can fail on a bad run, leaving the restaurant/activity pool too small.

        Retries up to MAX_SEARCH_RETRIES times with linear backoff.
        """
        import time as _time

        for attempt in range(1 + self.MAX_SEARCH_RETRIES):
            results = self.google_places.search_places_by_text(**kwargs)

            if results:  # Got results — return immediately
                return results

            # Empty results could be a 500 or genuinely no matches
            if attempt < self.MAX_SEARCH_RETRIES:
                delay = self.SEARCH_RETRY_DELAY * (attempt + 1)  # 1s, 2s
                query = kwargs.get("query", "?")
                log_agent_raw(
                    f"🔄 Text search empty for '{query}' — "
                    f"retrying in {delay:.0f}s ({attempt + 2}/{1 + self.MAX_SEARCH_RETRIES})",
                    agent_name="PlacesAgent",
                )
                _time.sleep(delay)

        return []

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────

    def generate_reply(self, messages=None, sender=None, config=None) -> str:
        log_agent_raw("PlacesAgent v9.5 processing request...", agent_name="PlacesAgent")
        self._update_weather_status("Initializing weather forecast...")
        self._update_restaurant_status("Initializing restaurant search...")
        self._update_activity_status("Initializing activity search...")

        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, "name") else "Unknown"
            self.log_conversation_message(message_type="INCOMING", content=last_message, sender=sender_name, truncate=500)

        preferences = self.trip_storage.get_preferences(self.trip_id)
        if not preferences:
            self._update_planner_status("Error: preferences not found")
            self._update_weather_status("Error: preferences not found")
            return self.signal_completion(f"Error: Could not find preferences for trip {self.trip_id}")

        num_days = self._calculate_trip_days(preferences)
        log_agent_raw(f"Trip: {preferences.destination}, {num_days} days, targets: {num_days*3} restaurants, {num_days*3} activities", agent_name="PlacesAgent")

        try:
            start_time = time.time()

            # ══════════════════════════════════════════════════════════════
            # PHASE 1: Parallel API calls
            # ══════════════════════════════════════════════════════════════
            log_agent_raw("🚀 Phase 1: Parallel fetch (weather + restaurants + activities)", agent_name="PlacesAgent")
            weather_forecasts, cuisine_restaurants, interest_activities = self._run_parallel_fetches(preferences, num_days)
            api_duration = time.time() - start_time
            log_agent_raw(f"✅ Phase 1 complete in {api_duration:.1f}s — weather={len(weather_forecasts)}, restaurants={len(cuisine_restaurants)}, activities={len(interest_activities)}", agent_name="PlacesAgent")

            # Process weather
            weather_by_date = {}
            weather_dicts = []
            for f in weather_forecasts:
                d = self._weather_to_dict(f)
                weather_dicts.append(d)
                if d.get("date"):
                    weather_by_date[d["date"]] = d
            trip_days = self._compute_trip_days(preferences, weather_by_date)
            self._store_weather(weather_dicts, preferences)

            # Process restaurants & activities
            self._update_restaurant_status(f"Processing {len(cuisine_restaurants)} restaurant results...")
            self._update_activity_status(f"Processing {len(interest_activities)} activity results...")
            restaurants, activities = self._segregate_and_enrich(cuisine_restaurants, interest_activities, preferences)
            self._update_restaurant_status(f"Found {len(restaurants)} restaurants matching your tastes")
            self._update_activity_status(f"Found {len(activities)} activities matching your interests")

            if not restaurants and not activities:
                self._update_planner_status("No matching places found")
                return self.signal_completion("I couldn't find any places matching your interests.")

            self._store_results(restaurants, activities, preferences, api_duration)

            # ══════════════════════════════════════════════════════════════
            # PHASE 2: Scalable LLM pipeline (v9.4)
            # ══════════════════════════════════════════════════════════════
            log_agent_raw("🧠 Phase 2: Scalable LLM pipeline (planner + N writers + nuggets)", agent_name="PlacesAgent")
            self._update_planner_status(f"AI planning {len(trip_days)}-day itinerary...")

            recommendation = self._generate_travel_plan(
                weather_forecasts, restaurants, activities,
                trip_days, preferences, num_days,
            )

            # Final status
            if weather_forecasts:
                min_t = min(f.temp_min for f in weather_forecasts)
                max_t = max(f.temp_max for f in weather_forecasts)
                self._update_weather_status(f"Weather forecast complete — {len(weather_forecasts)} days, {min_t:.0f}°F–{max_t:.0f}°F")
            else:
                self._update_weather_status("Weather forecast complete — no data available")
            self._update_restaurant_status(f"Restaurant search complete — {len(restaurants)} options ready")
            self._update_activity_status(f"Activity search complete — {len(activities)} options ready")

            total_duration = time.time() - start_time
            log_agent_raw(f"✅ PlacesAgent v9.5 complete in {total_duration:.1f}s (API: {api_duration:.1f}s, LLM: {total_duration - api_duration:.1f}s)", agent_name="PlacesAgent")
            self.log_conversation_message(message_type="OUTGOING", content=recommendation, sender="chat_manager", truncate=1000)
            return self.signal_completion(recommendation)

        except Exception as e:
            log_agent_raw(f"Places search failed: {str(e)}", agent_name="PlacesAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="PlacesAgent")
            self._update_weather_status(f"Error: {str(e)[:80]}")
            self._update_restaurant_status(f"Error: {str(e)[:80]}")
            self._update_activity_status(f"Error: {str(e)[:80]}")
            return self.signal_completion(f"I encountered an error: {str(e)}. Please try again.")

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 1: PARALLEL API FETCHES
    # ─────────────────────────────────────────────────────────────────────

    def _run_parallel_fetches(self, preferences, num_days):
        import nest_asyncio
        async def _gather_all():
            return await asyncio.gather(
                self._fetch_weather_async(preferences),
                self._fetch_restaurants_async(preferences, num_days),
                self._fetch_activities_async(preferences, num_days),
                return_exceptions=True,
            )
        try:
            loop = asyncio.get_running_loop()
            nest_asyncio.apply()
            results = asyncio.run(_gather_all())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(_gather_all())
            finally:
                loop.close()

        weather = results[0] if not isinstance(results[0], Exception) else []
        restaurants = results[1] if not isinstance(results[1], Exception) else []
        activities = results[2] if not isinstance(results[2], Exception) else []
        for i, label in enumerate(["Weather", "Restaurant", "Activity"]):
            if isinstance(results[i], Exception):
                log_agent_raw(f"⚠️ {label} fetch failed: {results[i]}", agent_name="PlacesAgent")
        return weather, restaurants, activities

    async def _fetch_weather_async(self, preferences):
        self._update_weather_status(f"Fetching forecast for {preferences.destination}...")
        try:
            weather_data = await self.weather_service.get_forecast(
                location=preferences.destination, start_date=preferences.departure_date, end_date=preferences.return_date)
            forecasts = []
            for fd in weather_data:
                f = self._parse_weather_data(fd)
                if f: forecasts.append(f)
            if forecasts:
                min_t, max_t = min(f.temp_min for f in forecasts), max(f.temp_max for f in forecasts)
                rainy = sum(1 for f in forecasts if (f.precipitation_probability or 0) > 50)
                self._update_weather_status(f"Forecast received — {len(forecasts)} days, {min_t:.0f}°F–{max_t:.0f}°F, {rainy} rainy day{'s' if rainy != 1 else ''}")
            else:
                self._update_weather_status("No forecast data available")
            log_agent_raw(f"✅ Weather: {len(forecasts)} day forecast received", agent_name="PlacesAgent")
            return forecasts
        except Exception as e:
            log_agent_raw(f"❌ Weather fetch failed: {e}", agent_name="PlacesAgent")
            self._update_weather_status(f"Weather unavailable: {str(e)[:60]}")
            return []

    def _parse_weather_data(self, data):
        try:
            return Weather(date=data["date"], temperature=data.get("temperature", 0), feels_like=data.get("feels_like", 0),
                temp_min=data.get("temp_min", 0), temp_max=data.get("temp_max", 0), description=data.get("description", ""),
                icon=data.get("icon"), humidity=data.get("humidity"), wind_speed=data.get("wind_speed"),
                precipitation_probability=data.get("precipitation_probability"), conditions=data.get("condition"))
        except Exception as e:
            log_agent_raw(f"⚠️ Weather parse error: {e}", agent_name="PlacesAgent")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # v9.5: RESTAURANT FETCH — retry wrapper + broader backfill
    # ─────────────────────────────────────────────────────────────────────

    async def _fetch_restaurants_async(self, preferences, num_days):
        destination = preferences.destination
        preferred = preferences.restaurant_prefs.preferred_cuisines
        interested = preferences.restaurant_prefs.interested_cuisines
        target_count = num_days * 3
        all_results, seen_ids = [], set()

        def _add(places, cuisine):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["cuisine_tag"] = cuisine
                    all_results.append(place)

        if not self.google_places or not self.google_places.client:
            self._update_restaurant_status("Google Places not configured")
            return []

        # ── Preferred cuisines (v9.5: with retry) ────────────────────
        preferred_per = max(3, target_count // max(len(preferred) + len(interested), 1))
        for cuisine in preferred:
            self._update_restaurant_status(f"Searching {cuisine} restaurants in {destination}...")
            results = self._search_text_with_retry(
                query=f"{cuisine} restaurant in {destination}",
                location=destination, included_type="restaurant",
                min_rating=3.5, max_results=preferred_per,
                agent_logger=self.logger,
            )
            _add(results, cuisine)

        # ── Interested cuisines (v9.5: with retry) ───────────────────
        interested_per = max(2, preferred_per // 2)
        for cuisine in interested:
            self._update_restaurant_status(f"Searching {cuisine} restaurants in {destination}...")
            results = self._search_text_with_retry(
                query=f"{cuisine} restaurant in {destination}",
                location=destination, included_type="restaurant",
                min_rating=3.5, max_results=interested_per,
                agent_logger=self.logger,
            )
            _add(results, cuisine)

        # ── Primary backfill (v9.5: with retry) ─────────────────────
        if len(all_results) < target_count:
            shortfall = target_count - len(all_results)
            self._update_restaurant_status(f"Finding {shortfall} more top-rated restaurants...")
            results = self._search_text_with_retry(
                query=f"best restaurant in {destination}",
                location=destination, included_type="restaurant",
                min_rating=4.0, max_results=shortfall,
                agent_logger=self.logger,
            )
            _add(results, "General")

        # ── v9.5: Broader backfill when still short (e.g. after 500s) ─
        if len(all_results) < target_count:
            shortfall = target_count - len(all_results)
            log_agent_raw(
                f"⚠️ Still {shortfall} restaurants short of target {target_count} — "
                f"trying broader backfill queries",
                agent_name="PlacesAgent",
            )
            # Strip "(CODE)" from destination for cleaner queries
            clean_dest = re.sub(r'\s*\([A-Z]{3}\)\s*$', '', destination).strip()
            backfill_queries = [
                f"popular restaurant in {clean_dest}",
                f"top rated dining in {clean_dest}",
                f"restaurant near downtown {clean_dest}",
            ]
            for bq in backfill_queries:
                if len(all_results) >= target_count:
                    break
                remaining = target_count - len(all_results)
                self._update_restaurant_status(f"Backfill: {bq}...")
                results = self._search_text_with_retry(
                    query=bq, location=destination, included_type="restaurant",
                    min_rating=3.5, max_results=min(remaining, 5),
                    agent_logger=self.logger,
                )
                _add(results, "General")

        final = all_results[:target_count]
        self._update_restaurant_status(f"Restaurant search done — {len(final)} candidates found")
        log_agent_raw(f"✅ Restaurants: {len(final)} found (target: {target_count})", agent_name="PlacesAgent")
        return final

    # ─────────────────────────────────────────────────────────────────────
    # v9.5: ACTIVITY FETCH — retry wrapper on all text search calls
    # ─────────────────────────────────────────────────────────────────────

    async def _fetch_activities_async(self, preferences, num_days):
        destination = preferences.destination
        preferred = preferences.activity_prefs.preferred_interests
        interested = preferences.activity_prefs.interested_interests
        target_count = num_days * 3
        all_results, seen_ids = [], set()

        def _add(places, tag):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["interest_tag"] = tag
                    all_results.append(place)

        if not self.google_places or not self.google_places.client:
            self._update_activity_status("Google Places not configured")
            return []

        # ── Preferred interests (v9.5: with retry) ───────────────────
        preferred_per = max(3, target_count // max(len(preferred) + len(interested), 1))
        for interest in preferred:
            self._update_activity_status(f"Searching {interest} in {destination}...")
            results = self._search_text_with_retry(
                query=f"{interest} in {destination}",
                location=destination, min_rating=3.5,
                max_results=preferred_per, agent_logger=self.logger,
            )
            _add(results, interest)

        # ── Interested interests (v9.5: with retry) ──────────────────
        interested_per = max(2, preferred_per // 2)
        for interest in interested:
            self._update_activity_status(f"Searching {interest} in {destination}...")
            results = self._search_text_with_retry(
                query=f"{interest} in {destination}",
                location=destination, min_rating=3.5,
                max_results=interested_per, agent_logger=self.logger,
            )
            _add(results, interest)

        # ── Seasonal events (v9.5: with retry) ───────────────────────
        try:
            trip_month = datetime.strptime(preferences.departure_date, "%Y-%m-%d").strftime("%B")
        except (ValueError, AttributeError):
            trip_month = ""

        if trip_month:
            self._update_activity_status(f"Searching {trip_month} festivals & events in {destination}...")
            festival_results = self._search_text_with_retry(
                query=f"{trip_month} festival event in {destination}",
                location=destination, min_rating=3.5, max_results=3,
                agent_logger=self.logger,
            )
            _add(festival_results, f"{trip_month} Festival/Event")
            if festival_results:
                log_agent_raw(f"🎉 Found {len(festival_results)} seasonal events for {trip_month}", agent_name="PlacesAgent")

        # ── Nearby category search (unchanged — uses Nearby Search API, not text) ─
        categories = self._determine_categories(preferences)
        non_restaurant = [c for c in categories if c != "restaurants"]
        if non_restaurant and len(all_results) < target_count:
            self._update_activity_status(f"Searching nearby {', '.join(non_restaurant)} within 5km...")
            place_types = list(set(t for cat in non_restaurant for t in self.CATEGORY_TYPES.get(cat, [])))
            nearby = self.google_places.search_places(
                location=destination, radius=5000, place_types=place_types,
                min_rating=3.5, max_results=8, agent_logger=self.logger,
            )
            for ptype, places in nearby.items():
                for pd in places:
                    pid = pd.get("place_id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        pd["interest_tag"] = ptype
                        all_results.append(pd)

        final = all_results[:target_count]
        self._update_activity_status(f"Activity search done — {len(final)} candidates found")
        log_agent_raw(f"✅ Activities: {len(final)} found (target: {target_count})", agent_name="PlacesAgent")
        return final

    # ─────────────────────────────────────────────────────────────────────
    # DATA PROCESSING
    # ─────────────────────────────────────────────────────────────────────

    def _determine_categories(self, preferences):
        all_interests = self._get_all_interests(preferences)
        categories = []
        interest_map = {"food": ["restaurants"], "dining": ["restaurants"], "culture": ["culture", "attractions"], "art": ["culture"],
            "history": ["attractions", "culture"], "museum": ["culture"], "sightseeing": ["attractions"], "shopping": ["shopping"],
            "nature": ["nature"], "outdoor": ["nature"], "park": ["nature"], "entertainment": ["entertainment"],
            "nightlife": ["entertainment"], "theater": ["entertainment", "culture"]}
        for interest in all_interests:
            il = interest.lower()
            for key, cats in interest_map.items():
                if key in il: categories.extend(cats)
        categories = list(set(categories))[:4]
        return categories if categories else ["attractions", "culture"]

    @staticmethod
    def _classify_day_weather(weather_dict):
        if not weather_dict: return "either"
        rain_prob = weather_dict.get("precipitation_probability", 0) or 0
        desc = (weather_dict.get("description") or "").lower()
        cond = (weather_dict.get("conditions") or "").lower()
        indoor_kw = ["rain", "storm", "thunder", "snow", "sleet", "drizzle", "heavy"]
        if rain_prob > 60 or any(kw in desc for kw in indoor_kw) or any(kw in cond for kw in indoor_kw): return "indoor"
        outdoor_kw = ["clear", "sunny", "fair", "fine"]
        if rain_prob <= 30 and (any(kw in desc for kw in outdoor_kw) or any(kw in cond for kw in outdoor_kw) or rain_prob == 0): return "outdoor"
        return "either"

    def _compute_trip_days(self, preferences, weather_by_date):
        try:
            start = datetime.strptime(preferences.departure_date, "%Y-%m-%d")
            end = datetime.strptime(preferences.return_date, "%Y-%m-%d")
        except (ValueError, AttributeError):
            return [{"day": i+1, "date": "", "weather_class": "either", "weather_summary": "N/A"} for i in range(5)]
        days, current, day_num = [], start, 1
        while current < end:
            date_str = current.strftime("%Y-%m-%d")
            weather = weather_by_date.get(date_str)
            wc = self._classify_day_weather(weather)
            ws = f"{weather.get('description', 'N/A')}, {weather.get('temp_min', '?')}–{weather.get('temp_max', '?')}°F, {(weather.get('precipitation_probability', 0) or 0):.0f}% rain" if weather else "No forecast"
            days.append({"day": day_num, "date": date_str, "weather_class": wc, "weather_summary": ws})
            current += timedelta(days=1)
            day_num += 1
        return days

    def _classify_venue_type(self, place_dict):
        primary = (place_dict.get("primary_type") or "").lower()
        types_list = [t.lower() for t in (place_dict.get("types") or [])]
        all_types = {primary} | set(types_list)
        if all_types & self.INDOOR_TYPES: return "indoor"
        if all_types & self.OUTDOOR_TYPES: return "outdoor"
        return "either"

    def _segregate_and_enrich(self, cuisine_restaurants, interest_activities, preferences):
        EXCLUDED = {"hotel", "lodging", "motel", "hostel", "resort", "resort_hotel"}
        RESTAURANT_KW = {"restaurant", "cafe", "bar", "bakery", "food"}
        restaurants = []
        for r in cuisine_restaurants:
            if (r.get("primary_type") or "").lower() in EXCLUDED: continue
            place = self._google_dict_to_place(r)
            if place:
                d = place.model_dump(mode="json")
                d["cuisine_tag"] = r.get("cuisine_tag", "")
                d["venue_type"] = "indoor"
                restaurants.append(d)
        activities = []
        for a in interest_activities:
            primary = (a.get("primary_type") or "").lower()
            if primary in EXCLUDED or primary in RESTAURANT_KW: continue
            place = self._google_dict_to_place(a)
            if place:
                d = place.model_dump(mode="json")
                d["interest_tag"] = a.get("interest_tag", "")
                d["venue_type"] = self._classify_venue_type(a)
                activities.append(d)
        return restaurants, activities

    def _google_dict_to_place(self, google_data):
        try:
            opening_hours = None
            if google_data.get("currentOpeningHours"):
                opening_hours = {"open_now": google_data["currentOpeningHours"].get("openNow"), "weekday_text": google_data["currentOpeningHours"].get("weekdayDescriptions", [])}
            reviews = None
            raw_reviews = google_data.get("reviews")
            if raw_reviews:
                from models.trip import HotelReview
                reviews = []
                for r in raw_reviews[:5]:
                    try: reviews.append(HotelReview(**r))
                    except: continue
            return Place(id=google_data.get("place_id", str(time.time())), name=google_data.get("name", "Unknown Place"),
                address=google_data.get("address", ""), latitude=google_data.get("latitude"), longitude=google_data.get("longitude"),
                rating=google_data.get("google_rating"), user_ratings_total=google_data.get("user_ratings_total"),
                category=google_data.get("primary_type", "other"), description=f"Rated {google_data.get('google_rating', 0)}/5 by {google_data.get('user_ratings_total', 0)} reviewers",
                photos=google_data.get("photos", [])[:5], opening_hours=opening_hours, price_level=google_data.get("price_level"),
                website=google_data.get("website"), reviews=reviews, phone_number=google_data.get("phone_number"), google_url=google_data.get("google_url"))
        except Exception as e:
            log_agent_raw(f"Failed to create place: {e}", agent_name="PlacesAgent")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # STORAGE
    # ─────────────────────────────────────────────────────────────────────

    def _store_weather(self, weather_dicts, preferences):
        if not weather_dicts: return
        self.trip_storage.add_weather(trip_id=self.trip_id, weather=weather_dicts,
            metadata={"destination": preferences.destination, "start_date": preferences.departure_date, "end_date": preferences.return_date, "search_time": datetime.now().isoformat(), "total_days": len(weather_dicts)})
        try:
            min_t = min(d.get("temp_min", 0) for d in weather_dicts)
            max_t = max(d.get("temp_max", 0) for d in weather_dicts)
            temps = [d.get("temperature", 0) for d in weather_dicts]
            rainy = sum(1 for d in weather_dicts if (d.get("precipitation_probability", 0) or 0) > 50)
            self.trip_storage.store_recommendation(trip_id=self.trip_id, category="weather", recommended_id="weather_forecast",
                reason=f"Weather in {preferences.destination}: {min_t:.0f}°F–{max_t:.0f}°F over {len(weather_dicts)} days. {rainy} day{'s' if rainy != 1 else ''} with rain expected.",
                metadata={"destination": preferences.destination, "num_days": len(weather_dicts), "temp_min": round(min_t, 1), "temp_max": round(max_t, 1), "avg_temp": round(sum(temps)/len(temps), 1) if temps else 0, "rainy_days": rainy})
        except Exception as e:
            log_agent_raw(f"⚠️ Weather recommendation storage failed: {e}", agent_name="PlacesAgent")
        log_agent_raw(f"💾 Stored {len(weather_dicts)} weather forecasts", agent_name="PlacesAgent")

    def _store_results(self, restaurants, activities, preferences, api_duration):
        meta = {"destination": preferences.destination, "search_time": datetime.now().isoformat(), "api_duration": api_duration}
        if restaurants: self.trip_storage.add_restaurants(trip_id=self.trip_id, restaurants=restaurants, metadata={**meta, "total_results": len(restaurants)})
        if activities: self.trip_storage.add_activities(trip_id=self.trip_id, activities=activities, metadata={**meta, "total_results": len(activities)})
        self.trip_storage.log_api_call(trip_id=self.trip_id, agent_name="PlacesAgent", api_name="GooglePlaces", duration=api_duration)

    def _weather_to_dict(self, weather): return weather.model_dump(mode="json")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: SCALABLE LLM PIPELINE (v9.4)
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_travel_plan(self, weather_forecasts, restaurants, activities, trip_days, preferences, num_days):
        if not restaurants and not activities:
            return "No places found matching your interests."

        restaurant_lookup = self._build_venue_lookup(restaurants)
        activity_lookup = self._build_venue_lookup(activities)
        weather_by_date = {}
        for f in weather_forecasts:
            date_key = f.date if hasattr(f, 'date') else f.get('date', '')
            if date_key: weather_by_date[date_key] = f

        self._current_destination = preferences.destination

        # ── Try scalable pipeline ─────────────────────────────────────
        try:
            result = self._three_phase_pipeline(
                weather_forecasts, restaurants, activities,
                trip_days, preferences, num_days,
                restaurant_lookup, activity_lookup, weather_by_date,
            )
            if result: return result
            log_agent_raw("⚠️ Scalable pipeline returned no results — falling back", agent_name="PlacesAgent")
        except Exception as e:
            log_agent_raw(f"⚠️ Scalable pipeline failed: {e} — falling back", agent_name="PlacesAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="PlacesAgent")

        # ── Fallback: single streaming call (v9.2 behavior) ──────────
        return self._fallback_single_stream(
            weather_forecasts, restaurants, activities, trip_days,
            preferences, num_days, restaurant_lookup, activity_lookup, weather_by_date,
        )

    def _three_phase_pipeline(self, weather_forecasts, restaurants, activities,
                              trip_days, preferences, num_days,
                              restaurant_lookup, activity_lookup, weather_by_date):
        """
        v9.4 Scalable pipeline:
          Phase 2a: Planner — assign venues to all day/slots (~4s)
          Phase 2b: N Writers + 1 Nuggets call — all parallel
            - Writers: ceil(num_days/3), each handles ≤3 days
            - Nuggets: dedicated LLM call, runs alongside writers
        """
        pipeline_start = time.time()

        # ══════════════════════════════════════════════════════════════
        # PHASE 2a: PLANNER — assign venues to slots
        # ══════════════════════════════════════════════════════════════
        self._update_planner_status("AI assigning venues to days...")
        log_agent_raw("📋 Phase 2a: Planner — assigning venues to day/slots", agent_name="PlacesAgent")
        planner_start = time.time()

        assignments = self._run_planner(
            weather_forecasts, restaurants, activities, trip_days, preferences, num_days
        )
        planner_duration = time.time() - planner_start

        if not assignments or not assignments.get("assignments"):
            log_agent_raw(f"⚠️ Planner failed after {planner_duration:.1f}s", agent_name="PlacesAgent")
            return None

        assigned_days = assignments["assignments"]
        log_agent_raw(
            f"✅ Planner complete in {planner_duration:.1f}s — {len(assigned_days)} days assigned",
            agent_name="PlacesAgent",
        )

        # Log the assignments for debugging
        for ad in assigned_days:
            venues = [ad.get(t, {}).get("venue_name", "?") for t in ["morning", "lunch", "afternoon", "dinner"]]
            log_agent_raw(f"   Day {ad.get('day')}: {', '.join(venues)}", agent_name="PlacesAgent")

        # ══════════════════════════════════════════════════════════════
        # PHASE 2b: DYNAMIC WRITERS + DEDICATED NUGGETS (all parallel)
        #
        # Writers scale by ceil(num_days / 3):
        #   1-3 days  → 1 writer
        #   4-6 days  → 2 writers
        #   7-9 days  → 3 writers
        #   10-12 days → 4 writers
        #
        # Nuggets run as a separate parallel LLM call — guaranteed.
        # ══════════════════════════════════════════════════════════════
        DAYS_PER_WRITER = 3
        num_writers = math.ceil(num_days / DAYS_PER_WRITER)

        # Chunk assigned days into groups of DAYS_PER_WRITER
        writer_chunks = []
        for i in range(num_writers):
            start_day = i * DAYS_PER_WRITER + 1
            end_day = (i + 1) * DAYS_PER_WRITER
            chunk_days = [d for d in assigned_days if start_day <= d.get("day", 0) <= end_day]
            chunk_meta = [td for td in trip_days if start_day <= td.get("day", 0) <= end_day]
            if chunk_days:  # Only create writer if it has days to write
                writer_chunks.append((chunk_days, chunk_meta))

        num_writers = len(writer_chunks)  # Actual count after filtering empty chunks
        # +1 for nuggets thread
        total_threads = num_writers + 1

        writer_labels = [chr(65 + i) for i in range(num_writers)]  # A, B, C, D...
        chunk_desc = ", ".join(
            f"{label}({len(chunk[0])} days)" for label, chunk in zip(writer_labels, writer_chunks)
        )

        self._update_planner_status(f"AI writing {num_days}-day travel journal...")
        log_agent_raw(
            f"✍️ Phase 2b: {num_writers} writer(s) + nuggets (all parallel) — {chunk_desc}",
            agent_name="PlacesAgent",
        )
        writer_start = time.time()

        # ── Run all writers + nuggets in parallel ─────────────────────
        partial_plan = {"daily_schedule": [], "nuggets": []}
        writer_results = []

        with ThreadPoolExecutor(max_workers=total_threads, thread_name_prefix="writer") as executor:
            # Submit day writers
            writer_futures = []
            for i, (chunk_days, chunk_meta) in enumerate(writer_chunks):
                future = executor.submit(
                    self._run_writer,
                    writer_label=writer_labels[i],
                    assigned_days=chunk_days,
                    trip_days_meta=chunk_meta,
                    preferences=preferences,
                    num_days=num_days,
                    restaurant_lookup=restaurant_lookup,
                    activity_lookup=activity_lookup,
                    weather_by_date=weather_by_date,
                    partial_plan=partial_plan,
                )
                writer_futures.append((writer_labels[i], future))

            # Submit nuggets generator in parallel with writers
            nuggets_future = executor.submit(
                self._generate_nuggets,
                assigned_days=assigned_days,
                trip_days=trip_days,
                preferences=preferences,
                weather_forecasts=weather_forecasts,
            )

            # Collect writer results
            for label, future in writer_futures:
                result = future.result()
                writer_results.append((label, result))

            # Collect nuggets result
            nuggets_result = nuggets_future.result()

        writer_duration = time.time() - writer_start
        total_duration = time.time() - pipeline_start

        # ── Merge results ─────────────────────────────────────────────
        partial_plan["daily_schedule"].sort(key=lambda d: d.get("day", 0))

        # Add nuggets from dedicated call
        if nuggets_result:
            partial_plan["nuggets"] = nuggets_result

        days_count = len(partial_plan["daily_schedule"])
        nuggets_count = len(partial_plan["nuggets"])

        # Log writer performance
        for label, result in writer_results:
            log_agent_raw(
                f"   Writer {label}: {result.get('days', 0)} days in {result.get('duration', 0):.1f}s",
                agent_name="PlacesAgent",
            )
        log_agent_raw(
            f"   Nuggets: {nuggets_count} in {nuggets_result is not None and 'ok' or 'failed'}",
            agent_name="PlacesAgent",
        )
        log_agent_raw(
            f"✅ Scalable pipeline complete in {total_duration:.1f}s "
            f"(planner: {planner_duration:.1f}s, writers+nuggets: {writer_duration:.1f}s) — "
            f"{days_count} days, {nuggets_count} nuggets, {num_writers} writer(s)",
            agent_name="PlacesAgent",
        )

        if days_count == 0:
            return None

        # ── Store final plan ──────────────────────────────────────────
        try:
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id, category="daily_plan", recommended_id="daily_plan",
                reason=json.dumps(partial_plan),
                metadata={"destination": preferences.destination, "num_days": num_days, "format": "structured_v1",
                    "structured_data": partial_plan, "streaming": False, "days_complete": days_count, "days_total": num_days})
        except Exception as e:
            log_agent_raw(f"⚠️ Final plan storage failed: {e}", agent_name="PlacesAgent")

        summary_text = self._structured_plan_to_text(partial_plan, preferences)
        try:
            self._store_place_recommendations(
                summary_text,
                [v for v in restaurant_lookup.values() if isinstance(v, dict) and "name" in v],
                [v for v in activity_lookup.values() if isinstance(v, dict) and "name" in v],
            )
        except Exception:
            pass

        self._update_planner_status("Travel plan complete")
        return summary_text

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 2a: PLANNER — assign venues to slots
    # v9.5: Dynamic repeat rules based on pool size
    # ─────────────────────────────────────────────────────────────────────

    def _run_planner(self, weather_forecasts, restaurants, activities, trip_days, preferences, num_days):
        """
        Fast LLM call that assigns venues to day/time slots.
        Output: flat venue names only — Python enriches with type/category.
        ~200 output tokens, ~3-5 seconds.

        v9.5: Dynamic repeat rules — when pool < slots, instructs LLM to
        spread repeats instead of block-copying day groups.
        """
        rest_lines = [f"  {r.get('name', '?')} [{r.get('cuisine_tag', '?')}]" for r in restaurants]
        act_lines = [f"  {a.get('name', '?')} [{a.get('interest_tag', '?')}, {a.get('venue_type', 'either')}]" for a in activities]
        day_lines = [f"  Day {d['day']} ({d['date']}): {d['weather_class']}" for d in trip_days]

        # ── v9.5: Dynamic repeat rules based on pool size vs slots ────
        num_restaurant_slots = num_days * 2   # lunch + dinner per day
        num_activity_slots = num_days * 2     # morning + afternoon per day

        if len(restaurants) >= num_restaurant_slots and len(activities) >= num_activity_slots:
            repeat_rule = "No repeats — every venue appears only once."
        else:
            shortages = []
            if len(restaurants) < num_restaurant_slots:
                shortages.append(
                    f"{len(restaurants)} restaurants for {num_restaurant_slots} restaurant slots"
                )
            if len(activities) < num_activity_slots:
                shortages.append(
                    f"{len(activities)} activities for {num_activity_slots} activity slots"
                )
            repeat_rule = (
                f"NOTE: Limited pool — {' and '.join(shortages)}. "
                "Repeats are necessary, but SPREAD them out: "
                "never repeat a venue on consecutive days, "
                "use every available venue before repeating any, "
                "and vary the time slot when repeating "
                "(e.g. lunch on day 1 → dinner on day 4)."
            )

        prompt = textwrap.dedent(f"""\
Assign venues for a {num_days}-day trip to {preferences.destination}.

WEATHER: {chr(10).join(day_lines)}

RESTAURANTS: {chr(10).join(rest_lines)}

ACTIVITIES: {chr(10).join(act_lines)}

RULES: 4 slots/day: morning=activity, lunch=restaurant, afternoon=activity, dinner=restaurant.
EXACT names only. Rotate cuisines. Indoor activities on indoor days.
{repeat_rule}
Preferred: {', '.join(preferences.restaurant_prefs.preferred_cuisines)} cuisines, {', '.join(preferences.activity_prefs.preferred_interests)} activities.

Return JSON: {{"days":[{{"day":1,"date":"YYYY-MM-DD","morning":"venue","lunch":"venue","afternoon":"venue","dinner":"venue"}}]}}""")

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "Output ONLY a JSON object. No text, no markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )

            usage = response.usage
            if usage:
                log_agent_raw(
                    f"📊 Planner tokens — prompt: {usage.prompt_tokens}, "
                    f"completion: {usage.completion_tokens}, total: {usage.total_tokens}",
                    agent_name="PlacesAgent",
                )

            finish_reason = response.choices[0].finish_reason
            raw = response.choices[0].message.content.strip()
            log_agent_raw(f"📋 Planner output: {len(raw)} chars, finish_reason={finish_reason}", agent_name="PlacesAgent")

            if finish_reason == "length":
                log_agent_raw("⚠️ Planner truncated — increase max_tokens", agent_name="PlacesAgent")

            raw = re.sub(r',\s*([}\]])', r'\1', raw)
            parsed = json.loads(raw)

            flat_days = parsed.get("days") or parsed.get("assignments") or []
            if not flat_days:
                log_agent_raw("⚠️ Planner returned no days", agent_name="PlacesAgent")
                return None

            rest_map = {}
            for r in restaurants:
                name = r.get("name", "")
                if name:
                    rest_map[name.lower()] = {"cuisine_tag": r.get("cuisine_tag", ""), "type": "restaurant"}

            act_map = {}
            for a in activities:
                name = a.get("name", "")
                if name:
                    act_map[name.lower()] = {"interest_tag": a.get("interest_tag", ""), "type": "activity"}

            enriched_days = []
            for fd in flat_days:
                day = {"day": fd.get("day"), "date": fd.get("date", "")}
                for slot_time, expected_type in [("morning", "activity"), ("lunch", "restaurant"), ("afternoon", "activity"), ("dinner", "restaurant")]:
                    venue_name = fd.get(slot_time, "")
                    if isinstance(venue_name, dict):
                        day[slot_time] = venue_name
                        continue

                    vn_lower = venue_name.lower() if venue_name else ""
                    if expected_type == "restaurant" and vn_lower in rest_map:
                        day[slot_time] = {"venue_name": venue_name, "type": "restaurant", "category": rest_map[vn_lower]["cuisine_tag"]}
                    elif expected_type == "activity" and vn_lower in act_map:
                        day[slot_time] = {"venue_name": venue_name, "type": "activity", "category": act_map[vn_lower]["interest_tag"]}
                    else:
                        matched = False
                        lookup = rest_map if expected_type == "restaurant" else act_map
                        for key, info in lookup.items():
                            if key in vn_lower or vn_lower in key:
                                cat_key = "cuisine_tag" if expected_type == "restaurant" else "interest_tag"
                                day[slot_time] = {"venue_name": venue_name, "type": expected_type, "category": info[cat_key]}
                                matched = True
                                break
                        if not matched:
                            day[slot_time] = {"venue_name": venue_name, "type": expected_type, "category": "General"}

                enriched_days.append(day)

            return {"assignments": enriched_days}

        except Exception as e:
            log_agent_raw(f"⚠️ Planner LLM failed: {e}", agent_name="PlacesAgent")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 2b: WRITER — write day narratives only (no nuggets)
    # ─────────────────────────────────────────────────────────────────────

    def _run_writer(self, writer_label, assigned_days, trip_days_meta,
                    preferences, num_days,
                    restaurant_lookup, activity_lookup, weather_by_date,
                    partial_plan):
        """
        Streaming tool-call Writer. Writes day narratives ONLY (no nuggets).
        Each writer handles ≤3 days. Called in a thread — writes directly
        to shared partial_plan and stores each day to Redis immediately.
        """
        writer_start = time.time()
        day_nums = [d.get("day") for d in assigned_days]
        log_agent_raw(f"✍️ Writer {writer_label} starting — Days {day_nums}", agent_name="PlacesAgent")

        # Build writer prompt with assignments + weather
        day_blocks = []
        for ad in assigned_days:
            day_num = ad.get("day", "?")
            date = ad.get("date", "")
            td = next((t for t in trip_days_meta if t.get("day") == day_num), {})
            weather_info = td.get("weather_summary", "N/A")

            slots_desc = []
            for slot_time in ["morning", "lunch", "afternoon", "dinner"]:
                slot = ad.get(slot_time, {})
                name = slot.get("venue_name", "?")
                stype = slot.get("type", "?")
                cat = slot.get("category", "?")
                if stype == "restaurant":
                    match = self._find_venue_match(name, restaurant_lookup)
                else:
                    match = self._find_venue_match(name, activity_lookup)
                rating_val = match.get('rating') if match else None
                rating = f" {rating_val:.1f}★" if rating_val is not None else ""
                details = ""
                if match:
                    addr = match.get("address", "")
                    reviews_total = match.get("user_ratings_total", 0)
                    if addr:
                        details += f" | {addr}"
                    if reviews_total:
                        details += f" | {reviews_total} reviews"
                slots_desc.append(f"    {slot_time}: {name} ({stype}, {cat}){rating}{details}")

            day_blocks.append(f"  Day {day_num} ({date}) — Weather: {weather_info}\n" + "\n".join(slots_desc))

        prompt = textwrap.dedent(f"""\
Write engaging tour-guide descriptions for these pre-assigned days in {preferences.destination}.

TRAVELER PROFILE:
- Preferred cuisines: {', '.join(preferences.restaurant_prefs.preferred_cuisines) or 'None'}
- Interested cuisines: {', '.join(preferences.restaurant_prefs.interested_cuisines) or 'None'}
- Preferred activities: {', '.join(preferences.activity_prefs.preferred_interests) or 'None'}
- Interested activities: {', '.join(preferences.activity_prefs.interested_interests) or 'None'}
- Pace: {preferences.activity_prefs.pace}

DAILY ASSIGNMENTS:
{chr(10).join(day_blocks)}

INSTRUCTIONS:
Call emit_day for EACH day above (in order). Use the EXACT venue names given.
You MUST call emit_day exactly {len(assigned_days)} time(s) — once per day listed above. No more, no less.

STYLE RULES:
- You are an enthusiastic, knowledgeable tour guide addressing the traveler directly
- Use second person ("you'll discover", "don't miss the") — NEVER first person ("I visited")
- Each day: creative evocative title + 1-2 sentence intro referencing the weather
- Each slot narrative: EXACTLY 2 sentences that are SPECIFIC to this venue:
  * Sentence 1: What makes THIS place unique — mention a specific feature, famous item,
    signature dish, architectural detail, or what it's known for
  * Sentence 2: Why it's perfect for this traveler or a practical tip
- Be warm, enthusiastic, and paint a picture — make the traveler excited to visit
- GOOD examples:
  "The British Museum houses over 8 million works including the Rosetta Stone and Elgin Marbles — you could spend days here and still discover something new. As a museum enthusiast, head straight to the Egyptian galleries on the upper floor for the best experience."
  "Rules, established in 1798, is London's oldest restaurant and serves legendary game pies and classic roasts in a setting dripping with Victorian charm. It's the perfect introduction to traditional British dining — try the venison if it's on the menu."
- BAD (too generic): "Relish authentic Indian cuisine served in a beautiful venue."

TOKEN BUDGET IS LIMITED — exactly 2 sentences per slot, no more.""")

        # ── Streaming LLM call with emit_day ONLY ─────────────────────
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": (
                        "You are an enthusiastic expert tour guide writing venue descriptions for a travel itinerary. "
                        "Every narrative MUST mention something SPECIFIC to that venue — a signature dish, famous exhibit, "
                        "architectural feature, or what it's renowned for. NEVER write generic descriptions that could apply "
                        "to any similar venue. Use second person (you/your). NEVER first person. "
                        "Exactly 2 sentences per slot. Use the emit_day tool ONLY."
                    )},
                    {"role": "user", "content": prompt},
                ],
                tools=[EMIT_DAY_TOOL],  # Only emit_day — no nuggets
                tool_choice="required",
                parallel_tool_calls=True,
                temperature=0.7,
                max_tokens=2500,
                stream=True,
            )
        except Exception as e:
            log_agent_raw(f"⚠️ Writer {writer_label} LLM call failed: {e}", agent_name="PlacesAgent")
            return {"days": 0, "duration": time.time() - writer_start}

        # ── Accumulate and dispatch tool calls ────────────────────────
        tool_buffers = {}
        current_index = -1
        days_emitted = 0

        for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice or not choice.delta: continue
            delta = choice.delta

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index

                    if idx is not None and idx != current_index:
                        if current_index >= 0 and current_index in tool_buffers:
                            d = self._flush_day_tool_call(
                                tool_buffers[current_index], writer_label,
                                partial_plan, num_days, preferences,
                                restaurant_lookup, activity_lookup, weather_by_date,
                            )
                            days_emitted += d
                        current_index = idx
                        if idx not in tool_buffers:
                            tool_buffers[idx] = {"name": "", "arguments": ""}

                    target_idx = idx if idx is not None else current_index
                    if target_idx >= 0 and target_idx in tool_buffers:
                        if tc.function:
                            if tc.function.name: tool_buffers[target_idx]["name"] += tc.function.name
                            if tc.function.arguments: tool_buffers[target_idx]["arguments"] += tc.function.arguments

        # Flush last tool call
        if current_index >= 0 and current_index in tool_buffers:
            d = self._flush_day_tool_call(
                tool_buffers[current_index], writer_label,
                partial_plan, num_days, preferences,
                restaurant_lookup, activity_lookup, weather_by_date,
            )
            days_emitted += d

        duration = time.time() - writer_start
        log_agent_raw(
            f"✅ Writer {writer_label} complete in {duration:.1f}s — {days_emitted} days",
            agent_name="PlacesAgent",
        )
        return {"days": days_emitted, "duration": duration}

    def _flush_day_tool_call(self, tool_call, writer_label, partial_plan, num_days,
                             preferences, restaurant_lookup, activity_lookup, weather_by_date):
        """Flush a completed emit_day tool call. Returns days_added (0 or 1)."""
        name = tool_call.get("name", "")
        raw_args = tool_call.get("arguments", "")
        if name != "emit_day" or not raw_args:
            return 0

        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            log_agent_raw(f"⚠️ Writer {writer_label} emit_day JSON failed: {e}", agent_name="PlacesAgent")
            return 0

        self._enrich_single_day(args, restaurant_lookup, activity_lookup, weather_by_date)
        partial_plan["daily_schedule"].append(args)
        days_done = len(partial_plan["daily_schedule"])
        day_num = args.get("day", "?")

        # Per-day feed messages
        activity_names = [s.get("venue_name", "") for s in args.get("slots", []) if s.get("type") == "activity"]
        restaurant_names = [s.get("venue_name", "") for s in args.get("slots", []) if s.get("type") == "restaurant"]
        if activity_names: self._update_activity_status(f"📅 Day {day_num}: {', '.join(activity_names[:2])}")
        if restaurant_names: self._update_restaurant_status(f"📅 Day {day_num}: {', '.join(restaurant_names[:2])}")
        weather_info = args.get("weather", {})
        if weather_info:
            self._update_weather_status(f"📅 Day {day_num}: {weather_info.get('icon', '')} {weather_info.get('temp_high', '')}°F {weather_info.get('description', '')}")

        # Store partial plan for progressive rendering
        try:
            sorted_schedule = sorted(partial_plan["daily_schedule"], key=lambda d: d.get("day", 0))
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id, category="daily_plan", recommended_id="daily_plan",
                reason=json.dumps({"daily_schedule": sorted_schedule, "nuggets": partial_plan["nuggets"]}),
                metadata={"destination": getattr(self, '_current_destination', ''), "num_days": num_days,
                    "format": "structured_v1", "structured_data": {"daily_schedule": sorted_schedule, "nuggets": partial_plan["nuggets"]},
                    "streaming": True, "days_complete": days_done, "days_total": num_days})
        except Exception as e:
            log_agent_raw(f"⚠️ Partial plan store failed: {e}", agent_name="PlacesAgent")

        log_agent_raw(f"📅 Writer {writer_label}: Day {day_num}/{num_days} emitted", agent_name="PlacesAgent")
        return 1

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 2b (parallel): DEDICATED NUGGETS GENERATOR
    # ─────────────────────────────────────────────────────────────────────

    def _generate_nuggets(self, assigned_days, trip_days, preferences, weather_forecasts):
        """
        Dedicated LLM call for travel nuggets. Runs in parallel with day writers.
        Does NOT depend on writer output — uses planner assignments + weather data.
        Returns list of nugget dicts or None on failure.
        """
        nugget_start = time.time()
        log_agent_raw("💡 Nuggets generator starting (parallel with writers)", agent_name="PlacesAgent")
        self._update_planner_status("Generating travel tips...")

        # Build context from planner assignments (not writer output)
        day_summaries = []
        for ad in assigned_days:
            day_num = ad.get("day", "?")
            date = ad.get("date", "")
            venues = []
            for slot_time in ["morning", "lunch", "afternoon", "dinner"]:
                slot = ad.get(slot_time, {})
                name = slot.get("venue_name", "?")
                cat = slot.get("category", "?")
                venues.append(f"{name} ({cat})")
            # Get weather for this day
            td = next((t for t in trip_days if t.get("day") == day_num), {})
            weather_summary = td.get("weather_summary", "N/A")
            day_summaries.append(f"Day {day_num} ({date}): {', '.join(venues)} — Weather: {weather_summary}")

        try:
            trip_month = datetime.strptime(preferences.departure_date, "%Y-%m-%d").strftime("%B %Y")
        except (ValueError, AttributeError):
            trip_month = "the travel period"

        weather_overview = "No forecast available."
        if weather_forecasts:
            min_t = min(f.temp_min for f in weather_forecasts)
            max_t = max(f.temp_max for f in weather_forecasts)
            rainy = sum(1 for f in weather_forecasts if (f.precipitation_probability or 0) > 50)
            weather_overview = f"{min_t:.0f}°F–{max_t:.0f}°F, {rainy} rainy day(s)"

        prompt = textwrap.dedent(f"""\
Generate 5 travel info nuggets for a trip to {preferences.destination} ({trip_month}).

TRIP OVERVIEW:
- Weather: {weather_overview}
- Preferred cuisines: {', '.join(preferences.restaurant_prefs.preferred_cuisines) or 'None'}
- Preferred activities: {', '.join(preferences.activity_prefs.preferred_interests) or 'None'}

DAILY PLAN:
{chr(10).join(day_summaries)}

Generate exactly 5 nuggets as a JSON object with a "nuggets" array.
Each nugget: {{"id": "...", "title": "Short Title Here", "content": "1-2 concise, specific sentences", "color": "..."}}

Required nuggets:
  1. id="packing_tips", color="sky" — specific packing advice based on the weather data above
  2. id="local_events", color="purple" — seasonal events or festivals happening in {trip_month}
  3. id="cuisine_rationale", color="orange" — why the chosen restaurants match the traveler's tastes
  4. id="activity_rationale", color="green" — why these activities were selected, weather-aware scheduling
  5. id="seasonal_tip", color="emerald" — practical travel advice for {preferences.destination} in {trip_month}

Return ONLY valid JSON — no markdown, no backticks.""")

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "You are a travel expert. Return ONLY a JSON object with a 'nuggets' array. No other text."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=600,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)

            if isinstance(parsed, list):
                nuggets = parsed
            elif isinstance(parsed, dict) and "nuggets" in parsed:
                nuggets = parsed["nuggets"]
            else:
                log_agent_raw(f"⚠️ Nuggets: unexpected format — {type(parsed)}", agent_name="PlacesAgent")
                nuggets = None

            duration = time.time() - nugget_start
            if nuggets:
                log_agent_raw(f"✅ Nuggets complete in {duration:.1f}s — {len(nuggets)} nuggets", agent_name="PlacesAgent")
            else:
                log_agent_raw(f"⚠️ Nuggets returned empty after {duration:.1f}s", agent_name="PlacesAgent")

            return nuggets

        except Exception as e:
            duration = time.time() - nugget_start
            log_agent_raw(f"⚠️ Nuggets LLM failed after {duration:.1f}s: {e}", agent_name="PlacesAgent")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # ENRICH A SINGLE DAY
    # ─────────────────────────────────────────────────────────────────────

    def _enrich_single_day(self, day_data, restaurant_lookup, activity_lookup, weather_by_date):
        date_str = day_data.get("date", "")
        weather = weather_by_date.get(date_str)
        if weather:
            _desc = weather.description if hasattr(weather, 'description') else weather.get('description', '')
            _precip = weather.precipitation_probability if hasattr(weather, 'precipitation_probability') else weather.get('precipitation_probability', 0)
            _temp_max = weather.temp_max if hasattr(weather, 'temp_max') else weather.get('temp_max', 0)
            _temp_min = weather.temp_min if hasattr(weather, 'temp_min') else weather.get('temp_min', 0)
            day_data["weather"] = {"icon": get_weather_icon(_desc or "", _precip or 0), "temp_high": round(_temp_max, 0),
                "temp_low": round(_temp_min, 0), "description": _desc or "", "precipitation_prob": _precip or 0}

        for slot in day_data.get("slots", []):
            venue_name, slot_type, category = slot.get("venue_name", ""), slot.get("type", ""), slot.get("category", "")
            if slot_type == "restaurant":
                match = self._find_venue_match(venue_name, restaurant_lookup)
                if match:
                    slot.update({"rating": match.get("rating"), "place_id": match.get("id"), "address": match.get("address", ""),
                        "photos": match.get("photos", [])[:2], "google_url": match.get("google_url", ""), "cuisine_tag": match.get("cuisine_tag", category)})
                slot["icon"] = get_cuisine_icon(slot.get("cuisine_tag", category))
            elif slot_type == "activity":
                match = self._find_venue_match(venue_name, activity_lookup)
                if match:
                    slot.update({"rating": match.get("rating"), "place_id": match.get("id"), "address": match.get("address", ""),
                        "photos": match.get("photos", [])[:2], "google_url": match.get("google_url", ""),
                        "interest_tag": match.get("interest_tag", category), "venue_type": match.get("venue_type", "either")})
                slot["icon"] = get_activity_icon(slot.get("interest_tag", category))

    # ─────────────────────────────────────────────────────────────────────
    # VENUE LOOKUP
    # ─────────────────────────────────────────────────────────────────────

    def _build_venue_lookup(self, places):
        lookup = {}
        for place in places:
            name = place.get("name", "")
            if name:
                lookup[name.lower()] = place
                for w in name.lower().split():
                    if len(w) >= 3 and w not in {"the", "and", "for", "with", "near"}:
                        key = f"_partial_{w}"
                        if key not in lookup: lookup[key] = place
        return lookup

    def _find_venue_match(self, venue_name, lookup):
        if not venue_name: return None
        nl = venue_name.lower()
        if nl in lookup: return lookup[nl]
        for key, place in lookup.items():
            if key.startswith("_partial_"): continue
            if key in nl or nl in key: return place
        for w in nl.split():
            if len(w) >= 3 and w not in {"the", "and", "for"}:
                pk = f"_partial_{w}"
                if pk in lookup: return lookup[pk]
        return None

    # ─────────────────────────────────────────────────────────────────────
    # FALLBACK: Single streaming call (v9.2.1 behavior)
    # ─────────────────────────────────────────────────────────────────────

    def _fallback_single_stream(self, weather_forecasts, restaurants, activities,
                                trip_days, preferences, num_days,
                                restaurant_lookup, activity_lookup, weather_by_date):
        """Fallback: single streaming tool-call, then json_object if that fails too."""
        log_agent_raw("🔄 Fallback: single streaming tool-call", agent_name="PlacesAgent")
        self._update_planner_status("Generating travel plan (fallback)...")

        prompt = self._build_fallback_prompt(weather_forecasts, restaurants, activities, trip_days, preferences, num_days)

        # Try streaming tool calls first
        try:
            result = self._run_single_stream(prompt, num_days, preferences, restaurant_lookup, activity_lookup, weather_by_date)
            if result: return result
        except Exception as e:
            log_agent_raw(f"⚠️ Single stream failed: {e}", agent_name="PlacesAgent")

        # Last resort: json_object mode
        return self._fallback_json_plan(prompt, num_days, preferences, restaurants, activities, restaurant_lookup, activity_lookup, weather_by_date)

    def _run_single_stream(self, prompt, num_days, preferences, restaurant_lookup, activity_lookup, weather_by_date):
        """Single streaming tool-call (v9.2.1 behavior)."""
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": (
                    "You are an enthusiastic expert tour guide. Every narrative MUST mention something SPECIFIC to that venue — "
                    "a signature dish, famous exhibit, or what it's known for. NEVER generic descriptions. "
                    "Second person (you/your), NEVER first person. 2 sentences per narrative. Use the provided tools."
                )},
                {"role": "user", "content": prompt},
            ],
            tools=[EMIT_DAY_TOOL, EMIT_NUGGETS_TOOL], tool_choice="required", parallel_tool_calls=True,
            temperature=0.8, max_tokens=3000, stream=True,
        )

        partial_plan = {"daily_schedule": [], "nuggets": []}
        tool_buffers, current_index = {}, -1

        for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice or not choice.delta: continue
            if choice.delta.tool_calls:
                for tc in choice.delta.tool_calls:
                    idx = tc.index
                    if idx is not None and idx != current_index:
                        if current_index >= 0 and current_index in tool_buffers:
                            self._flush_fallback_tool_call(tool_buffers[current_index], partial_plan, num_days, preferences, restaurant_lookup, activity_lookup, weather_by_date)
                        current_index = idx
                        if idx not in tool_buffers: tool_buffers[idx] = {"name": "", "arguments": ""}
                    target_idx = idx if idx is not None else current_index
                    if target_idx >= 0 and target_idx in tool_buffers:
                        if tc.function:
                            if tc.function.name: tool_buffers[target_idx]["name"] += tc.function.name
                            if tc.function.arguments: tool_buffers[target_idx]["arguments"] += tc.function.arguments

        if current_index >= 0 and current_index in tool_buffers:
            self._flush_fallback_tool_call(tool_buffers[current_index], partial_plan, num_days, preferences, restaurant_lookup, activity_lookup, weather_by_date)

        if not partial_plan["daily_schedule"]: return None

        # Store final
        self.trip_storage.store_recommendation(trip_id=self.trip_id, category="daily_plan", recommended_id="daily_plan",
            reason=json.dumps(partial_plan), metadata={"destination": preferences.destination, "num_days": num_days,
                "format": "structured_v1", "structured_data": partial_plan, "streaming": False,
                "days_complete": len(partial_plan["daily_schedule"]), "days_total": num_days})

        summary = self._structured_plan_to_text(partial_plan, preferences)
        try:
            self._store_place_recommendations(summary,
                [v for v in restaurant_lookup.values() if isinstance(v, dict) and "name" in v],
                [v for v in activity_lookup.values() if isinstance(v, dict) and "name" in v])
        except: pass
        self._update_planner_status("Travel plan complete")
        return summary

    def _flush_fallback_tool_call(self, tool_call, partial_plan, num_days, preferences,
                                  restaurant_lookup, activity_lookup, weather_by_date):
        """Flush tool calls from fallback single-stream (handles both emit_day and emit_nuggets)."""
        name = tool_call.get("name", "")
        raw_args = tool_call.get("arguments", "")
        if not name or not raw_args: return

        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            return

        if name == "emit_day":
            self._enrich_single_day(args, restaurant_lookup, activity_lookup, weather_by_date)
            partial_plan["daily_schedule"].append(args)
            day_num = args.get("day", "?")
            log_agent_raw(f"📅 Writer FB: Day {day_num}/{num_days} emitted", agent_name="PlacesAgent")
        elif name == "emit_nuggets":
            new_nuggets = args.get("nuggets", [])
            partial_plan["nuggets"].extend(new_nuggets)
            log_agent_raw(f"💡 Writer FB: {len(new_nuggets)} nuggets emitted", agent_name="PlacesAgent")

    def _build_fallback_prompt(self, weather_forecasts, restaurants, activities, trip_days, preferences, num_days):
        """Build the full prompt for single-call fallback."""
        weather_summary = "No forecast available."
        if weather_forecasts:
            min_t, max_t = min(f.temp_min for f in weather_forecasts), max(f.temp_max for f in weather_forecasts)
            rainy = sum(1 for f in weather_forecasts if (f.precipitation_probability or 0) > 50)
            weather_summary = f"Temperature: {min_t:.0f}°F–{max_t:.0f}°F, {rainy} rainy days"

        day_lines = [f"  Day {d['day']} ({d['date']}): {d['weather_summary']} → {d['weather_class']}" for d in trip_days]
        rest_lines = [f"  - {r.get('name', '?')} ({r.get('cuisine_tag', '?')}) {(r.get('rating') or 0):.1f}★" for r in restaurants]
        act_lines = [f"  - {a.get('name', '?')} [{a.get('venue_type', 'either')}] ({a.get('interest_tag', '?')}) {(a.get('rating') or 0):.1f}★" for a in activities]

        try: trip_month = datetime.strptime(preferences.departure_date, "%Y-%m-%d").strftime("%B %Y")
        except: trip_month = "the travel period"

        self._current_destination = preferences.destination
        return textwrap.dedent(f"""\
Create a {num_days}-day travel plan for {preferences.destination} ({preferences.departure_date} to {preferences.return_date}).

WEATHER: {weather_summary}
{chr(10).join(day_lines)}

RESTAURANTS ({len(restaurants)}):
{chr(10).join(rest_lines)}

ACTIVITIES ({len(activities)}):
{chr(10).join(act_lines)}

PREFERENCES:
Preferred cuisines: {', '.join(preferences.restaurant_prefs.preferred_cuisines) or 'None'}
Interested cuisines: {', '.join(preferences.restaurant_prefs.interested_cuisines) or 'None'}
Preferred activities: {', '.join(preferences.activity_prefs.preferred_interests) or 'None'}
Interested activities: {', '.join(preferences.activity_prefs.interested_interests) or 'None'}
Pace: {preferences.activity_prefs.pace}

Call emit_day once per day (in order), then emit_nuggets once with 5 nuggets.
RULES: Use EXACT venue names. Rotate cuisines. 4 slots per day.
Each narrative: exactly 2 sentences — mention something SPECIFIC to that venue (signature dish, famous exhibit, what it's known for), then why it suits this traveler.
Nuggets: packing_tips(sky), local_events(purple), cuisine_rationale(orange), activity_rationale(green), seasonal_tip(emerald)""")

    def _fallback_json_plan(self, prompt, num_days, preferences, restaurants, activities, restaurant_lookup, activity_lookup, weather_by_date):
        """Last resort: json_object mode."""
        log_agent_raw("🔄 Last resort: json_object mode", agent_name="PlacesAgent")
        json_prompt = prompt + '\n\nRespond with JSON: {"daily_schedule": [...], "nuggets": [...]}'
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(model=settings.llm_model,
                messages=[{"role": "system", "content": "Respond with valid JSON only."}, {"role": "user", "content": json_prompt}],
                temperature=0.8, max_tokens=3000, response_format={"type": "json_object"})
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"): raw = re.sub(r"^```(?:json)?\s*", "", raw); raw = re.sub(r"\s*```$", "", raw)
            plan = json.loads(raw)
        except Exception as e:
            log_agent_raw(f"⚠️ JSON fallback failed: {e}", agent_name="PlacesAgent")
            return f"I found {len(restaurants)} restaurants and {len(activities)} activities in {preferences.destination}."

        for day in plan.get("daily_schedule", []):
            self._enrich_single_day(day, restaurant_lookup, activity_lookup, weather_by_date)
        try:
            self.trip_storage.store_recommendation(trip_id=self.trip_id, category="daily_plan", recommended_id="daily_plan",
                reason=json.dumps(plan), metadata={"destination": preferences.destination, "num_days": num_days,
                    "format": "structured_v1", "structured_data": plan, "streaming": False,
                    "days_complete": len(plan.get("daily_schedule", [])), "days_total": num_days})
        except: pass
        self._update_planner_status("Travel plan complete")
        return self._structured_plan_to_text(plan, preferences)

    # ─────────────────────────────────────────────────────────────────────
    # TEXT CONVERSION & STORAGE HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _structured_plan_to_text(self, plan, preferences):
        lines = []
        for nugget in plan.get("nuggets", []):
            t, c = nugget.get("title", ""), nugget.get("content", "")
            if t and c: lines.extend([f"### {t}", c, ""])
        lines.extend(["### 📅 Day-by-Day Itinerary", ""])
        for day in plan.get("daily_schedule", []):
            lines.append(f"**Day {day.get('day', '?')} ({day.get('date', '')}): {day.get('title', '')}**")
            if day.get("intro"): lines.append(day["intro"])
            for slot in day.get("slots", []):
                r = slot.get("rating")
                rs = f" ({r} stars)" if r else ""
                lines.append(f"{slot.get('time', '').capitalize()}: **{slot.get('venue_name', '')}**{rs} — {slot.get('narrative', '')}")
            lines.append("")
        return "\n".join(lines)

    def _extract_mentioned_ids(self, plan_text, places, label):
        mentioned, seen = [], set()
        for place in sorted(places, key=lambda p: len(p.get("name", "")), reverse=True):
            name, pid = place.get("name", ""), place.get("id", "")
            if name and pid and name in plan_text and pid not in seen:
                seen.add(pid); mentioned.append(pid)
        return mentioned

    def _store_place_recommendations(self, plan_text, restaurants, activities):
        rec_rest = self._extract_mentioned_ids(plan_text, restaurants, "restaurants")
        if rec_rest:
            pid = rec_rest[0]
            p = next((r for r in restaurants if r.get("id") == pid), None)
            self.trip_storage.store_recommendation(trip_id=self.trip_id, category="restaurant", recommended_id=pid,
                reason=f"Top dining pick — {p.get('cuisine_tag', '')} cuisine, {p.get('rating', 0):.1f} stars" if p else "Top dining pick",
                metadata={"name": p.get("name", "") if p else "", "all_recommended_ids": rec_rest, "total_options_reviewed": len(restaurants)})
        rec_act = self._extract_mentioned_ids(plan_text, activities, "activities")
        if rec_act:
            pid = rec_act[0]
            p = next((a for a in activities if a.get("id") == pid), None)
            self.trip_storage.store_recommendation(trip_id=self.trip_id, category="activity", recommended_id=pid,
                reason=f"Top activity — {p.get('interest_tag', '')}, {p.get('rating', 0):.1f} stars" if p else "Top activity",
                metadata={"name": p.get("name", "") if p else "", "all_recommended_ids": rec_act, "total_options_reviewed": len(activities)})


# ============================================================================
# FACTORY
# ============================================================================

def create_places_agent(trip_id, trip_storage, **kwargs):
    return PlacesAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)