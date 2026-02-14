"""
Places Agent - Preference-Aware, Weather-Aware, Day-Planned
Location: backend/agents/places_agent.py

Changes (v6 — enriched Place data):
  - _google_dict_to_place: now passes through reviews, phone_number,
    google_url, user_ratings_total from Google Places v4 data
  - Everything else from v5 (recommendation storage)
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
    Places Agent v6 — Preference-aware, weather-aware, day-planned,
    with structured recommendation storage and enriched Place data.
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
You are a Places & Dining Expert helping travelers discover amazing locations.

Your job:
1. Find restaurants that match the traveler's cuisine preferences
2. Find activities and attractions that match their interests
3. Consider weather forecasts when planning indoor vs outdoor activities
4. Plan meals with cuisine variety - avoid the same cuisine on consecutive days
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

        self.trip_id = trip_id
        self.trip_storage = trip_storage
        self.google_places = get_google_places_service()

        log_agent_raw("Places Agent v6 initialized", agent_name="PlacesAgent")

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

    def generate_reply(self, messages=None, sender=None, config=None) -> str:
        log_agent_raw("PlacesAgent v6 processing request...", agent_name="PlacesAgent")

        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, "name") else "Unknown"
            self.log_conversation_message(message_type="INCOMING", content=last_message, sender=sender_name, truncate=500)

        preferences = self.trip_storage.get_preferences(self.trip_id)
        if not preferences:
            return self.signal_completion(f"Error: Could not find preferences for trip {self.trip_id}")

        try:
            start_time = time.time()
            weather_by_date = self._load_weather_data()
            trip_days = self._compute_trip_days(preferences, weather_by_date)

            cuisine_restaurants = self._search_restaurants_by_cuisine(preferences)
            interest_activities = self._search_activities_by_interest(preferences)
            api_duration = time.time() - start_time

            restaurants, activities = self._segregate_and_enrich(cuisine_restaurants, interest_activities, preferences)

            if not restaurants and not activities:
                return self.signal_completion("I couldn't find any places matching your interests.")

            self._store_results(restaurants, activities, preferences, api_duration)
            recommendation = self._generate_daily_plan(restaurants, activities, trip_days, preferences)

            self.log_conversation_message(message_type="OUTGOING", content=recommendation, sender="chat_manager", truncate=1000)
            return self.signal_completion(recommendation)

        except Exception as e:
            log_agent_raw(f"Places search failed: {str(e)}", agent_name="PlacesAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="PlacesAgent")
            return self.signal_completion(f"I encountered an error: {str(e)}. Please try again.")

    def _load_weather_data(self) -> Dict[str, Dict]:
        try:
            all_options = self.trip_storage.get_all_options(self.trip_id)
            weather_list = all_options.get("weather", [])
            if not weather_list:
                return {}
            weather_by_date = {}
            for w in weather_list:
                date_str = w.get("date", "")
                if date_str:
                    weather_by_date[date_str] = w
            return weather_by_date
        except Exception:
            return {}

    @staticmethod
    def _classify_day_weather(weather_dict: Optional[Dict]) -> str:
        if not weather_dict:
            return "either"
        rain_prob = weather_dict.get("precipitation_probability", 0) or 0
        description = (weather_dict.get("description") or "").lower()
        conditions = (weather_dict.get("conditions") or "").lower()
        indoor_keywords = ["rain", "storm", "thunder", "snow", "sleet", "drizzle", "heavy"]
        if rain_prob > 60 or any(kw in description for kw in indoor_keywords) or any(kw in conditions for kw in indoor_keywords):
            return "indoor"
        outdoor_keywords = ["clear", "sunny", "fair", "fine"]
        if rain_prob <= 30 and (any(kw in description for kw in outdoor_keywords) or any(kw in conditions for kw in outdoor_keywords) or rain_prob == 0):
            return "outdoor"
        return "either"

    def _compute_trip_days(self, preferences, weather_by_date):
        try:
            start = datetime.strptime(preferences.departure_date, "%Y-%m-%d")
            end = datetime.strptime(preferences.return_date, "%Y-%m-%d")
        except (ValueError, AttributeError):
            return [{"day": i + 1, "date": "", "weather_class": "either", "weather_summary": "N/A"} for i in range(5)]
        days = []
        current = start
        day_num = 1
        while current < end:
            date_str = current.strftime("%Y-%m-%d")
            weather = weather_by_date.get(date_str)
            weather_class = self._classify_day_weather(weather)
            if weather:
                summary = f"{weather.get('description', 'N/A')}, {weather.get('temp_min', '?')}-{weather.get('temp_max', '?')}F, {(weather.get('precipitation_probability', 0) or 0):.0f}% rain"
            else:
                summary = "No forecast available"
            days.append({"day": day_num, "date": date_str, "weather_class": weather_class, "weather_summary": summary})
            current += timedelta(days=1)
            day_num += 1
        return days

    def _search_restaurants_by_cuisine(self, preferences) -> List[Dict]:
        destination = preferences.destination
        preferred = preferences.restaurant_prefs.preferred_cuisines
        interested = preferences.restaurant_prefs.interested_cuisines
        all_results = []
        seen_ids = set()
        def _add(places, cuisine):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["cuisine_tag"] = cuisine
                    all_results.append(place)
        if not self.google_places or not self.google_places.client:
            return []
        for cuisine in preferred:
            results = self.google_places.search_places_by_text(query=f"{cuisine} restaurant in {destination}", location=destination, included_type="restaurant", min_rating=3.5, max_results=5, agent_logger=self.logger)
            _add(results, cuisine)
        for cuisine in interested:
            results = self.google_places.search_places_by_text(query=f"{cuisine} restaurant in {destination}", location=destination, included_type="restaurant", min_rating=3.5, max_results=3, agent_logger=self.logger)
            _add(results, cuisine)
        if len(all_results) < 5:
            results = self.google_places.search_places_by_text(query=f"best restaurant in {destination}", location=destination, included_type="restaurant", min_rating=4.0, max_results=5, agent_logger=self.logger)
            _add(results, "General")
        max_r = getattr(settings, "places_agent_restaurants_max_results", 15)
        return all_results[:max_r]

    def _search_activities_by_interest(self, preferences) -> List[Dict]:
        destination = preferences.destination
        preferred = preferences.activity_prefs.preferred_interests
        interested = preferences.activity_prefs.interested_interests
        all_results = []
        seen_ids = set()
        def _add(places, tag):
            for place in places:
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    place["interest_tag"] = tag
                    all_results.append(place)
        if not self.google_places or not self.google_places.client:
            return []
        for interest in preferred:
            results = self.google_places.search_places_by_text(query=f"{interest} in {destination}", location=destination, min_rating=3.5, max_results=5, agent_logger=self.logger)
            _add(results, interest)
        for interest in interested:
            results = self.google_places.search_places_by_text(query=f"{interest} in {destination}", location=destination, min_rating=3.5, max_results=3, agent_logger=self.logger)
            _add(results, interest)
        categories = self._determine_categories(preferences)
        non_restaurant = [c for c in categories if c != "restaurants"]
        if non_restaurant:
            place_types = list(set(t for cat in non_restaurant for t in self.CATEGORY_TYPES.get(cat, [])))
            nearby = self.google_places.search_places(location=destination, radius=5000, place_types=place_types, min_rating=3.5, max_results=8, agent_logger=self.logger)
            for ptype, places in nearby.items():
                for pd in places:
                    pid = pd.get("place_id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        pd["interest_tag"] = ptype
                        all_results.append(pd)
        max_a = getattr(settings, "places_agent_activities_max_results", 15)
        return all_results[:max_a]

    def _determine_categories(self, preferences) -> List[str]:
        all_interests = self._get_all_interests(preferences)
        categories = []
        interest_map = {"food": ["restaurants"], "dining": ["restaurants"], "culture": ["culture", "attractions"], "art": ["culture"], "history": ["attractions", "culture"], "museum": ["culture"], "sightseeing": ["attractions"], "shopping": ["shopping"], "nature": ["nature"], "outdoor": ["nature"], "park": ["nature"], "entertainment": ["entertainment"], "nightlife": ["entertainment"], "theater": ["entertainment", "culture"]}
        for interest in all_interests:
            il = interest.lower()
            for key, cats in interest_map.items():
                if key in il:
                    categories.extend(cats)
        categories = list(set(categories))[:4]
        return categories if categories else ["attractions", "culture"]

    def _classify_venue_type(self, place_dict: Dict) -> str:
        primary = (place_dict.get("primary_type") or "").lower()
        types_list = [t.lower() for t in (place_dict.get("types") or [])]
        all_types = {primary} | set(types_list)
        if all_types & self.INDOOR_TYPES: return "indoor"
        if all_types & self.OUTDOOR_TYPES: return "outdoor"
        return "either"

    def _segregate_and_enrich(self, cuisine_restaurants, interest_activities, preferences):
        EXCLUDED = {"hotel", "lodging", "motel", "hostel", "resort", "resort_hotel"}
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
        RESTAURANT_KEYWORDS = {"restaurant", "cafe", "bar", "bakery", "food"}
        for a in interest_activities:
            primary = (a.get("primary_type") or "").lower()
            if primary in EXCLUDED or primary in RESTAURANT_KEYWORDS: continue
            place = self._google_dict_to_place(a)
            if place:
                d = place.model_dump(mode="json")
                d["interest_tag"] = a.get("interest_tag", "")
                d["venue_type"] = self._classify_venue_type(a)
                activities.append(d)
        return restaurants, activities

    def _google_dict_to_place(self, google_data: Dict) -> Optional[Place]:
        """
        Create Place object from Google Places parsed dict.

        v6: Now passes through reviews, phone_number, google_url,
        user_ratings_total - data that google_places_service v4 extracts
        but was previously discarded at this boundary.
        """
        try:
            opening_hours = None
            if google_data.get("currentOpeningHours"):
                opening_hours = {
                    "open_now": google_data["currentOpeningHours"].get("openNow"),
                    "weekday_text": google_data["currentOpeningHours"].get("weekdayDescriptions", []),
                }

            # v6: Parse reviews into HotelReview-compatible objects
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
                # v6: Google Places data previously discarded
                reviews=reviews,
                phone_number=google_data.get("phone_number"),
                google_url=google_data.get("google_url"),
            )
        except Exception as e:
            log_agent_raw(f"Failed to create place: {e}", agent_name="PlacesAgent")
            return None

    def _store_results(self, restaurants, activities, preferences, api_duration):
        meta = {"destination": preferences.destination, "search_time": datetime.now().isoformat(), "api_duration": api_duration}
        if restaurants:
            self.trip_storage.add_restaurants(trip_id=self.trip_id, restaurants=restaurants, metadata={**meta, "total_results": len(restaurants)})
        if activities:
            self.trip_storage.add_activities(trip_id=self.trip_id, activities=activities, metadata={**meta, "total_results": len(activities)})
        self.trip_storage.log_api_call(trip_id=self.trip_id, agent_name="PlacesAgent", api_name="GooglePlaces", duration=api_duration)

    def _extract_mentioned_ids(self, plan_text, places, label):
        mentioned, seen = [], set()
        sorted_places = sorted(places, key=lambda p: len(p.get("name", "")), reverse=True)
        for place in sorted_places:
            name, pid = place.get("name", ""), place.get("id", "")
            if name and pid and name in plan_text and pid not in seen:
                seen.add(pid)
                mentioned.append(pid)
        return mentioned

    def _store_place_recommendations(self, plan_text, restaurants, activities):
        rec_restaurant_ids = self._extract_mentioned_ids(plan_text, restaurants, "restaurants")
        if rec_restaurant_ids:
            primary_id = rec_restaurant_ids[0]
            primary = next((r for r in restaurants if r.get("id") == primary_id), None)
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id, category="restaurant", recommended_id=primary_id,
                reason=f"Top dining pick from {len(restaurants)} options" if not primary else f"Top dining pick - {primary.get('cuisine_tag', '')} cuisine, {primary.get('rating', 0):.1f} stars",
                metadata={"name": primary.get("name", "") if primary else "", "all_recommended_ids": rec_restaurant_ids, "total_options_reviewed": len(restaurants)},
            )
        rec_activity_ids = self._extract_mentioned_ids(plan_text, activities, "activities")
        if rec_activity_ids:
            primary_id = rec_activity_ids[0]
            primary = next((a for a in activities if a.get("id") == primary_id), None)
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id, category="activity", recommended_id=primary_id,
                reason=f"Top activity from {len(activities)} options" if not primary else f"Top activity - {primary.get('interest_tag', '')}, {primary.get('rating', 0):.1f} stars",
                metadata={"name": primary.get("name", "") if primary else "", "all_recommended_ids": rec_activity_ids, "total_options_reviewed": len(activities)},
            )

    def _generate_daily_plan(self, restaurants, activities, trip_days, preferences) -> str:
        if not restaurants and not activities:
            return "No places found matching your interests."

        rest_lines = [f"  - {r.get('name', '?')} ({r.get('cuisine_tag', '?')}) - {(r.get('rating') or 0):.1f} stars" for r in restaurants[:15]]
        restaurant_block = "\n".join(rest_lines) if rest_lines else "  (none found)"

        act_lines = [f"  - {a.get('name', '?')} [{a.get('venue_type', 'either')}] ({a.get('interest_tag', '?')}) - {(a.get('rating') or 0):.1f} stars" for a in activities[:15]]
        activity_block = "\n".join(act_lines) if act_lines else "  (none found)"

        day_lines = [f"  Day {d['day']} ({d['date']}): {d['weather_summary']} -> recommend {d['weather_class']} activities" for d in trip_days]
        weather_block = "\n".join(day_lines) if day_lines else "  (no weather data)"

        pref_cuisines = preferences.restaurant_prefs.preferred_cuisines
        int_cuisines = preferences.restaurant_prefs.interested_cuisines
        pref_interests = preferences.activity_prefs.preferred_interests
        int_interests = preferences.activity_prefs.interested_interests
        meals = preferences.restaurant_prefs.meals

        prompt = f"""You are building a day-by-day travel plan for {preferences.destination}.

