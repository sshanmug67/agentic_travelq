"""
Flight Agent - Real API with Centralized Storage
Location: backend/agents/flight_agent.py

Changes (v7):
  - Granular status updates: _update_status() sends real-time progress messages
    to Redis via trip_storage, enabling the frontend PlanningStatus component
    to show per-agent color-coded status (e.g. "Fetching 50 flight offers...")
  - Status messages at every workflow step: airport resolution, API call,
    deduplication, LLM curation, storage, and completion
  - Status includes dynamic counts (e.g. "Found 42 flights", "Deduplicating
    codeshare flights... 35 unique remaining")

Changes (v6):
  - Wide search + LLM curation: single API call for 50 results, dedup
    codeshares by route fingerprint, LLM curates top N diverse options
  - _curate_and_recommend(): LLM selects top N flights with carrier
    diversity + picks #1 recommendation in a single call
  - _fallback_curate_and_recommend(): deterministic round-robin fallback
  - _search_flights_api() accepts max_override for wide search
  - _parse_llm_json() handles nested JSON (arrays in objects)

Changes (v5):
  - Flights tagged as [PREFERRED], [INTERESTED], or [ALTERNATIVE] for LLM
  - _build_preferences_summary() now includes interested_carriers
  - Amadeus nonStop filter when max_stops == 0
  - Deduplication by offer ID + route fingerprint (codeshare aware)

Changes (v4):
  - _parse_amadeus_offer now extracts rich metadata: amenities, branded fare,
    last ticketing date, seats remaining, price breakdown, validating carrier
  - _parse_flight_segment now builds per-hop SegmentDetail[] with terminals,
    aircraft codes/names, operating carriers, and calculates layover durations
  - Added AIRCRAFT_NAMES lookup for common IATA aircraft codes
  - Added _parse_segment_details(), _extract_amenities(), _calc_layover_duration()
  - _parse_baggage updated to read includedCabinBags from fare details

Previous changes (v3):
  - Removed deterministic _pick_recommended_flight()
  - LLM now picks the recommended flight ID based on full user preferences
  - LLM returns structured JSON: { recommended_id, reason, summary }
  - Summary is the conversational message; recommended_id gets stored
"""
import json
import time
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.amadeus_service import get_amadeus_service
from services.airport_lookup_service import get_airport_lookup_service
from models.trip import Flight, FlightSegment, SegmentDetail, FlightAmenity

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai


# ─────────────────────────────────────────────────────────────────────────
# AIRCRAFT CODE → DISPLAY NAME (common IATA codes)
# ─────────────────────────────────────────────────────────────────────────

AIRCRAFT_NAMES: Dict[str, str] = {
    # Regional jets
    "E75": "Embraer E175",
    "E90": "Embraer E190",
    "E95": "Embraer E195",
    "CR9": "Bombardier CRJ-900",
    "CRJ": "Bombardier CRJ",
    "DH4": "Dash 8-Q400",
    # Airbus narrowbody
    "319": "Airbus A319",
    "320": "Airbus A320",
    "321": "Airbus A321",
    "32A": "Airbus A320",
    "32B": "Airbus A321",
    "32N": "Airbus A321neo",
    "32Q": "Airbus A321neo",
    # Airbus widebody
    "332": "Airbus A330-200",
    "333": "Airbus A330-300",
    "339": "Airbus A330-900neo",
    "359": "Airbus A350-900",
    "35K": "Airbus A350-1000",
    "388": "Airbus A380",
    # Boeing narrowbody
    "738": "Boeing 737-800",
    "73H": "Boeing 737-800",
    "7M8": "Boeing 737 MAX 8",
    "7M9": "Boeing 737 MAX 9",
    # Boeing widebody
    "744": "Boeing 747-400",
    "763": "Boeing 767-300",
    "764": "Boeing 767-400",
    "772": "Boeing 777-200",
    "773": "Boeing 777-300",
    "77W": "Boeing 777-300ER",
    "788": "Boeing 787-8 Dreamliner",
    "789": "Boeing 787-9 Dreamliner",
    "78X": "Boeing 787-10 Dreamliner",
}


# ─────────────────────────────────────────────────────────────────────────
# AIRLINE CODE → DISPLAY NAME (common IATA carrier codes)
# ─────────────────────────────────────────────────────────────────────────

AIRLINE_NAMES: Dict[str, str] = {
    # North America
    "AA": "American Airlines",
    "AC": "Air Canada",
    "AS": "Alaska Airlines",
    "B6": "JetBlue",
    "DL": "Delta Air Lines",
    "F8": "Flair Airlines",
    "HA": "Hawaiian Airlines",
    "NK": "Spirit Airlines",
    "UA": "United Airlines",
    "WN": "Southwest Airlines",
    "WS": "WestJet",
    "PD": "Porter Airlines",
    # Europe
    "A3": "Aegean Airlines",
    "AF": "Air France",
    "AY": "Finnair",
    "AZ": "ITA Airways",
    "BA": "British Airways",
    "BT": "airBaltic",
    "DY": "Norwegian",
    "EI": "Aer Lingus",
    "EW": "Eurowings",
    "FI": "Icelandair",
    "FR": "Ryanair",
    "IB": "Iberia",
    "JU": "Air Serbia",
    "KL": "KLM Royal Dutch Airlines",
    "LH": "Lufthansa",
    "LO": "LOT Polish Airlines",
    "LX": "Swiss International Air Lines",
    "OS": "Austrian Airlines",
    "OU": "Croatia Airlines",
    "PC": "Pegasus Airlines",
    "RO": "TAROM",
    "SK": "SAS Scandinavian Airlines",
    "SN": "Brussels Airlines",
    "TP": "TAP Air Portugal",
    "TK": "Turkish Airlines",
    "U2": "easyJet",
    "VS": "Virgin Atlantic",
    "VY": "Vueling",
    "W6": "Wizz Air",
    "WK": "Edelweiss Air",
    # Middle East & Africa
    "EK": "Emirates",
    "ET": "Ethiopian Airlines",
    "EY": "Etihad Airways",
    "GF": "Gulf Air",
    "MS": "EgyptAir",
    "QR": "Qatar Airways",
    "RJ": "Royal Jordanian",
    "SA": "South African Airways",
    "SV": "Saudia",
    "WY": "Oman Air",
    # Asia Pacific
    "AI": "Air India",
    "CX": "Cathay Pacific",
    "GA": "Garuda Indonesia",
    "JL": "Japan Airlines",
    "KE": "Korean Air",
    "MH": "Malaysia Airlines",
    "NH": "ANA All Nippon Airways",
    "NZ": "Air New Zealand",
    "OZ": "Asiana Airlines",
    "PR": "Philippine Airlines",
    "QF": "Qantas",
    "SQ": "Singapore Airlines",
    "TG": "Thai Airways",
    "TR": "Scoot",
    "VN": "Vietnam Airlines",
    # Latin America
    "AM": "Aeromexico",
    "AR": "Aerolineas Argentinas",
    "AV": "Avianca",
    "CM": "Copa Airlines",
    "G3": "Gol Airlines",
    "LA": "LATAM Airlines",
    # China
    "CA": "Air China",
    "CZ": "China Southern Airlines",
    "HU": "Hainan Airlines",
    "MU": "China Eastern Airlines",
}

# ─────────────────────────────────────────────────────────────────────────
# REVERSE LOOKUP: Airline display name → IATA code
# Used to convert frontend names ("United Airlines") to Amadeus codes ("UA")
# ─────────────────────────────────────────────────────────────────────────

AIRLINE_CODES: Dict[str, str] = {name.lower(): code for code, name in AIRLINE_NAMES.items()}


