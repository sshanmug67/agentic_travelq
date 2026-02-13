"""
Places Agent - Preference-Aware, Weather-Aware, Day-Planned
Location: backend/agents/places_agent.py

Searches for restaurants, attractions, shopping, museums, parks, etc.
Now uses cuisine and interest preferences to drive targeted searches,
reads weather data for indoor/outdoor activity planning, and builds
a day-by-day meal plan with cuisine rotation.

Changes (v4):
  - Cuisine-specific restaurant searches via Text Search API
    e.g. "Italian restaurant in London" instead of generic "restaurant"
  - ⭐ preferred cuisines/interests get more search slots than ☆ interested
  - Reads weather forecasts from trip storage (written by WeatherAgent)
  - Classifies each trip day as outdoor-friendly / indoor-preferred
  - Tags activities as indoor/outdoor for weather-aware assignment
  - LLM builds day-by-day plan: activities + lunch/dinner with cuisine rotation
  - Different cuisine for consecutive days where possible
  - Stores enriched restaurant/activity data with cuisine_tag and venue_type
"""
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.google_places_service import get_google_places_service
from models.trip import Place

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai


class PlacesAgent(TravelQBaseAgent):
    """
    Places Agent v4 — Preference-aware, weather-aware, day-planned.

    Uses Google Places API (New) for real data. Drives searches from
    user's cuisine and activity preferences, reads weather data for
    indoor/outdoor planning, and assigns restaurants to meal slots
    with cuisine rotation across trip days.
    """

    # ── Category mappings for Nearby Search (type-based) ──────────────
    CATEGORY_TYPES = {
        "restaurants": ["restaurant", "cafe", "bar"],
        "attractions": ["tourist_attraction", "museum", "art_gallery"],
        "shopping": ["shopping_mall", "department_store", "market"],
        "nature": ["park", "botanical_garden", "hiking_area"],
        "culture": ["museum", "art_gallery", "performing_arts_theater"],
        "entertainment": ["movie_theater", "amusement_park", "casino"],
    }

    # ── Venue-type classification for weather-aware planning ──────────
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
You are a Places & Dining Expert helping travelers discover amazing locations.

