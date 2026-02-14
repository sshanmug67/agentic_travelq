"""
Hotel Agent - Complete Implementation
Google Places + Xotelo + Booking Links + Amadeus Fallback

Changes (v5):
  - _create_hotel_from_google: now stores reviews, website, phone_number,
    google_url, price_level, property_type, all booking_links, cheapest_provider,
    is_estimated_price — data that Google Places returns but was previously discarded
  - _enrich_hotels_with_pricing: passes pricing metadata + all booking links through

Changes (v4):
  - Fixed: ALL user preferences now flow into hotel search
  - budget_per_night → post-fetch filtering (soft: 1.2x tolerance)
  - preferred_chains → targeted Google Places text searches
  - preferred_location → adjusts search radius
  - amenities → passed to LLM for recommendation weighting
  - room_type, price_range → passed to LLM for recommendation

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

# Budget tolerance: include hotels up to 20% over stated budget
BUDGET_TOLERANCE = 1.2


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
        
        # Build search parameters — ALL preferences extracted
        search_params = {
            "destination": preferences.destination,
            "check_in_date": preferences.departure_date,
            "check_out_date": preferences.return_date,
            "num_travelers": preferences.num_travelers,
            "min_rating": preferences.hotel_prefs.min_rating,
            "budget_per_night": preferences.budget.hotel_budget_per_night,
            "amenities": preferences.hotel_prefs.amenities or [],
            "preferred_location": getattr(preferences.hotel_prefs, 'preferred_location', None),
            "room_type": getattr(preferences.hotel_prefs, 'room_type', None),
            "price_range": getattr(preferences.hotel_prefs, 'price_range', None),
            "preferred_chains": getattr(preferences.hotel_prefs, 'preferred_chains', []) or [],
        }
        
        log_agent_json(search_params, label="Search Parameters (full)", agent_name="HotelAgent")
        
        # Explicit log: which preferences are used WHERE
        log_agent_raw("📋 Preferences → Search Strategy:", agent_name="HotelAgent")
        log_agent_raw(f"   preferred_chains    → Google Text Search (targeted chain queries)", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['preferred_chains'] or 'None → skip chain search'}", agent_name="HotelAgent")
        log_agent_raw(f"   preferred_location  → Search radius adjustment", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['preferred_location'] or 'Any → default 5km'}", agent_name="HotelAgent")
        log_agent_raw(f"   budget_per_night    → Post-search budget filter (1.2x tolerance)", agent_name="HotelAgent")
        log_agent_raw(f"     Value: ${search_params['budget_per_night']}/night" if search_params['budget_per_night'] else "     Value: No limit", agent_name="HotelAgent")
        log_agent_raw(f"   min_rating          → Google API min_rating filter", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['min_rating']} stars", agent_name="HotelAgent")
        log_agent_raw(f"   amenities           → LLM recommendation weighting", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['amenities'] or 'None'}", agent_name="HotelAgent")
        log_agent_raw(f"   room_type           → LLM recommendation weighting", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['room_type'] or 'Any'}", agent_name="HotelAgent")
        log_agent_raw(f"   price_range         → LLM recommendation weighting", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['price_range'] or 'Any'}", agent_name="HotelAgent")
        
        try:
            start_time = time.time()
            
            # Search hotels
            hotels = self._search_hotels_complete(
                destination=search_params["destination"],
                check_in_date=search_params["check_in_date"],
                check_out_date=search_params["check_out_date"],
                adults=search_params["num_travelers"],
                min_rating=search_params["min_rating"],
                max_results=settings.hotel_agent_max_results,
                budget_per_night=search_params["budget_per_night"],
                preferred_chains=search_params["preferred_chains"],
                preferred_location=search_params["preferred_location"],
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
                    "sources": ["google_places", "xotelo", "booking_links"],
                    "preferred_chains": search_params["preferred_chains"],
                    "preferred_location": search_params["preferred_location"],
                    "budget_per_night": search_params["budget_per_night"],
                }
            )
            
            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="HotelAgent",
                api_name="GooglePlaces+Xotelo",
                duration=api_duration
            )
            
            log_agent_raw(f"💾 Stored {len(hotels)} hotels in storage", agent_name="HotelAgent")
            
            # LLM picks the best hotel
            recommendation = self._generate_recommendation(hotels, preferences)
            
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
        max_results: int = 10,
        budget_per_night: float = 0,
        preferred_chains: List[str] = None,
        preferred_location: str = None,
    ) -> List[Hotel]:
        """Complete hotel search workflow with preference-aware discovery."""
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw("🔍 COMPLETE HOTEL SEARCH WORKFLOW (preference-aware)", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        
        preferred_chains = preferred_chains or []
        
        # Calculate nights
        check_in_dt = datetime.fromisoformat(check_in_date)
        check_out_dt = datetime.fromisoformat(check_out_date)
        num_nights = (check_out_dt - check_in_dt).days
        
        # Adjust search radius based on preferred_location
        search_radius = self._get_search_radius(preferred_location)
        
        log_agent_raw(f"📋 Search: {destination}, {check_in_date}→{check_out_date}, "
                     f"{num_nights}n, radius={search_radius}m", agent_name="HotelAgent")
        
        # STRATEGY 1: Google Places
        if self.google_places and self.google_places.client:
            all_google_hotels = []
            seen_place_ids = set()
            
            # Step 1a: Targeted searches for preferred chains
            if preferred_chains:
                log_agent_raw(f"🏷️  Searching preferred chains: {preferred_chains}", 
                            agent_name="HotelAgent")
                for chain_name in preferred_chains:
                    chain_hotels = self.google_places.search_hotels_by_text(
                        query=f"{chain_name} hotel in {destination}",
                        location=destination,
                        radius=search_radius,
                        min_rating=min_rating,
                        agent_logger=self.logger
                    )
                    if chain_hotels:
                        log_agent_raw(f"   ✓ {chain_name}: {len(chain_hotels)} hotels", 
                                    agent_name="HotelAgent")
                        for hotel in chain_hotels:
                            pid = hotel.get('place_id')
                            if pid and pid not in seen_place_ids:
                                seen_place_ids.add(pid)
                                hotel['_matched_chain'] = chain_name
                                all_google_hotels.append(hotel)
            
            # Step 1b: General nearby search to fill remaining slots
            remaining_slots = max_results - len(all_google_hotels)
            if remaining_slots > 0:
                general_hotels = self.google_places.search_hotels(
                    location=destination,
                    radius=search_radius,
                    min_rating=min_rating,
                    agent_logger=self.logger
                )
                if general_hotels:
                    for hotel in general_hotels:
                        pid = hotel.get('place_id')
                        if pid and pid not in seen_place_ids:
                            seen_place_ids.add(pid)
                            all_google_hotels.append(hotel)
                            if len(all_google_hotels) >= max_results:
                                break
            
            chain_matched = sum(1 for h in all_google_hotels if h.get('_matched_chain'))
            log_agent_raw(f"📊 Combined: {len(all_google_hotels)} unique hotels "
                        f"(chain-matched: {chain_matched})", agent_name="HotelAgent")
            
            if all_google_hotels:
                all_google_hotels = all_google_hotels[:max_results]
                
                enriched_hotels = self._enrich_hotels_with_pricing(
                    google_hotels=all_google_hotels,
                    destination=destination,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    num_nights=num_nights,
                    adults=adults
                )
                
                if enriched_hotels:
                    enriched_hotels = self._filter_by_budget(enriched_hotels, budget_per_night)
                    if enriched_hotels:
                        return enriched_hotels
        else:
            log_agent_raw("⚠️ Google Places not available", agent_name="HotelAgent")
        
        # STRATEGY 2: Amadeus fallback
        if self.amadeus_service and self.amadeus_service.client:
            city_code = self._resolve_city_code(destination)
            if city_code:
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
                        hotels = [self._parse_hotel_data(h) for h in hotels_data]
                        hotels = [h for h in hotels if h]
                        if hotels:
                            hotels = self._filter_by_budget(hotels, budget_per_night)
                            if hotels:
                                return hotels
                except Exception as e:
                    log_agent_raw(f"❌ Amadeus failed: {str(e)}", agent_name="HotelAgent")
        
        # STRATEGY 3: Mock data
        log_agent_raw("⚠️ All APIs failed, using mock data", agent_name="HotelAgent")
        return self._generate_mock_hotels(destination, check_in_date, check_out_date)
    
    # ─────────────────────────────────────────────────────────────────────
    # PREFERENCE HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _get_search_radius(self, preferred_location: Optional[str]) -> int:
        """Map preferred_location to search radius in meters."""
        if not preferred_location:
            return 5000
        location_lower = preferred_location.lower().replace('_', ' ')
        radius_map = {
            "city center": 3000, "city_center": 3000, "downtown": 3000, "central": 3000,
            "near airport": 15000, "near_airport": 15000, "airport": 15000,
            "quiet area": 10000, "quiet_area": 10000, "suburbs": 10000, "suburban": 10000,
            "beach": 8000, "beachfront": 8000,
        }
        for key, radius in radius_map.items():
            if key in location_lower:
                return radius
        return 5000

    def _filter_by_budget(self, hotels: List[Hotel], budget_per_night: float) -> List[Hotel]:
        """Soft budget filter with BUDGET_TOLERANCE (1.2x)."""
        if not budget_per_night or budget_per_night <= 0:
            return hotels
        max_price = budget_per_night * BUDGET_TOLERANCE
        within_budget = [h for h in hotels if h.price_per_night <= max_price]
        log_agent_raw(
            f"💰 Budget: ${budget_per_night}/night (max ${max_price:.0f}) → "
            f"{len(within_budget)}/{len(hotels)} pass", agent_name="HotelAgent"
        )
        return within_budget if within_budget else hotels

    # ─────────────────────────────────────────────────────────────────────
    # PRICING ENRICHMENT
    # ─────────────────────────────────────────────────────────────────────
    
    def _enrich_hotels_with_pricing(
        self,
        google_hotels: List[Dict],
        destination: str,
        check_in_date: str,
        check_out_date: str,
        num_nights: int,
        adults: int
    ) -> List[Hotel]:
        """
        Enrich Google Places hotels with pricing, booking links, and metadata.
        
        v5: Now passes all pricing metadata (cheapest_provider, is_estimated)
        and all booking links (not just booking_com) through to Hotel model.
        """
        log_agent_raw("💰 Enriching with Xotelo Pricing & Booking Links", agent_name="HotelAgent")
        
        enriched_hotels = []
        xotelo_success_count = 0
        
        for idx, google_hotel in enumerate(google_hotels, 1):
            hotel_name = google_hotel.get('name', 'Unknown')
            matched_chain = google_hotel.get('_matched_chain', '')
            chain_tag = f" [chain: {matched_chain}]" if matched_chain else ""
            
            log_agent_raw(f"🏨 Hotel {idx}/{len(google_hotels)}: {hotel_name}{chain_tag}", 
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
                        log_agent_raw(f"   ✓ Xotelo: ${pricing['total_price']:.2f} "
                                    f"(${pricing['price_per_night']:.2f}/night) "
                                    f"via {pricing.get('cheapest_provider', 'N/A')}", 
                                    agent_name="HotelAgent")
                except Exception as e:
                    log_agent_raw(f"   ⚠️ Xotelo error: {str(e)}", agent_name="HotelAgent")
            
            # Fallback to estimation
            if not pricing:
                pricing = self._estimate_price(
                    google_hotel.get('price_level', 2),
                    google_hotel.get('google_rating', 3.5),
                    num_nights
                )
                log_agent_raw(f"   ✓ Estimated: ${pricing['total_price']:.2f} "
                            f"(${pricing['price_per_night']:.2f}/night)", 
                            agent_name="HotelAgent")
            
            # Generate ALL booking links
            booking_links_raw = self.booking_links.generate_all_links(
                hotel_name=hotel_name,
                city=destination,
                check_in=check_in_date,
                check_out=check_out_date,
                adults=adults,
                latitude=google_hotel.get('latitude'),
                longitude=google_hotel.get('longitude')
            )
            
            log_agent_raw(f"   ✓ Generated {len(booking_links_raw)} booking links", 
                        agent_name="HotelAgent")
            
            # v5: Flatten booking links to {provider_name: url} for frontend
            booking_links_flat = {}
            primary_booking_url = None
            for key, link_data in booking_links_raw.items():
                if isinstance(link_data, dict) and link_data.get('url'):
                    provider_name = link_data.get('name', key)
                    booking_links_flat[provider_name] = link_data['url']
                    if not primary_booking_url:
                        primary_booking_url = link_data['url']
            
            # Create hotel object with full enrichment
            hotel = self._create_hotel_from_google(
                google_data=google_hotel,
                pricing=pricing,
                booking_links=booking_links_flat,
                primary_booking_url=primary_booking_url,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                num_nights=num_nights
            )
            
            enriched_hotels.append(hotel)
        
        log_agent_raw(f"📊 Enrichment: {len(enriched_hotels)} hotels, "
                    f"Xotelo: {xotelo_success_count}, "
                    f"Estimated: {len(enriched_hotels) - xotelo_success_count}",
                    agent_name="HotelAgent")
        
        return enriched_hotels
    
    def _estimate_price(self, price_level: int, rating: float, num_nights: int) -> Dict[str, Any]:
        """Estimate price from Google price_level + rating"""
        base_prices = {0: 50, 1: 85, 2: 150, 3: 275, 4: 450}
        base_price = base_prices.get(price_level, 150)
        
        if rating >= 4.7:     multiplier = 1.4
        elif rating >= 4.5:   multiplier = 1.3
        elif rating >= 4.0:   multiplier = 1.15
        elif rating >= 3.5:   multiplier = 1.0
        else:                 multiplier = 0.85
        
        price_per_night = base_price * multiplier
        total_price = price_per_night * num_nights
        
        return {
            'price_per_night': round(price_per_night, 2),
            'total_price': round(total_price, 2),
            'currency': 'USD',
            'num_nights': num_nights,
            'is_estimated': True,
            'price_source': 'estimated_from_google_price_level',
            'cheapest_provider': None,
        }
    
    def _create_hotel_from_google(
        self,
        google_data: Dict,
        pricing: Dict,
        booking_links: Dict[str, str],
        primary_booking_url: Optional[str],
        check_in_date: str,
        check_out_date: str,
        num_nights: int
    ) -> Hotel:
        """
        Create Hotel object from Google Places + pricing + booking links.
        
        v5: Now passes through ALL Google Places data that _parse_place_result
        extracts: reviews, website, phone_number, google_url, price_level,
        property_type. Also stores all OTA booking links and price metadata.
        """
        # Parse reviews into HotelReview objects
        reviews = []
        if google_data.get('reviews'):
            for review_dict in google_data['reviews'][:MAX_REVIEWS_PER_HOTEL]:
                try:
                    reviews.append(HotelReview(**review_dict))
                except Exception:
                    continue
        
        # Map primary_type to human-readable property_type
        primary_type = google_data.get('primary_type', '')
        property_type_map = {
            'hotel': 'Hotel',
            'resort_hotel': 'Resort',
            'motel': 'Motel',
            'lodging': 'Lodging',
            'bed_and_breakfast': 'B&B',
            'guest_house': 'Guest House',
            'hostel': 'Hostel',
        }
        property_type = property_type_map.get(primary_type, primary_type.replace('_', ' ').title() if primary_type else None)
        
        return Hotel(
            id=google_data.get('place_id', str(time.time())),
            name=google_data.get('name', 'Unknown Hotel'),
            hotel_code=google_data.get('place_id', ''),
            latitude=google_data.get('latitude', 0.0),
            longitude=google_data.get('longitude', 0.0),
            address=google_data.get('address', ''),
            # Google Places ratings
            place_id=google_data.get('place_id'),
            google_rating=google_data.get('google_rating'),
            user_ratings_total=google_data.get('user_ratings_total'),
            reviews=reviews,
            # Pricing (from Xotelo or estimated)
            price_per_night=pricing['price_per_night'],
            total_price=pricing['total_price'],
            currency=pricing['currency'],
            # Stay details
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            num_nights=num_nights,
            # Photos
            photos=google_data.get('photos', []),
            # Primary booking link (for backward compat)
            booking_url=primary_booking_url,
            # ── v5: Google Places data previously discarded ──────────────
            website=google_data.get('website'),
            phone_number=google_data.get('phone_number'),
            google_url=google_data.get('google_url'),
            business_status=google_data.get('business_status'),
            property_type=property_type,
            price_level=google_data.get('price_level'),
            # ── v5: Pricing metadata ─────────────────────────────────────
            is_estimated_price=pricing.get('is_estimated', True),
            cheapest_provider=pricing.get('cheapest_provider'),
            # ── v5: All OTA booking links ────────────────────────────────
            booking_links=booking_links if booking_links else None,
            # Description — store price source for debugging
            description=f"Price source: {pricing.get('price_source', 'unknown')}",
        )
    
    def _parse_hotel_data(self, data: Dict) -> Optional[Hotel]:
        """Parse Amadeus hotel data into Hotel object"""
        try:
            amenities_dict = data.get("amenities", {})
            amenities = HotelAmenities(**amenities_dict) if amenities_dict else None
            return Hotel(
                id=data["id"], name=data["name"], hotel_code=data["hotel_code"],
                latitude=data["latitude"], longitude=data["longitude"], address=data["address"],
                city=data.get("city"), distance_from_center=data.get("distance_from_center"),
                rating=data.get("rating"), review_count=data.get("review_count"),
                price_per_night=data["price_per_night"], total_price=data["total_price"],
                currency=data["currency"], check_in_date=data["check_in_date"],
                check_out_date=data["check_out_date"], num_nights=data["num_nights"],
                room_type=data.get("room_type"), amenities=amenities,
                description=data.get("description"), photos=data.get("photos", []),
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
        lines = []
        lines.append(f"Hotel budget per night: ${preferences.budget.hotel_budget_per_night}")
        lines.append(f"Minimum rating: {preferences.hotel_prefs.min_rating} stars")
        if hasattr(preferences.hotel_prefs, 'amenities') and preferences.hotel_prefs.amenities:
            lines.append(f"Preferred amenities: {', '.join(preferences.hotel_prefs.amenities)}")
        if hasattr(preferences.hotel_prefs, 'preferred_location') and preferences.hotel_prefs.preferred_location:
            lines.append(f"Preferred location: {preferences.hotel_prefs.preferred_location.replace('_', ' ')}")
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
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    def _generate_recommendation(self, hotels: List[Hotel], preferences: Any) -> str:
        if not hotels:
            return "I couldn't find any hotels matching your criteria."

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

You MUST respond with ONLY a JSON object in this exact format, nothing else:
{{
  "recommended_id": "<the hotel ID from the list above>",
  "reason": "<1-2 sentences explaining why this is the best match>",
  "summary": "<3-4 sentence friendly recommendation>"
}}

CRITICAL RULES:
- recommended_id MUST be one of these exact values: {valid_ids}
- Do NOT invent a hotel ID. Pick from the list above.
- Respond with valid JSON only. No markdown, no backticks, no extra text.
"""
        log_agent_raw("🤖 Asking LLM to pick best hotel...", agent_name="HotelAgent")

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
            log_agent_raw(f"📥 LLM raw: {raw_response}", agent_name="HotelAgent")

            result = self._parse_llm_json(raw_response)
            if not result:
                return self._fallback_recommendation(hotels, preferences)

            recommended_id = str(result.get("recommended_id", ""))
            reason = result.get("reason", "Best overall match")
            summary = result.get("summary", "")

            if recommended_id not in valid_ids:
                return self._fallback_recommendation(hotels, preferences)

            recommended_hotel = next(h for h in hotels if str(h.id) == recommended_id)

            self.trip_storage.store_recommendation(
                trip_id=self.trip_id, category="hotel",
                recommended_id=recommended_id, reason=reason,
                metadata={
                    "name": recommended_hotel.name,
                    "hotel_name": recommended_hotel.name,
                    "total_price": recommended_hotel.total_price,
                    "price_per_night": recommended_hotel.price_per_night,
                    "price": recommended_hotel.total_price,
                    "rating": recommended_hotel.google_rating or recommended_hotel.rating,
                    "reviews": recommended_hotel.user_ratings_total or recommended_hotel.review_count or 0,
                    "total_options_reviewed": len(hotels)
                }
            )

            log_agent_raw(f"⭐ LLM picked {recommended_id} ({recommended_hotel.name}): {reason}",
                         agent_name="HotelAgent")

            return summary if summary else (
                f"I recommend {recommended_hotel.name} at "
                f"${recommended_hotel.total_price:.2f} for {recommended_hotel.num_nights} nights. {reason}"
            )

        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="HotelAgent")
            return self._fallback_recommendation(hotels, preferences)

    def _fallback_recommendation(self, hotels: List[Hotel], preferences: Any) -> str:
        budget = getattr(preferences.budget, 'hotel_budget_per_night', None)
        if budget and budget > 0:
            within_budget = [h for h in hotels if h.price_per_night <= budget * BUDGET_TOLERANCE]
            candidates = within_budget if within_budget else hotels
        else:
            candidates = hotels

        best = max(candidates, key=lambda h: (h.google_rating or h.rating or 0))

        self.trip_storage.store_recommendation(
            trip_id=self.trip_id, category="hotel",
            recommended_id=str(best.id),
            reason="Fallback: highest rated within budget",
            metadata={
                "name": best.name, "hotel_name": best.name,
                "total_price": best.total_price,
                "price_per_night": best.price_per_night,
                "price": best.total_price,
                "rating": best.google_rating or best.rating,
                "reviews": best.user_ratings_total or best.review_count or 0,
                "total_options_reviewed": len(hotels), "is_fallback": True
            }
        )

        rating_str = f"{best.google_rating or best.rating or 'unrated'}★"
        reviews_count = best.user_ratings_total or best.review_count or 0
        return (
            f"I reviewed {len(hotels)} hotels for your trip. "
            f"My top recommendation is {best.name} at "
            f"${best.total_price:.2f} for {best.num_nights} nights "
            f"({rating_str} with {reviews_count} reviews)."
        )

    # ─────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ─────────────────────────────────────────────────────────────────────

    def _resolve_city_code(self, destination: str) -> Optional[str]:
        city_map = {
            "london": "LON", "paris": "PAR", "new york": "NYC", "tokyo": "TYO",
            "dubai": "DXB", "singapore": "SIN", "hong kong": "HKG", "barcelona": "BCN",
            "rome": "ROM", "amsterdam": "AMS", "madrid": "MAD", "berlin": "BER",
            "sydney": "SYD", "melbourne": "MEL", "los angeles": "LAX",
            "san francisco": "SFO", "miami": "MIA", "las vegas": "LAS",
            "chicago": "CHI", "boston": "BOS"
        }
        dest_lower = destination.lower().strip()
        if len(dest_lower) == 3 and dest_lower.isalpha():
            return dest_lower.upper()
        for city, code in city_map.items():
            if city in dest_lower:
                return code
        return None
    
    def _generate_mock_hotels(self, destination: str, check_in: str, check_out: str) -> List[Hotel]:
        from datetime import datetime
        check_in_dt = datetime.fromisoformat(check_in)
        check_out_dt = datetime.fromisoformat(check_out)
        num_nights = (check_out_dt - check_in_dt).days
        return [
            Hotel(id="MOCK001", name="Grand Plaza Hotel", hotel_code="MOCK001",
                  latitude=51.5074, longitude=-0.1278, address="123 Main Street",
                  city=destination, distance_from_center=2.5, rating=4.5,
                  price_per_night=150.0, total_price=150.0 * num_nights, currency="USD",
                  check_in_date=check_in, check_out_date=check_out, num_nights=num_nights,
                  room_type="Deluxe Room",
                  amenities=HotelAmenities(wifi=True, parking=True, pool=True, gym=True,
                      restaurant=True, room_service=True, air_conditioning=True, bar=True, breakfast=True),
                  description="Mock data", property_type="Hotel"),
            Hotel(id="MOCK002", name="City View Inn", hotel_code="MOCK002",
                  latitude=51.5074, longitude=-0.1278, address="456 Park Avenue",
                  city=destination, distance_from_center=1.2, rating=4.0,
                  price_per_night=120.0, total_price=120.0 * num_nights, currency="USD",
                  check_in_date=check_in, check_out_date=check_out, num_nights=num_nights,
                  room_type="Standard Room",
                  amenities=HotelAmenities(wifi=True, gym=True, restaurant=True,
                      air_conditioning=True, breakfast=True),
                  description="Mock data", property_type="Hotel"),
        ]


def create_hotel_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> HotelAgent:
    """Factory function to create HotelAgent"""
    return HotelAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)