def _resolve_carrier_codes(carrier_names: List[str]) -> List[str]:
    """
    Convert airline display names to IATA carrier codes for Amadeus API.

    Accepts both display names ("United Airlines") and raw codes ("UA").
    Unrecognized names are silently skipped with a log warning.

    Returns:
        List of unique IATA codes, e.g. ["UA", "BA", "DL"]
    """
    codes: List[str] = []
    for name in carrier_names:
        # Already a 2-letter code?
        if len(name) <= 3 and name.upper() in AIRLINE_NAMES:
            codes.append(name.upper())
        else:
            code = AIRLINE_CODES.get(name.lower())
            if code:
                codes.append(code)
            else:
                log_agent_raw(
                    f"⚠️ Could not resolve carrier name '{name}' to IATA code — skipping",
                    agent_name="FlightAgent"
                )
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


class FlightAgent(TravelQBaseAgent):
    """
    Flight Agent with real Amadeus API + centralized storage
    
    v7: Granular status updates for frontend PlanningStatus component
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """You are a Flight Search Assistant that recommends flights based on user preferences.

You will be given:
1. A list of available flights with IDs, prices, airlines, stops, and times
2. Each flight is tagged as [PREFERRED], [INTERESTED], or [ALTERNATIVE] based on the user's carrier preferences
3. The user's preferences (budget, preferred airlines, interested airlines, time preferences, cabin class, etc.)

Your job is to pick the BEST flight for this specific user and explain why.

Ranking guidelines:
- [PREFERRED] airline flights should be ranked highest IF they meet budget and stop constraints
- [INTERESTED] airline flights are good second choices
- [ALTERNATIVE] flights are important for showing low-cost or better-route options the user might not have considered
- Always weigh price, stops, duration, and departure times alongside carrier preference