Your job:
1. Find restaurants that match the traveler's cuisine preferences
2. Find activities and attractions that match their interests
3. Consider weather forecasts when planning indoor vs outdoor activities
4. Plan meals with cuisine variety — avoid the same cuisine on consecutive days
5. Provide practical details (ratings, hours, why each place is special)

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

        # Storage
        self.trip_id = trip_id
        self.trip_storage = trip_storage

        # API Service
        self.google_places = get_google_places_service()

        log_agent_raw("📍 PlacesAgent v4 initialized", agent_name="PlacesAgent")
        log_agent_raw("   ✓ Google Places service (Nearby + Text Search)", agent_name="PlacesAgent")
        log_agent_raw("   ✓ Weather-aware activity planning", agent_name="PlacesAgent")
        log_agent_raw("   ✓ Cuisine-driven restaurant search", agent_name="PlacesAgent")

    # ══════════════════════════════════════════════════════════════════════
    # HELPERS — preference access
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _get_all_interests(preferences) -> List[str]:
        """Combine preferred + interested activity interests."""
        return (
            preferences.activity_prefs.preferred_interests
            + preferences.activity_prefs.interested_interests
        )

    @staticmethod
    def _get_all_cuisines(preferences) -> List[str]:
        """Combine preferred + interested cuisines."""
        return (
            preferences.restaurant_prefs.preferred_cuisines
            + preferences.restaurant_prefs.interested_cuisines
        )

    # ══════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════

    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None,
    ) -> str:
        """Generate reply with preference-driven, weather-aware place results."""
        log_agent_raw("🔍 PlacesAgent v4 processing request...", agent_name="PlacesAgent")

        # Log incoming message
        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, "name") else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name,
                truncate=500,
            )

        # ── 1. Get preferences ────────────────────────────────────────
        preferences = self.trip_storage.get_preferences(self.trip_id)

        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="PlacesAgent")
            return self.signal_completion(f"Error: {error_msg}")

        log_agent_raw(f"✅ Retrieved preferences for trip {self.trip_id}", agent_name="PlacesAgent")

        try:
            start_time = time.time()

            # ── 2. Get weather data from storage ──────────────────────
            weather_by_date = self._load_weather_data()

            # ── 3. Compute trip days ──────────────────────────────────
            trip_days = self._compute_trip_days(preferences, weather_by_date)
            log_agent_raw(
                f"📅 Trip: {len(trip_days)} days, "
                f"{sum(1 for d in trip_days if d['weather_class'] == 'outdoor')} outdoor-friendly, "
                f"{sum(1 for d in trip_days if d['weather_class'] == 'indoor')} indoor-preferred",
                agent_name="PlacesAgent",
            )

            # ── 4. Search restaurants by cuisine ──────────────────────
            cuisine_restaurants = self._search_restaurants_by_cuisine(preferences)

            # ── 5. Search activities by interest ──────────────────────
            interest_activities = self._search_activities_by_interest(preferences)

            api_duration = time.time() - start_time

            # ── 6. Merge, dedupe, classify ────────────────────────────
            restaurants, activities = self._segregate_and_enrich(
                cuisine_restaurants, interest_activities, preferences
            )

            log_agent_raw(
                f"📊 Final: {len(restaurants)} restaurants, {len(activities)} activities "
                f"in {api_duration:.2f}s",
                agent_name="PlacesAgent",
            )

            if not restaurants and not activities:
                return self.signal_completion(
                    "I couldn't find any places matching your interests. "
                    "Try broadening your search criteria."
                )

            # ── 7. Store in trip storage ──────────────────────────────
            self._store_results(restaurants, activities, preferences, api_duration)

            # ── 8. Generate day-by-day recommendation via LLM ─────────
            recommendation = self._generate_daily_plan(
                restaurants, activities, trip_days, preferences
            )

            self.log_conversation_message(
                message_type="OUTGOING",
                content=recommendation,
                sender="chat_manager",
                truncate=1000,
            )

            return self.signal_completion(recommendation)

        except Exception as e:
            log_agent_raw(f"❌ Places search failed: {str(e)}", agent_name="PlacesAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="PlacesAgent")
            return self.signal_completion(f"I encountered an error: {str(e)}. Please try again.")

    # ══════════════════════════════════════════════════════════════════════
    # WEATHER — read from storage & classify
    # ══════════════════════════════════════════════════════════════════════

    def _load_weather_data(self) -> Dict[str, Dict]:
        """
        Read weather forecasts written by WeatherAgent from trip storage.

        Returns:
            Dict keyed by date string (YYYY-MM-DD) → weather dict
            Empty dict if weather not yet available (agent hasn't run yet).
        """
        try:
            all_options = self.trip_storage.get_all_options(self.trip_id)
            weather_list = all_options.get("weather", [])

            if not weather_list:
                log_agent_raw(
                    "⚠️  No weather data in storage — WeatherAgent may not have run yet. "
                    "Proceeding without weather-aware planning.",
                    agent_name="PlacesAgent",
                )
                return {}

            weather_by_date = {}
            for w in weather_list:
                date_str = w.get("date", "")
                if date_str:
                    weather_by_date[date_str] = w

            log_agent_raw(
                f"🌤️  Loaded {len(weather_by_date)} days of weather data",
                agent_name="PlacesAgent",
            )
            return weather_by_date

        except Exception as e:
            log_agent_raw(f"⚠️  Failed to load weather: {e}", agent_name="PlacesAgent")
            return {}

    @staticmethod
    def _classify_day_weather(weather_dict: Optional[Dict]) -> str:
        """
        Classify a day's weather for activity planning.

        Returns:
            'outdoor'  — clear/sunny, rain probability ≤ 30%
            'indoor'   — rain/storm likely, rain probability > 60%
            'either'   — mixed conditions or no data
        """
        if not weather_dict:
            return "either"

        rain_prob = weather_dict.get("precipitation_probability", 0) or 0
        description = (weather_dict.get("description") or "").lower()
        conditions = (weather_dict.get("conditions") or "").lower()

        # Strong indoor signals
        indoor_keywords = ["rain", "storm", "thunder", "snow", "sleet", "drizzle", "heavy"]
        if rain_prob > 60 or any(kw in description for kw in indoor_keywords) or any(kw in conditions for kw in indoor_keywords):
            return "indoor"

        # Strong outdoor signals
        outdoor_keywords = ["clear", "sunny", "fair", "fine"]
        if rain_prob <= 30 and (
            any(kw in description for kw in outdoor_keywords)
            or any(kw in conditions for kw in outdoor_keywords)
            or rain_prob == 0
        ):
            return "outdoor"

        return "either"

    def _compute_trip_days(
        self, preferences, weather_by_date: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Build a per-day structure with date and weather classification.

        Returns list of dicts:
            [
                {"day": 1, "date": "2026-02-20", "weather_class": "outdoor",
                 "weather_summary": "Clear, 55-62°F, 10% rain"},
                ...
            ]
        """
        try:
            start = datetime.strptime(preferences.departure_date, "%Y-%m-%d")
            end = datetime.strptime(preferences.return_date, "%Y-%m-%d")
        except (ValueError, AttributeError):
            log_agent_raw("⚠️  Could not parse trip dates, defaulting to 5 days", agent_name="PlacesAgent")
            return [{"day": i + 1, "date": "", "weather_class": "either", "weather_summary": "N/A"} for i in range(5)]

        days = []
        current = start
        day_num = 1
        while current < end:
            date_str = current.strftime("%Y-%m-%d")
            weather = weather_by_date.get(date_str)
            weather_class = self._classify_day_weather(weather)

            if weather:
                temp_min = weather.get("temp_min", "?")
                temp_max = weather.get("temp_max", "?")
                rain = weather.get("precipitation_probability", 0) or 0
                desc = weather.get("description", "N/A")
                summary = f"{desc}, {temp_min}-{temp_max}°F, {rain:.0f}% rain"
            else:
                summary = "No forecast available"

            days.append({
                "day": day_num,
                "date": date_str,
                "weather_class": weather_class,
                "weather_summary": summary,
            })
            current += timedelta(days=1)
            day_num += 1

        return days

    # ══════════════════════════════════════════════════════════════════════
    # RESTAURANT SEARCH — cuisine-driven via Text Search
    # ══════════════════════════════════════════════════════════════════════

    def _search_restaurants_by_cuisine(self, preferences) -> List[Dict]:
        """
        Search restaurants using cuisine preferences via Text Search API.

        ⭐ preferred_cuisines → 5 results each
        ☆  interested_cuisines → 3 results each
        +  generic "best restaurant" fallback for variety

        Each result is tagged with cuisine_tag for later meal planning.
        """
        destination = preferences.destination
        preferred = preferences.restaurant_prefs.preferred_cuisines
        interested = preferences.restaurant_prefs.interested_cuisines

        log_agent_raw("=" * 80, agent_name="PlacesAgent")
        log_agent_raw("🍽️  CUISINE-SPECIFIC RESTAURANT SEARCH", agent_name="PlacesAgent")
        log_agent_raw(f"   ⭐ Preferred: {', '.join(preferred) if preferred else 'None'}", agent_name="PlacesAgent")
        log_agent_raw(f"   ☆  Interested: {', '.join(interested) if interested else 'None'}", agent_name="PlacesAgent")
        log_agent_raw("=" * 80, agent_name="PlacesAgent")

        all_results: List[Dict] = []
        seen_ids: set = set()

        def _add_results(places: List[Dict], cuisine: str):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["cuisine_tag"] = cuisine
                    all_results.append(place)

        if not self.google_places or not self.google_places.client:
            log_agent_raw("❌ Google Places not available", agent_name="PlacesAgent")
            return []

        # ⭐ Preferred cuisines — more results
        for cuisine in preferred:
            query = f"{cuisine} restaurant in {destination}"
            log_agent_raw(f"   ⭐ Searching: \"{query}\"", agent_name="PlacesAgent")
            results = self.google_places.search_places_by_text(
                query=query,
                location=destination,
                included_type="restaurant",
                min_rating=3.5,
                max_results=5,
                agent_logger=self.logger,
            )
            _add_results(results, cuisine)
            log_agent_raw(f"      → {len(results)} results", agent_name="PlacesAgent")

        # ☆ Interested cuisines — fewer results
        for cuisine in interested:
            query = f"{cuisine} restaurant in {destination}"
            log_agent_raw(f"   ☆  Searching: \"{query}\"", agent_name="PlacesAgent")
            results = self.google_places.search_places_by_text(
                query=query,
                location=destination,
                included_type="restaurant",
                min_rating=3.5,
                max_results=3,
                agent_logger=self.logger,
            )
            _add_results(results, cuisine)
            log_agent_raw(f"      → {len(results)} results", agent_name="PlacesAgent")

        # Fallback generic search for variety
        if len(all_results) < 5:
            query = f"best restaurant in {destination}"
            log_agent_raw(f"   🔄 Fallback: \"{query}\"", agent_name="PlacesAgent")
            results = self.google_places.search_places_by_text(
                query=query,
                location=destination,
                included_type="restaurant",
                min_rating=4.0,
                max_results=5,
                agent_logger=self.logger,
            )
            _add_results(results, "General")

        max_restaurants = getattr(settings, "places_agent_restaurants_max_results", 15)
        all_results = all_results[:max_restaurants]

        log_agent_raw(
            f"🍽️  Total restaurants: {len(all_results)} (deduped, capped at {max_restaurants})",
            agent_name="PlacesAgent",
        )
        return all_results

    # ══════════════════════════════════════════════════════════════════════
    # ACTIVITY SEARCH — interest-driven via Text + Nearby Search
    # ══════════════════════════════════════════════════════════════════════

    def _search_activities_by_interest(self, preferences) -> List[Dict]:
        """
        Search activities using interest preferences.

        Strategy:
          1. Text Search for each specific interest
             ⭐ preferred → 5 results,  ☆ interested → 3 results
          2. Nearby Search for general category types (museum, park, etc.)
          3. Merge + dedupe

        Each result is tagged with interest_tag for later planning.
        """
        destination = preferences.destination
        preferred = preferences.activity_prefs.preferred_interests
        interested = preferences.activity_prefs.interested_interests

        log_agent_raw("=" * 80, agent_name="PlacesAgent")
        log_agent_raw("🎯 INTEREST-SPECIFIC ACTIVITY SEARCH", agent_name="PlacesAgent")
        log_agent_raw(f"   ⭐ Preferred: {', '.join(preferred) if preferred else 'None'}", agent_name="PlacesAgent")
        log_agent_raw(f"   ☆  Interested: {', '.join(interested) if interested else 'None'}", agent_name="PlacesAgent")
        log_agent_raw("=" * 80, agent_name="PlacesAgent")

        all_results: List[Dict] = []
        seen_ids: set = set()

        def _add_results(places: List[Dict], tag: str):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["interest_tag"] = tag
                    all_results.append(place)

        if not self.google_places or not self.google_places.client:
            log_agent_raw("❌ Google Places not available", agent_name="PlacesAgent")
            return []

        # ⭐ Preferred interests — text search, more results
        for interest in preferred:
            query = f"{interest} in {destination}"
            log_agent_raw(f"   ⭐ Searching: \"{query}\"", agent_name="PlacesAgent")
            results = self.google_places.search_places_by_text(
                query=query,
                location=destination,
                min_rating=3.5,
                max_results=5,
                agent_logger=self.logger,
            )
            _add_results(results, interest)
            log_agent_raw(f"      → {len(results)} results", agent_name="PlacesAgent")

        # ☆ Interested — text search, fewer results
        for interest in interested:
            query = f"{interest} in {destination}"
            log_agent_raw(f"   ☆  Searching: \"{query}\"", agent_name="PlacesAgent")
            results = self.google_places.search_places_by_text(
                query=query,
                location=destination,
                min_rating=3.5,
                max_results=3,
                agent_logger=self.logger,
            )
            _add_results(results, interest)
            log_agent_raw(f"      → {len(results)} results", agent_name="PlacesAgent")

        # Nearby Search for general types to fill gaps
        categories = self._determine_categories(preferences)
        non_restaurant_categories = [c for c in categories if c != "restaurants"]

        if non_restaurant_categories:
            place_types = []
            for cat in non_restaurant_categories:
                place_types.extend(self.CATEGORY_TYPES.get(cat, []))
            place_types = list(set(place_types))

            log_agent_raw(f"   🔄 Nearby Search types: {', '.join(place_types)}", agent_name="PlacesAgent")

            nearby_results = self.google_places.search_places(
                location=destination,
                radius=5000,
                place_types=place_types,
                min_rating=3.5,
                max_results=8,
                agent_logger=self.logger,
            )
            for place_type, places in nearby_results.items():
                for place_dict in places:
                    pid = place_dict.get("place_id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        place_dict["interest_tag"] = place_type
                        all_results.append(place_dict)

        max_activities = getattr(settings, "places_agent_activities_max_results", 15)
        all_results = all_results[:max_activities]

        log_agent_raw(
            f"🎯 Total activities: {len(all_results)} (deduped, capped at {max_activities})",
            agent_name="PlacesAgent",
        )
        return all_results

    # ══════════════════════════════════════════════════════════════════════
    # CATEGORY MAPPING (kept for Nearby Search fallback)
    # ══════════════════════════════════════════════════════════════════════

    def _determine_categories(self, preferences) -> List[str]:
        """Map user interests to Nearby Search categories."""
        all_interests = self._get_all_interests(preferences)

        log_agent_raw(
            f"📋 User interests: {', '.join(all_interests) if all_interests else 'None specified'}",
            agent_name="PlacesAgent",
        )

        categories: List[str] = []

        interest_map = {
            "food": ["restaurants"],
            "dining": ["restaurants"],
            "culture": ["culture", "attractions"],
            "art": ["culture"],
            "history": ["attractions", "culture"],
            "museum": ["culture"],
            "sightseeing": ["attractions"],
            "shopping": ["shopping"],
            "nature": ["nature"],
            "outdoor": ["nature"],
            "park": ["nature"],
            "entertainment": ["entertainment"],
            "nightlife": ["entertainment"],
            "theater": ["entertainment", "culture"],
        }

        for interest in all_interests:
            interest_lower = interest.lower()
            for key, cats in interest_map.items():
                if key in interest_lower:
                    categories.extend(cats)

        categories = list(set(categories))[:4]

        if not categories:
            categories = ["attractions", "culture"]

        log_agent_raw(f"🎯 Nearby Search categories: {', '.join(categories)}", agent_name="PlacesAgent")
        return categories

    # ══════════════════════════════════════════════════════════════════════
    # SEGREGATE, ENRICH, CLASSIFY
    # ══════════════════════════════════════════════════════════════════════

    def _classify_venue_type(self, place_dict: Dict) -> str:
        """
        Classify a place as 'indoor', 'outdoor', or 'either'
        based on its Google Places primary_type and types list.
        """
        primary = (place_dict.get("primary_type") or "").lower()
        types_list = [t.lower() for t in (place_dict.get("types") or [])]
        all_types = {primary} | set(types_list)

        if all_types & self.INDOOR_TYPES:
            return "indoor"
        if all_types & self.OUTDOOR_TYPES:
            return "outdoor"
        return "either"

    def _segregate_and_enrich(
        self,
        cuisine_restaurants: List[Dict],
        interest_activities: List[Dict],
        preferences,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Convert raw Google Places dicts into storage-ready dicts.
        Adds venue_type (indoor/outdoor) and cuisine_tag / interest_tag.
        Filters out hotels (handled by HotelAgent).
        """
        EXCLUDED = {"hotel", "lodging", "motel", "hostel", "resort", "resort_hotel"}

        restaurants = []
        for r in cuisine_restaurants:
            primary = (r.get("primary_type") or "").lower()
            if primary in EXCLUDED:
                continue
            place = self._google_dict_to_place(r)
            if place:
                d = place.model_dump(mode="json")
                d["cuisine_tag"] = r.get("cuisine_tag", "")
                d["venue_type"] = "indoor"  # restaurants are always indoor
                restaurants.append(d)

        activities = []
        for a in interest_activities:
            primary = (a.get("primary_type") or "").lower()
            if primary in EXCLUDED:
                continue
            # skip anything that looks like a restaurant — it belongs above
            RESTAURANT_KEYWORDS = {"restaurant", "cafe", "bar", "bakery", "food"}
            if primary in RESTAURANT_KEYWORDS:
                continue
            place = self._google_dict_to_place(a)
            if place:
                d = place.model_dump(mode="json")
                d["interest_tag"] = a.get("interest_tag", "")
                d["venue_type"] = self._classify_venue_type(a)
                activities.append(d)

        return restaurants, activities

    def _google_dict_to_place(self, google_data: Dict) -> Optional[Place]:
        """Create Place object from Google Places parsed dict."""
        try:
            opening_hours = None
            if google_data.get("currentOpeningHours"):
                opening_hours = {
                    "open_now": google_data["currentOpeningHours"].get("openNow"),
                    "weekday_text": google_data["currentOpeningHours"].get("weekdayDescriptions", []),
                }

            return Place(
                id=google_data.get("place_id", str(time.time())),
                name=google_data.get("name", "Unknown Place"),
                address=google_data.get("address", ""),
                latitude=google_data.get("latitude"),
                longitude=google_data.get("longitude"),
                rating=google_data.get("google_rating"),
                category=google_data.get("primary_type", "other"),
                description=(
                    f"Rated {google_data.get('google_rating', 0)}/5 "
                    f"by {google_data.get('user_ratings_total', 0)} reviewers"
                ),
                photos=google_data.get("photos", [])[:5],
                opening_hours=opening_hours,
                price_level=google_data.get("price_level"),
                website=google_data.get("website"),
            )
        except Exception as e:
            log_agent_raw(f"⚠️ Failed to create place: {e}", agent_name="PlacesAgent")
            return None

    # ══════════════════════════════════════════════════════════════════════
    # STORAGE
    # ══════════════════════════════════════════════════════════════════════

    def _store_results(
        self,
        restaurants: List[Dict],
        activities: List[Dict],
        preferences,
        api_duration: float,
    ):
        """Store restaurants and activities in trip storage."""
        meta = {
            "destination": preferences.destination,
            "search_time": datetime.now().isoformat(),
            "api_duration": api_duration,
        }

        if restaurants:
            self.trip_storage.add_restaurants(
                trip_id=self.trip_id,
                restaurants=restaurants,
                metadata={**meta, "total_results": len(restaurants)},
            )
            log_agent_raw(f"💾 Stored {len(restaurants)} restaurants", agent_name="PlacesAgent")

        if activities:
            self.trip_storage.add_activities(
                trip_id=self.trip_id,
                activities=activities,
                metadata={**meta, "total_results": len(activities)},
            )
            log_agent_raw(f"💾 Stored {len(activities)} activities", agent_name="PlacesAgent")

        self.trip_storage.log_api_call(
            trip_id=self.trip_id,
            agent_name="PlacesAgent",
            api_name="GooglePlaces",
            duration=api_duration,
        )

    # ══════════════════════════════════════════════════════════════════════
    # LLM — day-by-day plan with weather & cuisine rotation
    # ══════════════════════════════════════════════════════════════════════

    def _generate_daily_plan(
        self,
        restaurants: List[Dict],
        activities: List[Dict],
        trip_days: List[Dict],
        preferences,
    ) -> str:
        """
        Use LLM to build a day-by-day recommendation that:
        - Assigns indoor activities on rainy days, outdoor on clear days
        - Assigns restaurants to lunch & dinner with cuisine rotation
        - Avoids same cuisine on consecutive days
        - Highlights ⭐ preferred places
        """
        if not restaurants and not activities:
            return "No places found matching your interests."

        # ── Build restaurant summary ──────────────────────────────────
        rest_lines = []
        for r in restaurants[:15]:
            cuisine = r.get("cuisine_tag", "?")
            name = r.get("name", "Unknown")
            rating = r.get("rating") or 0
            rest_lines.append(f"  - {name} ({cuisine}) — {rating:.1f}★")
        restaurant_block = "\n".join(rest_lines) if rest_lines else "  (none found)"

        # ── Build activity summary with venue type ────────────────────
        act_lines = []
        for a in activities[:15]:
            tag = a.get("interest_tag", "?")
            name = a.get("name", "Unknown")
            rating = a.get("rating") or 0
            vtype = a.get("venue_type", "either")
            act_lines.append(f"  - {name} [{vtype}] ({tag}) — {rating:.1f}★")
        activity_block = "\n".join(act_lines) if act_lines else "  (none found)"

        # ── Build weather schedule ────────────────────────────────────
        day_lines = []
        for d in trip_days:
            day_lines.append(
                f"  Day {d['day']} ({d['date']}): {d['weather_summary']} → recommend {d['weather_class']} activities"
            )
        weather_block = "\n".join(day_lines) if day_lines else "  (no weather data)"

        # ── Preference context ────────────────────────────────────────
        pref_cuisines = preferences.restaurant_prefs.preferred_cuisines
        int_cuisines = preferences.restaurant_prefs.interested_cuisines
        pref_interests = preferences.activity_prefs.preferred_interests
        int_interests = preferences.activity_prefs.interested_interests
        meals = preferences.restaurant_prefs.meals

        prompt = f"""
            You are building a day-by-day travel plan for {preferences.destination}.

            TRIP DATES & WEATHER:
            {weather_block}

            RESTAURANTS FOUND (with cuisine tag):
            {restaurant_block}

            ACTIVITIES FOUND (with venue type: indoor/outdoor/either):
            {activity_block}

            USER PREFERENCES:
            ⭐ Preferred cuisines: {', '.join(pref_cuisines) if pref_cuisines else 'None'}
            ☆  Interested cuisines: {', '.join(int_cuisines) if int_cuisines else 'None'}
            ⭐ Preferred activities: {', '.join(pref_interests) if pref_interests else 'None'}
            ☆  Interested activities: {', '.join(int_interests) if int_interests else 'None'}
            Meals to plan: {', '.join(meals)}
            Pace: {preferences.activity_prefs.pace}

            RULES:
            1. On days marked "indoor" → prefer [indoor] activities. On "outdoor" days → prefer [outdoor] activities.
            2. Assign a restaurant for EACH meal slot (lunch, dinner) EACH day.
            3. ROTATE cuisines: never assign the same cuisine for consecutive meals.
            e.g. if lunch is Italian, dinner should be different; if dinner is Indian, next day's lunch should be different.
            4. ⭐ Preferred cuisines should appear MORE often than ☆ interested ones.
            5. ⭐ Preferred activities should be scheduled on the BEST weather days.
            6. Keep it conversational, enthusiastic, and practical (4-6 sentences per day).
            7. Mention specific restaurant and activity names with their ratings.

            Write a concise day-by-day plan (one short paragraph per day).
            """
        log_agent_raw("\n\nSystem Prompt:", agent_name="PlacesAgent")
        log_agent_raw(f"{self.system_message}", agent_name="PlacesAgent")

        log_agent_raw("\n\nPrompt:", agent_name="PlacesAgent")
        log_agent_raw(f"{prompt}", agent_name="PlacesAgent")

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {e}", agent_name="PlacesAgent")
            total = len(restaurants) + len(activities)
            return (
                f"I found {total} amazing places in {preferences.destination}! "
                f"Including {len(restaurants)} restaurants across "
                f"{len(set(r.get('cuisine_tag', '') for r in restaurants))} cuisines "
                f"and {len(activities)} activities. "
                f"Check the full list for details."
            )


# ══════════════════════════════════════════════════════════════════════════
# FACTORY
# ══════════════════════════════════════════════════════════════════════════

def create_places_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> PlacesAgent:
    """Factory function to create PlacesAgent"""
    return PlacesAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)