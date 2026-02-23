"""
Places Agent v8 — Four-Persona Parallel Agent
Location: backend/agents/places_agent.py

Proxies as FOUR frontend agents:
  🌤️  Weather Agent      — fetches Open-Meteo forecast
  🍽️  Restaurant Agent   — searches Google Places for cuisine matches
  🎭  Activities Agent   — searches Google Places for interest matches
  📋  Travel Planner     — LLM curates day-by-day itinerary

Changes (v8 — Parallel Four-Persona):
  - Integrated weather fetching directly (no separate WeatherAgent needed)
  - Phase 1: asyncio.gather runs weather + restaurant + activity searches in parallel
  - Phase 2: Single LLM call produces comprehensive travel plan including:
      * Day-by-day itinerary with weather-aware scheduling
      * Packing tips and weather cautions
      * Cuisine preference rationale
      * Activity selection rationale
      * Seasonal festivals / local events (best-effort via Google Places)
  - Dynamic result counts: 3× trip days for restaurants and activities
  - Updates four separate frontend status rows via _update_*_status() helpers
  - Stores weather data + weather recommendation (preserves frontend weather card)

Changes (v7 — Granular Status Messages):
  - Added _update_status() helper for real-time progress to Redis
  - Status messages sent to BOTH "restaurant" and "places" agent rows

Changes (v6 — enriched Place data):
  - _google_dict_to_place: passes through reviews, phone_number, google_url
"""
import time
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.google_places_service import get_google_places_service
from services.weather_service import get_weather_service
from models.trip import Place, Weather

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai


class PlacesAgent(TravelQBaseAgent):
    """
    Places Agent v8 — Four-Persona Parallel Agent.

    Externally appears as four agents on the frontend:
      - Weather Agent:    fetches forecast, updates "weather" status row
      - Restaurant Agent: searches cuisines, updates "restaurant" status row
      - Activities Agent: searches interests, updates "places" status row
      - Travel Planner:   LLM curates daily plan, updates all rows "Done"

    Internally runs Phase 1 (three API streams in parallel via asyncio.gather)
    then Phase 2 (single LLM call with all data).
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
        system_message = """
You are a Travel Planning Expert who creates comprehensive, weather-aware
day-by-day itineraries. You combine weather forecasts, restaurant options,
activities, and local events into a practical and exciting travel plan.

Your expertise covers:
1. Weather-smart scheduling (indoor activities on rainy days, outdoor on clear)
2. Cuisine diversity and preference matching
3. Activity planning aligned with traveler interests
4. Practical packing and preparation advice
5. Local festivals, seasonal events, and cultural happenings