You MUST respond with valid JSON only — no markdown, no backticks, no extra text.
"""
        
        super().__init__(
            name="FlightAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="FlightAgent",
            system_message=system_message,
            description="Searches flights and provides personalized recommendations",
            **kwargs
        )
        
        # Storage
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        
        # API services
        self.amadeus_service = get_amadeus_service()
        self.airport_lookup = get_airport_lookup_service()
        
        log_agent_raw("✈️ FlightAgent initialized (REAL API MODE)", agent_name="FlightAgent")

    # ─────────────────────────────────────────────────────────────────────
    # v7: GRANULAR STATUS UPDATES
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, message: str) -> None:
        """
        Send a granular status message to the frontend via trip_storage.
        
        v7: The PlanningStatus component polls these messages and displays
        them color-coded per agent (e.g. Flight Agent = red).
        
        Messages are stored in Redis alongside the agent's status field
        so the frontend poll picks them up in real time.
        """
        try:
            self.trip_storage.update_agent_status_message(
                trip_id=self.trip_id,
                agent_name="flight",
                message=message
            )
            log_agent_raw(f"📡 Status → {message}", agent_name="FlightAgent")
        except Exception as e:
            # Status updates are non-critical — don't break the workflow
            log_agent_raw(f"⚠️ Status update failed: {str(e)}", agent_name="FlightAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """
        Generate reply: Call API, store options, return recommendation.

        v7: Granular status updates at every workflow step.
        v6: Wide search + LLM curation:
          1. Single API call for 50 results (no carrier filter)
          2. Deduplicate codeshares by route fingerprint
          3. Tag all flights as [PREFERRED], [INTERESTED], [ALTERNATIVE]
          4. LLM curates top N diverse options + picks #1 recommendation
          5. Only curated flights stored for frontend display
        """
        log_agent_raw("🔍 FlightAgent processing request...", agent_name="FlightAgent")
        
        # v7: Initial status
        self._update_status("Initializing flight search...")
        
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
        
        # ✅ Get preferences from storage
        self._update_status("Loading travel preferences...")
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="FlightAgent")
            self._update_status("Error: preferences not found")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences from storage for trip {self.trip_id}", 
                     agent_name="FlightAgent")
        
        # ✅ Build search parameters from structured preferences object
        search_params = {
            "origin": preferences.origin,
            "destination": preferences.destination,
            "departure_date": preferences.departure_date,
            "return_date": preferences.return_date,
            "cabin_class": preferences.flight_prefs.cabin_class.upper(),
            "num_travelers": preferences.num_travelers,
            "budget": preferences.budget.flight_budget,
            "max_stops": preferences.flight_prefs.max_stops
        }
        
        log_agent_json(search_params, label="Flight Search Parameters (from storage)", 
                      agent_name="FlightAgent")
        
        try:
            # Step 1: Resolve city names to airport codes
            self._update_status(
                f"Resolving airports for {search_params['origin']} → {search_params['destination']}..."
            )
            
            origin_code = self._resolve_location(search_params["origin"])
            destination_code = self._resolve_location(search_params["destination"])
            
            if not origin_code or not destination_code:
                error_msg = "Could not resolve origin or destination to airport code"
                log_agent_raw(f"❌ {error_msg}", agent_name="FlightAgent")
                self._update_status("Error: could not resolve airports")
                return f"I'm sorry, I couldn't find the airport for your route. Please use airport codes like JFK, LAX, LHR."
            
            log_agent_raw(f"✓ Resolved: {search_params['origin']} → {origin_code}, {search_params['destination']} → {destination_code}", 
                         agent_name="FlightAgent")
            
            # v7: Status with resolved codes
            self._update_status(f"Airports resolved: {origin_code} → {destination_code}")
            
            # ── v5: Resolve carrier preferences to IATA codes ────────────
            preferred_carriers = preferences.flight_prefs.preferred_carriers or []
            interested_carriers = preferences.flight_prefs.interested_carriers or []
            all_carrier_names = preferred_carriers + interested_carriers

            preferred_codes = _resolve_carrier_codes(preferred_carriers)
            interested_codes = _resolve_carrier_codes(interested_carriers)
            all_carrier_codes = list(dict.fromkeys(preferred_codes + interested_codes))  # dedup, order preserved

            log_agent_json({
                "preferred_carriers": preferred_carriers,
                "preferred_codes": preferred_codes,
                "interested_carriers": interested_carriers,
                "interested_codes": interested_codes,
                "all_carrier_codes": all_carrier_codes,
            }, label="Carrier Preference Resolution", agent_name="FlightAgent")

            # ── v5: nonStop flag ─────────────────────────────────────────
            non_stop = True if search_params["max_stops"] == 0 else None

            # ── v6: Wide search + LLM curation ────────────────────────────
            display_max = settings.flight_agent_max_results
            WIDE_SEARCH_MAX = display_max * 5

            start_time = time.time()

            # v7: Status — searching with count
            self._update_status(
                f"Fetching up to {WIDE_SEARCH_MAX} flight offers from {origin_code} to {destination_code}..."
            )

            log_agent_raw(
                f"🔍 Fetching up to {WIDE_SEARCH_MAX} flights for deduplication pool",
                agent_name="FlightAgent"
            )
            raw_flights = self._search_flights_api(
                origin=origin_code,
                destination=destination_code,
                departure_date=search_params["departure_date"],
                return_date=search_params["return_date"],
                adults=search_params["num_travelers"],
                cabin_class=search_params["cabin_class"],
                included_airlines=None,   # no filter — widest net
                non_stop=non_stop,
                max_override=WIDE_SEARCH_MAX,
            )

            # v7: Status — raw results received
            self._update_status(f"Found {len(raw_flights)} flight offers")

            # ── Deduplicate codeshares by route fingerprint ──────────────
            self._update_status(f"Deduplicating {len(raw_flights)} codeshare flights...")

            all_flights: List[Flight] = []
            seen_ids: set = set()
            seen_routes: Dict[str, int] = {}  # fingerprint → index
            codeshare_dupes = 0

            for f in raw_flights:
                if f.id in seen_ids:
                    continue
                fp = self._flight_fingerprint(f)
                if fp in seen_routes:
                    # Same physical route — keep the preferred-carrier version
                    existing_idx = seen_routes[fp]
                    existing = all_flights[existing_idx]
                    existing_tag = self._tag_flight(existing, preferred_codes, interested_codes)
                    new_tag = self._tag_flight(f, preferred_codes, interested_codes)

                    # Prefer: PREFERRED > INTERESTED > ALTERNATIVE
                    # Within same tier, prefer cheaper
                    tag_priority = {"[PREFERRED]": 0, "[INTERESTED]": 1, "[ALTERNATIVE]": 2}
                    existing_pri = tag_priority[existing_tag]
                    new_pri = tag_priority[new_tag]

                    if new_pri < existing_pri:
                        # log_agent_raw(
                        #     f"   🔄 Codeshare upgrade: {existing.airline} {existing_tag} → "
                        #     f"{f.airline} {new_tag} (same route)",
                        #     agent_name="FlightAgent"
                        # )
                        seen_ids.add(f.id)
                        all_flights[existing_idx] = f
                    elif new_pri == existing_pri and f.price < existing.price:
                        # log_agent_raw(
                        #     f"   🔄 Codeshare swap (cheaper): {existing.airline} ${existing.price:.2f} → "
                        #     f"{f.airline} ${f.price:.2f}",
                        #     agent_name="FlightAgent"
                        # )
                        seen_ids.add(f.id)
                        all_flights[existing_idx] = f
                    # else:
                        # log_agent_raw(
                        #     f"   🔗 Codeshare skip: {f.airline} ({f.airline_code}) "
                        #     f"= same route as {existing.airline} ({existing.airline_code})",
                        #     agent_name="FlightAgent"
                        # )
                    codeshare_dupes += 1
                else:
                    seen_ids.add(f.id)
                    seen_routes[fp] = len(all_flights)
                    all_flights.append(f)

            api_duration = time.time() - start_time

            # v7: Status — dedup complete
            self._update_status(
                f"{len(all_flights)} unique flights after deduplication "
                f"({codeshare_dupes} codeshares removed)"
            )

            # ── Summary ──────────────────────────────────────────────────
            carrier_breakdown = {}
            for f in all_flights:
                tag = self._tag_flight(f, preferred_codes, interested_codes)
                key = f"{f.airline} ({f.airline_code}) {tag}"
                carrier_breakdown[key] = carrier_breakdown.get(key, 0) + 1

            # log_agent_json(
            #     carrier_breakdown,
            #     label="Deduped Flight Pool by Carrier",
            #     agent_name="FlightAgent"
            # )
            # log_agent_raw(
            #     f"✅ {len(raw_flights)} raw → {len(all_flights)} unique "
            #     f"({codeshare_dupes} codeshare dupes removed) in {api_duration:.2f}s",
            #     agent_name="FlightAgent"
            # )

            # Step 3: LLM curates top N from the full deduped pool
            # v7: Status — LLM curation starting
            self._update_status(
                f"AI selecting best {display_max} options from {len(all_flights)} flights..."
            )

            curated_flights, recommendation = self._curate_and_recommend(
                all_flights, preferences, preferred_codes, interested_codes, display_max
            )

            # v7: Status — curation complete
            self._update_status(
                f"Selected top {len(curated_flights)} flights with recommendation"
            )

            # Step 4: Store the curated flights in centralized storage
            self._update_status(f"Saving {len(curated_flights)} flight options...")

            flights_dict = [self._flight_to_dict(f) for f in curated_flights]

            self.trip_storage.add_flights(
                trip_id=self.trip_id,
                flights=flights_dict,
                metadata={
                    "origin": origin_code,
                    "origin_input": search_params["origin"],
                    "destination": destination_code,
                    "destination_input": search_params["destination"],
                    "departure_date": search_params["departure_date"],
                    "return_date": search_params["return_date"],
                    "search_time": datetime.now().isoformat(),
                    "total_results_from_api": len(raw_flights),
                    "after_dedup": len(all_flights),
                    "curated_for_display": len(curated_flights),
                    "preferred_carrier_results": len([
                        f for f in curated_flights if f.airline_code in preferred_codes
                    ]) if preferred_codes else 0,
                    "interested_carrier_results": len([
                        f for f in curated_flights if f.airline_code in interested_codes
                    ]) if interested_codes else 0,
                    "api_duration": api_duration,
                    "search_strategy": "wide_search_llm_curate",
                }
            )
            
            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="FlightAgent",
                api_name="Amadeus",
                duration=api_duration
            )
            
            log_agent_raw(f"💾 Stored {len(curated_flights)} curated flights in centralized storage "
                         f"(from {len(all_flights)} deduped / {len(raw_flights)} raw)", 
                         agent_name="FlightAgent")
            
            # v7: Final status
            self._update_status(
                f"Flight search complete — {len(curated_flights)} options ready"
            )
            
            # Log outgoing
            # self.log_conversation_message(
            #     message_type="OUTGOING",
            #     content=recommendation,
            #     sender="chat_manager",
            #     truncate=1000
            # )
            
            return self.signal_completion(recommendation) 
            
        except Exception as e:
            log_agent_raw(f"❌ Flight search failed: {str(e)}", agent_name="FlightAgent")
            self._update_status(f"Error: {str(e)[:80]}")
            error_msg = f"I encountered an error searching for flights: {str(e)}. Please try again or check your search parameters."
            return self.signal_completion(error_msg)
    
    def _search_flights_api(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        adults: int = 1,
        cabin_class: str = "ECONOMY",
        included_airlines: Optional[List[str]] = None,
        non_stop: Optional[bool] = None,
        max_override: Optional[int] = None,
    ) -> List[Flight]:
        """
        Call Amadeus API to search flights.

        v5 additions:
          included_airlines — list of IATA carrier codes to filter by
          non_stop           — if True, only direct flights (max_stops == 0)
          max_override       — override settings.flight_agent_max_results for this call
        """
        if not self.amadeus_service or not self.amadeus_service.client:
            log_agent_raw("⚠️ Amadeus not configured, using mock data", agent_name="FlightAgent")
            self._update_status("Amadeus API not configured — using sample data")
            return self._generate_mock_flights(origin, destination, departure_date)
        
        cabin_class_upper = cabin_class.upper()

        # ✅ Read max results — use override if provided, else centralized settings
        max_results = max_override if max_override is not None else settings.flight_agent_max_results
        
        api_params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": adults,
            "travelClass": cabin_class_upper,
            "max": max_results,
        }

        # v5: Optional carrier filter
        if included_airlines:
            api_params["includedAirlineCodes"] = ",".join(included_airlines)

        # v5: Optional nonStop filter
        if non_stop is True:
            api_params["nonStop"] = "true"

        log_agent_raw("=" * 80, agent_name="FlightAgent")
        log_agent_raw("📡 Calling Amadeus API with parameters:", agent_name="FlightAgent")
        log_agent_json(api_params, label="Amadeus API Request", agent_name="FlightAgent")
        log_agent_raw("=" * 80, agent_name="FlightAgent")

        # v7: Status — API call in progress
        self._update_status(
            f"Calling Amadeus API for {origin}→{destination} ({cabin_class_upper})..."
        )

        try:
            # Build kwargs dynamically so we only send params that are set
            search_kwargs = {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "returnDate": return_date,
                "adults": adults,
                "travelClass": cabin_class_upper,
                "max": max_results,
            }
            if included_airlines:
                search_kwargs["includedAirlineCodes"] = ",".join(included_airlines)
            if non_stop is True:
                search_kwargs["nonStop"] = "true"

            response = self.amadeus_service.client.shopping.flight_offers_search.get(
                **search_kwargs
            )
            
            log_agent_raw(f"✅ Amadeus API SUCCESS - Received {len(response.data)} offers", 
                        agent_name="FlightAgent")

            # v7: Status — parsing results
            self._update_status(f"Parsing {len(response.data)} flight offers...")

            flights = []
            for offer in response.data:
                # log_agent_json(offer, label="\n\nFlight Details from Amadeus: ", 
                #       agent_name="FlightAgent")

                flight = self._parse_amadeus_offer(offer)
                if flight:
                    flights.append(flight)
            
            # v7: Status — parsing complete
            self._update_status(f"Parsed {len(flights)} valid flight offers")
            
            return flights

        except Exception as e:
            log_agent_raw(f"❌ Amadeus API FAILED: {type(e).__name__}: {str(e)}", agent_name="FlightAgent")
            
            if hasattr(e, 'response'):
                log_agent_raw(f"Response Status: {getattr(e.response, 'status_code', 'N/A')}", 
                            agent_name="FlightAgent")
            
            # If the carrier-filtered search failed, return empty (Phase 2 will catch it)
            if included_airlines:
                log_agent_raw(
                    f"⚠️ Carrier-filtered search failed for {included_airlines} — "
                    f"returning empty (open search will cover this)",
                    agent_name="FlightAgent"
                )
                self._update_status(f"Carrier search failed for {','.join(included_airlines)}")
                return []

            log_agent_raw("⚠️ Falling back to mock data", agent_name="FlightAgent")
            self._update_status("API unavailable — using sample flight data")
            return self._generate_mock_flights(origin, destination, departure_date)
    

    # ─────────────────────────────────────────────────────────────────────
    # v4: RICH AMADEUS PARSING
    # ─────────────────────────────────────────────────────────────────────

    def _parse_amadeus_offer(self, offer: Any) -> Optional[Flight]:
        """
        Parse Amadeus flight offer into Flight object with rich metadata.
        
        v4: Now extracts per-segment details (terminals, aircraft, operating
        carrier), amenities, branded fare, booking metadata, and price breakdown.
        """
        try:
            itineraries = offer.get('itineraries', [])
            if not itineraries:
                return None
            
            is_round_trip = len(itineraries) == 2
            price_total = float(offer['price']['total'])
            price_base = float(offer['price'].get('base', 0))
            currency = offer['price']['currency']
            first_segment = itineraries[0]['segments'][0]
            airline_code = first_segment['carrierCode']

            # Fare details from first traveler
            traveler_pricings = offer.get('travelerPricings', [])
            fare_details: List[Dict] = []
            if traveler_pricings:
                fare_details = traveler_pricings[0].get('fareDetailsBySegment', [])

            # Cabin class + branded fare from first segment's fare detail
            cabin_class = 'ECONOMY'
            branded_fare = None
            if fare_details:
                cabin_class = fare_details[0].get('cabin', 'ECONOMY')
                branded_fare = (
                    fare_details[0].get('brandedFareLabel')
                    or fare_details[0].get('brandedFare')
                )

            # Baggage
            checked_bags, cabin_bags = self._parse_baggage(offer, cabin_class)

            # Amenities (merged + deduplicated across all segments)
            amenities = self._extract_amenities(fare_details)

            # Booking metadata
            last_ticketing_date = offer.get('lastTicketingDate')
            seats_remaining = offer.get('numberOfBookableSeats')
            validating_codes = offer.get('validatingAirlineCodes', [])
            validating_carrier = validating_codes[0] if validating_codes else None

            if is_round_trip:
                outbound = self._parse_flight_segment(itineraries[0], fare_details)
                return_flight = self._parse_flight_segment(itineraries[1], fare_details)
                total_duration = f"{outbound.duration} + {return_flight.duration}"
                
                return Flight(
                    id=offer['id'],
                    airline=outbound.airline,
                    airline_code=airline_code,
                    is_round_trip=True,
                    outbound=outbound,
                    return_flight=return_flight,
                    total_duration=total_duration,
                    price=price_total,
                    currency=currency,
                    cabin_class=cabin_class,
                    checked_bags=checked_bags,
                    cabin_bags=cabin_bags,
                    branded_fare=branded_fare,
                    amenities=amenities,
                    last_ticketing_date=last_ticketing_date,
                    seats_remaining=seats_remaining,
                    price_base=price_base,
                    price_taxes=round(price_total - price_base, 2),
                    validating_carrier=validating_carrier,
                )
            else:
                segment = self._parse_flight_segment(itineraries[0], fare_details)
                
                return Flight(
                    id=offer['id'],
                    airline=segment.airline,
                    airline_code=airline_code,
                    is_round_trip=False,
                    origin=segment.departure_airport,
                    destination=segment.arrival_airport,
                    departure_time=segment.departure_time,
                    arrival_time=segment.arrival_time,
                    duration=segment.duration,
                    flight_number=segment.flight_number,
                    stops=segment.stops,
                    layovers=segment.layovers,
                    price=price_total,
                    currency=currency,
                    cabin_class=cabin_class,
                    checked_bags=checked_bags,
                    cabin_bags=cabin_bags,
                    branded_fare=branded_fare,
                    amenities=amenities,
                    last_ticketing_date=last_ticketing_date,
                    seats_remaining=seats_remaining,
                    price_base=price_base,
                    price_taxes=round(price_total - price_base, 2),
                    validating_carrier=validating_carrier,
                )
        except Exception as e:
            log_agent_raw(f"⚠️ Failed to parse flight offer: {str(e)}", agent_name="FlightAgent")
            return None
    
    def _parse_flight_segment(
        self,
        itinerary: Dict,
        fare_details_by_segment: List[Dict]
    ) -> FlightSegment:
        """
        Parse a single itinerary leg into FlightSegment with per-hop details.
        
        v4: Now builds SegmentDetail[] for each hop and calculates layover
        durations between consecutive hops.
        """
        segments = itinerary['segments']
        first_segment = segments[0]
        last_segment = segments[-1]
        
        airline_code = first_segment['carrierCode']
        airline = AIRLINE_NAMES.get(airline_code, airline_code)
        flight_number = f"{airline_code}{first_segment['number']}"
        duration = itinerary['duration']
        duration_formatted = self._format_duration(duration)
        layovers = [seg['arrival']['iataCode'] for seg in segments[:-1]]

        # v4: Per-hop details
        segment_details = self._parse_segment_details(segments, fare_details_by_segment)

        # v4: Layover durations between consecutive hops
        layover_durations = []
        for i in range(len(segments) - 1):
            arr_time = segments[i]['arrival']['at']
            dep_time = segments[i + 1]['departure']['at']
            layover_durations.append(self._calc_layover_duration(arr_time, dep_time))
        
        return FlightSegment(
            departure_airport=first_segment['departure']['iataCode'],
            arrival_airport=last_segment['arrival']['iataCode'],
            departure_time=first_segment['departure']['at'],
            arrival_time=last_segment['arrival']['at'],
            duration=duration_formatted,
            airline=airline,
            airline_code=airline_code,
            flight_number=flight_number,
            stops=len(segments) - 1,
            layovers=layovers,
            segments=segment_details,
            layover_durations=layover_durations,
        )

    def _parse_segment_details(
        self,
        segments: List[Dict],
        fare_details_by_segment: List[Dict]
    ) -> List[SegmentDetail]:
        """
        Parse each physical hop into a SegmentDetail, merging fare info
        from travelerPricings[].fareDetailsBySegment[].
        """
        # Build lookup: segment_id → fare detail
        fare_lookup: Dict[str, Dict] = {}
        for fd in fare_details_by_segment:
            fare_lookup[str(fd.get('segmentId', ''))] = fd

        details = []
        for seg in segments:
            seg_id = str(seg.get('id', ''))
            fare = fare_lookup.get(seg_id, {})
            aircraft_code = seg.get('aircraft', {}).get('code')

            operating = seg.get('operating', {})
            operating_code = operating.get('carrierCode')
            operating_name = operating.get('carrierName')

            detail = SegmentDetail(
                segment_id=seg_id,
                departure_airport=seg['departure']['iataCode'],
                arrival_airport=seg['arrival']['iataCode'],
                departure_time=seg['departure']['at'],
                arrival_time=seg['arrival']['at'],
                departure_terminal=seg['departure'].get('terminal'),
                arrival_terminal=seg['arrival'].get('terminal'),
                duration=self._format_duration(seg.get('duration', 'PT0M')),
                marketing_carrier=seg['carrierCode'],
                marketing_flight_number=f"{seg['carrierCode']}{seg['number']}",
                operating_carrier=operating_code,
                operating_carrier_name=operating_name,
                aircraft_code=aircraft_code,
                aircraft_name=AIRCRAFT_NAMES.get(aircraft_code) if aircraft_code else None,
                cabin_class=fare.get('cabin'),
                branded_fare=fare.get('brandedFareLabel') or fare.get('brandedFare'),
                fare_class=fare.get('class'),
            )
            details.append(detail)

        return details

    def _extract_amenities(self, fare_details_by_segment: List[Dict]) -> List[FlightAmenity]:
        """
        Merge amenities across all segments, deduplicate by description.
        Returns a unique list of amenities with chargeable flag.
        """
        seen: set = set()
        amenities: List[FlightAmenity] = []
        for fd in fare_details_by_segment:
            for am in fd.get('amenities', []):
                desc = am.get('description', '')
                if desc and desc not in seen:
                    seen.add(desc)
                    amenities.append(FlightAmenity(
                        description=desc,
                        is_chargeable=am.get('isChargeable', True),
                        amenity_type=am.get('amenityType', 'OTHER'),
                    ))
        return amenities

    def _calc_layover_duration(self, arrival_time: str, next_departure_time: str) -> str:
        """Calculate layover time between two consecutive segments."""
        try:
            arr = datetime.fromisoformat(arrival_time)
            dep = datetime.fromisoformat(next_departure_time)
            diff = dep - arr
            total_minutes = int(diff.total_seconds() / 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}h {minutes}m"
        except Exception:
            return "—"

    def _parse_baggage(self, offer: Dict, cabin_class: str) -> tuple:
        """
        Parse baggage allowances from Amadeus offer.
        Returns (checked_bags, cabin_bags).
        
        v4: Also reads includedCabinBags quantity from fare details.
        """
        checked_bags = None
        cabin_bags = None
        
        try:
            traveler_pricings = offer.get('travelerPricings', [])
            if traveler_pricings:
                fare_detail = traveler_pricings[0].get('fareDetailsBySegment', [])
                if fare_detail and len(fare_detail) > 0:
                    segment_details = fare_detail[0]
                    
                    # Checked bags
                    checked_allowance = segment_details.get('includedCheckedBags')
                    if checked_allowance and isinstance(checked_allowance, dict):
                        quantity = checked_allowance.get('quantity')
                        weight = checked_allowance.get('weight')
                        if quantity is not None or weight:
                            checked_bags = {
                                "quantity": quantity if quantity else 0,
                                "weight": weight,
                                "weight_unit": checked_allowance.get('weightUnit', 'KG')
                            }
                    
                    # Cabin bags — read from fare detail if available
                    cabin_included = segment_details.get('includedCabinBags')
                    if cabin_included and isinstance(cabin_included, dict):
                        cabin_qty = cabin_included.get('quantity', 1)
                    else:
                        cabin_qty = 2 if cabin_class.upper() in ('BUSINESS', 'FIRST') else 1

                    cabin_wt = 16 if cabin_class.upper() in ('BUSINESS', 'FIRST') else 8
                    cabin_bags = {"quantity": cabin_qty, "weight": cabin_wt, "weight_unit": "KG"}

        except Exception as e:
            log_agent_raw(f"⚠️ Could not parse baggage info: {str(e)}", agent_name="FlightAgent")
            cabin_bags = {"quantity": 1, "weight": 8, "weight_unit": "KG"}
        
        return checked_bags, cabin_bags

    def _format_duration(self, duration: str) -> str:
        """Convert PT7H30M to '7h 30m'"""
        hours = re.search(r'(\d+)H', duration)
        minutes = re.search(r'(\d+)M', duration)
        h = hours.group(1) if hours else "0"
        m = minutes.group(1) if minutes else "0"
        return f"{h}h {m}m"


    # ─────────────────────────────────────────────────────────────────────
    # v5: CARRIER TAGGING
    # ─────────────────────────────────────────────────────────────────────

    def _tag_flight(
        self,
        flight: Flight,
        preferred_codes: List[str],
        interested_codes: List[str]
    ) -> str:
        """
        Tag a flight based on how its carrier matches user preferences.

        Returns one of:
          "[PREFERRED]"   — carrier is in user's priority list
          "[INTERESTED]"  — carrier is in user's interested list
          "[ALTERNATIVE]" — carrier was not specified by the user
        """
        code = flight.airline_code
        if code in preferred_codes:
            return "[PREFERRED]"
        elif code in interested_codes:
            return "[INTERESTED]"
        else:
            return "[ALTERNATIVE]"


    # ─────────────────────────────────────────────────────────────────────
    # LLM-DRIVEN CURATION + RECOMMENDATION (v6)
    # ─────────────────────────────────────────────────────────────────────

    def _curate_and_recommend(
        self,
        all_flights: List[Flight],
        preferences: Any,
        preferred_codes: List[str],
        interested_codes: List[str],
        display_max: int,
    ) -> tuple:
        """
        v6: LLM curates the best N flights from a wide deduped pool AND
        picks the #1 recommendation in a single call.

        v7: Granular status updates during curation.

        Returns:
            (curated_flights: List[Flight], recommendation_text: str)
        """
        if not all_flights:
            self._update_status("No flights found for this route")
            return ([], "I couldn't find any flights for your route. Please check your dates and try again.")

        # If the pool is already small enough, skip curation — just recommend
        if len(all_flights) <= display_max:
            log_agent_raw(
                f"ℹ️ Pool ({len(all_flights)}) ≤ display_max ({display_max}), "
                f"skipping curation — using _generate_recommendation directly",
                agent_name="FlightAgent"
            )
            self._update_status(
                f"Analyzing {len(all_flights)} flights for best recommendation..."
            )
            recommendation = self._generate_recommendation(
                all_flights, preferences, preferred_codes, interested_codes
            )
            return (all_flights, recommendation)

        flights_table = self._build_flights_table(all_flights, preferred_codes, interested_codes)
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(f.id) for f in all_flights]

        preferred_count = sum(1 for f in all_flights if f.airline_code in preferred_codes)
        interested_count = sum(1 for f in all_flights if f.airline_code in interested_codes)
        alternative_count = len(all_flights) - preferred_count - interested_count

        # v7: Status — LLM curation with breakdown
        self._update_status(
            f"AI reviewing {len(all_flights)} flights "
            f"({preferred_count} preferred, {interested_count} interested, "
            f"{alternative_count} alternatives)..."
        )

        prompt = f"""You are reviewing {len(all_flights)} flight options to curate the best {display_max} for the user.

