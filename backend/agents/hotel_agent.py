"""
Hotel Agent - Complete Implementation
Google Places + Xotelo + Booking Links + Amadeus Fallback

Changes (v8):
  - _create_hotel_from_google: maps pricing['all_providers'] → provider_prices
    field on Hotel model, enabling multi-OTA price comparison in frontend

Changes (v7):
  - Granular status updates: _update_status() sends real-time progress messages
    to Redis via trip_storage, enabling the frontend PlanningStatus component
    to show per-agent color-coded status (e.g. Hotel Agent = blue)
  - Status messages at every workflow step: chain search, general search,
    pricing enrichment (with per-hotel progress), budget filtering,
    LLM curation, storage, and completion
  - Status includes dynamic counts and hotel names during enrichment

Changes (v6):
  - Wide search + LLM curation: fetch 3x max_results, LLM curates top N
  - interested_chains now extracted and searched (was completely ignored)
  - Chain tagging: [PREFERRED], [INTERESTED], [ALTERNATIVE] for LLM
  - _curate_and_recommend(): LLM selects top N hotels with chain diversity,
    location mix, price range variety + picks #1 in single call
  - _fallback_curate_and_recommend(): deterministic fallback
  - Enriched hotels table for LLM: chain tag, property type, price source,
    estimated vs real pricing, location info
  - Summary prompt: WHY, count reviewed, specific alternatives
  - store_recommendation: stores summary (not reason) for Top Picks card

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

Hotel Agent — _enrich_hotels_with_pricing REPLACEMENT (async batch + Redis cache)

This replaces the existing _enrich_hotels_with_pricing in hotel_agent.py.

FLOW:
  1. Check Redis for cached Xotelo pricing for each hotel+dates combo
  2. Send only CACHE MISSES to xotelo.batch_get_prices()
  3. Store fresh results back in Redis (60 min TTL)
  4. Merge cached + fresh results, build Hotel objects

API SAVINGS:
  - 33 hotels × 2 Xotelo calls = 66 requests per user search
  - With cache: second identical search = 0 Xotelo requests
  - Free tier: 1,000 req/month → ~15 searches without cache, 100+ with cache

REQUIREMENTS:
  - redis package (pip install redis)
  - Redis server running (already required for Celery/status updates)
  - Add _get_redis_client() and _xotelo_cache_key() methods to HotelAgent

CACHE KEY FORMAT:
  xotelo:pricing:{name_hash}:{destination}:{check_in}:{check_out}

CACHE TTL: 60 minutes (configurable via XOTELO_CACHE_TTL_SECONDS)

"""
import json
import re
import time
import asyncio
import hashlib
import redis

from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.amadeus_service import get_amadeus_service
from services.google_places_service import get_google_places_service
from services.xotelo_service import get_xotelo_service
from utils.booking_links import BookingLinkGenerator
from models.trip import Hotel, HotelAmenities, HotelReview, HotelProviderPrice

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai

# Maximum number of reviews to store per hotel (independent of hotel max_results)
MAX_REVIEWS_PER_HOTEL = 5

# Budget tolerance: include hotels up to 20% over stated budget
BUDGET_TOLERANCE = 1.2

# v6: Wide search multiplier — fetch 3x display_max, LLM curates down
WIDE_SEARCH_MULTIPLIER = 3

# How long Xotelo pricing stays valid in Redis (seconds)
# 60 minutes is a good balance — prices don't change minute to minute
XOTELO_CACHE_TTL_SECONDS = 3600  # 60 minutes

class HotelAgent(TravelQBaseAgent):
    """
    Hotel Agent with multiple API sources:
    - Google Places for discovery
    - Xotelo for real pricing
    - Amadeus as fallback
    - Booking links for conversion
    
    v8: provider_prices passed through for multi-OTA comparison
    v7: Granular status updates for frontend PlanningStatus component
    v6: Wide search + LLM curation pattern (mirrors FlightAgent v6)
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """You are a Hotel Search Assistant that recommends hotels based on user preferences.

You will be given:
1. A list of available hotels with IDs, prices, ratings, reviews, and locations
2. The user's preferences (budget, minimum rating, amenities, trip purpose, etc.)
3. Chain preference tags: [PREFERRED], [INTERESTED], or [ALTERNATIVE]