Be enthusiastic, knowledgeable, and specific!
"""

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

        log_agent_raw(
            "Places Agent v8 initialized (four-persona parallel)",
            agent_name="PlacesAgent",
        )

    # ─────────────────────────────────────────────────────────────────────
    # STATUS HELPERS — each targets a different frontend row
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, message: str, agent_name: str = "places"):
        """Send a granular status message to Redis for the frontend."""
        try:
            self.trip_storage.update_agent_status_message(
                self.trip_id, agent_name, message
            )
        except Exception as e:
            log_agent_raw(
                f"Status update failed ({agent_name}): {e}",
                agent_name="PlacesAgent",
            )

    def _update_weather_status(self, message: str):
        self._update_status(message, agent_name="weather")

    def _update_restaurant_status(self, message: str):
        self._update_status(message, agent_name="restaurant")

    def _update_activity_status(self, message: str):
        self._update_status(message, agent_name="places")

    def _update_planner_status(self, message: str):
        """Update all rows with a planner-phase message."""
        self._update_status(message, agent_name="restaurant")
        self._update_status(message, agent_name="places")

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_all_interests(preferences) -> List[str]:
        return (
            preferences.activity_prefs.preferred_interests
            + preferences.activity_prefs.interested_interests
        )

    @staticmethod
    def _get_all_cuisines(preferences) -> List[str]:
        return (
            preferences.restaurant_prefs.preferred_cuisines
            + preferences.restaurant_prefs.interested_cuisines
        )

    def _calculate_trip_days(self, preferences) -> int:
        """Return number of days in the trip."""
        try:
            dep = datetime.strptime(preferences.departure_date, "%Y-%m-%d")
            ret = datetime.strptime(preferences.return_date, "%Y-%m-%d")
            return max((ret - dep).days, 1)
        except (ValueError, AttributeError):
            return 5  # sensible default

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────

    def generate_reply(self, messages=None, sender=None, config=None) -> str:
        log_agent_raw("PlacesAgent v8 processing request...", agent_name="PlacesAgent")

        # Initialize all four status rows
        self._update_weather_status("Initializing weather forecast...")
        self._update_restaurant_status("Initializing restaurant search...")
        self._update_activity_status("Initializing activity search...")

        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, "name") else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING", content=last_message,
                sender=sender_name, truncate=500,
            )

        # Load preferences
        preferences = self.trip_storage.get_preferences(self.trip_id)
        if not preferences:
            msg = f"Error: Could not find preferences for trip {self.trip_id}"
            self._update_weather_status("Error: preferences not found")
            self._update_restaurant_status("Error: preferences not found")
            self._update_activity_status("Error: preferences not found")
            return self.signal_completion(msg)

        num_days = self._calculate_trip_days(preferences)
        log_agent_raw(
            f"Trip: {preferences.destination}, {num_days} days, "
            f"dynamic targets: {num_days * 3} restaurants, {num_days * 3} activities",
            agent_name="PlacesAgent",
        )

        try:
            start_time = time.time()

            # ══════════════════════════════════════════════════════════════
            # PHASE 1: Parallel API calls — Weather + Restaurants + Activities
            # ══════════════════════════════════════════════════════════════
            log_agent_raw(
                "🚀 Phase 1: Parallel fetch (weather + restaurants + activities)",
                agent_name="PlacesAgent",
            )

            weather_forecasts, cuisine_restaurants, interest_activities = (
                self._run_parallel_fetches(preferences, num_days)
            )

            api_duration = time.time() - start_time
            log_agent_raw(
                f"✅ Phase 1 complete in {api_duration:.1f}s — "
                f"weather={len(weather_forecasts)}, "
                f"restaurants={len(cuisine_restaurants)}, "
                f"activities={len(interest_activities)}",
                agent_name="PlacesAgent",
            )

            # ── Process weather ───────────────────────────────────────────
            weather_by_date = {}
            weather_dicts = []
            for f in weather_forecasts:
                d = self._weather_to_dict(f)
                weather_dicts.append(d)
                if d.get("date"):
                    weather_by_date[d["date"]] = d

            trip_days = self._compute_trip_days(preferences, weather_by_date)

            # Store weather data (preserves frontend weather card)
            self._store_weather(weather_dicts, preferences)

            # ── Process restaurants & activities ──────────────────────────
            self._update_restaurant_status(
                f"Processing {len(cuisine_restaurants)} restaurant results..."
            )
            self._update_activity_status(
                f"Processing {len(interest_activities)} activity results..."
            )

            restaurants, activities = self._segregate_and_enrich(
                cuisine_restaurants, interest_activities, preferences
            )

            self._update_restaurant_status(
                f"Found {len(restaurants)} restaurants matching your tastes"
            )
            self._update_activity_status(
                f"Found {len(activities)} activities matching your interests"
            )

            if not restaurants and not activities:
                self._update_planner_status("No matching places found")
                return self.signal_completion(
                    "I couldn't find any places matching your interests."
                )

            # Store restaurant + activity results
            self._store_results(restaurants, activities, preferences, api_duration)

            # ══════════════════════════════════════════════════════════════
            # PHASE 2: Single LLM call — comprehensive travel plan
            # ══════════════════════════════════════════════════════════════
            log_agent_raw(
                "🧠 Phase 2: LLM generating comprehensive travel plan",
                agent_name="PlacesAgent",
            )

            self._update_planner_status(
                f"AI planning {len(trip_days)}-day itinerary with "
                f"{len(restaurants)} restaurants and {len(activities)} activities..."
            )

            recommendation = self._generate_travel_plan(
                weather_forecasts, restaurants, activities,
                trip_days, preferences, num_days,
            )

            # ── Final status on all four rows ─────────────────────────────
            if weather_forecasts:
                temps = [f.temperature for f in weather_forecasts]
                min_t = min(f.temp_min for f in weather_forecasts)
                max_t = max(f.temp_max for f in weather_forecasts)
                self._update_weather_status(
                    f"Weather forecast complete — {len(weather_forecasts)} days, "
                    f"{min_t:.0f}°F–{max_t:.0f}°F"
                )
            else:
                self._update_weather_status("Weather forecast complete — no data available")

            self._update_restaurant_status(
                f"Restaurant search complete — {len(restaurants)} options ready"
            )
            self._update_activity_status(
                f"Activity search complete — {len(activities)} options ready"
            )

            total_duration = time.time() - start_time
            log_agent_raw(
                f"✅ PlacesAgent v8 complete in {total_duration:.1f}s "
                f"(API: {api_duration:.1f}s, LLM: {total_duration - api_duration:.1f}s)",
                agent_name="PlacesAgent",
            )

            self.log_conversation_message(
                message_type="OUTGOING", content=recommendation,
                sender="chat_manager", truncate=1000,
            )
            return self.signal_completion(recommendation)

        except Exception as e:
            log_agent_raw(f"Places search failed: {str(e)}", agent_name="PlacesAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="PlacesAgent")
            self._update_weather_status(f"Error: {str(e)[:80]}")
            self._update_restaurant_status(f"Error: {str(e)[:80]}")
            self._update_activity_status(f"Error: {str(e)[:80]}")
            return self.signal_completion(
                f"I encountered an error: {str(e)}. Please try again."
            )

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 1: PARALLEL API FETCHES
    # ─────────────────────────────────────────────────────────────────────

    def _run_parallel_fetches(
        self, preferences, num_days: int
    ) -> Tuple[List[Weather], List[Dict], List[Dict]]:
        """
        Run weather, restaurant, and activity searches in parallel
        using asyncio.gather. Returns (weather_forecasts, restaurants, activities).
        """
        import nest_asyncio

        async def _gather_all():
            return await asyncio.gather(
                self._fetch_weather_async(preferences),
                self._fetch_restaurants_async(preferences, num_days),
                self._fetch_activities_async(preferences, num_days),
                return_exceptions=True,
            )

        # Handle event loop: Celery may or may not have one running
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

        # Unpack with error safety
        weather = results[0] if not isinstance(results[0], Exception) else []
        restaurants = results[1] if not isinstance(results[1], Exception) else []
        activities = results[2] if not isinstance(results[2], Exception) else []

        if isinstance(results[0], Exception):
            log_agent_raw(f"⚠️ Weather fetch failed: {results[0]}", agent_name="PlacesAgent")
        if isinstance(results[1], Exception):
            log_agent_raw(f"⚠️ Restaurant fetch failed: {results[1]}", agent_name="PlacesAgent")
        if isinstance(results[2], Exception):
            log_agent_raw(f"⚠️ Activity fetch failed: {results[2]}", agent_name="PlacesAgent")

        return weather, restaurants, activities

    # ── Weather fetch ─────────────────────────────────────────────────

    async def _fetch_weather_async(self, preferences) -> List[Weather]:
        """Fetch weather forecast from Open-Meteo API."""
        self._update_weather_status(
            f"Fetching forecast for {preferences.destination}..."
        )

        try:
            weather_data = await self.weather_service.get_forecast(
                location=preferences.destination,
                start_date=preferences.departure_date,
                end_date=preferences.return_date,
            )

            forecasts = []
            for forecast_dict in weather_data:
                forecast = self._parse_weather_data(forecast_dict)
                if forecast:
                    forecasts.append(forecast)

            if forecasts:
                min_t = min(f.temp_min for f in forecasts)
                max_t = max(f.temp_max for f in forecasts)
                rainy = sum(
                    1 for f in forecasts
                    if (f.precipitation_probability or 0) > 50
                )
                self._update_weather_status(
                    f"Forecast received — {len(forecasts)} days, "
                    f"{min_t:.0f}°F–{max_t:.0f}°F, "
                    f"{rainy} rainy day{'s' if rainy != 1 else ''}"
                )
            else:
                self._update_weather_status("No forecast data available")

            log_agent_raw(
                f"✅ Weather: {len(forecasts)} day forecast received",
                agent_name="PlacesAgent",
            )
            return forecasts

        except Exception as e:
            log_agent_raw(f"❌ Weather fetch failed: {e}", agent_name="PlacesAgent")
            self._update_weather_status(f"Weather unavailable: {str(e)[:60]}")
            return []

    def _parse_weather_data(self, data: Dict) -> Optional[Weather]:
        try:
            return Weather(
                date=data["date"],
                temperature=data.get("temperature", 0),
                feels_like=data.get("feels_like", 0),
                temp_min=data.get("temp_min", 0),
                temp_max=data.get("temp_max", 0),
                description=data.get("description", ""),
                icon=data.get("icon"),
                humidity=data.get("humidity"),
                wind_speed=data.get("wind_speed"),
                precipitation_probability=data.get("precipitation_probability"),
                conditions=data.get("condition"),
            )
        except Exception as e:
            log_agent_raw(f"⚠️ Weather parse error: {e}", agent_name="PlacesAgent")
            return None

    # ── Restaurant fetch ──────────────────────────────────────────────

    async def _fetch_restaurants_async(
        self, preferences, num_days: int
    ) -> List[Dict]:
        """Search Google Places for restaurants matching cuisine preferences.
        Target count: 3× trip days (gives LLM enough variety to curate).
        """
        destination = preferences.destination
        preferred = preferences.restaurant_prefs.preferred_cuisines
        interested = preferences.restaurant_prefs.interested_cuisines
        target_count = num_days * 3

        all_results: List[Dict] = []
        seen_ids: set = set()

        def _add(places, cuisine):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["cuisine_tag"] = cuisine
                    all_results.append(place)

        if not self.google_places or not self.google_places.client:
            self._update_restaurant_status(
                "Google Places not configured — using sample data"
            )
            return []

        # Preferred cuisines: more results per cuisine
        preferred_per = max(3, target_count // max(len(preferred) + len(interested), 1))
        if preferred:
            self._update_restaurant_status(
                f"Searching preferred cuisines: {', '.join(preferred)}..."
            )
        for cuisine in preferred:
            self._update_restaurant_status(
                f"Searching {cuisine} restaurants in {destination}..."
            )
            results = self.google_places.search_places_by_text(
                query=f"{cuisine} restaurant in {destination}",
                location=destination, included_type="restaurant",
                min_rating=3.5, max_results=preferred_per,
                agent_logger=self.logger,
            )
            _add(results, cuisine)

        # Interested cuisines: fewer results per cuisine
        interested_per = max(2, preferred_per // 2)
        if interested:
            self._update_restaurant_status(
                f"Searching interested cuisines: {', '.join(interested)}..."
            )
        for cuisine in interested:
            self._update_restaurant_status(
                f"Searching {cuisine} restaurants in {destination}..."
            )
            results = self.google_places.search_places_by_text(
                query=f"{cuisine} restaurant in {destination}",
                location=destination, included_type="restaurant",
                min_rating=3.5, max_results=interested_per,
                agent_logger=self.logger,
            )
            _add(results, cuisine)

        # Fill up if under target
        if len(all_results) < target_count:
            shortfall = target_count - len(all_results)
            self._update_restaurant_status(
                f"Finding {shortfall} more top-rated restaurants..."
            )
            results = self.google_places.search_places_by_text(
                query=f"best restaurant in {destination}",
                location=destination, included_type="restaurant",
                min_rating=4.0, max_results=shortfall,
                agent_logger=self.logger,
            )
            _add(results, "General")

        final = all_results[:target_count]
        self._update_restaurant_status(
            f"Restaurant search done — {len(final)} candidates found"
        )
        log_agent_raw(
            f"✅ Restaurants: {len(final)} found (target: {target_count})",
            agent_name="PlacesAgent",
        )
        return final

    # ── Activity fetch ────────────────────────────────────────────────

    async def _fetch_activities_async(
        self, preferences, num_days: int
    ) -> List[Dict]:
        """Search Google Places for activities matching interest preferences.
        Target count: 3× trip days.
        Also searches for seasonal festivals/events (best-effort).
        """
        destination = preferences.destination
        preferred = preferences.activity_prefs.preferred_interests
        interested = preferences.activity_prefs.interested_interests
        target_count = num_days * 3

        all_results: List[Dict] = []
        seen_ids: set = set()

        def _add(places, tag):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["interest_tag"] = tag
                    all_results.append(place)

        if not self.google_places or not self.google_places.client:
            self._update_activity_status(
                "Google Places not configured — using sample data"
            )
            return []

        # Preferred interests: more results
        preferred_per = max(3, target_count // max(len(preferred) + len(interested), 1))
        if preferred:
            self._update_activity_status(
                f"Searching preferred interests: {', '.join(preferred)}..."
            )
        for interest in preferred:
            self._update_activity_status(
                f"Searching {interest} in {destination}..."
            )
            results = self.google_places.search_places_by_text(
                query=f"{interest} in {destination}",
                location=destination, min_rating=3.5,
                max_results=preferred_per, agent_logger=self.logger,
            )
            _add(results, interest)

        # Interested interests: fewer results
        interested_per = max(2, preferred_per // 2)
        if interested:
            self._update_activity_status(
                f"Searching interested topics: {', '.join(interested)}..."
            )
        for interest in interested:
            self._update_activity_status(
                f"Searching {interest} in {destination}..."
            )
            results = self.google_places.search_places_by_text(
                query=f"{interest} in {destination}",
                location=destination, min_rating=3.5,
                max_results=interested_per, agent_logger=self.logger,
            )
            _add(results, interest)

        # ── Seasonal festivals / local events (best-effort) ──────────
        try:
            trip_month = datetime.strptime(
                preferences.departure_date, "%Y-%m-%d"
            ).strftime("%B")  # e.g. "March"
        except (ValueError, AttributeError):
            trip_month = ""

        if trip_month:
            self._update_activity_status(
                f"Searching {trip_month} festivals & events in {destination}..."
            )
            festival_results = self.google_places.search_places_by_text(
                query=f"{trip_month} festival event in {destination}",
                location=destination, min_rating=3.5,
                max_results=3, agent_logger=self.logger,
            )
            _add(festival_results, f"{trip_month} Festival/Event")

            if festival_results:
                log_agent_raw(
                    f"🎉 Found {len(festival_results)} seasonal events for {trip_month}",
                    agent_name="PlacesAgent",
                )

        # ── Category-based nearby search for variety ──────────────────
        categories = self._determine_categories(preferences)
        non_restaurant = [c for c in categories if c != "restaurants"]
        if non_restaurant and len(all_results) < target_count:
            self._update_activity_status(
                f"Searching nearby {', '.join(non_restaurant)} within 5km..."
            )
            place_types = list(set(
                t for cat in non_restaurant
                for t in self.CATEGORY_TYPES.get(cat, [])
            ))
            nearby = self.google_places.search_places(
                location=destination, radius=5000,
                place_types=place_types, min_rating=3.5,
                max_results=8, agent_logger=self.logger,
            )
            for ptype, places in nearby.items():
                for pd in places:
                    pid = pd.get("place_id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        pd["interest_tag"] = ptype
                        all_results.append(pd)

        final = all_results[:target_count]
        self._update_activity_status(
            f"Activity search done — {len(final)} candidates found"
        )
        log_agent_raw(
            f"✅ Activities: {len(final)} found (target: {target_count})",
            agent_name="PlacesAgent",
        )
        return final

    # ─────────────────────────────────────────────────────────────────────
    # DATA PROCESSING (unchanged from v7)
    # ─────────────────────────────────────────────────────────────────────

    def _determine_categories(self, preferences) -> List[str]:
        all_interests = self._get_all_interests(preferences)
        categories = []
        interest_map = {
            "food": ["restaurants"], "dining": ["restaurants"],
            "culture": ["culture", "attractions"], "art": ["culture"],
            "history": ["attractions", "culture"], "museum": ["culture"],
            "sightseeing": ["attractions"], "shopping": ["shopping"],
            "nature": ["nature"], "outdoor": ["nature"], "park": ["nature"],
            "entertainment": ["entertainment"], "nightlife": ["entertainment"],
            "theater": ["entertainment", "culture"],
        }
        for interest in all_interests:
            il = interest.lower()
            for key, cats in interest_map.items():
                if key in il:
                    categories.extend(cats)
        categories = list(set(categories))[:4]
        return categories if categories else ["attractions", "culture"]

    @staticmethod
    def _classify_day_weather(weather_dict: Optional[Dict]) -> str:
        if not weather_dict:
            return "either"
        rain_prob = weather_dict.get("precipitation_probability", 0) or 0
        description = (weather_dict.get("description") or "").lower()
        conditions = (weather_dict.get("conditions") or "").lower()
        indoor_kw = ["rain", "storm", "thunder", "snow", "sleet", "drizzle", "heavy"]
        if rain_prob > 60 or any(kw in description for kw in indoor_kw) or any(kw in conditions for kw in indoor_kw):
            return "indoor"
        outdoor_kw = ["clear", "sunny", "fair", "fine"]
        if rain_prob <= 30 and (
            any(kw in description for kw in outdoor_kw)
            or any(kw in conditions for kw in outdoor_kw)
            or rain_prob == 0
        ):
            return "outdoor"
        return "either"

    def _compute_trip_days(self, preferences, weather_by_date):
        try:
            start = datetime.strptime(preferences.departure_date, "%Y-%m-%d")
            end = datetime.strptime(preferences.return_date, "%Y-%m-%d")
        except (ValueError, AttributeError):
            return [
                {"day": i + 1, "date": "", "weather_class": "either",
                 "weather_summary": "N/A"}
                for i in range(5)
            ]
        days = []
        current = start
        day_num = 1
        while current < end:
            date_str = current.strftime("%Y-%m-%d")
            weather = weather_by_date.get(date_str)
            weather_class = self._classify_day_weather(weather)
            if weather:
                summary = (
                    f"{weather.get('description', 'N/A')}, "
                    f"{weather.get('temp_min', '?')}–{weather.get('temp_max', '?')}°F, "
                    f"{(weather.get('precipitation_probability', 0) or 0):.0f}% rain"
                )
            else:
                summary = "No forecast available"
            days.append({
                "day": day_num, "date": date_str,
                "weather_class": weather_class, "weather_summary": summary,
            })
            current += timedelta(days=1)
            day_num += 1
        return days

    def _classify_venue_type(self, place_dict: Dict) -> str:
        primary = (place_dict.get("primary_type") or "").lower()
        types_list = [t.lower() for t in (place_dict.get("types") or [])]
        all_types = {primary} | set(types_list)
        if all_types & self.INDOOR_TYPES:
            return "indoor"
        if all_types & self.OUTDOOR_TYPES:
            return "outdoor"
        return "either"

    def _segregate_and_enrich(self, cuisine_restaurants, interest_activities, preferences):
        EXCLUDED = {"hotel", "lodging", "motel", "hostel", "resort", "resort_hotel"}
        RESTAURANT_KW = {"restaurant", "cafe", "bar", "bakery", "food"}

        restaurants = []
        for r in cuisine_restaurants:
            if (r.get("primary_type") or "").lower() in EXCLUDED:
                continue
            place = self._google_dict_to_place(r)
            if place:
                d = place.model_dump(mode="json")
                d["cuisine_tag"] = r.get("cuisine_tag", "")
                d["venue_type"] = "indoor"
                restaurants.append(d)

        activities = []
        for a in interest_activities:
            primary = (a.get("primary_type") or "").lower()
            if primary in EXCLUDED or primary in RESTAURANT_KW:
                continue
            place = self._google_dict_to_place(a)
            if place:
                d = place.model_dump(mode="json")
                d["interest_tag"] = a.get("interest_tag", "")
                d["venue_type"] = self._classify_venue_type(a)
                activities.append(d)

        return restaurants, activities

    def _google_dict_to_place(self, google_data: Dict) -> Optional[Place]:
        """Create Place from Google Places dict (v6: enriched data)."""
        try:
            opening_hours = None
            if google_data.get("currentOpeningHours"):
                opening_hours = {
                    "open_now": google_data["currentOpeningHours"].get("openNow"),
                    "weekday_text": google_data["currentOpeningHours"].get(
                        "weekdayDescriptions", []
                    ),
                }

            reviews = None
            raw_reviews = google_data.get("reviews")
            if raw_reviews:
                from models.trip import HotelReview
                reviews = []
                for r in raw_reviews[:5]:
                    try:
                        reviews.append(HotelReview(**r))
                    except Exception:
                        continue

            return Place(
                id=google_data.get("place_id", str(time.time())),
                name=google_data.get("name", "Unknown Place"),
                address=google_data.get("address", ""),
                latitude=google_data.get("latitude"),
                longitude=google_data.get("longitude"),
                rating=google_data.get("google_rating"),
                user_ratings_total=google_data.get("user_ratings_total"),
                category=google_data.get("primary_type", "other"),
                description=(
                    f"Rated {google_data.get('google_rating', 0)}/5 "
                    f"by {google_data.get('user_ratings_total', 0)} reviewers"
                ),
                photos=google_data.get("photos", [])[:5],
                opening_hours=opening_hours,
                price_level=google_data.get("price_level"),
                website=google_data.get("website"),
                reviews=reviews,
                phone_number=google_data.get("phone_number"),
                google_url=google_data.get("google_url"),
            )
        except Exception as e:
            log_agent_raw(f"Failed to create place: {e}", agent_name="PlacesAgent")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # STORAGE
    # ─────────────────────────────────────────────────────────────────────

    def _store_weather(self, weather_dicts: List[Dict], preferences):
        """Store weather data and recommendation (preserves frontend weather card)."""
        if not weather_dicts:
            return

        self.trip_storage.add_weather(
            trip_id=self.trip_id,
            weather=weather_dicts,
            metadata={
                "destination": preferences.destination,
                "start_date": preferences.departure_date,
                "end_date": preferences.return_date,
                "search_time": datetime.now().isoformat(),
                "total_days": len(weather_dicts),
            },
        )

        # Store weather recommendation (consumed by frontend weather card)
        try:
            temps = [d.get("temperature", 0) for d in weather_dicts]
            min_t = min(d.get("temp_min", 0) for d in weather_dicts)
            max_t = max(d.get("temp_max", 0) for d in weather_dicts)
            rainy = sum(
                1 for d in weather_dicts
                if (d.get("precipitation_probability", 0) or 0) > 50
            )
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="weather",
                recommended_id="weather_forecast",
                reason=(
                    f"Weather in {preferences.destination}: "
                    f"{min_t:.0f}°F–{max_t:.0f}°F over {len(weather_dicts)} days. "
                    f"{rainy} day{'s' if rainy != 1 else ''} with rain expected."
                ),
                metadata={
                    "destination": preferences.destination,
                    "num_days": len(weather_dicts),
                    "temp_min": round(min_t, 1),
                    "temp_max": round(max_t, 1),
                    "avg_temp": round(sum(temps) / len(temps), 1) if temps else 0,
                    "rainy_days": rainy,
                },
            )
        except Exception as e:
            log_agent_raw(
                f"⚠️ Weather recommendation storage failed: {e}",
                agent_name="PlacesAgent",
            )

        log_agent_raw(
            f"💾 Stored {len(weather_dicts)} weather forecasts",
            agent_name="PlacesAgent",
        )

    def _store_results(self, restaurants, activities, preferences, api_duration):
        meta = {
            "destination": preferences.destination,
            "search_time": datetime.now().isoformat(),
            "api_duration": api_duration,
        }
        if restaurants:
            self.trip_storage.add_restaurants(
                trip_id=self.trip_id, restaurants=restaurants,
                metadata={**meta, "total_results": len(restaurants)},
            )
        if activities:
            self.trip_storage.add_activities(
                trip_id=self.trip_id, activities=activities,
                metadata={**meta, "total_results": len(activities)},
            )
        self.trip_storage.log_api_call(
            trip_id=self.trip_id, agent_name="PlacesAgent",
            api_name="GooglePlaces", duration=api_duration,
        )

    def _weather_to_dict(self, weather: Weather) -> Dict:
        return weather.model_dump(mode="json")

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 2: COMPREHENSIVE TRAVEL PLAN (single LLM call)
    # ─────────────────────────────────────────────────────────────────────

    def _generate_travel_plan(
        self,
        weather_forecasts: List[Weather],
        restaurants: List[Dict],
        activities: List[Dict],
        trip_days: List[Dict],
        preferences,
        num_days: int,
    ) -> str:
        """
        Single LLM call that produces the complete travel plan:
          - Day-by-day itinerary (weather-aware)
          - Packing tips and weather cautions
          - Cuisine preference rationale
          - Activity selection rationale
          - Seasonal festivals / local events
        """
        if not restaurants and not activities:
            return "No places found matching your interests."

        # ── Build context blocks for the prompt ──────────────────────────

        # Weather block
        if weather_forecasts:
            min_t = min(f.temp_min for f in weather_forecasts)
            max_t = max(f.temp_max for f in weather_forecasts)
            rainy = sum(
                1 for f in weather_forecasts
                if (f.precipitation_probability or 0) > 50
            )
            weather_summary = (
                f"Temperature range: {min_t:.0f}°F–{max_t:.0f}°F\n"
                f"Rainy days (>50% chance): {rainy}/{len(weather_forecasts)}"
            )
        else:
            weather_summary = "No forecast available — plan for variable conditions."

        day_lines = [
            f"  Day {d['day']} ({d['date']}): {d['weather_summary']} "
            f"→ recommend {d['weather_class']} activities"
            for d in trip_days
        ]
        weather_block = "\n".join(day_lines) if day_lines else "  (no weather data)"

        # Restaurant block
        rest_lines = [
            f"  - {r.get('name', '?')} ({r.get('cuisine_tag', '?')}) "
            f"— {(r.get('rating') or 0):.1f} stars"
            for r in restaurants[:num_days * 3]
        ]
        restaurant_block = "\n".join(rest_lines) if rest_lines else "  (none found)"

        # Activity block
        act_lines = [
            f"  - {a.get('name', '?')} [{a.get('venue_type', 'either')}] "
            f"({a.get('interest_tag', '?')}) — {(a.get('rating') or 0):.1f} stars"
            for a in activities[:num_days * 3]
        ]
        activity_block = "\n".join(act_lines) if act_lines else "  (none found)"

        # Preferences
        pref_cuisines = preferences.restaurant_prefs.preferred_cuisines
        int_cuisines = preferences.restaurant_prefs.interested_cuisines
        pref_interests = preferences.activity_prefs.preferred_interests
        int_interests = preferences.activity_prefs.interested_interests
        meals = preferences.restaurant_prefs.meals

        # Seasonal context
        try:
            trip_month = datetime.strptime(
                preferences.departure_date, "%Y-%m-%d"
            ).strftime("%B %Y")
        except (ValueError, AttributeError):
            trip_month = "the travel period"

        # Festival entries (tagged with "Festival/Event" interest_tag)
        festival_entries = [
            a for a in activities
            if "festival" in (a.get("interest_tag") or "").lower()
            or "event" in (a.get("interest_tag") or "").lower()
        ]
        festival_block = ""
        if festival_entries:
            fest_lines = [
                f"  - {f.get('name', '?')} — {(f.get('rating') or 0):.1f} stars"
                for f in festival_entries
            ]
            festival_block = (
                f"\nSEASONAL FESTIVALS / LOCAL EVENTS ({trip_month}):\n"
                + "\n".join(fest_lines)
            )

        # ── The comprehensive prompt ─────────────────────────────────────

        prompt = f"""You are creating a COMPREHENSIVE travel plan for {preferences.destination}