ALL AVAILABLE FLIGHTS:
{flights_table}

Flight breakdown: {preferred_count} from preferred airlines, {interested_count} from interested airlines, {alternative_count} alternatives

USER PREFERENCES:
{prefs_summary}

YOUR TASK:
Select the top {display_max} flights that give the user the best set of OPTIONS to choose from,
then pick your #1 recommendation from those {display_max}.

SELECTION CRITERIA (in priority order):
1. CARRIER DIVERSITY: Include flights from each [PREFERRED] carrier if available.
   Then include [INTERESTED] carriers. Fill remaining slots with [ALTERNATIVE] carriers
   that offer meaningfully better price/timing/routing.
2. AVOID NEAR-DUPLICATES: Don't select multiple flights from the same carrier with
   similar price and timing. Pick the best variant from each carrier.
3. PRICE RANGE: Include a mix — some premium options from preferred carriers AND
   budget-friendly alternatives so the user can compare value.
4. SCHEDULE VARIETY: Include different departure times when possible (morning vs evening).
5. ROUTING VARIETY: Prefer different connection points over same layover city.

RECOMMENDATION CRITERIA for picking #1:
- [PREFERRED] airlines get priority if budget/stops are acceptable
- [INTERESTED] airlines are good second choices
- [ALTERNATIVE] flights are worth recommending if significantly cheaper or better-timed

