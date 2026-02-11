"""
Places Agent - Real Implementation using Google Places API (New)
Location: backend/agents/places_agent.py

Searches for restaurants, attractions, shopping, museums, parks, etc.
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.google_places_service import get_google_places_service
from models.trip import Place

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai


class PlacesAgent(TravelQBaseAgent):
    """
    Places Agent - Finds restaurants, attractions, and points of interest
    
    Uses Google Places API (New) for real data
    """
    
    # Category mappings
    CATEGORY_TYPES = {
        "restaurants": ["restaurant", "cafe", "bar"],
        "attractions": ["tourist_attraction", "museum", "art_gallery"],
        "shopping": ["shopping_mall", "department_store", "market"],
        "nature": ["park", "botanical_garden", "hiking_area"],
        "culture": ["museum", "art_gallery", "performing_arts_theater"],
        "entertainment": ["movie_theater", "amusement_park", "casino"]
    }
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """
You are a Places & Attractions Expert helping travelers discover amazing locations.

Your job:
1. Find the best restaurants, attractions, and activities
2. Consider user interests and preferences
3. Provide variety (mix of popular and hidden gems)
4. Include practical details (ratings, hours, prices)

Be enthusiastic, knowledgeable, and helpful!
"""
        
        super().__init__(
            name="PlacesAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="PlacesAgent",
            system_message=system_message,
            description="Finds restaurants, attractions, and points of interest",
            **kwargs
        )
        
        # Storage
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        
        # API Service
        self.google_places = get_google_places_service()
        
        log_agent_raw("📍 PlacesAgent initialized", agent_name="PlacesAgent")
        log_agent_raw("   ✓ Google Places service", agent_name="PlacesAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """Generate reply with place search results"""
        log_agent_raw("🔍 PlacesAgent processing request...", agent_name="PlacesAgent")
        
        # Log incoming message
        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name,
                truncate=500
            )
        
        # Get preferences
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="PlacesAgent")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences for trip {self.trip_id}", agent_name="PlacesAgent")
        
        try:
            start_time = time.time()
            
            # Determine which categories to search based on interests
            categories_to_search = self._determine_categories(preferences)
            
            # Search places
            places_by_category = self._search_places_complete(
                destination=preferences.destination,
                categories=categories_to_search,
                min_rating=3.5
            )
            
            api_duration = time.time() - start_time
            
            # Flatten all places
            all_places = []
            for category_places in places_by_category.values():
                all_places.extend(category_places)
            
            log_agent_raw(f"✅ Search complete: {len(all_places)} places in {api_duration:.2f}s", 
                         agent_name="PlacesAgent")
            
            if not all_places:
                return self.signal_completion(
                    "I couldn't find any places matching your interests. "
                    "Try broadening your search criteria."
                )
            
            # Store ALL places

            # Segregate places into restaurants and activities
            restaurants = []
            activities = []
            restaurent_count = 0
            activity_count = 0
            max_restaurant = 5
            max_activity = 5

            RESTAURANT_KEYWORDS = ['restaurant', 'cafe', 'bar', 'bakery', 'food']
            EXCLUDED_CATEGORIES = ['hotel', 'lodging', 'motel', 'hostel', 'resort']  # Handled by HotelsAgent

            for place in all_places:
                place_dict = self._place_to_dict(place)
                category = place.category.lower()
                
                # Skip excluded categories
                if category in EXCLUDED_CATEGORIES:
                    continue
                
                # Check if any restaurant keyword appears in the category
                is_restaurant = any(keyword in category for keyword in RESTAURANT_KEYWORDS)
                
                if is_restaurant:
                    restaurent_count +=1
                    if(restaurent_count <= max_restaurant):
                        restaurants.append(place_dict)
                else:
                    activity_count +=1
                    if(activity_count <= max_activity):
                        activities.append(place_dict)

            # Store separately
            if restaurants:
                self.trip_storage.add_restaurants(
                    trip_id=self.trip_id,
                    restaurants=restaurants,
                    metadata={
                        "destination": preferences.destination,
                        "search_time": datetime.now().isoformat(),
                        "total_results": len(restaurants),
                        "api_duration": api_duration
                    }
                )
                log_agent_raw(f"💾 Stored {len(restaurants)} restaurants", agent_name="PlacesAgent")

            if activities:
                self.trip_storage.add_activities(
                    trip_id=self.trip_id,
                    activities=activities,
                    metadata={
                        "destination": preferences.destination,
                        "search_time": datetime.now().isoformat(),
                        "total_results": len(activities),
                        "api_duration": api_duration
                    }
                )
                log_agent_raw(f"💾 Stored {len(activities)} activities", agent_name="PlacesAgent")

            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="PlacesAgent",
                api_name="GooglePlaces",
                duration=api_duration
            )
            
            # Generate recommendation
            recommendation = self._generate_recommendation(places_by_category, preferences)
            
            # Log outgoing
            self.log_conversation_message(
                message_type="OUTGOING",
                content=recommendation,
                sender="chat_manager",
                truncate=1000
            )
            
            return self.signal_completion(recommendation)
            
        except Exception as e:
            log_agent_raw(f"❌ Places search failed: {str(e)}", agent_name="PlacesAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="PlacesAgent")
            error_msg = f"I encountered an error: {str(e)}. Please try again."
            return self.signal_completion(error_msg)
    
    def _determine_categories(self, preferences) -> List[str]:
        """Determine which categories to search based on user interests"""
        interests = preferences.activity_prefs.interests if preferences.activity_prefs.interests else []
        
        log_agent_raw(f"📋 User interests: {', '.join(interests) if interests else 'None specified'}", 
                     agent_name="PlacesAgent")
        
        categories = ["restaurants"]  # Always include restaurants
        
        # Map interests to categories
        interest_map = {
            "food": ["restaurants"],
            "dining": ["restaurants"],
            "culture": ["culture", "attractions"],
            "art": ["culture"],
            "history": ["attractions", "culture"],
            "sightseeing": ["attractions"],
            "shopping": ["shopping"],
            "nature": ["nature"],
            "outdoor": ["nature"],
            "entertainment": ["entertainment"],
            "nightlife": ["entertainment"]
        }
        
        for interest in interests:
            interest_lower = interest.lower()
            for key, cats in interest_map.items():
                if key in interest_lower:
                    categories.extend(cats)
        
        # Remove duplicates and limit
        categories = list(set(categories))[:4]  # Max 4 categories
        
        # If no specific interests, use default mix
        if len(categories) == 1:  # Only restaurants
            categories.extend(["attractions", "culture"])
        
        log_agent_raw(f"🎯 Will search categories: {', '.join(categories)}", 
                     agent_name="PlacesAgent")
        
        return categories
    
    def _search_places_complete(
        self,
        destination: str,
        categories: List[str],
        min_rating: float = 3.5
    ) -> Dict[str, List[Place]]:
        """
        Complete places search workflow
        
        Returns:
            Dictionary with category names as keys, lists of Place objects as values
        """
        log_agent_raw("=" * 80, agent_name="PlacesAgent")
        log_agent_raw("🔍 COMPLETE PLACES SEARCH", agent_name="PlacesAgent")
        log_agent_raw("=" * 80, agent_name="PlacesAgent")
        
        if not self.google_places or not self.google_places.client:
            log_agent_raw("❌ Google Places not available", agent_name="PlacesAgent")
            return {}
        
        # Convert categories to place types
        place_types = []
        for category in categories:
            types = self.CATEGORY_TYPES.get(category, [])
            place_types.extend(types)
        
        # Remove duplicates
        place_types = list(set(place_types))
        
        log_agent_raw(f"📍 Searching for: {', '.join(place_types)}", agent_name="PlacesAgent")
        
        # Search
        results = self.google_places.search_places(
            location=destination,
            radius=5000,
            place_types=place_types,
            min_rating=min_rating,
            max_results=10,
            agent_logger=self.logger
        )
        
        # Convert to Place objects organized by category
        places_by_category = {}
        
        for place_type, place_dicts in results.items():
            # Map place type back to category
            category = self._get_category_for_type(place_type)
            
            if category not in places_by_category:
                places_by_category[category] = []
            
            for place_dict in place_dicts:
                place = self._create_place_from_google(place_dict)
                if place:
                    places_by_category[category].append(place)
        
        log_agent_raw("=" * 80, agent_name="PlacesAgent")
        
        return places_by_category
    
    def _get_category_for_type(self, place_type: str) -> str:
        """Map place type back to category name"""
        for category, types in self.CATEGORY_TYPES.items():
            if place_type in types:
                return category
        return "other"
    
    def _create_place_from_google(self, google_data: Dict) -> Optional[Place]:
        """Create Place object from Google Places data"""
        try:
            # Extract opening hours
            opening_hours = None
            if google_data.get('currentOpeningHours'):
                opening_hours = {
                    'open_now': google_data['currentOpeningHours'].get('openNow'),
                    'weekday_text': google_data['currentOpeningHours'].get('weekdayDescriptions', [])
                }
            
            return Place(
                id=google_data.get('place_id', str(time.time())),
                name=google_data.get('name', 'Unknown Place'),
                address=google_data.get('address', ''),
                latitude=google_data.get('latitude'),
                longitude=google_data.get('longitude'),
                rating=google_data.get('google_rating'),
                category=google_data.get('primary_type', 'other'),
                description=f"Rated {google_data.get('google_rating', 0)}/5 by {google_data.get('user_ratings_total', 0)} reviewers",
                photos=google_data.get('photos', [])[:5],
                opening_hours=opening_hours,
                price_level=google_data.get('price_level'),
                website=google_data.get('website')
            )
        except Exception as e:
            log_agent_raw(f"⚠️ Failed to create place: {str(e)}", agent_name="PlacesAgent")
            return None
    
    def _place_to_dict(self, place: Place) -> Dict:
        """Convert Place to dict for storage"""
        return place.model_dump(mode='json')
    
    def _generate_recommendation(
        self,
        places_by_category: Dict[str, List[Place]],
        preferences: Any
    ) -> str:
        """Generate LLM recommendation"""
        
        if not places_by_category:
            return "No places found matching your interests."
        
        # Build summary
        summary_parts = []
        for category, places in places_by_category.items():
            if places:
                top_place = max(places, key=lambda p: p.rating or 0)
                summary_parts.append(f"- {category.title()}: {len(places)} options (top: {top_place.name}, {top_place.rating:.1f}★)")
        
        # Build prompt
        prompt = f"""
Based on places search results, provide enthusiastic recommendations.

DESTINATION: {preferences.destination}
SEARCH RESULTS:
{chr(10).join(summary_parts)}

USER INTERESTS: {', '.join(preferences.activity_prefs.interests) if preferences.activity_prefs.interests else 'General sightseeing'}

Provide a conversational recommendation (4-5 sentences):
- Mention the variety of options found
- Highlight 2-3 specific places with names and why they're special
- Match recommendations to user interests
- Keep it exciting and encouraging

Be enthusiastic and specific!
"""
        
        # Call LLM
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="PlacesAgent")
            
            # Fallback
            total_places = sum(len(places) for places in places_by_category.values())
            return (f"I found {total_places} amazing places in {preferences.destination}! "
                   f"Check out the full list for restaurants, attractions, and activities.")


def create_places_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> PlacesAgent:
    """Factory function to create PlacesAgent"""
    return PlacesAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)