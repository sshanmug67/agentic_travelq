"""
Hotel Agent - Complete Implementation
Google Places + Xotelo + Booking Links + Amadeus Fallback

Changes (v9 — Smart Pricing):
  - _enrich_hotels_with_pricing completely rewritten with priority-ordered pricing
  - Pricing order: Preferred → Interested → Budget picks (bottom-up) → Top rated (top-down)
  - New _price_hotel_batch() helper: prices a batch via Redis cache + Xotelo
  - Stops at TARGET (15) priced hotels instead of pricing all 33+
  - Budget picks: prices from bottom of rating-sorted alternatives upward
    in batches of 5 until 3 real prices found (lower-rated ≈ cheaper)
  - Top alternatives: fills remaining slots from top of sorted list
  - Estimated API calls: ~34 (was ~66) — zero wasted prices

Changes (v8):
  - _create_hotel_from_google: maps pricing['all_providers'] → provider_prices
    field on Hotel model, enabling multi-OTA price comparison in frontend

Changes (v7):
  - Granular status updates: _update_status() sends real-time progress messages

Changes (v6):
  - Wide search + LLM curation: fetch 3x max_results, LLM curates top N
  - interested_chains now extracted and searched
  - Chain tagging: [PREFERRED], [INTERESTED], [ALTERNATIVE]

Changes (v5):
  - _create_hotel_from_google: enriched data pass-through

Changes (v4):
  - Fixed: ALL user preferences now flow into hotel search

Location: backend/agents/hotel_agent.py

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
XOTELO_CACHE_TTL_SECONDS = 3600  # 60 minutes

# v9: Smart pricing — how many budget picks to find from bottom of sorted list
BUDGET_PICKS_TARGET = 3

# v9: How many bottom-alternatives to try per batch when hunting for budget picks
BUDGET_BATCH_SIZE = 3

# v9: Max over-budget chain hotels to keep for LLM (preferred first, then interested)
# Enforced in _filter_by_budget so the LLM physically can't exceed this count
MAX_OVER_BUDGET_CHAINS = 4


class HotelAgent(TravelQBaseAgent):
    """
    Hotel Agent with multiple API sources:
    - Google Places for discovery
    - Xotelo for real pricing
    - Amadeus as fallback
    - Booking links for conversion

    v9: Smart pricing — prices hotels in priority order, stops at target.
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

        log_agent_raw("🏨 HotelAgent initialized (v9 — SMART PRICING + PROVIDER PRICES + GRANULAR STATUS + LLM CURATION)", agent_name="HotelAgent")
        log_agent_raw("   ✓ Google Places service", agent_name="HotelAgent")
        log_agent_raw("   ✓ Xotelo pricing service", agent_name="HotelAgent")
        log_agent_raw("   ✓ Amadeus fallback", agent_name="HotelAgent")
        log_agent_raw("   ✓ Booking link generator", agent_name="HotelAgent")
        log_agent_raw(f"   ✓ Display max: {settings.hotel_agent_max_results}", agent_name="HotelAgent")
        log_agent_raw(f"   ✓ Wide search: {settings.hotel_agent_max_results * WIDE_SEARCH_MULTIPLIER} hotels", agent_name="HotelAgent")
        log_agent_raw(f"   ✓ Smart pricing: target={settings.hotel_agent_max_results}, budget_picks={BUDGET_PICKS_TARGET}", agent_name="HotelAgent")

    # ─────────────────────────────────────────────────────────────────────
    # v7: GRANULAR STATUS UPDATES
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, message: str) -> None:
        """Send a granular status message to the frontend via trip_storage."""
        try:
            self.trip_storage.update_agent_status_message(
                trip_id=self.trip_id,
                agent_name="hotel",
                message=message
            )
            log_agent_raw(f"📡 Status → {message}", agent_name="HotelAgent")
        except Exception as e:
            log_agent_raw(f"⚠️ Status update failed: {str(e)}", agent_name="HotelAgent")

    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """Generate reply with complete hotel search."""
        log_agent_raw("🔍 HotelAgent processing request...", agent_name="HotelAgent")

        self._update_status("Initializing hotel search...")

        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name,
                truncate=500
            )

        self._update_status("Loading travel preferences...")
        preferences = self.trip_storage.get_preferences(self.trip_id)

        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="HotelAgent")
            self._update_status("Error: preferences not found")
            return self.signal_completion(f"Error: {error_msg}")

        log_agent_raw(f"✅ Retrieved preferences for trip {self.trip_id}", agent_name="HotelAgent")

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

            display_max = settings.hotel_agent_max_results
            wide_search_max = display_max * WIDE_SEARCH_MULTIPLIER

            log_agent_raw(f"📊 Wide search: fetch up to {wide_search_max}, smart-price to {display_max}",
                         agent_name="HotelAgent")

            self._update_status(
                f"Searching up to {wide_search_max} hotels in {search_params['destination']}..."
            )

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

            log_agent_raw(f"✅ Search + smart pricing complete: {len(all_hotels)} hotels in {api_duration:.2f}s",
                         agent_name="HotelAgent")

            if not all_hotels:
                self._update_status("No hotels found matching your criteria")
                return self.signal_completion(
                    "I couldn't find any hotels matching your criteria. "
                    "Try adjusting your dates or location."
                )

            self._update_status(
                f"AI selecting best {display_max} from {len(all_hotels)} hotels..."
            )

            curated_hotels, recommendation_text = self._curate_and_recommend(
                all_hotels=all_hotels,
                preferences=preferences,
                preferred_chains=search_params["preferred_chains"],
                interested_chains=search_params["interested_chains"],
                display_max=display_max,
            )

            self._update_status(f"Saving {len(curated_hotels)} hotel options...")

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
                    "pricing_strategy": "smart_v9",
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

            self._update_status(
                f"Hotel search complete — {len(curated_hotels)} options ready"
            )

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

        v9: Uses smart pricing — only prices TARGET hotels in priority order.
        v7: Granular status updates at each search phase.
        """
        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw("🔍 WIDE HOTEL SEARCH (v9 — smart pricing)", agent_name="HotelAgent")
        log_agent_raw("=" * 80, agent_name="HotelAgent")

        preferred_chains = preferred_chains or []
        interested_chains = interested_chains or []

        check_in_dt = datetime.fromisoformat(check_in_date)
        check_out_dt = datetime.fromisoformat(check_out_date)
        num_nights = (check_out_dt - check_in_dt).days

        search_radius = self._get_search_radius(preferred_location)

        log_agent_raw(f"📋 Search: {destination}, {check_in_date}→{check_out_date}, "
                     f"{num_nights}n, radius={search_radius}m, target={max_results}",
                     agent_name="HotelAgent")

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

                preferred_found = sum(1 for h in all_google_hotels if h.get('_chain_tier') == 'preferred')
                self._update_status(
                    f"Found {preferred_found} preferred chain hotels"
                )

            # Step 1b: Targeted searches for INTERESTED chains
            if interested_chains:
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

            self._update_status(
                f"Found {len(all_google_hotels)} hotels "
                f"({chain_preferred} preferred, {chain_interested} interested, "
                f"{chain_alt} alternatives)"
            )

            if all_google_hotels:
                all_google_hotels = all_google_hotels[:max_results]

                self._update_status(
                    f"Smart pricing: selecting best {settings.hotel_agent_max_results} to price..."
                )

                enriched_hotels = self._enrich_hotels_with_pricing(
                    google_hotels=all_google_hotels,
                    destination=destination,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    num_nights=num_nights,
                    adults=adults,
                    budget_per_night=budget_per_night,
                )

                if enriched_hotels:
                    if budget_per_night and budget_per_night > 0:
                        self._update_status(
                            f"Filtering by budget: ${budget_per_night}/night..."
                        )

                    enriched_hotels = self._filter_by_budget(
                        enriched_hotels, budget_per_night,
                        preferred_chains=preferred_chains,
                        interested_chains=interested_chains,
                    )

                    if enriched_hotels:
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
        """Get Redis client for Xotelo pricing cache (lazy init)."""
        if not hasattr(self, '_redis_client') or self._redis_client is None:
            try:
                from config.settings import settings
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
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
        """Build deterministic Redis key for hotel+dates pricing lookup."""
        normalized = " ".join(hotel_name.lower().strip().split())
        name_hash = hashlib.md5(normalized.encode()).hexdigest()[:12]
        dest_clean = destination.lower().strip().replace(" ", "_")
        return f"xotelo:pricing:{name_hash}:{dest_clean}:{check_in}:{check_out}"

    # ─────────────────────────────────────────────────────────────────────
    # v6: CHAIN TAGGING
    # ─────────────────────────────────────────────────────────────────────

    def _tag_hotel(self, hotel: Hotel, preferred_chains: List[str], interested_chains: List[str]) -> str:
        """Tag a hotel as [PREFERRED], [INTERESTED], or [ALTERNATIVE]."""
        hotel_name_lower = hotel.name.lower()

        for chain in preferred_chains:
            if chain.lower() in hotel_name_lower:
                return "[PREFERRED]"

        for chain in interested_chains:
            if chain.lower() in hotel_name_lower:
                return "[INTERESTED]"

        return "[ALTERNATIVE]"

    # ─────────────────────────────────────────────────────────────────────
    # v6: LLM CURATION + RECOMMENDATION
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
        LLM curates top N hotels from pool + picks #1 recommendation.
        Returns (curated_hotels, recommendation_text).
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
            curated = all_hotels
            recommendation_text = self._recommend_only(
                curated, preferences, preferred_chains, interested_chains
            )
            return (curated, recommendation_text)

        hotels_table = self._build_hotels_table_for_curation(
            all_hotels, preferred_chains, interested_chains
        )
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(h.id) for h in all_hotels]

        preferred_count = sum(1 for h in all_hotels
                            if self._tag_hotel(h, preferred_chains, interested_chains) == "[PREFERRED]")
        interested_count = sum(1 for h in all_hotels
                             if self._tag_hotel(h, preferred_chains, interested_chains) == "[INTERESTED]")
        alternative_count = len(all_hotels) - preferred_count - interested_count

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
            Select the top {display_max} hotels using the MANDATORY SLOT ALLOCATION below,
            then pick your #1 recommendation from those {display_max}.

            MANDATORY SLOT ALLOCATION (follow this strictly):
            Your {display_max} selections MUST include these categories:

            SLOT 1 — PREFERRED & INTERESTED CHAINS (up to 4 slots):
            - Include up to 4 [PREFERRED] and [INTERESTED] hotels, even if over budget
            - Prioritize [PREFERRED] first, then [INTERESTED]
            - Pick the best variant from each chain (avoid near-duplicates from same chain)
            - If fewer than 4 [PREFERRED]+[INTERESTED] exist, that's fine — use what's available
            - These give the user the option to see and choose their favorite chains

            SLOT 2 — BUDGET-FRIENDLY OPTIONS (3 slots):
            - Include 3 of the cheapest hotels from the list
            - These should be noticeably cheaper than the chain hotels
            - Gives the user affordable alternatives to compare against

            SLOT 3 — BEST FIT (remaining slots to reach {display_max}):
            - Fill with the best overall hotels based on rating, location, value, and amenities
            - Prioritize variety: different price points, locations, and property types
            - Avoid duplicating chains or price ranges already covered above

            ADDITIONAL SELECTION GUIDELINES:
            - AVOID NEAR-DUPLICATES: Don't select multiple hotels from the same chain with
              similar price and rating
            - LOCATION VARIETY: Include hotels in different areas when possible
            - If a hotel fits multiple slots (e.g. a cheap [INTERESTED] hotel), count it
              in the higher-priority slot and fill the freed slot with another option

            RECOMMENDATION CRITERIA for picking #1:
            - [PREFERRED] chain hotels get priority if rating/budget/location are acceptable
            - [INTERESTED] chain hotels are good second choices
            - [ALTERNATIVE] hotels are worth recommending if significantly cheaper, better-rated, or better-located

            CHAIN TRANSPARENCY (IMPORTANT):
            - If you do NOT pick a [PREFERRED] hotel as #1, you MUST explain why in the summary
              (e.g. "Your preferred Marriott options start at $X/night which exceeds your $Y budget")
            - If you pick an [INTERESTED] hotel instead, explain the connection
              (e.g. "However, I found a great Hilton option within your budget")
            - If NO [PREFERRED] or [INTERESTED] hotels are in the list, say so
              (e.g. "No Marriott or Hilton properties were available for these dates")
            - If a [PREFERRED] hotel IS within budget and you still didn't pick it, explain what
              the recommended hotel offers that the preferred chain doesn't

            Respond with ONLY valid JSON:
            {{
            "selected_ids": [<exactly {display_max} hotel IDs from the list above, as strings>],
            "recommended_id": "<your #1 pick from the selected IDs>",
            "reason": "<1-2 sentences: why this is the best match>",
            "summary": "<4-5 sentence user-facing recommendation. Open by stating how many hotels you reviewed. If your #1 pick is NOT from a [PREFERRED] chain, explain why the preferred chain wasn't chosen (e.g. over budget, unavailable). If you picked an [INTERESTED] chain hotel instead, highlight that connection. Then explain WHY you picked this hotel — what makes it the best fit. Give specifics: hotel name, price per night, total price, rating. Finally, name 1-2 concrete alternatives from DIFFERENT chains with their price and what trade-off they offer. NEVER mention hotel IDs — users don't see those.>"
            }}

            CRITICAL RULES:
            - selected_ids MUST contain exactly {display_max} IDs (or fewer if less are available)
            - ALL IDs must be from this list: {valid_ids}
            - recommended_id MUST be one of the selected_ids
            - Respond with valid JSON only. No markdown, no backticks, no extra text.
            """

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

            self._update_status(
                f"AI selected {len(curated)} hotels — "
                f"top pick: {recommended_hotel.name} at ${recommended_hotel.price_per_night:.0f}/night"
            )

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

        self._update_status(f"AI picking best hotel from {len(hotels)} options...")

        prompt = f"""Here are {len(hotels)} available hotels:

{hotels_table}

User preferences:
{prefs_summary}

Pick the single best hotel for this user. Consider chain preferences ([PREFERRED] > [INTERESTED] > [ALTERNATIVE]),
budget, minimum rating, amenities, location, and trip purpose.

CHAIN TRANSPARENCY (IMPORTANT):
- If you do NOT pick a [PREFERRED] hotel as #1, you MUST explain why in the summary
  (e.g. "Your preferred Marriott options start at $X/night which exceeds your $Y budget")
- If you pick an [INTERESTED] hotel instead, explain the connection
  (e.g. "However, I found a great Hilton option within your budget")
- If NO [PREFERRED] or [INTERESTED] hotels are in the list, say so
- If a [PREFERRED] hotel IS within budget and you still didn't pick it, explain what
  the recommended hotel offers that the preferred chain doesn't

Respond with ONLY valid JSON:
{{
  "recommended_id": "<the hotel ID from the list above>",
  "reason": "<1-2 sentences: why this is the best match>",
  "summary": "<4-5 sentence user-facing recommendation. Open by stating how many hotels you reviewed. If your #1 pick is NOT from a [PREFERRED] chain, explain why the preferred chain wasn't chosen (e.g. over budget, unavailable). If you picked an [INTERESTED] chain hotel instead, highlight that connection. Then explain WHY you picked this hotel. Give specifics: hotel name, price per night, total price, rating. Name 1-2 alternatives from DIFFERENT chains. NEVER mention hotel IDs.>"
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
                max_tokens=600
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
        Deterministic fallback following mandatory slot allocation:
        Slot 1: up to 4 preferred/interested chain hotels
        Slot 2: 4 cheapest alternatives (budget picks)
        Slot 3: remaining filled by highest-rated
        """
        log_agent_raw("🔄 Using deterministic fallback curation (slot allocation)", agent_name="HotelAgent")
        self._update_status(f"Selecting top {display_max} hotels by slot allocation...")

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

        sort_key = lambda h: (-(h.google_rating or h.rating or 0), h.price_per_night)
        preferred.sort(key=sort_key)
        interested.sort(key=sort_key)
        alternatives.sort(key=sort_key)

        curated = []
        seen_ids = set()

        def add_hotel(h):
            if h.id not in seen_ids and len(curated) < display_max:
                curated.append(h)
                seen_ids.add(h.id)
                return True
            return False

        # Slot 1: Up to MAX_OVER_BUDGET_CHAINS preferred + interested
        chain_slots = MAX_OVER_BUDGET_CHAINS
        chain_added = 0
        for h in preferred:
            if chain_added >= chain_slots:
                break
            if add_hotel(h):
                chain_added += 1
        for h in interested:
            if chain_added >= chain_slots:
                break
            if add_hotel(h):
                chain_added += 1

        # Slot 2: 4 cheapest alternatives (sort by price ASC)
        budget_alts = sorted(alternatives, key=lambda h: h.price_per_night)
        budget_added = 0
        for h in budget_alts:
            if budget_added >= 4:
                break
            if add_hotel(h):
                budget_added += 1

        # Slot 3: Fill remaining with highest-rated (already sorted by rating)
        for h in alternatives:
            if len(curated) >= display_max:
                break
            add_hotel(h)

        # If still under, pull from any remaining
        if len(curated) < display_max:
            for h in all_hotels:
                if len(curated) >= display_max:
                    break
                add_hotel(h)

        if preferred:
            recommended = preferred[0]
        elif interested:
            recommended = interested[0]
        else:
            recommended = curated[0] if curated else all_hotels[0]

        tag = self._tag_hotel(recommended, preferred_chains, interested_chains)

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
        """Build enriched hotel table with chain tags and metadata."""
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

    def _filter_by_budget(
        self,
        hotels: List[Hotel],
        budget_per_night: float,
        preferred_chains: List[str] = None,
        interested_chains: List[str] = None,
    ) -> List[Hotel]:
        """
        Soft budget filter with BUDGET_TOLERANCE (1.2x).
        
        Chain hotels that are OVER budget are kept so the user can see their
        preferred chains, but capped at MAX_OVER_BUDGET_CHAINS (4) to prevent
        the LLM from filling the list with expensive chain hotels.
        
        Priority: preferred over-budget first, then interested over-budget,
        sorted by rating within each tier. Within-budget chain hotels pass
        through normally (they don't count toward the cap).
        """
        if not budget_per_night or budget_per_night <= 0:
            return hotels
        
        preferred_chains = preferred_chains or []
        interested_chains = interested_chains or []
        max_price = budget_per_night * BUDGET_TOLERANCE
        
        within_budget = []
        over_budget_preferred = []
        over_budget_interested = []
        seen_ids = set()
        
        for h in hotels:
            if h.id in seen_ids:
                continue
            seen_ids.add(h.id)
            
            tag = self._tag_hotel(h, preferred_chains, interested_chains)
            is_within = h.price_per_night <= max_price
            
            if is_within:
                within_budget.append(h)
            elif tag == "[PREFERRED]":
                over_budget_preferred.append(h)
            elif tag == "[INTERESTED]":
                over_budget_interested.append(h)
            # else: over-budget alternative → dropped
        
        # Sort over-budget chains by rating (best first) for selection
        sort_key = lambda h: (-(h.google_rating or h.rating or 0), h.price_per_night)
        over_budget_preferred.sort(key=sort_key)
        over_budget_interested.sort(key=sort_key)
        
        # Cap: take best preferred first, then interested, up to MAX_OVER_BUDGET_CHAINS
        chain_exempt = []
        remaining_slots = MAX_OVER_BUDGET_CHAINS
        
        for h in over_budget_preferred:
            if remaining_slots <= 0:
                break
            chain_exempt.append(h)
            remaining_slots -= 1
        
        for h in over_budget_interested:
            if remaining_slots <= 0:
                break
            chain_exempt.append(h)
            remaining_slots -= 1
        
        dropped_chains = (len(over_budget_preferred) + len(over_budget_interested)) - len(chain_exempt)
        
        kept = within_budget + chain_exempt
        
        log_agent_raw(
            f"💰 Budget: ${budget_per_night}/night (max ${max_price:.0f}) → "
            f"{len(within_budget)} within budget + {len(chain_exempt)} chain-exempt "
            f"(cap {MAX_OVER_BUDGET_CHAINS}) = {len(kept)}/{len(hotels)} kept"
            f"{f' ({dropped_chains} over-budget chains dropped)' if dropped_chains > 0 else ''}",
            agent_name="HotelAgent"
        )

        self._update_status(
            f"Budget filter: {len(kept)}/{len(hotels)} hotels kept "
            f"({len(chain_exempt)} over-budget chain hotels, capped at {MAX_OVER_BUDGET_CHAINS})"
        )

        return kept if kept else hotels

    # ─────────────────────────────────────────────────────────────────────
    # v9: SMART PRICING — PRIORITY-ORDERED WITH EARLY STOP
    # ─────────────────────────────────────────────────────────────────────

    def _enrich_hotels_with_pricing(
        self,
        google_hotels: List[Dict],
        destination: str,
        check_in_date: str,
        check_out_date: str,
        num_nights: int,
        adults: int,
        budget_per_night: float = 0,
    ) -> List[Hotel]:
        """
        v9: Smart pricing — price hotels in priority order, stop when we
        have TARGET (15) **within-budget** hotels (or exhaust all candidates).

        Budget-aware counting: every hotel gets added to the result (so
        the LLM can see premium chain options), but only within-budget
        hotels count toward the stopping condition. This eliminates the
        need for a post-budget backfill phase.

        Pricing order:
          Phase 1: ALL preferred chain hotels  (always priced)
          Phase 2: ALL interested chain hotels (always priced)
          Phase 3: Budget picks from BOTTOM of rating-sorted alternatives
                   (lower rated ≈ cheaper — batches of 3 until 3 real prices)
          Phase 4: Top-rated alternatives from TOP of sorted list
                   (fill remaining budget slots, or exhaust candidates)

        Every priced hotel reaches the LLM. Zero waste.
        """
        TARGET = settings.hotel_agent_max_results  # 15
        max_budget = (budget_per_night * BUDGET_TOLERANCE) if budget_per_night and budget_per_night > 0 else 0

        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw(
            f"💰 SMART PRICING v9: target={TARGET} within-budget hotels, "
            f"budget_picks={BUDGET_PICKS_TARGET}, pool={len(google_hotels)}, "
            f"max_price=${max_budget:.0f}/night" if max_budget else
            f"💰 SMART PRICING v9: target={TARGET}, "
            f"budget_picks={BUDGET_PICKS_TARGET}, pool={len(google_hotels)}, "
            f"no budget limit",
            agent_name="HotelAgent"
        )
        log_agent_raw("=" * 80, agent_name="HotelAgent")

        # ── Helper: count within-budget hotels ───────────────────────
        def budget_count(hotels: List[Hotel]) -> int:
            """Count hotels within budget. If no budget set, count all."""
            if not max_budget:
                return len(hotels)
            return sum(1 for h in hotels if h.price_per_night <= max_budget)

        # ── Step 1: Categorize and sort ──────────────────────────────
        preferred = [h for h in google_hotels if h.get('_chain_tier') == 'preferred']
        interested = [h for h in google_hotels if h.get('_chain_tier') == 'interested']
        alternatives = [h for h in google_hotels if h.get('_chain_tier') not in ('preferred', 'interested')]

        # Sort alternatives: best rated first (top = quality, bottom = budget)
        alternatives.sort(
            key=lambda h: (
                -(h.get('google_rating') or 0),
                -(h.get('user_ratings_total') or 0)
            )
        )

        log_agent_raw(
            f"📊 Categorized: {len(preferred)} preferred, {len(interested)} interested, "
            f"{len(alternatives)} alternatives (sorted by rating DESC)",
            agent_name="HotelAgent"
        )

        if alternatives:
            top_alt = alternatives[0]
            bot_alt = alternatives[-1]
            log_agent_raw(
                f"   Top alternative: {top_alt.get('name', '?')} "
                f"(★{top_alt.get('google_rating', '?')}, "
                f"{top_alt.get('user_ratings_total', '?')} reviews)",
                agent_name="HotelAgent"
            )
            log_agent_raw(
                f"   Bottom alternative: {bot_alt.get('name', '?')} "
                f"(★{bot_alt.get('google_rating', '?')}, "
                f"{bot_alt.get('user_ratings_total', '?')} reviews)",
                agent_name="HotelAgent"
            )

        all_priced: List[Hotel] = []
        attempted_ids: set = set()

        # ── Phase 1: Price ALL preferred ─────────────────────────────
        if preferred:
            self._update_status(
                f"Pricing {len(preferred)} preferred chain hotels..."
            )
            log_agent_raw(
                f"👑 Phase 1: Pricing {len(preferred)} preferred hotels",
                agent_name="HotelAgent"
            )

            results = self._price_hotel_batch(
                preferred, destination, check_in_date, check_out_date,
                num_nights, adults
            )
            all_priced.extend(results)
            for h in preferred:
                attempted_ids.add(h.get('place_id'))

            bc = budget_count(all_priced)
            real = sum(1 for h in results if not h.is_estimated_price)
            log_agent_raw(
                f"   → {len(results)} preferred priced ({real} real) — "
                f"within budget: {bc}/{TARGET}",
                agent_name="HotelAgent"
            )

        # ── Phase 2: Price ALL interested ────────────────────────────
        if interested and budget_count(all_priced) < TARGET:
            self._update_status(
                f"Pricing {len(interested)} interested chain hotels..."
            )
            log_agent_raw(
                f"⭐ Phase 2: Pricing {len(interested)} interested hotels",
                agent_name="HotelAgent"
            )

            results = self._price_hotel_batch(
                interested, destination, check_in_date, check_out_date,
                num_nights, adults
            )
            all_priced.extend(results)
            for h in interested:
                attempted_ids.add(h.get('place_id'))

            bc = budget_count(all_priced)
            real = sum(1 for h in results if not h.is_estimated_price)
            log_agent_raw(
                f"   → {len(results)} interested priced ({real} real) — "
                f"within budget: {bc}/{TARGET}",
                agent_name="HotelAgent"
            )

        # ── Phase 3: Budget picks from BOTTOM of sorted alternatives ─
        budget_real_prices = 0
        bottom_cursor = len(alternatives)  # Start from end (lowest rated)

        log_agent_raw(
            f"💰 Phase 3: Budget picks — scanning bottom of {len(alternatives)} "
            f"sorted alternatives (target: {BUDGET_PICKS_TARGET} real prices)",
            agent_name="HotelAgent"
        )
        self._update_status("Finding budget-friendly alternatives...")

        while budget_real_prices < BUDGET_PICKS_TARGET and bottom_cursor > 0:
            batch_start = max(0, bottom_cursor - BUDGET_BATCH_SIZE)
            batch = [
                h for h in alternatives[batch_start:bottom_cursor]
                if h.get('place_id') not in attempted_ids
            ]

            if not batch:
                bottom_cursor = batch_start
                continue

            batch_names = [h.get('name', '?')[:30] for h in batch]
            self._update_status(
                f"Checking budget options (positions {batch_start + 1}-{bottom_cursor})..."
            )
            log_agent_raw(
                f"   Batch [{batch_start + 1}-{bottom_cursor}]: {batch_names}",
                agent_name="HotelAgent"
            )

            results = self._price_hotel_batch(
                batch, destination, check_in_date, check_out_date,
                num_nights, adults
            )

            added_in_batch = 0
            real_in_batch = 0
            for hotel in results:
                if not hotel.is_estimated_price and budget_real_prices >= BUDGET_PICKS_TARGET:
                    # Already have enough budget picks — skip remaining
                    continue
                all_priced.append(hotel)
                added_in_batch += 1
                if not hotel.is_estimated_price:
                    budget_real_prices += 1
                    real_in_batch += 1

            for h in batch:
                attempted_ids.add(h.get('place_id'))

            bc = budget_count(all_priced)
            log_agent_raw(
                f"   → {added_in_batch} added ({real_in_batch} real) — "
                f"budget picks: {budget_real_prices}/{BUDGET_PICKS_TARGET}, "
                f"within budget: {bc}/{TARGET}",
                agent_name="HotelAgent"
            )

            bottom_cursor = batch_start

        log_agent_raw(
            f"   Budget phase complete: {budget_real_prices} real budget prices found",
            agent_name="HotelAgent"
        )

        # ── Phase 4: Top alternatives from TOP of sorted list ────────
        # Keep pricing until we have TARGET within-budget hotels
        # or exhaust all unattempted alternatives.

        bc = budget_count(all_priced)
        if bc < TARGET:
            unattempted_top = [
                h for h in alternatives
                if h.get('place_id') not in attempted_ids
            ]

            if unattempted_top:
                remaining_budget_slots = TARGET - bc
                # Price in batches to avoid over-fetching
                cursor = 0

                log_agent_raw(
                    f"🏆 Phase 4: Need {remaining_budget_slots} more within-budget hotels — "
                    f"{len(unattempted_top)} unattempted alternatives available",
                    agent_name="HotelAgent"
                )

                while budget_count(all_priced) < TARGET and cursor < len(unattempted_top):
                    shortfall = TARGET - budget_count(all_priced)
                    # Fetch shortfall + small buffer (some may be over budget)
                    batch_size = min(shortfall + 3, len(unattempted_top) - cursor)
                    batch = unattempted_top[cursor:cursor + batch_size]
                    cursor += batch_size

                    self._update_status(
                        f"Pricing top-rated alternatives (batch of {len(batch)})..."
                    )
                    log_agent_raw(
                        f"   Phase 4 batch: {len(batch)} hotels "
                        f"(need {shortfall} more within budget)...",
                        agent_name="HotelAgent"
                    )

                    results = self._price_hotel_batch(
                        batch, destination, check_in_date, check_out_date,
                        num_nights, adults
                    )
                    all_priced.extend(results)

                    for h in batch:
                        attempted_ids.add(h.get('place_id'))

                    bc = budget_count(all_priced)
                    real = sum(1 for h in results if not h.is_estimated_price)
                    over = sum(1 for h in results if max_budget and h.price_per_night > max_budget)
                    log_agent_raw(
                        f"   → {len(results)} priced ({real} real, {over} over budget) — "
                        f"within budget: {bc}/{TARGET}",
                        agent_name="HotelAgent"
                    )
        else:
            log_agent_raw(
                f"   ✅ Already have {bc}/{TARGET} within-budget hotels — skipping Phase 4",
                agent_name="HotelAgent"
            )

        # ── Final tally ──────────────────────────────────────────────
        total_final = len(all_priced)
        total_real = sum(1 for h in all_priced if not h.is_estimated_price)
        total_estimated = total_final - total_real
        total_within_budget = budget_count(all_priced)
        total_attempted = len(attempted_ids)

        log_agent_raw("=" * 80, agent_name="HotelAgent")
        log_agent_raw(
            f"✅ Smart pricing complete: {total_final} hotels total, "
            f"{total_within_budget} within budget "
            f"({total_real} real, {total_estimated} estimated)",
            agent_name="HotelAgent"
        )
        log_agent_raw(
            f"   Xotelo calls: ~{total_attempted * 2} (was ~{len(google_hotels) * 2}) — "
            f"saved ~{(len(google_hotels) - total_attempted) * 2} API calls",
            agent_name="HotelAgent"
        )
        log_agent_raw("=" * 80, agent_name="HotelAgent")

        self._update_status(
            f"Pricing complete: {total_within_budget} within budget, "
            f"{total_final} total ({total_real} real prices)"
        )

        return all_priced

    # ─────────────────────────────────────────────────────────────────────
    # v9: BATCH PRICING HELPER (Redis cache + Xotelo)
    # ─────────────────────────────────────────────────────────────────────

    def _price_hotel_batch(
        self,
        google_hotels_batch: List[Dict],
        destination: str,
        check_in_date: str,
        check_out_date: str,
        num_nights: int,
        adults: int,
    ) -> List[Hotel]:
        """
        Price a batch of hotels via Redis cache + Xotelo async batch.
        Returns list of Hotel objects (with real or estimated prices).

        Extracted from the old monolithic _enrich_hotels_with_pricing so it
        can be called per-phase in the smart pricing pipeline.

        Flow:
        1. Check Redis cache for each hotel
        2. Send cache misses to xotelo.batch_get_prices()
        3. Cache fresh Xotelo results in Redis
        4. Build Hotel objects (real price if available, estimated fallback)
        """
        if not google_hotels_batch:
            return []

        total = len(google_hotels_batch)
        redis_client = self._get_redis_client()

        # ── 1. Redis cache check ─────────────────────────────────────
        pricing_map: Dict[int, Optional[Dict]] = {}
        cached_indices: set = set()
        hotels_needing_xotelo: List[Dict] = []
        xotelo_index_map: Dict[int, int] = {}
        cache_hits = 0

        if redis_client:
            pipe = redis_client.pipeline()
            cache_keys = []

            for idx, hotel in enumerate(google_hotels_batch):
                key = self._xotelo_cache_key(
                    hotel.get('name', 'Unknown'),
                    destination, check_in_date, check_out_date
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
                            batch_idx = len(hotels_needing_xotelo)
                            xotelo_index_map[batch_idx] = idx
                            hotels_needing_xotelo.append(google_hotels_batch[idx])
                    else:
                        batch_idx = len(hotels_needing_xotelo)
                        xotelo_index_map[batch_idx] = idx
                        hotels_needing_xotelo.append(google_hotels_batch[idx])

            except Exception as e:
                self.logger.warning(f"⚠️  Redis cache read failed: {e}")
                hotels_needing_xotelo = list(google_hotels_batch)
                xotelo_index_map = {i: i for i in range(total)}
                cache_hits = 0
                cached_indices.clear()
        else:
            hotels_needing_xotelo = list(google_hotels_batch)
            xotelo_index_map = {i: i for i in range(total)}

        # ── 2. Xotelo batch for cache misses ─────────────────────────
        xotelo_success = 0

        if hotels_needing_xotelo:
            start_time = time.time()

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

            # ── 3. Cache fresh results ───────────────────────────────
            cache_pipe = redis_client.pipeline() if redis_client else None

            for batch_idx, pricing in batch_results:
                original_idx = xotelo_index_map[batch_idx]
                pricing_map[original_idx] = pricing

                if pricing is not None:
                    xotelo_success += 1

                    if cache_pipe:
                        try:
                            hotel_name = google_hotels_batch[original_idx].get('name', 'Unknown')
                            key = self._xotelo_cache_key(
                                hotel_name, destination,
                                check_in_date, check_out_date
                            )
                            cache_pipe.setex(
                                key, XOTELO_CACHE_TTL_SECONDS,
                                json.dumps(pricing)
                            )
                        except Exception:
                            pass

            if cache_pipe:
                try:
                    cache_pipe.execute()
                except Exception:
                    pass

            pricing_duration = time.time() - start_time
            log_agent_raw(
                f"   Xotelo batch: {len(hotels_needing_xotelo)} hotels in "
                f"{pricing_duration:.1f}s ({xotelo_success} success, "
                f"{cache_hits} cached)",
                agent_name="HotelAgent"
            )

        # ── 4. Build Hotel objects ───────────────────────────────────
        hotels: List[Hotel] = []

        for idx, google_hotel in enumerate(google_hotels_batch):
            pricing = pricing_map.get(idx)

            if not pricing:
                pricing = self._estimate_price(
                    google_hotel.get('price_level', 2),
                    google_hotel.get('google_rating', 3.5),
                    num_nights
                )

            booking_links_raw = self.booking_links.generate_all_links(
                hotel_name=google_hotel.get('name', ''),
                city=destination,
                check_in=check_in_date,
                check_out=check_out_date,
                adults=adults,
                latitude=google_hotel.get('latitude'),
                longitude=google_hotel.get('longitude')
            )

            booking_links_flat = {}
            primary_booking_url = None
            for key, link_data in booking_links_raw.items():
                if isinstance(link_data, dict) and link_data.get('url'):
                    provider_name = link_data.get('name', key)
                    booking_links_flat[provider_name] = link_data['url']
                    if not primary_booking_url:
                        primary_booking_url = link_data['url']

            hotel = self._create_hotel_from_google(
                google_data=google_hotel,
                pricing=pricing,
                booking_links=booking_links_flat,
                primary_booking_url=primary_booking_url,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                num_nights=num_nights
            )

            hotels.append(hotel)

        return hotels

    # ─────────────────────────────────────────────────────────────────────
    # PRICE ESTIMATION & HOTEL CREATION
    # ─────────────────────────────────────────────────────────────────────

    def _estimate_price(self, price_level: int, rating: float, num_nights: int) -> Dict[str, Any]:
        """Estimate price from Google price_level + rating."""
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

        v8: Maps pricing['all_providers'] → provider_prices for multi-OTA comparison.
        v5: Passes through ALL Google Places data.
        """
        reviews = []
        if google_data.get('reviews'):
            for review_dict in google_data['reviews'][:MAX_REVIEWS_PER_HOTEL]:
                try:
                    reviews.append(HotelReview(**review_dict))
                except Exception:
                    continue

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
        property_type = property_type_map.get(
            primary_type,
            primary_type.replace('_', ' ').title() if primary_type else None
        )

        # v8: Build provider_prices from Xotelo all_providers
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
            booking_url=primary_booking_url,
            website=google_data.get('website'),
            phone_number=google_data.get('phone_number'),
            google_url=google_data.get('google_url'),
            business_status=google_data.get('business_status'),
            property_type=property_type,
            price_level=google_data.get('price_level'),
            is_estimated_price=pricing.get('is_estimated', True),
            cheapest_provider=pricing.get('cheapest_provider'),
            provider_prices=provider_prices,
            booking_links=booking_links if booking_links else None,
            description=f"Price source: {pricing.get('price_source', 'unknown')}",
        )

    def _parse_hotel_data(self, data: Dict) -> Optional[Hotel]:
        """Parse Amadeus hotel data into Hotel object."""
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
        """Convert Hotel to dict for storage."""
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
    """Factory function to create HotelAgent."""
    return HotelAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)