Respond with ONLY valid JSON:
{{
  "selected_ids": [<exactly {display_max} flight IDs from the list above, as strings>],
  "recommended_id": "<your #1 pick from the selected IDs>",
  "reason": "<1-2 sentences: why this is the best match>",
  "summary": "<3-4 sentence user-facing recommendation. Open by stating how many flights you reviewed (use the exact number from above), then explain WHY you picked this flight — explain what makes it the best fit for this user's specific preferences (e.g. it's from a preferred airline, best price-to-quality ratio, fewest stops, ideal departure time, matches their budget). Then give specifics: airline name, departure time, price, and connection city. Finally, name 1-2 concrete alternatives from DIFFERENT airlines with their price and what trade-off they offer. NEVER mention flight IDs. NEVER repeat the same airline as both pick and alternative.>"
}}

CRITICAL RULES:
- selected_ids MUST contain exactly {display_max} IDs (or fewer if less are available)
- ALL IDs must be from this list: {valid_ids}
- recommended_id MUST be one of the selected_ids
- Respond with valid JSON only. No markdown, no backticks, no extra text.
"""

        log_agent_raw(
            f"🤖 Asking LLM to curate top {display_max} from {len(all_flights)} flights...",
            agent_name="FlightAgent"
        )

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
            # log_agent_raw(f"📥 LLM curation response: {raw_response}", agent_name="FlightAgent")

            result = self._parse_llm_json(raw_response)

            if not result or "selected_ids" not in result:
                # log_agent_raw("⚠️ Failed to parse curation JSON, using fallback", agent_name="FlightAgent")
                self._update_status("AI curation parse failed — using smart fallback...")
                return self._fallback_curate_and_recommend(
                    all_flights, preferences, preferred_codes, interested_codes, display_max
                )

            # ── Validate and collect selected flights ────────────────
            selected_ids = [str(sid) for sid in result["selected_ids"]]
            recommended_id = str(result.get("recommended_id", ""))
            reason = result.get("reason", "Best overall match")
            summary = result.get("summary", "")

            # Filter to valid IDs only
            valid_selected = [sid for sid in selected_ids if sid in valid_ids]
            if not valid_selected:
                # log_agent_raw("⚠️ No valid IDs in LLM selection, using fallback", agent_name="FlightAgent")
                self._update_status("AI returned invalid selections — using smart fallback...")
                return self._fallback_curate_and_recommend(
                    all_flights, preferences, preferred_codes, interested_codes, display_max
                )

            # Build curated flight list preserving LLM's order
            id_to_flight = {str(f.id): f for f in all_flights}
            curated = [id_to_flight[sid] for sid in valid_selected if sid in id_to_flight]

            # Validate recommended_id is in the curated set
            curated_ids = [str(f.id) for f in curated]
            if recommended_id not in curated_ids:
                # log_agent_raw(
                #     f"⚠️ recommended_id '{recommended_id}' not in curated set, using first",
                #     agent_name="FlightAgent"
                # )
                recommended_id = curated_ids[0]
                reason = "Best option from curated selection"

            recommended_flight = id_to_flight[recommended_id]

            # v7: Status — curation success
            self._update_status(
                f"AI selected {len(curated)} flights — "
                f"top pick: {recommended_flight.airline} at ${recommended_flight.price:.0f}"
            )

            # ── Log carrier diversity in curated set ─────────────────
            curated_carriers = {}
            for f in curated:
                tag = self._tag_flight(f, preferred_codes, interested_codes)
                key = f"{f.airline} ({f.airline_code}) {tag}"
                curated_carriers[key] = curated_carriers.get(key, 0) + 1

            # log_agent_json(
            #     curated_carriers,
            #     label=f"LLM Curated Top {len(curated)} — Carrier Diversity",
            #     agent_name="FlightAgent"
            # )

            # ── Store recommendation ─────────────────────────────────
            is_direct = self._is_direct_flight(recommended_flight)
            tag = self._tag_flight(recommended_flight, preferred_codes, interested_codes)

            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="flight",
                recommended_id=recommended_id,
                reason=summary or reason,
                metadata={
                    "airline": recommended_flight.airline,
                    "airline_code": recommended_flight.airline_code,
                    "price": recommended_flight.price,
                    "is_direct": is_direct,
                    "carrier_match": tag,
                    "reason_short": reason,
                    "total_pool_reviewed": len(all_flights),
                    "curated_count": len(curated),
                    "preferred_in_curated": sum(1 for f in curated if f.airline_code in preferred_codes),
                    "interested_in_curated": sum(1 for f in curated if f.airline_code in interested_codes),
                }
            )

            log_agent_raw(
                f"⭐ LLM curated {len(curated)} flights, picked #{recommended_id} {tag} "
                f"({recommended_flight.airline} ${recommended_flight.price:.2f}): {reason}",
                agent_name="FlightAgent"
            )

            recommendation_text = summary if summary else (
                f"I recommend flight {recommended_id} by {recommended_flight.airline}. {reason}"
            )
            return (curated, recommendation_text)

        except Exception as e:
            log_agent_raw(f"⚠️ LLM curation failed: {str(e)}", agent_name="FlightAgent")
            self._update_status("AI curation error — using smart fallback...")
            return self._fallback_curate_and_recommend(
                all_flights, preferences, preferred_codes, interested_codes, display_max
            )

    def _fallback_curate_and_recommend(
        self,
        all_flights: List[Flight],
        preferences: Any,
        preferred_codes: List[str],
        interested_codes: List[str],
        display_max: int,
    ) -> tuple:
        """
        Fallback curation when LLM fails: deterministic carrier-diverse selection.
        Picks flights round-robin by preference tier, cheapest within each carrier.
        """
        log_agent_raw("🔧 Using fallback curation (deterministic)", agent_name="FlightAgent")
        self._update_status(f"Selecting top {display_max} flights by carrier diversity...")

        # Group by carrier code, sorted by price within each
        from collections import defaultdict
        by_carrier: Dict[str, List[Flight]] = defaultdict(list)
        for f in sorted(all_flights, key=lambda x: x.price):
            by_carrier[f.airline_code].append(f)

        # Priority order: preferred carriers first, then interested, then others
        preferred_carrier_list = [c for c in preferred_codes if c in by_carrier]
        interested_carrier_list = [c for c in interested_codes if c in by_carrier]
        other_carrier_list = [c for c in by_carrier if c not in preferred_codes and c not in interested_codes]

        curated = []
        seen_carrier_count: Dict[str, int] = defaultdict(int)

        # Round-robin: preferred → interested → alternatives
        for carrier_group in [preferred_carrier_list, interested_carrier_list, other_carrier_list]:
            for code in carrier_group:
                for f in by_carrier[code]:
                    if len(curated) >= display_max:
                        break
                    if seen_carrier_count[code] < 2:  # max 2 per carrier
                        curated.append(f)
                        seen_carrier_count[code] += 1
                if len(curated) >= display_max:
                    break
            if len(curated) >= display_max:
                break

        # If still under display_max, fill with cheapest remaining
        curated_ids = {str(f.id) for f in curated}
        for f in sorted(all_flights, key=lambda x: x.price):
            if len(curated) >= display_max:
                break
            if str(f.id) not in curated_ids:
                curated.append(f)
                curated_ids.add(str(f.id))

        # Pick recommendation: cheapest preferred > cheapest interested > cheapest overall
        preferred_curated = [f for f in curated if f.airline_code in preferred_codes]
        interested_curated = [f for f in curated if f.airline_code in interested_codes]

        if preferred_curated:
            pick = sorted(preferred_curated, key=lambda f: f.price)[0]
        elif interested_curated:
            pick = sorted(interested_curated, key=lambda f: f.price)[0]
        else:
            pick = sorted(curated, key=lambda f: f.price)[0]

        tag = self._tag_flight(pick, preferred_codes, interested_codes)

        self.trip_storage.store_recommendation(
            trip_id=self.trip_id,
            category="flight",
            recommended_id=str(pick.id),
            reason=f"Fallback: best price from {tag} carriers",
            metadata={
                "airline": pick.airline,
                "airline_code": pick.airline_code,
                "price": pick.price,
                "is_direct": self._is_direct_flight(pick),
                "carrier_match": tag,
                "total_pool_reviewed": len(all_flights),
                "curated_count": len(curated),
                "is_fallback": True
            }
        )

        # log_agent_raw(
        #     f"⭐ Fallback curated {len(curated)} flights, picked #{pick.id} {tag} "
        #     f"({pick.airline} ${pick.price:.2f})",
        #     agent_name="FlightAgent"
        # )

        # v7: Status
        self._update_status(
            f"Selected {len(curated)} flights — top pick: {pick.airline} at ${pick.price:.0f}"
        )

        summary = (
            f"I reviewed {len(all_flights)} flights and selected the top {len(curated)} options. "
            f"My top pick is {pick.airline} at ${pick.price:.2f} — "
            f"the most affordable option from your {'preferred' if tag == '[PREFERRED]' else 'available'} airlines."
        )
        return (curated, summary)


    # ─────────────────────────────────────────────────────────────────────
    # LEGACY: Single-flight recommendation (used when pool ≤ display_max)
    # ─────────────────────────────────────────────────────────────────────

    def _build_flights_table(
        self,
        flights: List[Flight],
        preferred_codes: List[str],
        interested_codes: List[str]
    ) -> str:
        """
        Build a compact text table of all flights for the LLM prompt.
        v5: Each row is tagged with [PREFERRED], [INTERESTED], or [ALTERNATIVE].
        """
        rows = []
        for f in flights:
            tag = self._tag_flight(f, preferred_codes, interested_codes)

            if f.is_round_trip and f.outbound and f.return_flight:
                rows.append(
                    f"{tag} ID: {f.id} | {f.airline} ({f.airline_code}) | ${f.price:.2f} | "
                    f"Out: {f.outbound.departure_airport}→{f.outbound.arrival_airport} "
                    f"{f.outbound.departure_time} ({f.outbound.duration}, {f.outbound.stops} stops"
                    f"{', via ' + ','.join(f.outbound.layovers) if f.outbound.layovers else ''}) | "
                    f"Return: {f.return_flight.departure_airport}→{f.return_flight.arrival_airport} "
                    f"{f.return_flight.departure_time} ({f.return_flight.duration}, {f.return_flight.stops} stops"
                    f"{', via ' + ','.join(f.return_flight.layovers) if f.return_flight.layovers else ''})"
                )
            else:
                rows.append(
                    f"{tag} ID: {f.id} | {f.airline} ({f.airline_code}) {f.flight_number} | ${f.price:.2f} | "
                    f"{f.origin}→{f.destination} {f.departure_time} "
                    f"({f.duration}, {f.stops} stops)"
                )
        return "\n".join(rows)

    def _build_preferences_summary(self, preferences: Any) -> str:
        """
        Build a readable summary of user preferences for the LLM.
        v5: Now includes interested_carriers for complete picture.
        """
        lines = []
        lines.append(f"Flight budget: ${preferences.budget.flight_budget}")
        lines.append(f"Cabin class: {preferences.flight_prefs.cabin_class}")
        lines.append(f"Max stops: {preferences.flight_prefs.max_stops}")
        
        if hasattr(preferences.flight_prefs, 'time_preference'):
            lines.append(f"Time preference: {preferences.flight_prefs.time_preference}")
        
        # v5: Show both preferred and interested carriers
        if hasattr(preferences.flight_prefs, 'preferred_carriers') and preferences.flight_prefs.preferred_carriers:
            lines.append(f"⭐ Preferred airlines (priority): {', '.join(preferences.flight_prefs.preferred_carriers)}")
        
        if hasattr(preferences.flight_prefs, 'interested_carriers') and preferences.flight_prefs.interested_carriers:
            lines.append(f"☆ Interested airlines (good alternatives): {', '.join(preferences.flight_prefs.interested_carriers)}")
        
        if not (preferences.flight_prefs.preferred_carriers or preferences.flight_prefs.interested_carriers):
            lines.append("Airlines: No preference (open to all)")

        if hasattr(preferences.flight_prefs, 'seat_preference'):
            lines.append(f"Seat preference: {preferences.flight_prefs.seat_preference}")
        
        lines.append(f"Trip purpose: {preferences.trip_purpose}")
        lines.append(f"Travelers: {preferences.num_travelers}")
        
        return "\n".join(lines)

    def _parse_llm_json(self, text: str) -> Optional[Dict]:
        """
        Safely parse JSON from LLM response.
        Strips markdown fences and handles common LLM formatting issues.
        Handles nested objects and arrays (e.g. selected_ids: [...]).
        """
        # Strip markdown code fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find a JSON object (including nested braces/brackets)
            # Match from first { to last }
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    pass
        
        return None

    def _generate_recommendation(
        self,
        flights: List[Flight],
        preferences: Any,
        preferred_codes: List[str],
        interested_codes: List[str],
    ) -> str:
        """
        LLM picks the best flight based on user preferences.
        
        v5: Flights are tagged and LLM sees full carrier preference context.
        v7: Granular status updates.
        Returns the conversational summary. The recommended_id is stored
        in centralized storage for the frontend to consume.
        """
        if not flights:
            return "I couldn't find any flights for your route. Please check your dates and try again."
        
        # Build the prompt with tagged flights
        flights_table = self._build_flights_table(flights, preferred_codes, interested_codes)
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(f.id) for f in flights]

        # Count by tag for context
        preferred_count = sum(1 for f in flights if f.airline_code in preferred_codes)
        interested_count = sum(1 for f in flights if f.airline_code in interested_codes)
        alternative_count = len(flights) - preferred_count - interested_count

        # v7: Status
        self._update_status(
            f"AI picking best flight from {len(flights)} options..."
        )
        
        prompt = f"""Here are the available flights:

{flights_table}

Flight breakdown: {preferred_count} from preferred airlines, {interested_count} from interested airlines, {alternative_count} alternatives

User preferences:
{prefs_summary}

Pick the single best flight for this user. Consider their budget, airline preferences, 
time preferences, number of stops, and trip purpose.

Ranking guidance:
- Flights from [PREFERRED] airlines should be ranked highest if they meet budget and stop constraints
- Flights from [INTERESTED] airlines are good second choices
- [ALTERNATIVE] flights are valuable if they offer significantly better price, fewer stops, or better timing
- A much cheaper alternative is worth mentioning even if the user preferred a specific airline

You MUST respond with ONLY a JSON object in this exact format, nothing else:
{{
  "recommended_id": "<the flight ID from the list above>",
  "reason": "<1-2 sentences explaining why this is the best match for this user's preferences>",
  "summary": "<3-4 sentence user-facing recommendation. Open by stating how many flights you reviewed (use the exact number from above), then explain WHY you picked this flight — explain what makes it the best fit for this user's specific preferences (e.g. it's from a preferred airline, best price-to-quality ratio, fewest stops, ideal departure time, matches their budget). Then give specifics: airline name, departure time, price, and connection city. Finally, name 1-2 concrete alternatives from DIFFERENT airlines with their price and what trade-off they offer. NEVER mention flight IDs. NEVER repeat the same airline as both pick and alternative.>"
}}

