"""
Hotel Agent - Complete Implementation
Google Places + Xotelo + Booking Links + Amadeus Fallback

Strategy:
1. Google Places → Hotel discovery (reviews, ratings, photos)
2. Xotelo → Real pricing (free API)
3. Estimation → Fallback when Xotelo unavailable
4. Amadeus → Backup option if Google fails
5. Booking Links → Direct users to OTAs

Changes (v2):
  - Removed plain-text recommendation
  - LLM now picks the recommended hotel ID based on full user preferences
  - LLM returns structured JSON: { recommended_id, reason, summary }
  - Summary is the conversational message; recommended_id gets stored
  - store_recommendation() called so frontend can read recommendations.hotel

Changes (v3):
  - Fixed: max_results now flows from settings.hotel_agent_max_results
  - Fixed: reviews-per-hotel limit decoupled from hotel max_results
  - Fixed: generate_reply passes max_results to _search_hotels_complete

Location: backend/agents/hotel_agent.py
"""
import json
import re
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

# Maximum number of reviews to store per hotel (independent of hotel max_results)
MAX_REVIEWS_PER_HOTEL = 5


class HotelAgent(TravelQBaseAgent):
    """
    Hotel Agent with multiple API sources:
    - Google Places for discovery
    - Xotelo for real pricing
    - Amadeus as fallback
    - Booking links for conversion
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """You are a Hotel Search Assistant that recommends hotels based on user preferences.

You will be given:
1. A list of available hotels with IDs, prices, ratings, reviews, and locations
2. The user's preferences (budget, minimum rating, amenities, trip purpose, etc.)

Your job is to pick the BEST hotel for this specific user and explain why.