Your job is to curate the best selection AND pick your #1 recommendation.

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
        
        log_agent_raw("🏨 HotelAgent initialized (v8 — PROVIDER PRICES + GRANULAR STATUS + WIDE SEARCH + LLM CURATION)", agent_name="HotelAgent")
        log_agent_raw("   ✓ Google Places service", agent_name="HotelAgent")
        log_agent_raw("   ✓ Xotelo pricing service", agent_name="HotelAgent")
        log_agent_raw("   ✓ Amadeus fallback", agent_name="HotelAgent")
        log_agent_raw("   ✓ Booking link generator", agent_name="HotelAgent")
        log_agent_raw(f"   ✓ Display max: {settings.hotel_agent_max_results}", agent_name="HotelAgent")
        log_agent_raw(f"   ✓ Wide search: {settings.hotel_agent_max_results * WIDE_SEARCH_MULTIPLIER} hotels", agent_name="HotelAgent")

    # ─────────────────────────────────────────────────────────────────────
    # v7: GRANULAR STATUS UPDATES
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, message: str) -> None:
        """
        Send a granular status message to the frontend via trip_storage.
        
        v7: The PlanningStatus component polls these messages and displays
        them color-coded per agent (e.g. Hotel Agent = blue).
        
        Messages are stored in Redis alongside the agent's status field
        so the frontend poll picks them up in real time.
        """
        try:
            self.trip_storage.update_agent_status_message(
                trip_id=self.trip_id,
                agent_name="hotel",
                message=message
            )
            log_agent_raw(f"📡 Status → {message}", agent_name="HotelAgent")
        except Exception as e:
            # Status updates are non-critical — don't break the workflow
            log_agent_raw(f"⚠️ Status update failed: {str(e)}", agent_name="HotelAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """Generate reply with complete hotel search
        
        v7: Granular status updates at every workflow step.
        """
        log_agent_raw("🔍 HotelAgent processing request...", agent_name="HotelAgent")
        
        # v7: Initial status
        self._update_status("Initializing hotel search...")
        
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
        self._update_status("Loading travel preferences...")
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="HotelAgent")
            self._update_status("Error: preferences not found")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences for trip {self.trip_id}", agent_name="HotelAgent")
        
        # Build search parameters — ALL preferences extracted (v6: added interested_chains)
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
            "interested_chains": getattr(preferences.hotel_prefs, 'interested_chains', []) or [],
        }
        
        log_agent_json(search_params, label="Search Parameters (full)", agent_name="HotelAgent")
        
        # Explicit log: which preferences are used WHERE
        log_agent_raw("📋 Preferences → Search Strategy:", agent_name="HotelAgent")
        log_agent_raw(f"   ⭐ preferred_chains  → Google Text Search (priority chain queries)", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['preferred_chains'] or 'None → skip chain search'}", agent_name="HotelAgent")
        log_agent_raw(f"   ☆ interested_chains  → Google Text Search (secondary chain queries)", agent_name="HotelAgent")
        log_agent_raw(f"     Value: {search_params['interested_chains'] or 'None → skip'}", agent_name="HotelAgent")
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
            
            # v6: Calculate wide search and display max
            display_max = settings.hotel_agent_max_results
            wide_search_max = display_max * WIDE_SEARCH_MULTIPLIER
            
            log_agent_raw(f"📊 Wide search: fetch up to {wide_search_max}, curate to {display_max}",
                         agent_name="HotelAgent")
            
            # v7: Status — starting wide search
            self._update_status(
                f"Searching up to {wide_search_max} hotels in {search_params['destination']}..."
            )
            
            # Search hotels (wide pool)
            all_hotels = self._search_hotels_complete(
                destination=search_params["destination"],
                check_in_date=search_params["check_in_date"],
                check_out_date=search_params["check_out_date"],
                adults=search_params["num_travelers"],
                min_rating=search_params["min_rating"],
                max_results=wide_search_max,
                budget_per_night=search_params["budget_per_night"],
                preferred_chains=search_params["preferred_chains"],
                interested_chains=search_params["interested_chains"],
                preferred_location=search_params["preferred_location"],
            )
            
            api_duration = time.time() - start_time
            
            log_agent_raw(f"✅ Wide search complete: {len(all_hotels)} hotels in {api_duration:.2f}s", 
                         agent_name="HotelAgent")
            
            if not all_hotels:
                self._update_status("No hotels found matching your criteria")
                return self.signal_completion(
                    "I couldn't find any hotels matching your criteria. "
                    "Try adjusting your dates or location."
                )
            
            # v7: Status — starting curation
            self._update_status(
                f"AI selecting best {display_max} from {len(all_hotels)} hotels..."
            )
            
            # v6: LLM curates top N from wide pool + picks recommendation
            curated_hotels, recommendation_text = self._curate_and_recommend(
                all_hotels=all_hotels,
                preferences=preferences,
                preferred_chains=search_params["preferred_chains"],
                interested_chains=search_params["interested_chains"],
                display_max=display_max,
            )
            
            # v7: Status — saving results
            self._update_status(f"Saving {len(curated_hotels)} hotel options...")
            
            # Store only curated hotels
            hotels_dict = [self._hotel_to_dict(h) for h in curated_hotels]
            
            self.trip_storage.add_hotels(
                trip_id=self.trip_id,
                hotels=hotels_dict,
                metadata={
                    "destination": search_params["destination"],
                    "check_in_date": search_params["check_in_date"],
                    "check_out_date": search_params["check_out_date"],
                    "search_time": datetime.now().isoformat(),
                    "total_results": len(curated_hotels),
                    "total_pool": len(all_hotels),
                    "api_duration": api_duration,
                    "sources": ["google_places", "xotelo", "booking_links"],
                    "preferred_chains": search_params["preferred_chains"],
                    "interested_chains": search_params["interested_chains"],
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
            
            log_agent_raw(f"💾 Stored {len(curated_hotels)} curated hotels (from {len(all_hotels)} pool)",
                         agent_name="HotelAgent")
            
            # v7: Final status
            self._update_status(
                f"Hotel search complete — {len(curated_hotels)} options ready"
            )
            
            # self.log_conversation_message(
            #     message_type="OUTGOING",
            #     content=recommendation_text,
            #     sender="chat_manager",
            #     truncate=1000
            # )
            
            return self.signal_completion(recommendation_text)
            
        except Exception as e:
            log_agent_raw(f"❌ Hotel search failed: {str(e)}", agent_name="HotelAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="HotelAgent")
            self._update_status(f"Error: {str(e)[:80]}")
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
        max_results: int = 45,
        budget_per_night: float = 0,
        preferred_chains: List[str] = None,
        interested_chains: List[str] = None,
        preferred_location: str = None,
    ) -> List[Hotel]:
        """
        Complete hotel search workflow with preference-aware discovery.
        
        v7: Granular status updates at each search phase.
        v6: Now also searches interested_chains (was previously ignored).
        Fetches wide pool for LLM curation.
        """
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw("🔍 WIDE HOTEL SEARCH (v7 — granular status + preference-aware)", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        
        preferred_chains = preferred_chains or []
        interested_chains = interested_chains or []
        
        # Calculate nights
        check_in_dt = datetime.fromisoformat(check_in_date)
        check_out_dt = datetime.fromisoformat(check_out_date)
        num_nights = (check_out_dt - check_in_dt).days
        
        # Adjust search radius based on preferred_location
        search_radius = self._get_search_radius(preferred_location)
        
        log_agent_raw(f"📋 Search: {destination}, {check_in_date}→{check_out_date}, "
                     f"{num_nights}n, radius={search_radius}m, target={max_results}",
                     agent_name="HotelAgent")
        
        # v7: Status — search parameters
        self._update_status(
            f"Searching hotels in {destination} "
            f"({check_in_date} to {check_out_date}, {num_nights} nights)..."
        )
        
        # STRATEGY 1: Google Places
        if self.google_places and self.google_places.client:
            all_google_hotels = []
            seen_place_ids = set()
            
            # Step 1a: Targeted searches for PREFERRED chains
            if preferred_chains:
                # v7: Status — searching preferred chains
                self._update_status(
                    f"Searching preferred chains: {', '.join(preferred_chains)}..."
                )
                
                log_agent_raw(f"⭐ Searching preferred chains: {preferred_chains}", 
                            agent_name="HotelAgent")
                for chain_name in preferred_chains:
                    self._update_status(
                        f"Searching {chain_name} hotels in {destination}..."
                    )
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
                                hotel['_chain_tier'] = 'preferred'
                                all_google_hotels.append(hotel)
                
                # v7: Status — preferred chain results
                preferred_found = sum(1 for h in all_google_hotels if h.get('_chain_tier') == 'preferred')
                self._update_status(
                    f"Found {preferred_found} preferred chain hotels"
                )
            
            # Step 1b: Targeted searches for INTERESTED chains (v6: NEW)
            if interested_chains:
                # v7: Status — searching interested chains
                self._update_status(
                    f"Searching interested chains: {', '.join(interested_chains)}..."
                )
                
                log_agent_raw(f"☆  Searching interested chains: {interested_chains}",
                            agent_name="HotelAgent")
                for chain_name in interested_chains:
                    self._update_status(
                        f"Searching {chain_name} hotels in {destination}..."
                    )
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
                                hotel['_chain_tier'] = 'interested'
                                all_google_hotels.append(hotel)
                
                interested_found = sum(1 for h in all_google_hotels if h.get('_chain_tier') == 'interested')
                self._update_status(
                    f"Found {interested_found} interested chain hotels"
                )
            
            # Step 1c: General nearby search to fill remaining slots
            remaining_slots = max_results - len(all_google_hotels)
            if remaining_slots > 0:
                # v7: Status — general search
                self._update_status(
                    f"Searching {remaining_slots} more hotels in {destination}..."
                )
                
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
            
            chain_preferred = sum(1 for h in all_google_hotels if h.get('_chain_tier') == 'preferred')
            chain_interested = sum(1 for h in all_google_hotels if h.get('_chain_tier') == 'interested')
            chain_alt = len(all_google_hotels) - chain_preferred - chain_interested
            
            log_agent_raw(
                f"📊 Wide pool: {len(all_google_hotels)} unique hotels "
                f"(⭐ preferred: {chain_preferred}, ☆ interested: {chain_interested}, "
                f"alternatives: {chain_alt})",
                agent_name="HotelAgent"
            )
            
            # v7: Status — discovery complete
            self._update_status(
                f"Found {len(all_google_hotels)} hotels "
                f"({chain_preferred} preferred, {chain_interested} interested, "
                f"{chain_alt} alternatives)"
            )
            
            if all_google_hotels:
                all_google_hotels = all_google_hotels[:max_results]
                
                # v7: Status — starting pricing enrichment
                self._update_status(
                    f"Retrieving pricing for {len(all_google_hotels)} hotels..."
                )
                
                enriched_hotels = self._enrich_hotels_with_pricing(
                    google_hotels=all_google_hotels,
                    destination=destination,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    num_nights=num_nights,
                    adults=adults
                )
                
                if enriched_hotels:
                    # v7: Status — budget filtering
                    if budget_per_night and budget_per_night > 0:
                        self._update_status(
                            f"Filtering by budget: ${budget_per_night}/night..."
                        )
                    
                    enriched_hotels = self._filter_by_budget(enriched_hotels, budget_per_night)
                    
                    if enriched_hotels:
                        # v7: Status — enrichment complete
                        self._update_status(
                            f"{len(enriched_hotels)} hotels with pricing ready"
                        )
                        return enriched_hotels
        else:
            log_agent_raw("⚠️ Google Places not available", agent_name="HotelAgent")
            self._update_status("Google Places unavailable — trying fallback...")
        
        # STRATEGY 2: Amadeus fallback
        if self.amadeus_service and self.amadeus_service.client:
            self._update_status("Searching via Amadeus API fallback...")
            
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
                        self._update_status(f"Amadeus found {len(hotels_data)} hotels")
                        hotels = [self._parse_hotel_data(h) for h in hotels_data]
                        hotels = [h for h in hotels if h]
                        if hotels:
                            hotels = self._filter_by_budget(hotels, budget_per_night)
                            if hotels:
                                return hotels
                except Exception as e:
                    log_agent_raw(f"❌ Amadeus failed: {str(e)}", agent_name="HotelAgent")
                    self._update_status("Amadeus API failed")
        
        # STRATEGY 3: Mock data
        log_agent_raw("⚠️ All APIs failed, using mock data", agent_name="HotelAgent")
        self._update_status("All APIs unavailable — using sample hotel data")
        return self._generate_mock_hotels(destination, check_in_date, check_out_date)
    

    def _get_redis_client(self):
        """
        Get Redis client for Xotelo pricing cache (lazy init).
        
        Uses the same Redis URL as Celery/status updates.
        Returns None if Redis unavailable (graceful degradation).
        """
        if not hasattr(self, '_redis_client') or self._redis_client is None:
            try:
                from config.settings import settings
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,  # Return strings, not bytes
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._redis_client.ping()
                self.logger.info("✅ Redis connected for Xotelo pricing cache")
            except Exception as e:
                self.logger.warning(f"⚠️  Redis not available for pricing cache: {e}")
                self._redis_client = None
        return self._redis_client


    def _xotelo_cache_key(self, hotel_name: str, destination: str, check_in: str, check_out: str) -> str:
        """
        Build deterministic Redis key for hotel+dates pricing lookup.
        
        Normalizes hotel name to avoid misses from casing/whitespace.
        Uses MD5 hash prefix to keep keys short.
        
        Example: xotelo:pricing:a1b2c3d4e5f6:london:2026-02-23:2026-02-28
        """
        normalized = " ".join(hotel_name.lower().strip().split())
        name_hash = hashlib.md5(normalized.encode()).hexdigest()[:12]
        dest_clean = destination.lower().strip().replace(" ", "_")
        return f"xotelo:pricing:{name_hash}:{dest_clean}:{check_in}:{check_out}"

    # ─────────────────────────────────────────────────────────────────────
    # v6: CHAIN TAGGING (mirrors FlightAgent _tag_flight)
    # ─────────────────────────────────────────────────────────────────────

    def _tag_hotel(self, hotel: Hotel, preferred_chains: List[str], interested_chains: List[str]) -> str:
        """
        Tag a hotel as [PREFERRED], [INTERESTED], or [ALTERNATIVE].
        Matches hotel name against chain names (case-insensitive).
        """
        hotel_name_lower = hotel.name.lower()
        
        for chain in preferred_chains:
            if chain.lower() in hotel_name_lower:
                return "[PREFERRED]"
        
        for chain in interested_chains:
            if chain.lower() in hotel_name_lower:
                return "[INTERESTED]"
        
        return "[ALTERNATIVE]"

    # ─────────────────────────────────────────────────────────────────────
    # v6: LLM CURATION + RECOMMENDATION (mirrors FlightAgent v6)
    # ─────────────────────────────────────────────────────────────────────

    def _curate_and_recommend(
        self,
        all_hotels: List[Hotel],
        preferences: Any,
        preferred_chains: List[str],
        interested_chains: List[str],
        display_max: int,
    ) -> tuple:
        """
        LLM curates top N hotels from wide pool + picks #1 recommendation.
        Returns (curated_hotels, recommendation_text).
        
        v7: Granular status updates during curation.
        """
        if len(all_hotels) <= display_max:
            log_agent_raw(
                f"📋 Pool ({len(all_hotels)}) ≤ display_max ({display_max}), "
                f"skipping curation — LLM will just recommend",
                agent_name="HotelAgent"
            )
            self._update_status(
                f"Analyzing {len(all_hotels)} hotels for best recommendation..."
            )
            # Still need recommendation, just no curation needed
            curated = all_hotels
            recommendation_text = self._recommend_only(
                curated, preferences, preferred_chains, interested_chains
            )
            return (curated, recommendation_text)
        
        # Build enriched hotels table for LLM
        hotels_table = self._build_hotels_table_for_curation(
            all_hotels, preferred_chains, interested_chains
        )
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(h.id) for h in all_hotels]
        
        # Count by tag
        preferred_count = sum(1 for h in all_hotels
                            if self._tag_hotel(h, preferred_chains, interested_chains) == "[PREFERRED]")
        interested_count = sum(1 for h in all_hotels
                             if self._tag_hotel(h, preferred_chains, interested_chains) == "[INTERESTED]")
        alternative_count = len(all_hotels) - preferred_count - interested_count
        
        # v7: Status — LLM curation with breakdown
        self._update_status(
            f"AI reviewing {len(all_hotels)} hotels "
            f"({preferred_count} preferred, {interested_count} interested, "
            f"{alternative_count} alternatives)..."
        )
        
        prompt = f"""You are reviewing {len(all_hotels)} hotel options to curate the best {display_max} for the user.

            ALL AVAILABLE HOTELS:
            {hotels_table}

            Hotel breakdown: {preferred_count} from preferred chains, {interested_count} from interested chains, {alternative_count} alternatives

            USER PREFERENCES:
            {prefs_summary}

            YOUR TASK:
            Select the top {display_max} hotels that give the user the best set of OPTIONS to choose from,
            then pick your #1 recommendation from those {display_max}.

            SELECTION CRITERIA (in priority order):
            1. CHAIN PREFERENCE: Include hotels from each [PREFERRED] chain if available.
            Then include [INTERESTED] chain hotels. Fill remaining slots with [ALTERNATIVE]
            hotels that offer meaningfully better value, location, or ratings.
            2. AVOID NEAR-DUPLICATES: Don't select multiple hotels from the same chain with
            similar price and rating. Pick the best variant from each chain.
            3. PRICE RANGE: Include a mix — some premium options from preferred chains AND
            budget-friendly alternatives so the user can compare value.
            4. LOCATION VARIETY: Include hotels in different areas of the city when possible
            (city center, near landmarks, quieter neighborhoods).
            5. RATING MIX: Include highly-rated options AND good-value options.

            RECOMMENDATION CRITERIA for picking #1:
            - [PREFERRED] chain hotels get priority if rating/budget/location are acceptable
            - [INTERESTED] chain hotels are good second choices
            - [ALTERNATIVE] hotels are worth recommending if significantly cheaper, better-rated, or better-located

            Respond with ONLY valid JSON:
            {{
            "selected_ids": [<exactly {display_max} hotel IDs from the list above, as strings>],
            "recommended_id": "<your #1 pick from the selected IDs>",
            "reason": "<1-2 sentences: why this is the best match>",
            "summary": "<3-4 sentence user-facing recommendation. Open by stating how many hotels you reviewed (use the exact number from above), then explain WHY you picked this hotel — what makes it the best fit for this user's specific preferences (e.g. it's from a preferred chain, best value for money, highest rated, ideal location, has requested amenities). Then give specifics: hotel name, price per night, total price, rating. Finally, name 1-2 concrete alternatives from DIFFERENT chains with their price and what trade-off they offer (e.g. cheaper but further from center, higher rated but over budget). NEVER mention hotel IDs — users don't see those.>"
            }}

            CRITICAL RULES:
            - selected_ids MUST contain exactly {display_max} IDs (or fewer if less are available)
            - ALL IDs must be from this list: {valid_ids}
            - recommended_id MUST be one of the selected_ids
            - Respond with valid JSON only. No markdown, no backticks, no extra text.
            """

        # log_agent_raw(
        #     f"🤖 Asking LLM to curate top {display_max} from {len(all_hotels)} hotels...",
        #     agent_name="HotelAgent"
        # )

        # log_agent_raw(
        #     f"Hotel LLM Prompt:\n",
        #     agent_name="HotelAgent"
        # )

        # log_agent_raw(
        #     f"\n\n{prompt}\n",
        #     agent_name="HotelAgent"
        # )

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            raw_response = response.choices[0].message.content.strip()
            # log_agent_raw(f"📥 LLM curation response: {raw_response}", agent_name="HotelAgent")
            
            result = self._parse_llm_json(raw_response)
            if not result:
                log_agent_raw("⚠️ Failed to parse LLM JSON, using fallback", agent_name="HotelAgent")
                self._update_status("AI curation parse failed — using smart fallback...")
                return self._fallback_curate_and_recommend(
                    all_hotels, preferences, preferred_chains, interested_chains, display_max
                )
            
            selected_ids = [str(sid) for sid in result.get("selected_ids", [])]
            recommended_id = str(result.get("recommended_id", ""))
            reason = result.get("reason", "Best overall match")
            summary = result.get("summary", "")
            
            # Validate IDs
            valid_set = set(valid_ids)
            selected_ids = [sid for sid in selected_ids if sid in valid_set]
            
            if not selected_ids or recommended_id not in valid_set:
                log_agent_raw("⚠️ Invalid IDs from LLM, using fallback", agent_name="HotelAgent")
                self._update_status("AI returned invalid selections — using smart fallback...")
                return self._fallback_curate_and_recommend(
                    all_hotels, preferences, preferred_chains, interested_chains, display_max
                )
            
            if recommended_id not in selected_ids:
                selected_ids.insert(0, recommended_id)
                selected_ids = selected_ids[:display_max]
            
            # Build curated list
            hotel_map = {str(h.id): h for h in all_hotels}
            curated = [hotel_map[sid] for sid in selected_ids if sid in hotel_map]
            
            if not curated:
                return self._fallback_curate_and_recommend(
                    all_hotels, preferences, preferred_chains, interested_chains, display_max
                )
            
            recommended_hotel = hotel_map.get(recommended_id)
            if not recommended_hotel:
                recommended_hotel = curated[0]
                recommended_id = str(recommended_hotel.id)
            
            # v7: Status — curation success
            self._update_status(
                f"AI selected {len(curated)} hotels — "
                f"top pick: {recommended_hotel.name} at ${recommended_hotel.price_per_night:.0f}/night"
            )
            
            # Log chain diversity in curated set
            curated_chains = {}
            for h in curated:
                tag = self._tag_hotel(h, preferred_chains, interested_chains)
                key = f"{h.name} {tag}"
                curated_chains[key] = f"${h.price_per_night:.0f}/night"
            
            # log_agent_json(
            #     curated_chains,
            #     label=f"LLM Curated Top {len(curated)} — Chain Diversity",
            #     agent_name="HotelAgent"
            # )
            
            # Store recommendation (v6: summary as reason for Top Picks display)
            tag = self._tag_hotel(recommended_hotel, preferred_chains, interested_chains)
            
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="hotel",
                recommended_id=recommended_id,
                reason=summary or reason,
                metadata={
                    "name": recommended_hotel.name,
                    "hotel_name": recommended_hotel.name,
                    "total_price": recommended_hotel.total_price,
                    "price_per_night": recommended_hotel.price_per_night,
                    "price": recommended_hotel.total_price,
                    "rating": recommended_hotel.google_rating or recommended_hotel.rating,
                    "reviews": recommended_hotel.user_ratings_total or recommended_hotel.review_count or 0,
                    "chain_match": tag,
                    "reason_short": reason,
                    "total_pool_reviewed": len(all_hotels),
                    "curated_count": len(curated),
                    "preferred_in_curated": sum(1 for h in curated
                        if self._tag_hotel(h, preferred_chains, interested_chains) == "[PREFERRED]"),
                    "interested_in_curated": sum(1 for h in curated
                        if self._tag_hotel(h, preferred_chains, interested_chains) == "[INTERESTED]"),
                }
            )
            
            log_agent_raw(
                f"⭐ LLM curated {len(curated)} hotels, picked {recommended_hotel.name} {tag} "
                f"(${recommended_hotel.price_per_night:.2f}/night): {reason}",
                agent_name="HotelAgent"
            )
            
            recommendation_text = summary if summary else (
                f"I recommend {recommended_hotel.name} at "
                f"${recommended_hotel.total_price:.2f} for {recommended_hotel.num_nights} nights. {reason}"
            )
            return (curated, recommendation_text)
        
        except Exception as e:
            log_agent_raw(f"⚠️ LLM curation failed: {str(e)}", agent_name="HotelAgent")
            self._update_status("AI curation error — using smart fallback...")
            return self._fallback_curate_and_recommend(
                all_hotels, preferences, preferred_chains, interested_chains, display_max
            )

    def _recommend_only(
        self,
        hotels: List[Hotel],
        preferences: Any,
        preferred_chains: List[str],
        interested_chains: List[str],
    ) -> str:
        """When pool ≤ display_max, just pick recommendation (no curation needed)."""
        hotels_table = self._build_hotels_table_for_curation(
            hotels, preferred_chains, interested_chains
        )
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(h.id) for h in hotels]
        
        # v7: Status
        self._update_status(f"AI picking best hotel from {len(hotels)} options...")
        
        prompt = f"""Here are {len(hotels)} available hotels:

{hotels_table}

User preferences:
{prefs_summary}

Pick the single best hotel for this user. Consider chain preferences ([PREFERRED] > [INTERESTED] > [ALTERNATIVE]),
budget, minimum rating, amenities, location, and trip purpose.

Respond with ONLY valid JSON:
{{
  "recommended_id": "<the hotel ID from the list above>",
  "reason": "<1-2 sentences: why this is the best match>",
  "summary": "<3-4 sentence user-facing recommendation. Open by stating how many hotels you reviewed (use the exact number from above), then explain WHY you picked this hotel. Give specifics: hotel name, price per night, total price, rating. Name 1-2 alternatives from DIFFERENT chains. NEVER mention hotel IDs.>"
}}

CRITICAL RULES:
- recommended_id MUST be one of: {valid_ids}
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
                max_tokens=500
            )
            
            raw_response = response.choices[0].message.content.strip()
            log_agent_raw(f"📥 LLM recommendation: {raw_response}", agent_name="HotelAgent")
            
            result = self._parse_llm_json(raw_response)
            if not result:
                self._update_status("AI parse failed — using smart fallback...")
                return self._fallback_recommendation_text(hotels, preferences, preferred_chains, interested_chains)
            
            recommended_id = str(result.get("recommended_id", ""))
            reason = result.get("reason", "Best overall match")
            summary = result.get("summary", "")
            
            if recommended_id not in [str(h.id) for h in hotels]:
                self._update_status("AI returned invalid selection — using smart fallback...")
                return self._fallback_recommendation_text(hotels, preferences, preferred_chains, interested_chains)
            
            recommended_hotel = next(h for h in hotels if str(h.id) == recommended_id)
            tag = self._tag_hotel(recommended_hotel, preferred_chains, interested_chains)
            
            # v7: Status — recommendation made
            self._update_status(
                f"Recommended: {recommended_hotel.name} at ${recommended_hotel.price_per_night:.0f}/night"
            )
            
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="hotel",
                recommended_id=recommended_id,
                reason=summary or reason,
                metadata={
                    "name": recommended_hotel.name,
                    "hotel_name": recommended_hotel.name,
                    "total_price": recommended_hotel.total_price,
                    "price_per_night": recommended_hotel.price_per_night,
                    "price": recommended_hotel.total_price,
                    "rating": recommended_hotel.google_rating or recommended_hotel.rating,
                    "reviews": recommended_hotel.user_ratings_total or recommended_hotel.review_count or 0,
                    "chain_match": tag,
                    "reason_short": reason,
                    "total_pool_reviewed": len(hotels),
                }
            )
            
            log_agent_raw(
                f"⭐ LLM picked {recommended_hotel.name} {tag}: {reason}",
                agent_name="HotelAgent"
            )
            
            return summary if summary else (
                f"I recommend {recommended_hotel.name} at "
                f"${recommended_hotel.total_price:.2f} for {recommended_hotel.num_nights} nights. {reason}"
            )
        
        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="HotelAgent")
            self._update_status("AI recommendation error — using smart fallback...")
            return self._fallback_recommendation_text(hotels, preferences, preferred_chains, interested_chains)

    def _fallback_curate_and_recommend(
        self,
        all_hotels: List[Hotel],
        preferences: Any,
        preferred_chains: List[str],
        interested_chains: List[str],
        display_max: int,
    ) -> tuple:
        """
        Deterministic fallback: preferred first, then interested, then
        alternatives sorted by rating. Round-robin for chain diversity.
        """
        log_agent_raw("🔄 Using deterministic fallback curation", agent_name="HotelAgent")
        self._update_status(f"Selecting top {display_max} hotels by chain preference and rating...")
        
        preferred = []
        interested = []
        alternatives = []
        
        for h in all_hotels:
            tag = self._tag_hotel(h, preferred_chains, interested_chains)
            if tag == "[PREFERRED]":
                preferred.append(h)
            elif tag == "[INTERESTED]":
                interested.append(h)
            else:
                alternatives.append(h)
        
        # Sort each group by rating (desc), then price (asc)
        sort_key = lambda h: (-(h.google_rating or h.rating or 0), h.price_per_night)
        preferred.sort(key=sort_key)
        interested.sort(key=sort_key)
        alternatives.sort(key=sort_key)
        
        # Build curated: preferred first, then interested, fill with alternatives
        curated = []
        seen_names = set()
        
        for hotel_list in [preferred, interested, alternatives]:
            for h in hotel_list:
                # Avoid near-duplicates by name similarity
                name_key = h.name.lower().split()[0] if h.name else ""
                if name_key not in seen_names and len(curated) < display_max:
                    curated.append(h)
                    seen_names.add(name_key)
        
        # Fill remaining slots if needed
        if len(curated) < display_max:
            for h in all_hotels:
                if h not in curated and len(curated) < display_max:
                    curated.append(h)
        
        # Pick best as recommendation
        if preferred:
            recommended = preferred[0]
        elif interested:
            recommended = interested[0]
        else:
            recommended = curated[0] if curated else all_hotels[0]
        
        tag = self._tag_hotel(recommended, preferred_chains, interested_chains)
        
        # v7: Status
        self._update_status(
            f"Selected {len(curated)} hotels — "
            f"top pick: {recommended.name} at ${recommended.price_per_night:.0f}/night"
        )
        
        self.trip_storage.store_recommendation(
            trip_id=self.trip_id,
            category="hotel",
            recommended_id=str(recommended.id),
            reason=f"Fallback: highest rated {tag.lower()} hotel within budget",
            metadata={
                "name": recommended.name,
                "hotel_name": recommended.name,
                "total_price": recommended.total_price,
                "price_per_night": recommended.price_per_night,
                "price": recommended.total_price,
                "rating": recommended.google_rating or recommended.rating,
                "reviews": recommended.user_ratings_total or recommended.review_count or 0,
                "chain_match": tag,
                "total_pool_reviewed": len(all_hotels),
                "curated_count": len(curated),
                "is_fallback": True,
            }
        )
        
        rating = recommended.google_rating or recommended.rating or 0
        reviews = recommended.user_ratings_total or recommended.review_count or 0
        recommendation_text = (
            f"I reviewed {len(all_hotels)} hotels for your trip. "
            f"My top recommendation is {recommended.name} at "
            f"${recommended.price_per_night:.2f}/night "
            f"(${recommended.total_price:.2f} total for {recommended.num_nights} nights), "
            f"rated {rating}★ with {reviews} reviews."
        )
        
        log_agent_raw(
            f"⭐ Fallback picked {recommended.name} {tag} "
            f"(${recommended.price_per_night:.2f}/night)",
            agent_name="HotelAgent"
        )
        
        return (curated, recommendation_text)

    def _fallback_recommendation_text(
        self,
        hotels: List[Hotel],
        preferences: Any,
        preferred_chains: List[str],
        interested_chains: List[str],
    ) -> str:
        """Fallback recommendation text when LLM fails (recommend-only path)."""
        budget = getattr(preferences.budget, 'hotel_budget_per_night', None)
        if budget and budget > 0:
            within_budget = [h for h in hotels if h.price_per_night <= budget * BUDGET_TOLERANCE]
            candidates = within_budget if within_budget else hotels
        else:
            candidates = hotels
        
        # Prefer preferred chains, then interested, then highest rated
        preferred = [h for h in candidates
                    if self._tag_hotel(h, preferred_chains, interested_chains) == "[PREFERRED]"]
        interested_list = [h for h in candidates
                         if self._tag_hotel(h, preferred_chains, interested_chains) == "[INTERESTED]"]
        
        if preferred:
            best = max(preferred, key=lambda h: (h.google_rating or h.rating or 0))
        elif interested_list:
            best = max(interested_list, key=lambda h: (h.google_rating or h.rating or 0))
        else:
            best = max(candidates, key=lambda h: (h.google_rating or h.rating or 0))
        
        tag = self._tag_hotel(best, preferred_chains, interested_chains)
        
        # v7: Status
        self._update_status(
            f"Fallback pick: {best.name} at ${best.price_per_night:.0f}/night"
        )
        
        self.trip_storage.store_recommendation(
            trip_id=self.trip_id,
            category="hotel",
            recommended_id=str(best.id),
            reason=f"Fallback: highest rated {tag.lower()} hotel within budget",
            metadata={
                "name": best.name, "hotel_name": best.name,
                "total_price": best.total_price,
                "price_per_night": best.price_per_night,
                "price": best.total_price,
                "rating": best.google_rating or best.rating,
                "reviews": best.user_ratings_total or best.review_count or 0,
                "chain_match": tag,
                "total_pool_reviewed": len(hotels),
                "is_fallback": True,
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
    # v6: ENRICHED HOTEL TABLE FOR LLM
    # ─────────────────────────────────────────────────────────────────────

    def _build_hotels_table_for_curation(
        self,
        hotels: List[Hotel],
        preferred_chains: List[str],
        interested_chains: List[str],
    ) -> str:
        """
        Build enriched hotel table with chain tags and metadata.
        v6: Mirrors flight agent's enriched table format.
        """
        rows = []
        for h in hotels:
            tag = self._tag_hotel(h, preferred_chains, interested_chains)
            rating = h.google_rating or h.rating or 0
            reviews = h.user_ratings_total or h.review_count or 0
            price_source = "estimated" if h.is_estimated_price else "real"
            provider = f" via {h.cheapest_provider}" if h.cheapest_provider else ""
            prop_type = f" | Type: {h.property_type}" if h.property_type else ""
            
            rows.append(
                f"{tag} ID: {h.id} | {h.name} | "
                f"${h.price_per_night:.2f}/night (${h.total_price:.2f} total, {h.num_nights}n, {price_source}{provider}) | "
                f"Rating: {rating}★ ({reviews} reviews)"
                f"{prop_type} | "
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
        # v6: Distinguish preferred vs interested chains
        if hasattr(preferences.hotel_prefs, 'preferred_chains') and preferences.hotel_prefs.preferred_chains:
            lines.append(f"⭐ Preferred chains (priority): {', '.join(preferences.hotel_prefs.preferred_chains)}")
        if hasattr(preferences.hotel_prefs, 'interested_chains') and preferences.hotel_prefs.interested_chains:
            lines.append(f"☆ Interested chains (good alternatives): {', '.join(preferences.hotel_prefs.interested_chains)}")
        lines.append(f"Trip purpose: {preferences.trip_purpose}")
        lines.append(f"Travelers: {preferences.num_travelers}")
        lines.append(f"Destination: {preferences.destination}")
        return "\n".join(lines)
    
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
        
        # v7: Status — budget filter results
        self._update_status(
            f"Budget filter: {len(within_budget)}/{len(hotels)} hotels "
            f"within ${budget_per_night}/night"
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
        
        REDIS CACHE + ASYNC BATCH:
        1. Check Redis for each hotel's cached Xotelo pricing
        2. Only send cache-misses to Xotelo (saves API quota)
        3. Store fresh results in Redis with 60-min TTL
        4. Build Hotel objects from cached + fresh pricing
        
        v8: Redis caching for Xotelo API quota conservation (1,000 req/month)
             + provider_prices passed through to Hotel model
        v7: Per-hotel status updates during enrichment loop
        v5: Passes all pricing metadata and booking links through to Hotel model
        """
        from utils.logging_config import log_agent_raw
        
        log_agent_raw(
            "💰 Enriching with Xotelo Pricing & Booking Links (ASYNC BATCH + REDIS CACHE)",
            agent_name="HotelAgent"
        )
        
        total_hotels = len(google_hotels)
        
        # ── Step 1: Check Redis cache for existing pricing ───────────────
        
        redis_client = self._get_redis_client()
        pricing_map: Dict[int, Optional[Dict[str, Any]]] = {}
        hotels_needing_xotelo: List[Dict] = []
        xotelo_index_map: Dict[int, int] = {}  # xotelo_batch_idx → original_idx
        cache_hits = 0
        cached_indices = set()  # Track which orignal indices came from cache
        
        if redis_client:
            pipe = redis_client.pipeline()
            cache_keys = []
            
            for idx, hotel in enumerate(google_hotels):
                key = self._xotelo_cache_key(
                    hotel.get('name', 'Unknown'),
                    destination,
                    check_in_date,
                    check_out_date
                )
                cache_keys.append((idx, key))
                pipe.get(key)
            
            try:
                cached_values = pipe.execute()
                
                for (idx, key), cached_json in zip(cache_keys, cached_values):
                    if cached_json:
                        try:
                            pricing_map[idx] = json.loads(cached_json)
                            cached_indices.add(idx)
                            cache_hits += 1
                        except json.JSONDecodeError:
                            # Corrupted cache entry — treat as miss
                            xotelo_batch_idx = len(hotels_needing_xotelo)
                            xotelo_index_map[xotelo_batch_idx] = idx
                            hotels_needing_xotelo.append(google_hotels[idx])
                    else:
                        xotelo_batch_idx = len(hotels_needing_xotelo)
                        xotelo_index_map[xotelo_batch_idx] = idx
                        hotels_needing_xotelo.append(google_hotels[idx])
                        
            except Exception as e:
                self.logger.warning(f"⚠️  Redis cache read failed: {e} — fetching all from Xotelo")
                hotels_needing_xotelo = list(google_hotels)
                xotelo_index_map = {i: i for i in range(len(google_hotels))}
                cache_hits = 0
                cached_indices.clear()
        else:
            # No Redis available — all hotels need Xotelo
            hotels_needing_xotelo = list(google_hotels)
            xotelo_index_map = {i: i for i in range(len(google_hotels))}
        
        self.logger.info(
            f"📦 Cache: {cache_hits}/{total_hotels} hits, "
            f"{len(hotels_needing_xotelo)} need Xotelo API "
            f"(~{len(hotels_needing_xotelo) * 2} requests)"
        )
        
        self._update_status(
            f"Cache: {cache_hits} hits — fetching {len(hotels_needing_xotelo)} from Xotelo..."
        )
        
        # ── Step 2: Batch-fetch pricing for cache misses only ────────────
        
        start_time = time.time()
        xotelo_success_count = 0
        
        if hotels_needing_xotelo:
            self.logger.info(
                f"🌐 Fetching {len(hotels_needing_xotelo)} hotels from Xotelo "
                f"(~{len(hotels_needing_xotelo) * 2} API calls)"
            )
            
            # Always create a fresh event loop to avoid double-execution.
            # asyncio.run() can complete the batch then raise RuntimeError
            # during cleanup in Python 3.12/Celery, causing the except block
            # to re-run the entire batch (doubling API usage from ~66 to ~132).
            loop = asyncio.new_event_loop()
            try:
                batch_results = loop.run_until_complete(
                    self.xotelo.batch_get_prices(
                        hotels=hotels_needing_xotelo,
                        destination=destination,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        agent_logger=self.logger,
                    )
                )
            finally:
                loop.close()
            
            # ── Step 3: Store fresh results in Redis + merge into pricing_map ──
            
            cache_pipe = redis_client.pipeline() if redis_client else None
            
            for batch_idx, pricing in batch_results:
                original_idx = xotelo_index_map[batch_idx]
                pricing_map[original_idx] = pricing
                
                if pricing is not None:
                    xotelo_success_count += 1
                    
                    # Cache successful Xotelo results
                    if cache_pipe:
                        try:
                            hotel_name = google_hotels[original_idx].get('name', 'Unknown')
                            key = self._xotelo_cache_key(
                                hotel_name, destination,
                                check_in_date, check_out_date
                            )
                            cache_pipe.setex(
                                key,
                                XOTELO_CACHE_TTL_SECONDS,
                                json.dumps(pricing)
                            )
                        except Exception:
                            pass  # Never fail enrichment over cache writes
            
            # Execute all cache writes in one Redis roundtrip
            if cache_pipe:
                try:
                    cache_pipe.execute()
                    if xotelo_success_count > 0:
                        self.logger.info(
                            f"💾 Cached {xotelo_success_count} Xotelo results "
                            f"(TTL: {XOTELO_CACHE_TTL_SECONDS // 60}min)"
                        )
                except Exception as e:
                    self.logger.warning(f"⚠️  Redis cache write failed: {e}")
        else:
            self.logger.info("✨ All hotels served from cache — 0 Xotelo API calls!")
        
        pricing_duration = time.time() - start_time
        estimated_count = total_hotels - cache_hits - xotelo_success_count
        
        log_agent_raw(
            f"⚡ Pricing complete in {pricing_duration:.2f}s: "
            f"{cache_hits} cached, {xotelo_success_count} from Xotelo, "
            f"{estimated_count} estimated",
            agent_name="HotelAgent"
        )
        
        self._update_status(
            f"Pricing fetched in {pricing_duration:.1f}s — "
            f"{cache_hits} cached, {xotelo_success_count} real, "
            f"{estimated_count} estimated"
        )
        
        # ── Step 4: Build Hotel objects ──────────────────────────────────
        
        enriched_hotels = []
        
        for idx, google_hotel in enumerate(google_hotels):
            hotel_name = google_hotel.get('name', 'Unknown')
            chain_tier = google_hotel.get('_chain_tier', '')
            
            tier_tag = ""
            if chain_tier == 'preferred':
                tier_tag = " ⭐[PREFERRED]"
            elif chain_tier == 'interested':
                tier_tag = " ☆[INTERESTED]"
            
            # Get pricing (from cache, Xotelo, or estimate)
            pricing = pricing_map.get(idx)
            
            if pricing:
                source_label = "cached" if idx in cached_indices else pricing.get('cheapest_provider', 'xotelo')
                # log_agent_raw(
                #     f"🏨 {idx+1}/{total_hotels}: {hotel_name}{tier_tag} → "
                #     f"${pricing['total_price']:.2f} via {source_label}",
                #     agent_name="HotelAgent"
                # )
            else:
                # Fallback to estimation
                pricing = self._estimate_price(
                    google_hotel.get('price_level', 2),
                    google_hotel.get('google_rating', 3.5),
                    num_nights
                )
                log_agent_raw(
                    f"🏨 {idx+1}/{total_hotels}: {hotel_name}{tier_tag} → "
                    f"${pricing['total_price']:.2f} (estimated)",
                    agent_name="HotelAgent"
                )
            
            # Generate ALL booking links (fast, no HTTP)
            booking_links_raw = self.booking_links.generate_all_links(
                hotel_name=hotel_name,
                city=destination,
                check_in=check_in_date,
                check_out=check_out_date,
                adults=adults,
                latitude=google_hotel.get('latitude'),
                longitude=google_hotel.get('longitude')
            )
            
            # Flatten booking links to {provider_name: url}
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
        
        log_agent_raw(
            f"📊 Enrichment complete: {len(enriched_hotels)} hotels, "
            f"Cached: {cache_hits}, Xotelo: {xotelo_success_count}, "
            f"Estimated: {estimated_count}, "
            f"Total time: {pricing_duration:.2f}s",
            agent_name="HotelAgent"
        )
        
        self._update_status(
            f"Pricing complete: {len(enriched_hotels)} hotels "
            f"({cache_hits} cached, {xotelo_success_count} real, "
            f"{estimated_count} estimated)"
        )
        
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
        
        v8: Maps pricing['all_providers'] → provider_prices for multi-OTA
            price comparison in the frontend.
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
        
        # ── v8: Build provider_prices from Xotelo all_providers ──────────
        provider_prices = None
        all_providers = pricing.get('all_providers')
        if all_providers:
            provider_prices = [
                HotelProviderPrice(
                    provider=p['provider'],
                    price_per_night=p['price_per_night'],
                    total_price=p['total_price'],
                    rate_base=p.get('rate'),
                    rate_tax=p.get('tax'),
                    url=p.get('url'),
                )
                for p in sorted(all_providers, key=lambda x: x['total_price'])
            ]
        
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
            # ── v8: All provider prices for comparison ───────────────────
            provider_prices=provider_prices,
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
    # JSON PARSING
    # ─────────────────────────────────────────────────────────────────────

    def _parse_llm_json(self, text: str) -> Optional[Dict]:
        """Parse LLM JSON response, handling markdown fences and nested structures."""
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object with nested arrays
            brace_start = cleaned.find('{')
            if brace_start >= 0:
                depth = 0
                for i in range(brace_start, len(cleaned)):
                    if cleaned[i] == '{':
                        depth += 1
                    elif cleaned[i] == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(cleaned[brace_start:i+1])
                            except json.JSONDecodeError:
                                break
        return None

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