CRITICAL RULES:
- recommended_id MUST be one of these exact values: {valid_ids}
- Do NOT invent a flight ID. Pick from the list above.
- Respond with valid JSON only. No markdown, no backticks, no extra text.
"""
        
        log_agent_raw("🤖 Asking LLM to pick best flight based on preferences...", 
                     agent_name="FlightAgent")
        
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
            
            log_agent_raw(f"📥 LLM raw response: {raw_response}", agent_name="FlightAgent")
            
            # Parse the JSON
            result = self._parse_llm_json(raw_response)
            
            if not result:
                log_agent_raw("⚠️ Failed to parse LLM JSON, using fallback", agent_name="FlightAgent")
                self._update_status("AI parse failed — using smart fallback...")
                return self._fallback_recommendation(flights, preferences, preferred_codes, interested_codes)
            
            recommended_id = str(result.get("recommended_id", ""))
            reason = result.get("reason", "Best overall match")
            summary = result.get("summary", "")
            
            # Validate the ID exists in our flight list
            if recommended_id not in valid_ids:
                log_agent_raw(
                    f"⚠️ LLM returned invalid ID '{recommended_id}', "
                    f"valid IDs are {valid_ids}. Using fallback.",
                    agent_name="FlightAgent"
                )
                self._update_status("AI returned invalid selection — using smart fallback...")
                return self._fallback_recommendation(flights, preferences, preferred_codes, interested_codes)
            
            # Find the matching flight for metadata
            recommended_flight = next(f for f in flights if str(f.id) == recommended_id)
            
            # v7: Status — recommendation made
            self._update_status(
                f"Recommended: {recommended_flight.airline} at ${recommended_flight.price:.0f}"
            )
            
            # ✅ Store the recommendation
            is_direct = self._is_direct_flight(recommended_flight)
            tag = self._tag_flight(recommended_flight, preferred_codes, interested_codes)
            
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="flight",
                recommended_id=recommended_id,
                reason=summary or reason,
                metadata={
                    "airline": recommended_flight.airline,
                    "airline_code": recommended_flight.airline_code,
                    "price": recommended_flight.price,
                    "is_direct": is_direct,
                    "carrier_match": tag,
                    "reason_short": reason,
                    "total_options_reviewed": len(flights),
                    "preferred_options": preferred_count,
                    "interested_options": interested_count,
                    "alternative_options": alternative_count,
                }
            )
            
            log_agent_raw(
                f"⭐ LLM picked flight {recommended_id} {tag} "
                f"({recommended_flight.airline} ${recommended_flight.price:.2f}): {reason}",
                agent_name="FlightAgent"
            )
            
            return summary if summary else f"I recommend flight {recommended_id} by {recommended_flight.airline}. {reason}"
            
        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="FlightAgent")
            self._update_status("AI recommendation error — using smart fallback...")
            return self._fallback_recommendation(flights, preferences, preferred_codes, interested_codes)

    def _fallback_recommendation(
        self,
        flights: List[Flight],
        preferences: Any,
        preferred_codes: List[str],
        interested_codes: List[str],
    ) -> str:
        """
        Fallback when LLM fails: pick best preferred carrier flight,
        or cheapest if no preferred carriers match.

        v5: Prefers preferred > interested > cheapest alternative.
        """
        # Try preferred carriers first
        preferred_flights = [f for f in flights if f.airline_code in preferred_codes]
        interested_flights = [f for f in flights if f.airline_code in interested_codes]

        if preferred_flights:
            pick = sorted(preferred_flights, key=lambda f: f.price)[0]
            tag = "[PREFERRED]"
        elif interested_flights:
            pick = sorted(interested_flights, key=lambda f: f.price)[0]
            tag = "[INTERESTED]"
        else:
            pick = sorted(flights, key=lambda f: f.price)[0]
            tag = "[ALTERNATIVE]"

        self.trip_storage.store_recommendation(
            trip_id=self.trip_id,
            category="flight",
            recommended_id=str(pick.id),
            reason=f"Fallback: best price from {tag} carriers (LLM recommendation unavailable)",
            metadata={
                "airline": pick.airline,
                "airline_code": pick.airline_code,
                "price": pick.price,
                "is_direct": self._is_direct_flight(pick),
                "carrier_match": tag,
                "total_options_reviewed": len(flights),
                "is_fallback": True
            }
        )
        
        log_agent_raw(
            f"⭐ Fallback pick: flight {pick.id} {tag} ({pick.airline} ${pick.price:.2f})",
            agent_name="FlightAgent"
        )

        # v7: Status
        self._update_status(
            f"Fallback pick: {pick.airline} at ${pick.price:.0f}"
        )
        
        return (
            f"I found {len(flights)} flights for your route. "
            f"My top pick is {pick.airline} at ${pick.price:.2f} — "
            f"the most affordable option from your {'preferred' if tag == '[PREFERRED]' else 'available'} airlines."
        )

    def _is_direct_flight(self, flight: Flight) -> bool:
        """Check if a flight is direct (no stops on any leg)"""
        if flight.is_round_trip and flight.outbound and flight.return_flight:
            return flight.outbound.stops == 0 and flight.return_flight.stops == 0
        elif not flight.is_round_trip:
            return (flight.stops or 0) == 0
        return False

    def _flight_fingerprint(self, flight: Flight) -> str:
        """
        Generate a route-level fingerprint for codeshare deduplication.

        Two flights with the same fingerprint are the same physical journey
        (same aircraft, same times) just marketed under different carrier codes.
        """
        if flight.is_round_trip and flight.outbound and flight.return_flight:
            out = flight.outbound
            ret = flight.return_flight
            out_dep = str(out.departure_time)[:16]
            out_arr = str(out.arrival_time)[:16]
            ret_dep = str(ret.departure_time)[:16]
            ret_arr = str(ret.arrival_time)[:16]
            return (
                f"{out.departure_airport}|{out_dep}|{out.arrival_airport}|{out_arr}"
                f"||"
                f"{ret.departure_airport}|{ret_dep}|{ret.arrival_airport}|{ret_arr}"
            )
        else:
            dep = str(flight.departure_time)[:16]
            arr = str(flight.arrival_time)[:16]
            return f"{flight.origin}|{dep}|{flight.destination}|{arr}"


    # ─────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ─────────────────────────────────────────────────────────────────────

    def _resolve_location(self, location: str) -> Optional[str]:
        """Resolve city name to airport code"""
        if self.airport_lookup.validate_airport_code(location):
            return location
        
        airport_code = self.airport_lookup.convert_to_airport_code(location)
        
        if airport_code:
            log_agent_raw(f"   ✓ Converted '{location}' → {airport_code}", agent_name="FlightAgent")
        else:
            log_agent_raw(f"   ❌ Could not resolve '{location}'", agent_name="FlightAgent")
        
        return airport_code
    
    def _flight_to_dict(self, flight: Flight) -> Dict:
        """Convert Flight object to dict for storage"""
        return flight.model_dump(mode='json')
    
    def _generate_mock_flights(self, origin: str, dest: str, date: str) -> List[Flight]:
        """Generate mock flights when API is unavailable"""
        from datetime import timedelta
        
        dep_date = datetime.fromisoformat(date)
        
        return [
            Flight(
                id="FL001",
                airline="British Airways",
                airline_code="BA",
                is_round_trip=True,
                outbound=FlightSegment(
                    departure_airport=origin,
                    arrival_airport=dest,
                    departure_time=dep_date.replace(hour=8, minute=30),
                    arrival_time=dep_date.replace(hour=8, minute=30) + timedelta(hours=7),
                    duration="7h 0m",
                    airline="British Airways",
                    airline_code="BA",
                    flight_number="BA117",
                    stops=0,
                    layovers=[]
                ),
                return_flight=FlightSegment(
                    departure_airport=dest,
                    arrival_airport=origin,
                    departure_time=(dep_date + timedelta(days=5)).replace(hour=10, minute=0),
                    arrival_time=(dep_date + timedelta(days=5)).replace(hour=18, minute=30),
                    duration="8h 30m",
                    airline="British Airways",
                    airline_code="BA",
                    flight_number="BA118",
                    stops=0,
                    layovers=[]
                ),
                total_duration="7h 0m + 8h 30m",
                price=850,
                currency="USD",
                cabin_class="economy",
                checked_bags={"quantity": 1, "weight": 23, "weight_unit": "KG"},
                cabin_bags={"quantity": 1, "weight": 7, "weight_unit": "KG"}
            )
        ]


def create_flight_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> FlightAgent:
    """Factory function to create FlightAgent"""
    return FlightAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)