for {num_days} days ({preferences.departure_date} to {preferences.return_date}).

═══════════════════════════════════════════════════════════════════
WEATHER OVERVIEW
═══════════════════════════════════════════════════════════════════
{weather_summary}

DAILY FORECAST:
{weather_block}

═══════════════════════════════════════════════════════════════════
RESTAURANTS FOUND ({len(restaurants)} options, with cuisine tags)
═══════════════════════════════════════════════════════════════════
{restaurant_block}

═══════════════════════════════════════════════════════════════════
ACTIVITIES FOUND ({len(activities)} options, [indoor/outdoor/either])
═══════════════════════════════════════════════════════════════════
{activity_block}
{festival_block}

═══════════════════════════════════════════════════════════════════
TRAVELER PREFERENCES
═══════════════════════════════════════════════════════════════════
Preferred cuisines: {', '.join(pref_cuisines) if pref_cuisines else 'None specified'}
Interested cuisines: {', '.join(int_cuisines) if int_cuisines else 'None specified'}
Preferred activities: {', '.join(pref_interests) if pref_interests else 'None specified'}
Interested activities: {', '.join(int_interests) if int_interests else 'None specified'}
Meals to plan: {', '.join(meals)}
Pace: {preferences.activity_prefs.pace}
Entertainment hours/day: {preferences.activity_prefs.entertainment_hours_per_day}

