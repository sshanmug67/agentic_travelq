"""
Flight Agent - Real API with Centralized Storage
Location: backend/agents/flight_agent.py

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
    "AF": "Air France",
    "AY": "Finnair",
    "AZ": "ITA Airways",
    "BA": "British Airways",
    "EI": "Aer Lingus",
    "EW": "Eurowings",
    "FR": "Ryanair",
    "IB": "Iberia",
    "KL": "KLM Royal Dutch Airlines",
    "LH": "Lufthansa",
    "LO": "LOT Polish Airlines",
    "LX": "Swiss International Air Lines",
    "OS": "Austrian Airlines",
    "SK": "SAS Scandinavian Airlines",
    "SN": "Brussels Airlines",
    "TP": "TAP Air Portugal",
    "TK": "Turkish Airlines",
    "U2": "easyJet",
    "VY": "Vueling",
    "W6": "Wizz Air",
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


class FlightAgent(TravelQBaseAgent):
    """
    Flight Agent with real Amadeus API + centralized storage
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """You are a Flight Search Assistant that recommends flights based on user preferences.

You will be given:
1. A list of available flights with IDs, prices, airlines, stops, and times
2. The user's preferences (budget, preferred airlines, time preferences, cabin class, etc.)

Your job is to pick the BEST flight for this specific user and explain why.

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
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """
        Generate reply: Call API, store options, return recommendation
        """
        log_agent_raw("🔍 FlightAgent processing request...", agent_name="FlightAgent")
        
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
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="FlightAgent")
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
            origin_code = self._resolve_location(search_params["origin"])
            destination_code = self._resolve_location(search_params["destination"])
            
            if not origin_code or not destination_code:
                error_msg = "Could not resolve origin or destination to airport code"
                log_agent_raw(f"❌ {error_msg}", agent_name="FlightAgent")
                return f"I'm sorry, I couldn't find the airport for your route. Please use airport codes like JFK, LAX, LHR."
            
            log_agent_raw(f"✓ Resolved: {search_params['origin']} → {origin_code}, {search_params['destination']} → {destination_code}", 
                         agent_name="FlightAgent")
            
            # Step 2: Call Amadeus API
            start_time = time.time()
            
            flights = self._search_flights_api(
                origin=origin_code,
                destination=destination_code,
                departure_date=search_params["departure_date"],
                return_date=search_params["return_date"],
                adults=search_params["num_travelers"],
                cabin_class=search_params["cabin_class"]
            )
            
            api_duration = time.time() - start_time
            
            log_agent_raw(f"✅ API returned {len(flights)} flight options in {api_duration:.2f}s", 
                         agent_name="FlightAgent")

            # Step 3: Store ALL options in centralized storage
            flights_dict = [self._flight_to_dict(f) for f in flights]
            
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
                    "total_results": len(flights),
                    "api_duration": api_duration
                }
            )
            
            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="FlightAgent",
                api_name="Amadeus",
                duration=api_duration
            )
            
            log_agent_raw(f"💾 Stored {len(flights)} flights in centralized storage", 
                         agent_name="FlightAgent")
            
            # Step 4: LLM picks the best flight and explains why
            recommendation = self._generate_recommendation(flights, preferences)
            
            # Log outgoing
            self.log_conversation_message(
                message_type="OUTGOING",
                content=recommendation,
                sender="chat_manager",
                truncate=1000
            )
            
            return self.signal_completion(recommendation) 
            
        except Exception as e:
            log_agent_raw(f"❌ Flight search failed: {str(e)}", agent_name="FlightAgent")
            error_msg = f"I encountered an error searching for flights: {str(e)}. Please try again or check your search parameters."
            return self.signal_completion(error_msg)
    
    def _search_flights_api(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        adults: int = 1,
        cabin_class: str = "ECONOMY"
    ) -> List[Flight]:
        """
        Call Amadeus API to search flights
        """
        if not self.amadeus_service or not self.amadeus_service.client:
            log_agent_raw("⚠️ Amadeus not configured, using mock data", agent_name="FlightAgent")
            return self._generate_mock_flights(origin, destination, departure_date)
        
        cabin_class_upper = cabin_class.upper()

        # ✅ Read max results from centralized settings
        max_results = settings.flight_agent_max_results
        
        api_params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": adults,
            "travelClass": cabin_class_upper,
            "max": max_results
        }
        
        log_agent_raw("=" * 80, agent_name="FlightAgent")
        log_agent_raw("📡 Calling Amadeus API with parameters:", agent_name="FlightAgent")
        log_agent_json(api_params, label="Amadeus API Request", agent_name="FlightAgent")
        log_agent_raw("=" * 80, agent_name="FlightAgent")

        try:
            response = self.amadeus_service.client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date,
                returnDate=return_date,
                adults=adults,
                travelClass=cabin_class_upper,
                max=max_results
            )
            
            log_agent_raw(f"✅ Amadeus API SUCCESS - Received {len(response.data)} offers", 
                        agent_name="FlightAgent")

            flights = []
            for offer in response.data:
                log_agent_json(offer, label="\n\nFlight Details from Amadeus: ", 
                      agent_name="FlightAgent")

                flight = self._parse_amadeus_offer(offer)
                if flight:
                    flights.append(flight)
            
            return flights

        except Exception as e:
            log_agent_raw(f"❌ Amadeus API FAILED: {type(e).__name__}: {str(e)}", agent_name="FlightAgent")
            
            if hasattr(e, 'response'):
                log_agent_raw(f"Response Status: {getattr(e.response, 'status_code', 'N/A')}", 
                            agent_name="FlightAgent")
            
            log_agent_raw("⚠️ Falling back to mock data", agent_name="FlightAgent")
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
    # LLM-DRIVEN RECOMMENDATION
    # ─────────────────────────────────────────────────────────────────────

    def _build_flights_table(self, flights: List[Flight]) -> str:
        """
        Build a compact text table of all flights for the LLM prompt.
        Each row has the flight ID so the LLM can reference it.
        """
        rows = []
        for f in flights:
            if f.is_round_trip and f.outbound and f.return_flight:
                rows.append(
                    f"ID: {f.id} | {f.airline} | ${f.price:.2f} | "
                    f"Out: {f.outbound.departure_airport}→{f.outbound.arrival_airport} "
                    f"{f.outbound.departure_time} ({f.outbound.duration}, {f.outbound.stops} stops"
                    f"{', via ' + ','.join(f.outbound.layovers) if f.outbound.layovers else ''}) | "
                    f"Return: {f.return_flight.departure_airport}→{f.return_flight.arrival_airport} "
                    f"{f.return_flight.departure_time} ({f.return_flight.duration}, {f.return_flight.stops} stops"
                    f"{', via ' + ','.join(f.return_flight.layovers) if f.return_flight.layovers else ''})"
                )
            else:
                rows.append(
                    f"ID: {f.id} | {f.airline} {f.flight_number} | ${f.price:.2f} | "
                    f"{f.origin}→{f.destination} {f.departure_time} "
                    f"({f.duration}, {f.stops} stops)"
                )
        return "\n".join(rows)

    def _build_preferences_summary(self, preferences: Any) -> str:
        """
        Build a readable summary of user preferences for the LLM.
        """
        lines = []
        lines.append(f"Flight budget: ${preferences.budget.flight_budget}")
        lines.append(f"Cabin class: {preferences.flight_prefs.cabin_class}")
        lines.append(f"Max stops: {preferences.flight_prefs.max_stops}")
        
        if hasattr(preferences.flight_prefs, 'time_preference'):
            lines.append(f"Time preference: {preferences.flight_prefs.time_preference}")
        
        if hasattr(preferences.flight_prefs, 'preferred_carriers') and preferences.flight_prefs.preferred_carriers:
            lines.append(f"Preferred airlines: {', '.join(preferences.flight_prefs.preferred_carriers)}")
        
        if hasattr(preferences.flight_prefs, 'seat_preference'):
            lines.append(f"Seat preference: {preferences.flight_prefs.seat_preference}")
        
        lines.append(f"Trip purpose: {preferences.trip_purpose}")
        lines.append(f"Travelers: {preferences.num_travelers}")
        
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
        flights: List[Flight],
        preferences: Any
    ) -> str:
        """
        LLM picks the best flight based on user preferences.
        
        Returns the conversational summary. The recommended_id is stored
        in centralized storage for the frontend to consume.
        """
        if not flights:
            return "I couldn't find any flights for your route. Please check your dates and try again."
        
        # Build the prompt
        flights_table = self._build_flights_table(flights)
        prefs_summary = self._build_preferences_summary(preferences)
        valid_ids = [str(f.id) for f in flights]
        
        prompt = f"""Here are the available flights:

{flights_table}

User preferences:
{prefs_summary}

Pick the single best flight for this user. Consider their budget, preferred airlines, 
time preferences, number of stops, and trip purpose. Weigh the tradeoffs — a slightly 
more expensive direct flight may be better than a cheap one with 2 layovers for a 
business traveler, for example.

You MUST respond with ONLY a JSON object in this exact format, nothing else:
{{
  "recommended_id": "<the flight ID from the list above>",
  "reason": "<1-2 sentences explaining why this is the best match for this user's preferences>",
  "summary": "<3-4 sentence friendly recommendation mentioning how many options you reviewed, why you picked this one, and any notable alternatives>"
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
                return self._fallback_recommendation(flights, preferences)
            
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
                return self._fallback_recommendation(flights, preferences)
            
            # Find the matching flight for metadata
            recommended_flight = next(f for f in flights if str(f.id) == recommended_id)
            
            # ✅ Store the recommendation
            is_direct = self._is_direct_flight(recommended_flight)
            
            self.trip_storage.store_recommendation(
                trip_id=self.trip_id,
                category="flight",
                recommended_id=recommended_id,
                reason=reason,
                metadata={
                    "airline": recommended_flight.airline,
                    "price": recommended_flight.price,
                    "is_direct": is_direct,
                    "total_options_reviewed": len(flights)
                }
            )
            
            log_agent_raw(
                f"⭐ LLM picked flight {recommended_id} "
                f"({recommended_flight.airline} ${recommended_flight.price:.2f}): {reason}",
                agent_name="FlightAgent"
            )
            
            return summary if summary else f"I recommend flight {recommended_id} by {recommended_flight.airline}. {reason}"
            
        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="FlightAgent")
            return self._fallback_recommendation(flights, preferences)

    def _fallback_recommendation(self, flights: List[Flight], preferences: Any) -> str:
        """
        Fallback when LLM fails: pick cheapest flight, store it, return template.
        This is the safety net — not the primary path.
        """
        cheapest = sorted(flights, key=lambda f: f.price)[0]
        
        self.trip_storage.store_recommendation(
            trip_id=self.trip_id,
            category="flight",
            recommended_id=str(cheapest.id),
            reason="Fallback: lowest price (LLM recommendation unavailable)",
            metadata={
                "airline": cheapest.airline,
                "price": cheapest.price,
                "is_direct": self._is_direct_flight(cheapest),
                "total_options_reviewed": len(flights),
                "is_fallback": True
            }
        )
        
        log_agent_raw(
            f"⭐ Fallback pick: flight {cheapest.id} ({cheapest.airline} ${cheapest.price:.2f})",
            agent_name="FlightAgent"
        )
        
        return (
            f"I found {len(flights)} flights for your route. "
            f"My top pick is {cheapest.airline} at ${cheapest.price:.2f} — "
            f"the most affordable option available."
        )

    def _is_direct_flight(self, flight: Flight) -> bool:
        """Check if a flight is direct (no stops on any leg)"""
        if flight.is_round_trip and flight.outbound and flight.return_flight:
            return flight.outbound.stops == 0 and flight.return_flight.stops == 0
        elif not flight.is_round_trip:
            return (flight.stops or 0) == 0
        return False


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