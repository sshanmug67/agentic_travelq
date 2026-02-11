"""
Hotel Agent - Complete Implementation
Google Places + Xotelo + Booking Links + Amadeus Fallback

Strategy:
1. Google Places → Hotel discovery (reviews, ratings, photos)
2. Xotelo → Real pricing (free API)
3. Estimation → Fallback when Xotelo unavailable
4. Amadeus → Backup option if Google fails
5. Booking Links → Direct users to OTAs

Location: backend/agents/hotel_agent.py
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.amadeus_service import get_amadeus_service
from services.google_places_service import get_google_places_service
from services.xotelo_service import get_xotelo_service
from utils.booking_links import BookingLinkGenerator
from models.trip import Hotel, HotelAmenities, HotelReview

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai


class HotelAgent(TravelQBaseAgent):
    """
    Hotel Agent with multiple API sources:
    - Google Places for discovery
    - Xotelo for real pricing
    - Amadeus as fallback
    - Booking links for conversion
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """
You are a helpful Hotel Search Assistant with access to real hotel data.

Your job:
1. Search hotels using Google Places (reviews, photos, ratings)
2. Get real pricing from Xotelo API
3. Provide booking links to major sites
4. Give personalized recommendations

Be friendly, concise, and helpful. Focus on value, not just price.
"""
        
        super().__init__(
            name="HotelAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="HotelAgent",
            system_message=system_message,
            description="Searches hotels with real pricing and booking links",
            **kwargs
        )
        
        # Storage
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        
        # API Services
        self.amadeus_service = get_amadeus_service()
        self.google_places = get_google_places_service()
        self.xotelo = get_xotelo_service()
        self.booking_links = BookingLinkGenerator()
        
        log_agent_raw("🏨 HotelAgent initialized (HYBRID MODE)", agent_name="HotelAgent")
        log_agent_raw("   ✓ Google Places service", agent_name="HotelAgent")
        log_agent_raw("   ✓ Xotelo pricing service", agent_name="HotelAgent")
        log_agent_raw("   ✓ Amadeus fallback", agent_name="HotelAgent")
        log_agent_raw("   ✓ Booking link generator", agent_name="HotelAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """Generate reply with complete hotel search"""
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
        
        # Get preferences
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="HotelAgent")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences for trip {self.trip_id}", agent_name="HotelAgent")
        
        # Build search parameters
        search_params = {
            "destination": preferences.destination,
            "check_in_date": preferences.departure_date,
            "check_out_date": preferences.return_date,
            "num_travelers": preferences.num_travelers,
            "min_rating": preferences.hotel_prefs.min_rating,
            "budget_per_night": preferences.budget.hotel_budget_per_night,
            "amenities": preferences.hotel_prefs.amenities
        }
        
        log_agent_json(search_params, label="Search Parameters", agent_name="HotelAgent")
        
        try:
            start_time = time.time()
            
            # Search hotels with complete workflow
            hotels = self._search_hotels_complete(
                destination=search_params["destination"],
                check_in_date=search_params["check_in_date"],
                check_out_date=search_params["check_out_date"],
                adults=search_params["num_travelers"],
                min_rating=search_params["min_rating"]
            )
            
            api_duration = time.time() - start_time
            
            log_agent_raw(f"✅ Search complete: {len(hotels)} hotels in {api_duration:.2f}s", 
                         agent_name="HotelAgent")
            
            if not hotels:
                return self.signal_completion(
                    "I couldn't find any hotels matching your criteria. "
                    "Try adjusting your dates or location."
                )
            
            # Store ALL options
            hotels_dict = [self._hotel_to_dict(h) for h in hotels]
            
            self.trip_storage.add_hotels(
                trip_id=self.trip_id,
                hotels=hotels_dict,
                metadata={
                    "destination": search_params["destination"],
                    "check_in_date": search_params["check_in_date"],
                    "check_out_date": search_params["check_out_date"],
                    "search_time": datetime.now().isoformat(),
                    "total_results": len(hotels),
                    "api_duration": api_duration,
                    "sources": ["google_places", "xotelo", "booking_links"]
                }
            )
            
            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="HotelAgent",
                api_name="GooglePlaces+Xotelo",
                duration=api_duration
            )
            
            log_agent_raw(f"💾 Stored {len(hotels)} hotels in storage", agent_name="HotelAgent")
            
            # Generate recommendation
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
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="HotelAgent")
            error_msg = f"I encountered an error: {str(e)}. Please try again."
            return self.signal_completion(error_msg)
    
    def _search_hotels_complete(
        self,
        destination: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        min_rating: float = 3.0,
        max_results: int = 20
    ) -> List[Hotel]:
        """
        Complete hotel search workflow
        
        1. Google Places → Hotel discovery (preferred)
        2. Xotelo → Real pricing
        3. Estimation → Fallback
        4. Amadeus → Backup if Google fails
        5. Booking Links → All hotels
        """
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw("🔍 COMPLETE HOTEL SEARCH WORKFLOW", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        
        # Calculate nights
        check_in_dt = datetime.fromisoformat(check_in_date)
        check_out_dt = datetime.fromisoformat(check_out_date)
        num_nights = (check_out_dt - check_in_dt).days
        
        log_agent_raw(f"📋 Search Parameters:", agent_name="HotelAgent")
        log_agent_raw(f"   Destination: {destination}", agent_name="HotelAgent")
        log_agent_raw(f"   Check-in: {check_in_date}", agent_name="HotelAgent")
        log_agent_raw(f"   Check-out: {check_out_date}", agent_name="HotelAgent")
        log_agent_raw(f"   Nights: {num_nights}", agent_name="HotelAgent")
        log_agent_raw(f"   Adults: {adults}", agent_name="HotelAgent")
        log_agent_raw(f"   Min Rating: {min_rating}", agent_name="HotelAgent")
        
        # STRATEGY 1: Try Google Places (preferred)
        log_agent_raw("", agent_name="HotelAgent")
        log_agent_raw("📍 STRATEGY 1: Google Places Search", agent_name="HotelAgent")
        log_agent_raw("-" * 80, agent_name="HotelAgent")
        
        if self.google_places and self.google_places.client:
            google_hotels = self.google_places.search_hotels(
                location=destination,
                radius=5000,  # 5km radius
                min_rating=min_rating,
                agent_logger=self.logger
            )
            
            if google_hotels:
                log_agent_raw(f"✅ Google Places: Found {len(google_hotels)} hotels", 
                            agent_name="HotelAgent")
                
                # Limit to max_results
                google_hotels = google_hotels[:max_results]
                
                # Enrich with pricing and links
                enriched_hotels = self._enrich_hotels_with_pricing(
                    google_hotels=google_hotels,
                    destination=destination,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    num_nights=num_nights,
                    adults=adults
                )
                
                if enriched_hotels:
                    return enriched_hotels
        else:
            log_agent_raw("⚠️ Google Places not available", agent_name="HotelAgent")
        
        # STRATEGY 2: Try Amadeus (fallback)
        log_agent_raw("", agent_name="HotelAgent")
        log_agent_raw("📍 STRATEGY 2: Amadeus Search (Fallback)", agent_name="HotelAgent")
        log_agent_raw("-" * 80, agent_name="HotelAgent")
        
        if self.amadeus_service and self.amadeus_service.client:
            # Resolve city code
            city_code = self._resolve_city_code(destination)
            
            if city_code:
                log_agent_raw(f"✓ Resolved: {destination} → {city_code}", 
                            agent_name="HotelAgent")
                
                try:
                    min_rating_int = int(min_rating)
                    ratings = [str(r) for r in range(min_rating_int, 6)]
                    
                    hotels_data = self.amadeus_service.search_hotels(
                        city_code=city_code,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        adults=adults,
                        ratings=ratings,
                        radius=20,
                        radius_unit="KM",
                        agent_logger=self.logger
                    )
                    
                    if hotels_data:
                        log_agent_raw(f"✅ Amadeus returned {len(hotels_data)} hotels", 
                                    agent_name="HotelAgent")
                        
                        hotels = []
                        for hotel_dict in hotels_data:
                            hotel = self._parse_hotel_data(hotel_dict)
                            if hotel:
                                hotels.append(hotel)
                        
                        if hotels:
                            return hotels
                except Exception as e:
                    log_agent_raw(f"❌ Amadeus failed: {str(e)}", agent_name="HotelAgent")
        
        # STRATEGY 3: Mock data (last resort)
        log_agent_raw("", agent_name="HotelAgent")
        log_agent_raw("📍 STRATEGY 3: Mock Data (Last Resort)", agent_name="HotelAgent")
        log_agent_raw("⚠️ All APIs failed, using mock data", agent_name="HotelAgent")
        return self._generate_mock_hotels(destination, check_in_date, check_out_date)
    
    def _enrich_hotels_with_pricing(
        self,
        google_hotels: List[Dict],
        destination: str,
        check_in_date: str,
        check_out_date: str,
        num_nights: int,
        adults: int
    ) -> List[Hotel]:
        """Enrich Google Places hotels with pricing and booking links"""
        
        log_agent_raw("", agent_name="HotelAgent")
        log_agent_raw("💰 Enriching with Xotelo Pricing & Booking Links", agent_name="HotelAgent")
        log_agent_raw("-" * 80, agent_name="HotelAgent")
        
        enriched_hotels = []
        xotelo_success_count = 0
        
        for idx, google_hotel in enumerate(google_hotels, 1):
            hotel_name = google_hotel.get('name', 'Unknown')
            log_agent_raw(f"", agent_name="HotelAgent")
            log_agent_raw(f"🏨 Hotel {idx}/{len(google_hotels)}: {hotel_name}", 
                        agent_name="HotelAgent")
            
            # Try Xotelo pricing
            pricing = None
            if self.xotelo:
                try:
                    pricing = self.xotelo.get_price_for_hotel(
                        hotel_name=hotel_name,
                        location=destination,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        agent_logger=self.logger
                    )
                    
                    if pricing:
                        xotelo_success_count += 1
                        log_agent_raw(f"   ✓ Xotelo: ${pricing['total_price']:.2f} total "
                                    f"(${pricing['price_per_night']:.2f}/night) "
                                    f"via {pricing.get('cheapest_provider', 'N/A')}", 
                                    agent_name="HotelAgent")
                    else:
                        log_agent_raw(f"   ⚠️ Xotelo: No pricing found", agent_name="HotelAgent")
                except Exception as e:
                    log_agent_raw(f"   ⚠️ Xotelo error: {str(e)}", agent_name="HotelAgent")
            
            # Fallback to estimation
            if not pricing:
                pricing = self._estimate_price(
                    google_hotel.get('price_level', 2),
                    google_hotel.get('google_rating', 3.5),
                    num_nights
                )
                log_agent_raw(f"   ✓ Estimated: ${pricing['total_price']:.2f} total "
                            f"(${pricing['price_per_night']:.2f}/night)", 
                            agent_name="HotelAgent")
            
            # Generate booking links
            booking_links = self.booking_links.generate_all_links(
                hotel_name=hotel_name,
                city=destination,
                check_in=check_in_date,
                check_out=check_out_date,
                adults=adults,
                latitude=google_hotel.get('latitude'),
                longitude=google_hotel.get('longitude')
            )
            
            log_agent_raw(f"   ✓ Generated {len(booking_links)} booking links", 
                        agent_name="HotelAgent")
            
            # Create hotel object
            hotel = self._create_hotel_from_google(
                google_data=google_hotel,
                pricing=pricing,
                booking_links=booking_links,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                num_nights=num_nights
            )
            
            enriched_hotels.append(hotel)
        
        # Summary
        log_agent_raw("", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw("📊 ENRICHMENT SUMMARY", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw(f"   Total hotels: {len(enriched_hotels)}", agent_name="HotelAgent")
        log_agent_raw(f"   Xotelo pricing: {xotelo_success_count} hotels", agent_name="HotelAgent")
        log_agent_raw(f"   Estimated pricing: {len(enriched_hotels) - xotelo_success_count} hotels", 
                    agent_name="HotelAgent")
        log_agent_raw(f"   Success rate: {(xotelo_success_count/len(enriched_hotels)*100):.1f}%", 
                    agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        
        return enriched_hotels
    
    def _estimate_price(
        self,
        price_level: int,
        rating: float,
        num_nights: int
    ) -> Dict[str, Any]:
        """
        Estimate price from Google price_level + rating
        
        Price level scale:
        0 = Free
        1 = Inexpensive ($50-100/night)
        2 = Moderate ($100-200/night)
        3 = Expensive ($200-350/night)
        4 = Very Expensive ($350+/night)
        """
        base_prices = {
            0: 50,
            1: 85,
            2: 150,
            3: 275,
            4: 450
        }
        
        base_price = base_prices.get(price_level, 150)
        
        # Adjust by rating
        if rating >= 4.7:
            multiplier = 1.4
        elif rating >= 4.5:
            multiplier = 1.3
        elif rating >= 4.0:
            multiplier = 1.15
        elif rating >= 3.5:
            multiplier = 1.0
        else:
            multiplier = 0.85
        
        price_per_night = base_price * multiplier
        total_price = price_per_night * num_nights
        
        return {
            'price_per_night': round(price_per_night, 2),
            'total_price': round(total_price, 2),
            'currency': 'USD',
            'num_nights': num_nights,
            'is_estimated': True,
            'price_source': 'estimated_from_google_price_level'
        }
    
    def _create_hotel_from_google(
        self,
        google_data: Dict,
        pricing: Dict,
        booking_links: Dict,
        check_in_date: str,
        check_out_date: str,
        num_nights: int
    ) -> Hotel:
        """Create Hotel object from Google Places + pricing + links"""
        
        # Parse reviews
        reviews = []
        if google_data.get('reviews'):
            for review_dict in google_data['reviews'][:5]:
                try:
                    reviews.append(HotelReview(**review_dict))
                except:
                    continue
        
        return Hotel(
            id=google_data.get('place_id', str(time.time())),
            name=google_data.get('name', 'Unknown Hotel'),
            hotel_code=google_data.get('place_id', ''),
            
            # Location
            latitude=google_data.get('latitude', 0.0),
            longitude=google_data.get('longitude', 0.0),
            address=google_data.get('address', ''),
            
            # Google Places ratings
            place_id=google_data.get('place_id'),
            google_rating=google_data.get('google_rating'),
            user_ratings_total=google_data.get('user_ratings_total'),
            reviews=reviews,
            
            # Pricing
            price_per_night=pricing['price_per_night'],
            total_price=pricing['total_price'],
            currency=pricing['currency'],
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            num_nights=num_nights,
            
            # Details
            photos=google_data.get('photos', []),
            website=google_data.get('website'),
            phone_number=google_data.get('phone_number'),
            google_url=google_data.get('google_url'),
            business_status=google_data.get('business_status'),
            
            # Booking links
            booking_url=booking_links.get('booking_com', {}).get('url'),
            description=f"Price source: {pricing['price_source']}"
        )
    
    def _parse_hotel_data(self, data: Dict) -> Optional[Hotel]:
        """Parse Amadeus hotel data into Hotel object"""
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
    
    def _hotel_to_dict(self, hotel: Hotel) -> Dict:
        """Convert Hotel to dict for storage"""
        return hotel.model_dump(mode='json')
    
    def _generate_recommendation(
        self,
        hotels: List[Hotel],
        preferences: Dict[str, Any]
    ) -> str:
        """Generate LLM recommendation"""
        
        if not hotels:
            return "No hotels found matching your criteria."
        
        # Sort by total price
        hotels_sorted = sorted(hotels, key=lambda h: h.total_price)
        
        # Get top options
        cheapest = hotels_sorted[0]
        best_rated = max(hotels, key=lambda h: h.google_rating or h.rating or 0)
        
        # Build prompt
        prompt = f"""
Based on hotel search results, provide a helpful recommendation.

SEARCH RESULTS:
- Total hotels: {len(hotels)}
- Price range: ${hotels_sorted[0].total_price:.2f} - ${hotels_sorted[-1].total_price:.2f} ({cheapest.num_nights} nights)
- Rating range: {min(h.google_rating or h.rating or 0 for h in hotels):.1f} - {max(h.google_rating or h.rating or 0 for h in hotels):.1f} stars

TOP OPTIONS:
1. Best Value: {cheapest.name}
   - Price: ${cheapest.total_price:.2f} ({cheapest.num_nights} nights @ ${cheapest.price_per_night:.2f}/night)
   - Rating: {cheapest.google_rating or cheapest.rating or 'N/A'} stars
   - Reviews: {cheapest.user_ratings_total or cheapest.review_count or 0} reviews

2. Highest Rated: {best_rated.name}
   - Price: ${best_rated.total_price:.2f}
   - Rating: {best_rated.google_rating or best_rated.rating or 'N/A'} stars
   - Reviews: {best_rated.user_ratings_total or best_rated.review_count or 0} reviews

USER PREFERENCES:
- Budget per night: ${preferences.get('budget_per_night', 'Not specified')}
- Minimum rating: {preferences.get('min_rating', 3)} stars

Provide a conversational recommendation (3-4 sentences):
- Mention you reviewed all {len(hotels)} options
- Recommend your top pick with specific name and why
- Mention the number of reviews
- Note that users can check current prices on Booking.com, Expedia, etc.

Keep it natural and friendly.
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
            return (f"I reviewed {len(hotels)} hotels. My top recommendation is {cheapest.name} "
                   f"at ${cheapest.total_price:.2f} for {cheapest.num_nights} nights "
                   f"({cheapest.google_rating or cheapest.rating or 'unrated'} stars with "
                   f"{cheapest.user_ratings_total or cheapest.review_count or 0} reviews). "
                   f"You can check current prices on Booking.com, Expedia, and other sites.")
    
    def _resolve_city_code(self, destination: str) -> Optional[str]:
        """Resolve destination to city IATA code for Amadeus"""
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
        for city, code in city_map.items():
            if city in dest_lower:
                return code
        
        return None
    
    def _generate_mock_hotels(
        self,
        destination: str,
        check_in: str,
        check_out: str
    ) -> List[Hotel]:
        """Generate mock hotels when all APIs fail"""
        from datetime import datetime
        
        # Calculate nights
        check_in_dt = datetime.fromisoformat(check_in)
        check_out_dt = datetime.fromisoformat(check_out)
        num_nights = (check_out_dt - check_in_dt).days
        
        log_agent_raw("📝 Generating mock hotel data", agent_name="HotelAgent")
        
        return [
            Hotel(
                id="MOCK001",
                name="Grand Plaza Hotel",
                hotel_code="MOCK001",
                latitude=51.5074,
                longitude=-0.1278,
                address="123 Main Street",
                city=destination,
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
                description="Mock data - Luxury hotel",
                property_type="HOTEL"
            ),
            Hotel(
                id="MOCK002",
                name="City View Inn",
                hotel_code="MOCK002",
                latitude=51.5074,
                longitude=-0.1278,
                address="456 Park Avenue",
                city=destination,
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
                description="Mock data - Modern hotel",
                property_type="HOTEL"
            ),
            Hotel(
                id="MOCK003",
                name="Budget Stay Suites",
                hotel_code="MOCK003",
                latitude=51.5074,
                longitude=-0.1278,
                address="789 Budget Street",
                city=destination,
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
                description="Mock data - Affordable accommodation",
                property_type="HOTEL"
            )
        ]


def create_hotel_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> HotelAgent:
    """Factory function to create HotelAgent"""
    return HotelAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)