═══════════════════════════════════════════════════════════════════
YOUR RESPONSE MUST INCLUDE ALL OF THE FOLLOWING SECTIONS:
═══════════════════════════════════════════════════════════════════

### 🌤️ Weather Advisory & Packing Tips
- Summarize the overall weather pattern for the trip
- Flag any concerning weather days (heavy rain, extreme temps, fog)
- Provide a SPECIFIC packing list: clothing layers, rain gear, footwear,
  sun protection, and any destination-specific items
- Example: "Pack a compact umbrella and waterproof jacket for Days 2 and 4"

### 🍽️ Why These Restaurants
- Briefly explain how restaurants were selected based on the traveler's
  preferred and interested cuisines
- Highlight any standout picks and why they match the traveler's taste

### 🎭 Why These Activities
- Explain how activities were matched to the traveler's interests
- Note which activities were scheduled on specific days due to weather
  (e.g., "British Museum on Day 2 since rain is expected")

### 📅 Day-by-Day Itinerary
For EACH day, write one enthusiastic paragraph (4-6 sentences) covering:
- Morning activity (matched to weather and interests)
- Lunch restaurant (with cuisine tag and rating)
- Afternoon activity
- Dinner restaurant (with cuisine tag and rating)

RULES for the itinerary:
1. On "indoor" days → schedule indoor activities; on "outdoor" days → outdoor
2. Assign a restaurant for EACH meal slot EACH day
3. ROTATE cuisines: never repeat the same cuisine for consecutive meals
4. Preferred cuisines appear MORE often than interested ones
5. Preferred activities on the BEST weather days
6. Use EXACT restaurant and activity names as listed above — do not rename them
7. Mention ratings in parentheses, e.g., "(4.7 stars)"