You MUST respond with valid JSON only — no markdown, no backticks, no extra text.
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
        log_agent_raw(f"   ✓ Max results: {settings.hotel_agent_max_results}", agent_name="HotelAgent")
    
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
            
            # FIX: Pass max_results from settings instead of relying on hardcoded default
            hotels = self._search_hotels_complete(
                destination=search_params["destination"],
                check_in_date=search_params["check_in_date"],
                check_out_date=search_params["check_out_date"],
                adults=search_params["num_travelers"],
                min_rating=search_params["min_rating"],
                max_results=settings.hotel_agent_max_results
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
            
            # LLM picks the best hotel and explains why
            recommendation = self._generate_recommendation(hotels, preferences)
            
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
    
    # ─────────────────────────────────────────────────────────────────────
    # HOTEL SEARCH WORKFLOW
    # ─────────────────────────────────────────────────────────────────────

    def _search_hotels_complete(
        self,
        destination: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        min_rating: float = 3.0,
        max_results: int = 10
    ) -> List[Hotel]:
        """
        Complete hotel search workflow
        
        1. Google Places → Hotel discovery (preferred)
        2. Xotelo → Real pricing
        3. Estimation → Fallback
        4. Amadeus → Backup if Google fails
        5. Booking Links → All hotels
        
        Args:
            max_results: Maximum number of hotels to return. 
                         Driven by settings.hotel_agent_max_results (default 10).
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
        log_agent_raw(f"   Max Results: {max_results}", agent_name="HotelAgent")
        
        # STRATEGY 1: Try Google Places (preferred)
        log_agent_raw("", agent_name="HotelAgent")
        log_agent_raw("📍 STRATEGY 1: Google Places Search", agent_name="HotelAgent")
        log_agent_raw("-" * 80, agent_name="HotelAgent")
        
        if self.google_places and self.google_places.client:
            google_hotels = self.google_places.search_hotels(
                location=destination,
                radius=5000,
                min_rating=min_rating,
                agent_logger=self.logger
            )
            
            if google_hotels:
                log_agent_raw(f"✅ Google Places: Found {len(google_hotels)} hotels", 
                            agent_name="HotelAgent")
                
                google_hotels = google_hotels[:max_results]
                
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
                        max_results=max_results,
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

        # FIX: Use dedicated constant for review limit (was incorrectly using hotel_agent_max_results)
        reviews = []
        if google_data.get('reviews'):
            for review_dict in google_data['reviews'][:MAX_REVIEWS_PER_HOTEL]:
                try:
                    reviews.append(HotelReview(**review_dict))
                except:
                    continue
        
        return Hotel(
            id=google_data.get('place_id', str(time.time())),
            name=google_data.get('name', 'Unknown Hotel'),
            hotel_code=google_data.get('place_id', ''),
            latitude=google_data.get('latitude', 0.0),
            longitude=google_data.get('longitude', 0.0),
            address=google_data.get('address', ''),
            place_id=google_data.get('place_id'),
            google_rating=google_data.get('google_rating'),
            user_ratings_total=google_data.get('user_ratings_total'),
            reviews=reviews,
            price_per_night=pricing['price_per_night'],
            total_price=pricing['total_price'],
            currency=pricing['currency'],
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            num_nights=num_nights,
            photos=google_data.get('photos', []),
            website=google_data.get('website'),
            phone_number=google_data.get('phone_number'),
            google_url=google_data.get('google_url'),
            business_status=google_data.get('business_status'),
            booking_url=booking_links.get('booking_com', {}).get('url'),
            description=f"Price source: {pricing['price_source']}"
        )
    
    def _parse_hotel_data(self, data: Dict) -> Optional[Hotel]:
        """Parse Amadeus hotel data into Hotel object"""
        try:
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

    # ─────────────────────────────────────────────────────────────────────
    # LLM-DRIVEN RECOMMENDATION
    # ─────────────────────────────────────────────────────────────────────

    def _build_hotels_table(self, hotels: List[Hotel]) -> str:
        """
        Build a compact text table of all hotels for the LLM prompt.
        Each row has the hotel ID so the LLM can reference it.
        """
        rows = []
        for h in hotels:
            rating = h.google_rating or h.rating or 0
            reviews = h.user_ratings_total or h.review_count or 0
            rows.append(
                f"ID: {h.id} | {h.name} | "
                f"${h.total_price:.2f} total (${h.price_per_night:.2f}/night, {h.num_nights} nights) | "
                f"Rating: {rating}★ ({reviews} reviews) | "
                f"Address: {h.address or 'N/A'}"
            )
        return "\n".join(rows)

    def _build_preferences_summary(self, preferences: Any) -> str:
        """
        Build a readable summary of user preferences for the LLM.
        Includes ALL hotel-relevant fields from the preferences object.
        """
        lines = []
        lines.append(f"Hotel budget per night: ${preferences.budget.hotel_budget_per_night}")
        lines.append(f"Minimum rating: {preferences.hotel_prefs.min_rating} stars")
        
        if hasattr(preferences.hotel_prefs, 'amenities') and preferences.hotel_prefs.amenities:
            lines.append(f"Preferred amenities: {', '.join(preferences.hotel_prefs.amenities)}")
        
        if hasattr(preferences.hotel_prefs, 'preferred_location') and preferences.hotel_prefs.preferred_location:
            loc = preferences.hotel_prefs.preferred_location.replace('_', ' ')
            lines.append(f"Preferred location: {loc}")
        
        if hasattr(preferences.hotel_prefs, 'room_type') and preferences.hotel_prefs.room_type:
            lines.append(f"Room type: {preferences.hotel_prefs.room_type}")
        
        if hasattr(preferences.hotel_prefs, 'price_range') and preferences.hotel_prefs.price_range:
            lines.append(f"Price range: {preferences.hotel_prefs.price_range}")
        
        if hasattr(preferences.hotel_prefs, 'preferred_chains') and preferences.hotel_prefs.preferred_chains:
            lines.append(f"Preferred chains: {', '.join(preferences.hotel_prefs.preferred_chains)}")
        
        lines.append(f"Trip purpose: {preferences.trip_purpose}")
        lines.append(f"Travelers: {preferences.num_travelers}")
        lines.append(f"Destination: {preferences.destination}")
        
        return "\n".join(lines)

    def _parse_llm_json(self, text: str) -> Optional[Dict]:
        """
        Safely parse JSON from LLM response.
        Strips markdown fences and handles common LLM formatting issues.
        """
        # Strip markdown code fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        
        return None

    def _generate_recommendation(
        self,
        hotels: List[Hotel],
        preferences: Any
    ) -> str:
        """
        LLM picks the best hotel based on user preferences.

        Returns the conversational summary. The recommended_id is stored
        in centralized storage for the frontend to consume.
        """
        if not hotels:
            return "I couldn't find any hotels matching your criteria."

        # Build the prompt
        hotels_table = self._build_hotels_table(hotels)
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(h.id) for h in hotels]

        prompt = f"""Here are the available hotels:

{hotels_table}

User preferences:
{prefs_summary}

Pick the single best hotel for this user. Consider their budget per night, minimum rating
requirements, preferred amenities, preferred location (e.g. city center vs quiet area),
room type preference, price range expectation, trip purpose, and number of travelers.
Weigh the tradeoffs — a slightly more expensive hotel with excellent reviews and a central
location may be better than the cheapest option with poor ratings, especially for a leisure
trip. A business traveler may value wifi and location over pool access.

You MUST respond with ONLY a JSON object in this exact format, nothing else:
{{
  "recommended_id": "<the hotel ID from the list above>",
  "reason": "<1-2 sentences explaining why this is the best match for this user's preferences>",
  "summary": "<3-4 sentence friendly recommendation mentioning how many options you reviewed, why you picked this one, and any notable alternatives>"
}}

CRITICAL RULES:
- recommended_id MUST be one of these exact values: {valid_ids}
- Do NOT invent a hotel ID. Pick from the list above.
- Respond with valid JSON only. No markdown, no backticks, no extra text.
"""

        log_agent_raw("🤖 Asking LLM to pick best hotel based on preferences...",
                     agent_name="HotelAgent")

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)

            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400
            )

            raw_response = response.choices[0].message.content.strip()

            log_agent_raw(f"📥 LLM raw response: {raw_response}", agent_name="HotelAgent")

            # Parse the JSON
            result = self._parse_llm_json(raw_response)

            if not result:
                log_agent_raw("⚠️ Failed to parse LLM JSON, using fallback", agent_name="HotelAgent")
                return self._fallback_recommendation(hotels, preferences)

            recommended_id = str(result.get("recommended_id", ""))
            reason = result.get("reason", "Best overall match")
            summary = result.get("summary", "")

            # Validate the ID exists in our hotel list
            if recommended_id not in valid_ids:
                log_agent_raw(
                    f"⚠️ LLM returned invalid ID '{recommended_id}', "
                    f"valid IDs are {valid_ids}. Using fallback.",
                    agent_name="HotelAgent"
                )
                return self._fallback_recommendation(hotels, preferences)

            # Find the matching hotel for metadata
            recommended_hotel = next(h for h in hotels if str(h.id) == recommended_id)

            # ✅ Store the recommendation in centralized storage
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="hotel",
                recommended_id=recommended_id,
                reason=reason,
                metadata={
                    "name": recommended_hotel.name,
                    "total_price": recommended_hotel.total_price,
                    "price_per_night": recommended_hotel.price_per_night,
                    "rating": recommended_hotel.google_rating or recommended_hotel.rating,
                    "reviews": recommended_hotel.user_ratings_total or recommended_hotel.review_count or 0,
                    "total_options_reviewed": len(hotels)
                }
            )

            log_agent_raw(
                f"⭐ LLM picked hotel {recommended_id} "
                f"({recommended_hotel.name} ${recommended_hotel.total_price:.2f}): {reason}",
                agent_name="HotelAgent"
            )

            return summary if summary else (
                f"I recommend {recommended_hotel.name} at "
                f"${recommended_hotel.total_price:.2f} for {recommended_hotel.num_nights} nights. "
                f"{reason}"
            )

        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="HotelAgent")
            return self._fallback_recommendation(hotels, preferences)

    def _fallback_recommendation(self, hotels: List[Hotel], preferences: Any) -> str:
        """
        Fallback when LLM fails: pick best-rated hotel within budget, store it, return template.
        This is the safety net — not the primary path.
        """
        budget = getattr(preferences.budget, 'hotel_budget_per_night', None)

        # Filter by budget if available, else use all
        if budget and budget > 0:
            within_budget = [h for h in hotels if h.price_per_night <= budget * 1.1]
            candidates = within_budget if within_budget else hotels
        else:
            candidates = hotels

        # Pick highest rated among candidates
        best = max(
            candidates,
            key=lambda h: (h.google_rating or h.rating or 0)
        )

        self.trip_storage.store_recommendation(
            trip_id=self.trip_id,
            category="hotel",
            recommended_id=str(best.id),
            reason="Fallback: highest rated within budget (LLM recommendation unavailable)",
            metadata={
                "name": best.name,
                "total_price": best.total_price,
                "price_per_night": best.price_per_night,
                "rating": best.google_rating or best.rating,
                "reviews": best.user_ratings_total or best.review_count or 0,
                "total_options_reviewed": len(hotels),
                "is_fallback": True
            }
        )

        log_agent_raw(
            f"⭐ Fallback pick: hotel {best.id} "
            f"({best.name} ${best.total_price:.2f}, "
            f"{best.google_rating or best.rating or 'N/A'}★)",
            agent_name="HotelAgent"
        )

        rating_str = f"{best.google_rating or best.rating or 'unrated'}★"
        reviews_count = best.user_ratings_total or best.review_count or 0

        return (
            f"I reviewed {len(hotels)} hotels for your trip. "
            f"My top recommendation is {best.name} at "
            f"${best.total_price:.2f} for {best.num_nights} nights "
            f"({rating_str} with {reviews_count} reviews). "
            f"You can check current prices on Booking.com, Expedia, and other sites."
        )

    # ─────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ─────────────────────────────────────────────────────────────────────

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
        
        if len(dest_lower) == 3 and dest_lower.isalpha():
            return dest_lower.upper()
        
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
                    wifi=True, parking=True, pool=True, gym=True,
                    restaurant=True, room_service=True,
                    air_conditioning=True, bar=True, breakfast=True
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
                    wifi=True, gym=True, restaurant=True,
                    air_conditioning=True, breakfast=True
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
                    wifi=True, parking=True, air_conditioning=True
                ),
                description="Mock data - Affordable accommodation",
                property_type="HOTEL"
            )
        ]


def create_hotel_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> HotelAgent:
    """Factory function to create HotelAgent"""
    return HotelAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)