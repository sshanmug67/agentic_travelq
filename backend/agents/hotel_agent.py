"""
Hotel Agent - Real API with Centralized Storage
Location: backend/agents/hotel_agent.py
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.amadeus_service import get_amadeus_service
from models.trip import Hotel, HotelAmenities

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai


class HotelAgent(TravelQBaseAgent):
    """
    Hotel Agent with real Amadeus API + centralized storage
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """
You are a helpful Hotel Search Assistant.

Your job:
1. Search for hotels using real-time data
2. Review all available options
3. Provide a brief, conversational recommendation

Be friendly and helpful. Don't dump data - just give useful advice.
"""
        
        super().__init__(
            name="HotelAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="HotelAgent",
            system_message=system_message,
            description="Searches hotels and provides personalized recommendations",
            **kwargs
        )
        
        # Storage
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        
        # API service
        self.amadeus_service = get_amadeus_service()
        
        log_agent_raw("🏨 HotelAgent initialized (REAL API MODE)", agent_name="HotelAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """
        Generate reply: Call API, store options, return recommendation
        """
        log_agent_raw("🔍 HotelAgent processing request...", agent_name="HotelAgent")
        
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
        
        # Get preferences from storage
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="HotelAgent")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences from storage for trip {self.trip_id}", 
                     agent_name="HotelAgent")
        

        # Build search parameters
        search_params = {
            "destination": preferences.destination,
            "check_in_date": preferences.departure_date,
            "check_out_date": preferences.return_date,
            "num_travelers": preferences.num_travelers,
            "min_rating": preferences.hotel_prefs.min_rating,  # ✅ Direct access (it's a Pydantic model)
            "budget_per_night": preferences.budget.hotel_budget_per_night,  # ✅ Direct access
            "amenities": preferences.hotel_prefs.amenities  # ✅ Fixed: was 'preferred_amenities'
        }
        
        log_agent_json(search_params, label="Hotel Search Parameters (from storage)", 
                      agent_name="HotelAgent")
        
        try:
            # Resolve destination to city code
            city_code = self._resolve_city_code(search_params["destination"])
            
            if not city_code:
                error_msg = f"Could not resolve destination '{search_params['destination']}' to city code"
                log_agent_raw(f"❌ {error_msg}", agent_name="HotelAgent")
                return self.signal_completion(f"I'm sorry, I couldn't find hotels for that destination.")
            
            log_agent_raw(f"✓ Resolved: {search_params['destination']} → {city_code}", 
                         agent_name="HotelAgent")
            
            # Call Amadeus API
            start_time = time.time()
            
            hotels = self._search_hotels_api(
                city_code=city_code,
                check_in_date=search_params["check_in_date"],
                check_out_date=search_params["check_out_date"],
                adults=search_params["num_travelers"],
                min_rating=search_params["min_rating"]
            )
            
            api_duration = time.time() - start_time
            
            log_agent_raw(f"✅ API returned {len(hotels)} hotel options in {api_duration:.2f}s", 
                         agent_name="HotelAgent")
            
            # Store ALL options in centralized storage
            hotels_dict = [self._hotel_to_dict(h) for h in hotels]
            
            self.trip_storage.add_hotels(
                trip_id=self.trip_id,
                hotels=hotels_dict,
                metadata={
                    "destination": search_params["destination"],
                    "city_code": city_code,
                    "check_in_date": search_params["check_in_date"],
                    "check_out_date": search_params["check_out_date"],
                    "search_time": datetime.now().isoformat(),
                    "total_results": len(hotels),
                    "api_duration": api_duration
                }
            )
            
            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="HotelAgent",
                api_name="Amadeus",
                duration=api_duration
            )
            
            log_agent_raw(f"💾 Stored {len(hotels)} hotels in centralized storage", 
                         agent_name="HotelAgent")
            
            # Generate conversational recommendation
            recommendation = self._generate_recommendation(hotels, search_params)
            
            # Log outgoing
            self.log_conversation_message(
                message_type="OUTGOING",
                content=recommendation,
                sender="chat_manager",
                truncate=1000
            )
            
            return self.signal_completion(recommendation)
            
        except Exception as e:
            log_agent_raw(f"❌ Hotel search failed: {str(e)}", agent_name="HotelAgent")
            error_msg = f"I encountered an error searching for hotels: {str(e)}. Please try again."
            return self.signal_completion(error_msg)
    
    def _search_hotels_api(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        min_rating: float = 3.0  # ✅ Changed to float to match preferences
    ) -> List[Hotel]:
        """
        Call Amadeus API to search hotels
        """
        log_agent_raw(f"🔍 _search_hotels_api() called with:", agent_name="HotelAgent")
        log_agent_raw(f"   city_code: {city_code}", agent_name="HotelAgent")
        log_agent_raw(f"   check_in_date: {check_in_date}", agent_name="HotelAgent")
        log_agent_raw(f"   check_out_date: {check_out_date}", agent_name="HotelAgent")
        log_agent_raw(f"   adults: {adults} (type: {type(adults)})", agent_name="HotelAgent")
        log_agent_raw(f"   min_rating: {min_rating} (type: {type(min_rating)})", agent_name="HotelAgent")
        
        # Check if Amadeus is configured
        if not self.amadeus_service or not self.amadeus_service.client:
            log_agent_raw("⚠️ Amadeus not configured, using mock data", agent_name="HotelAgent")
            return self._generate_mock_hotels(city_code, check_in_date, check_out_date)
        
        # ✅ Convert min_rating to int for range() function
        min_rating_int = int(min_rating)
        log_agent_raw(f"   Converted min_rating {min_rating} → {min_rating_int}", agent_name="HotelAgent")
        
        # Build ratings filter (e.g., [3, 4, 5] for min_rating=3)
        ratings = [str(r) for r in range(min_rating_int, 6)]
        log_agent_raw(f"   Ratings filter: {ratings}", agent_name="HotelAgent")
        
        api_params = {
            "city_code": city_code,  # ✅ Fixed: cityCode → city_code
            "check_in_date": check_in_date,  # ✅ Fixed: checkInDate → check_in_date
            "check_out_date": check_out_date,  # ✅ Fixed: checkOutDate → check_out_date
            "adults": adults,
            "ratings": ratings,
            "radius": 20,
            "radius_unit": "KM"  # ✅ Fixed: radiusUnit → radius_unit
        }
        
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw("📡 Calling Amadeus Hotels API with parameters:", agent_name="HotelAgent")
        log_agent_json(api_params, label="Amadeus Hotel Request", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        
        # Call Amadeus API
        try:
            log_agent_raw("🌐 Calling self.amadeus_service.search_hotels()...", agent_name="HotelAgent")
            
            hotels_data = self.amadeus_service.search_hotels(**api_params)
            
            log_agent_raw(f"✅ Amadeus Hotels API SUCCESS - Received {len(hotels_data)} offers", 
                        agent_name="HotelAgent")
            
            # Parse into Hotel objects
            log_agent_raw(f"📋 Parsing {len(hotels_data)} hotel offers...", agent_name="HotelAgent")
            hotels = []
            for idx, hotel_dict in enumerate(hotels_data, 1):
                log_agent_raw(f"   Parsing hotel {idx}/{len(hotels_data)}: {hotel_dict.get('name', 'Unknown')}", 
                            agent_name="HotelAgent")
                hotel = self._parse_hotel_data(hotel_dict)
                if hotel:
                    hotels.append(hotel)
                    log_agent_raw(f"   ✓ Parsed successfully", agent_name="HotelAgent")
                else:
                    log_agent_raw(f"   ✗ Failed to parse", agent_name="HotelAgent")
            
            log_agent_raw(f"✅ Successfully parsed {len(hotels)}/{len(hotels_data)} hotels", 
                        agent_name="HotelAgent")
            
            return hotels
            
        except Exception as e:
            log_agent_raw("=" * 80, agent_name="HotelAgent")
            log_agent_raw(f"❌ Amadeus Hotels API FAILED", agent_name="HotelAgent")
            log_agent_raw(f"Error Type: {type(e).__name__}", agent_name="HotelAgent")
            log_agent_raw(f"Error Message: {str(e)}", agent_name="HotelAgent")
            
            # Import traceback for detailed error info
            import traceback
            log_agent_raw(f"Full Traceback:", agent_name="HotelAgent")
            log_agent_raw(traceback.format_exc(), agent_name="HotelAgent")
            
            log_agent_raw("=" * 80, agent_name="HotelAgent")
            
            # Fallback to mock data
            log_agent_raw("⚠️ Falling back to mock data", agent_name="HotelAgent")
            return self._generate_mock_hotels(city_code, check_in_date, check_out_date)
    
    def _parse_hotel_data(self, data: Dict) -> Optional[Hotel]:
        """Parse hotel data dict into Hotel object"""
        try:
            # Parse amenities
            amenities_dict = data.get("amenities", {})
            amenities = HotelAmenities(**amenities_dict) if amenities_dict else None
            
            return Hotel(
                id=data["id"],
                name=data["name"],
                hotel_code=data["hotel_code"],
                latitude=data["latitude"],
                longitude=data["longitude"],
                address=data["address"],
                city=data.get("city"),
                distance_from_center=data.get("distance_from_center"),
                rating=data.get("rating"),
                review_count=data.get("review_count"),
                price_per_night=data["price_per_night"],
                total_price=data["total_price"],
                currency=data["currency"],
                check_in_date=data["check_in_date"],
                check_out_date=data["check_out_date"],
                num_nights=data["num_nights"],
                room_type=data.get("room_type"),
                amenities=amenities,
                description=data.get("description"),
                photos=data.get("photos", []),
                property_type=data.get("property_type")
            )
        except Exception as e:
            log_agent_raw(f"⚠️ Failed to parse hotel: {str(e)}", agent_name="HotelAgent")
            return None
    
    def _generate_recommendation(
        self,
        hotels: List[Hotel],
        preferences: Dict[str, Any]
    ) -> str:
        """
        Use LLM to generate conversational recommendation
        """
        if not hotels:
            return "I couldn't find any hotels matching your criteria. Please adjust your preferences and try again."
        
        # Sort by value (rating / price ratio)
        hotels_sorted = sorted(hotels, key=lambda h: h.total_price)
        
        # Get key options
        cheapest = hotels_sorted[0]
        best_rated = max(hotels, key=lambda h: h.rating or 0)
        
        # Build prompt
        prompt = f"""
Based on the hotel search results, provide a helpful recommendation.

SEARCH RESULTS:
- Total hotels found: {len(hotels)}
- Price range: ${hotels_sorted[0].total_price:.2f} - ${hotels_sorted[-1].total_price:.2f} for {hotels_sorted[0].num_nights} nights
- Ratings: {min(h.rating or 0 for h in hotels):.1f} - {max(h.rating or 0 for h in hotels):.1f} stars

TOP OPTIONS:
1. Best Value: {cheapest.name} - ${cheapest.total_price:.2f} total ({cheapest.num_nights} nights @ ${cheapest.price_per_night:.2f}/night), {cheapest.rating or 'unrated'} stars
   Distance: {cheapest.distance_from_center or 'unknown'} km from center
   
2. Highest Rated: {best_rated.name} - ${best_rated.total_price:.2f} total, {best_rated.rating or 'unrated'} stars
   Distance: {best_rated.distance_from_center or 'unknown'} km from center

USER PREFERENCES:
- Budget per night: ${preferences.get('budget_per_night', 'Not specified')}
- Minimum rating: {preferences.get('min_rating', 3)} stars
- Required amenities: {', '.join(preferences.get('amenities', []))}

Provide a conversational recommendation (3-4 sentences):
- Mention how many options you reviewed
- Recommend your top pick with specific name and why
- Mention a budget alternative if relevant
- Highlight key amenities

Example: "I reviewed 15 hotels in London. My top recommendation is the Grand Plaza Hotel at $750 for 5 nights - it has a 4.5-star rating, great location just 2km from the city center, and includes wifi, pool, and breakfast. If you're looking to save, the City View Inn is only $600 and still offers excellent amenities."
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
                temperature=0.7,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="HotelAgent")
            # Fallback
            return f"I found {len(hotels)} hotels. My top pick is {cheapest.name} for ${cheapest.total_price:.2f} ({cheapest.num_nights} nights)."
    
    def _resolve_city_code(self, destination: str) -> Optional[str]:
        """Resolve destination to city IATA code"""
        # Simple mapping (extend as needed)
        city_map = {
            "london": "LON",
            "paris": "PAR",
            "new york": "NYC",
            "tokyo": "TYO",
            "dubai": "DXB",
            "singapore": "SIN",
            "hong kong": "HKG",
            "barcelona": "BCN",
            "rome": "ROM",
            "amsterdam": "AMS",
            "madrid": "MAD",
            "berlin": "BER",
            "sydney": "SYD",
            "melbourne": "MEL",
            "los angeles": "LAX",
            "san francisco": "SFO",
            "miami": "MIA",
            "las vegas": "LAS",
            "chicago": "CHI",
            "boston": "BOS"
        }
        
        dest_lower = destination.lower().strip()
        
        # Check if already a code
        if len(dest_lower) == 3 and dest_lower.isalpha():
            return dest_lower.upper()
        
        # Look up in map
        return city_map.get(dest_lower)
    
    def _hotel_to_dict(self, hotel: Hotel) -> Dict:
        """Convert Hotel object to dict for storage"""
        return hotel.model_dump(mode='json')
    
    def _generate_mock_hotels(
        self,
        city_code: str,
        check_in: str,
        check_out: str
    ) -> List[Hotel]:
        """Generate mock hotels when API is unavailable"""
        from datetime import datetime
        
        # Calculate nights
        check_in_dt = datetime.fromisoformat(check_in)
        check_out_dt = datetime.fromisoformat(check_out)
        num_nights = (check_out_dt - check_in_dt).days
        
        return [
            Hotel(
                id="HOTEL001",
                name="Grand Plaza Hotel",
                hotel_code="HOTEL001",
                latitude=51.5074,
                longitude=-0.1278,
                address="123 Main Street",
                city=city_code,
                distance_from_center=2.5,
                rating=4.5,
                price_per_night=150.0,
                total_price=150.0 * num_nights,
                currency="USD",
                check_in_date=check_in,
                check_out_date=check_out,
                num_nights=num_nights,
                room_type="Deluxe Room",
                amenities=HotelAmenities(
                    wifi=True,
                    parking=True,
                    pool=True,
                    gym=True,
                    restaurant=True,
                    room_service=True,
                    air_conditioning=True,
                    bar=True,
                    breakfast=True
                ),
                description="Luxury hotel in the heart of the city",
                property_type="HOTEL"
            ),
            Hotel(
                id="HOTEL002",
                name="City View Inn",
                hotel_code="HOTEL002",
                latitude=51.5074,
                longitude=-0.1278,
                address="456 Park Avenue",
                city=city_code,
                distance_from_center=1.2,
                rating=4.0,
                price_per_night=120.0,
                total_price=120.0 * num_nights,
                currency="USD",
                check_in_date=check_in,
                check_out_date=check_out,
                num_nights=num_nights,
                room_type="Standard Room",
                amenities=HotelAmenities(
                    wifi=True,
                    gym=True,
                    restaurant=True,
                    air_conditioning=True,
                    breakfast=True
                ),
                description="Modern hotel with city views",
                property_type="HOTEL"
            ),
            Hotel(
                id="HOTEL003",
                name="Budget Stay Suites",
                hotel_code="HOTEL003",
                latitude=51.5074,
                longitude=-0.1278,
                address="789 Budget Street",
                city=city_code,
                distance_from_center=5.0,
                rating=3.5,
                price_per_night=80.0,
                total_price=80.0 * num_nights,
                currency="USD",
                check_in_date=check_in,
                check_out_date=check_out,
                num_nights=num_nights,
                room_type="Economy Room",
                amenities=HotelAmenities(
                    wifi=True,
                    parking=True,
                    air_conditioning=True
                ),
                description="Affordable accommodation",
                property_type="HOTEL"
            )
        ]


def create_hotel_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> HotelAgent:
    """Factory function to create HotelAgent"""
    return HotelAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)