### 🎉 Local Events & Seasonal Tips
- Mention any seasonal festivals or events found (if any)
- If none were found, suggest what kinds of seasonal events are typical
  for {preferences.destination} in {trip_month}
- Include any local tips (public holidays, closures, tourist seasons)

Keep the overall tone conversational, enthusiastic, and practical.
Total response should be 400-800 words."""

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=1500,
            )
            plan_text = response.choices[0].message.content.strip()
            self._update_planner_status("Travel plan generated")
        except Exception as e:
            log_agent_raw(f"⚠️ LLM plan generation failed: {e}", agent_name="PlacesAgent")
            plan_text = (
                f"I found {len(restaurants)} restaurants and {len(activities)} "
                f"activities in {preferences.destination}! Check the options below."
            )
            self._update_planner_status("AI planning fallback — using summary")

        # Store recommendations
        try:
            self._store_place_recommendations(plan_text, restaurants, activities)
        except Exception:
            pass

        try:
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="daily_plan",
                recommended_id="daily_plan",
                reason=plan_text,
                metadata={
                    "destination": preferences.destination,
                    "num_days": num_days,
                    "num_restaurants": len(restaurants),
                    "num_activities": len(activities),
                },
            )
        except Exception:
            pass

        return plan_text

    # ─────────────────────────────────────────────────────────────────────
    # RECOMMENDATION EXTRACTION (unchanged from v7)
    # ─────────────────────────────────────────────────────────────────────

    def _extract_mentioned_ids(self, plan_text, places, label):
        mentioned, seen = [], set()
        sorted_places = sorted(
            places, key=lambda p: len(p.get("name", "")), reverse=True
        )
        for place in sorted_places:
            name, pid = place.get("name", ""), place.get("id", "")
            if name and pid and name in plan_text and pid not in seen:
                seen.add(pid)
                mentioned.append(pid)
        return mentioned

    def _store_place_recommendations(self, plan_text, restaurants, activities):
        rec_restaurant_ids = self._extract_mentioned_ids(
            plan_text, restaurants, "restaurants"
        )
        if rec_restaurant_ids:
            primary_id = rec_restaurant_ids[0]
            primary = next(
                (r for r in restaurants if r.get("id") == primary_id), None
            )
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="restaurant",
                recommended_id=primary_id,
                reason=(
                    f"Top dining pick — {primary.get('cuisine_tag', '')} cuisine, "
                    f"{primary.get('rating', 0):.1f} stars"
                    if primary
                    else f"Top dining pick from {len(restaurants)} options"
                ),
                metadata={
                    "name": primary.get("name", "") if primary else "",
                    "all_recommended_ids": rec_restaurant_ids,
                    "total_options_reviewed": len(restaurants),
                },
            )

        rec_activity_ids = self._extract_mentioned_ids(
            plan_text, activities, "activities"
        )
        if rec_activity_ids:
            primary_id = rec_activity_ids[0]
            primary = next(
                (a for a in activities if a.get("id") == primary_id), None
            )
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="activity",
                recommended_id=primary_id,
                reason=(
                    f"Top activity — {primary.get('interest_tag', '')}, "
                    f"{primary.get('rating', 0):.1f} stars"
                    if primary
                    else f"Top activity from {len(activities)} options"
                ),
                metadata={
                    "name": primary.get("name", "") if primary else "",
                    "all_recommended_ids": rec_activity_ids,
                    "total_options_reviewed": len(activities),
                },
            )


# ============================================================================
# FACTORY
# ============================================================================

def create_places_agent(
    trip_id: str, trip_storage: TripStorageInterface, **kwargs
) -> PlacesAgent:
    return PlacesAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)