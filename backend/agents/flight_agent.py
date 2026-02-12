"""
Flight Agent - Real API with Centralized Storage
Location: backend/agents/flight_agent.py

Changes (v3):
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
from models.trip import Flight, FlightSegment

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai

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
    

    def _parse_amadeus_offer(self, offer: Any) -> Optional[Flight]:
        """Parse Amadeus flight offer into Flight object (supports round-trip)"""
        try:
            itineraries = offer.get('itineraries', [])
            if not itineraries:
                return None
            
            is_round_trip = len(itineraries) == 2
            price = float(offer['price']['total'])
            currency = offer['price']['currency']
            first_segment = itineraries[0]['segments'][0]
            airline_code = first_segment['carrierCode']
            cabin_class = first_segment.get('cabin', 'ECONOMY')
            checked_bags, cabin_bags = self._parse_baggage(offer, cabin_class)
            
            if is_round_trip:
                outbound = self._parse_flight_segment(itineraries[0])
                return_flight = self._parse_flight_segment(itineraries[1])
                total_duration = f"{outbound.duration} + {return_flight.duration}"
                
                return Flight(
                    id=offer['id'],
                    airline=outbound.airline,
                    airline_code=airline_code,
                    is_round_trip=True,
                    outbound=outbound,
                    return_flight=return_flight,
                    total_duration=total_duration,
                    price=price,
                    currency=currency,
                    cabin_class=cabin_class,
                    checked_bags=checked_bags,
                    cabin_bags=cabin_bags
                )
            else:
                segment = self._parse_flight_segment(itineraries[0])
                
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
                    price=price,
                    currency=currency,
                    cabin_class=cabin_class,
                    checked_bags=checked_bags,
                    cabin_bags=cabin_bags
                )
        except Exception as e:
            log_agent_raw(f"⚠️ Failed to parse flight offer: {str(e)}", agent_name="FlightAgent")
            return None
    
    def _parse_flight_segment(self, itinerary: Dict) -> FlightSegment:
        """Parse a single flight segment (outbound or return)"""
        segments = itinerary['segments']
        first_segment = segments[0]
        last_segment = segments[-1]
        
        airline = first_segment['carrierCode']
        airline_code = first_segment['carrierCode']
        flight_number = f"{first_segment['carrierCode']}{first_segment['number']}"
        duration = itinerary['duration']
        duration_formatted = self._format_duration(duration)
        layovers = [seg['arrival']['iataCode'] for seg in segments[:-1]]
        
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
            layovers=layovers
        )

    def _parse_baggage(self, offer: Dict, cabin_class: str) -> tuple:
        """Parse baggage allowances - returns (checked_bags, cabin_bags)"""
        checked_bags = None
        cabin_bags = None
        
        try:
            traveler_pricings = offer.get('travelerPricings', [])
            if traveler_pricings:
                fare_detail = traveler_pricings[0].get('fareDetailsBySegment', [])
                if fare_detail and len(fare_detail) > 0:
                    segment_details = fare_detail[0]
                    
                    checked_allowance = segment_details.get('includedCheckedBags')
                    if checked_allowance and isinstance(checked_allowance, dict):
                        quantity = checked_allowance.get('quantity')
                        weight = checked_allowance.get('weight')
                        if quantity or weight:
                            checked_bags = {
                                "quantity": quantity if quantity else 0,
                                "weight": weight,
                                "weight_unit": checked_allowance.get('weightUnit', 'KG')
                            }
                    
                    if cabin_class.upper() in ['BUSINESS', 'FIRST']:
                        cabin_bags = {"quantity": 2, "weight": 16, "weight_unit": "KG"}
                    else:
                        cabin_bags = {"quantity": 1, "weight": 8, "weight_unit": "KG"}
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