TRIP DATES & WEATHER:
{weather_block}

RESTAURANTS FOUND (with cuisine tag):
{restaurant_block}

ACTIVITIES FOUND (with venue type: indoor/outdoor/either):
{activity_block}

USER PREFERENCES:
Preferred cuisines: {', '.join(pref_cuisines) if pref_cuisines else 'None'}
Interested cuisines: {', '.join(int_cuisines) if int_cuisines else 'None'}
Preferred activities: {', '.join(pref_interests) if pref_interests else 'None'}
Interested activities: {', '.join(int_interests) if int_interests else 'None'}
Meals to plan: {', '.join(meals)}
Pace: {preferences.activity_prefs.pace}

RULES:
1. On days marked "indoor" prefer indoor activities. On "outdoor" days prefer outdoor activities.
2. Assign a restaurant for EACH meal slot (lunch, dinner) EACH day.
3. ROTATE cuisines: never assign the same cuisine for consecutive meals.
4. Preferred cuisines should appear MORE often than interested ones.
5. Preferred activities should be scheduled on the BEST weather days.
6. Keep it conversational, enthusiastic, and practical (4-6 sentences per day).
7. Mention specific restaurant and activity names with their ratings.
8. Use the EXACT restaurant and activity names as listed above - do not rename or abbreviate them.

Write a concise day-by-day plan (one short paragraph per day)."""

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "system", "content": self.system_message}, {"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=800,
            )
            plan_text = response.choices[0].message.content.strip()
        except Exception as e:
            plan_text = f"I found {len(restaurants) + len(activities)} amazing places in {preferences.destination}!"

        try:
            self._store_place_recommendations(plan_text, restaurants, activities)
        except Exception:
            pass

        try:
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id, category="daily_plan", recommended_id="daily_plan",
                reason=plan_text, metadata={"destination": preferences.destination, "num_days": len(trip_days), "num_restaurants": len(restaurants), "num_activities": len(activities)},
            )
        except Exception:
            pass

        return plan_text


def create_places_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> PlacesAgent:
    return PlacesAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)