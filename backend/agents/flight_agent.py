"""
Flight Agent - Real API with Centralized Storage
Location: backend/agents/flight_agent.py
"""
import json
import time
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
        system_message = """
You are a helpful Flight Search Assistant.

Your job:
1. Search for flights using real-time data
2. Review all available options
3. Provide a brief, conversational recommendation

Be friendly and helpful. Don't dump data - just give useful advice.
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
        
        # Extract preferences
        # ✅ Get preferences from storage (no LLM extraction!)
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
            "cabin_class": preferences.flight_prefs.cabin_class.upper(),  # ✅ UPPERCASE
            "num_travelers": preferences.num_travelers,
            "budget": preferences.budget.flight_budget,
            "max_stops": preferences.flight_prefs.max_stops
        }
        
        log_agent_json(search_params, label="Flight Search Parameters (from storage)", 
                      agent_name="FlightAgent")
        
        try:
            # ✅ Step 1: Resolve city names to airport codes
            origin_code = self._resolve_location(search_params["origin"])
            destination_code = self._resolve_location(search_params["destination"])
            
            if not origin_code or not destination_code:
                error_msg = "Could not resolve origin or destination to airport code"
                log_agent_raw(f"❌ {error_msg}", agent_name="FlightAgent")
                return f"I'm sorry, I couldn't find the airport for your route. Please use airport codes like JFK, LAX, LHR."
            
            log_agent_raw(f"✓ Resolved: {search_params['origin']} → {origin_code}, {search_params['destination']} → {destination_code}", 
                         agent_name="FlightAgent")
            
            # ✅ Step 2: Call Amadeus API
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
            
            log_agent_raw(f"✅ API returned {len(flights)} flight options in {api_duration:.2f}s: Returned API Data:", 
                         agent_name="FlightAgent")
            
            log_agent_json(f"{flights}", 
                         agent_name="FlightAgent")

            # ✅ Step 3: Store ALL options in centralized storage
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
            
            # ✅ Step 4: Generate conversational recommendation (NO structured data)
            recommendation = self._generate_recommendation(flights, search_params)
            
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
            # ✅ Also signal completion on error
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
        # Check if Amadeus is configured
        if not self.amadeus_service or not self.amadeus_service.client:
            log_agent_raw("⚠️ Amadeus not configured, using mock data", agent_name="flightagent")
            return self._generate_mock_flights(origin, destination, departure_date)
        
        cabin_class_upper = cabin_class.upper()

        api_params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": adults,
            "travelClass": cabin_class_upper,
            "max": 50
        }
        
        log_agent_raw("=" * 80, agent_name="FlightAgent")
        log_agent_raw("📡 Calling Amadeus API with parameters:", agent_name="FlightAgent")
        log_agent_json(api_params, label="Amadeus API Request", agent_name="FlightAgent")
        log_agent_raw("=" * 80, agent_name="FlightAgent")

        # Call real Amadeus API
        try:
            response = self.amadeus_service.client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date,
                returnDate=return_date,
                adults=adults,
                travelClass=cabin_class_upper,
                max=5  # Get many options
            )
            
            # ✅ ADD THIS - Log success
            log_agent_raw(f"✅ Amadeus API SUCCESS - Received {len(response.data)} offers", 
                        agent_name="FlightAgent")

            # Parse response into Flight objects
            flights = []
            for offer in response.data:
                flight = self._parse_amadeus_offer(offer)
                if flight:
                    flights.append(flight)
            
            return flights
            

        except Exception as e:
            log_agent_raw("=" * 80, agent_name="FlightAgent")
            log_agent_raw(f"❌ Amadeus API FAILED", agent_name="FlightAgent")
            log_agent_raw(f"Error Type: {type(e).__name__}", agent_name="FlightAgent")
            log_agent_raw(f"Error Message: {str(e)}", agent_name="FlightAgent")
            
            # Try to get more details from the exception
            if hasattr(e, 'response'):
                log_agent_raw(f"Response Status: {getattr(e.response, 'status_code', 'N/A')}", 
                            agent_name="FlightAgent")
                log_agent_raw(f"Response Body: {getattr(e.response, 'body', 'N/A')}", 
                            agent_name="FlightAgent")
            
            log_agent_raw("=" * 80, agent_name="FlightAgent")
            
            # Fallback to mock data
            log_agent_raw("⚠️ Falling back to mock data", agent_name="FlightAgent")
            return self._generate_mock_flights(origin, destination, departure_date)
    

    def _parse_amadeus_offer(self, offer: Any) -> Optional[Flight]:
        """Parse Amadeus flight offer into Flight object (supports round-trip)"""
        try:
            itineraries = offer.get('itineraries', [])
            if not itineraries:
                return None
            
            # Check if round-trip
            is_round_trip = len(itineraries) == 2
            
            # Get price
            price = float(offer['price']['total'])
            currency = offer['price']['currency']
            
            # Get airline code
            first_segment = itineraries[0]['segments'][0]
            airline_code = first_segment['carrierCode']
            
            # Extract baggage
            cabin_class = first_segment.get('cabin', 'ECONOMY')
            checked_bags, cabin_bags = self._parse_baggage(offer, cabin_class)
            
            if is_round_trip:
                # Parse both outbound and return
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
                # One-way flight (legacy format for backward compatibility)
                segment = self._parse_flight_segment(itineraries[0])
                
                return Flight(
                    id=offer['id'],
                    airline=segment.airline,
                    airline_code=airline_code,
                    is_round_trip=False,
                    # Legacy fields
                    origin=segment.departure_airport,
                    destination=segment.arrival_airport,
                    departure_time=segment.departure_time,
                    arrival_time=segment.arrival_time,
                    duration=segment.duration,
                    flight_number=segment.flight_number,
                    stops=segment.stops,
                    layovers=segment.layovers,
                    # Common fields
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
        
        # Get airline name
        airline = first_segment['carrierCode']
        airline_code = first_segment['carrierCode']
        flight_number = f"{first_segment['carrierCode']}{first_segment['number']}"
        
        # Calculate duration
        duration = itinerary['duration']
        duration_formatted = self._format_duration(duration)
        
        # Get layovers
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
                    
                    # Checked baggage
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
                    
                    # Cabin baggage defaults
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
        import re
        hours = re.search(r'(\d+)H', duration)
        minutes = re.search(r'(\d+)M', duration)
        
        h = hours.group(1) if hours else "0"
        m = minutes.group(1) if minutes else "0"
        
        return f"{h}h {m}m"
    
    def _generate_recommendation(
        self,
        flights: List[Flight],
        preferences: Dict[str, Any]
    ) -> str:
        """
        Use LLM to generate conversational recommendation
        """
        if not flights:
            return "I couldn't find any flights for your route. Please check your dates and try again."
        
        # Sort by price
        flights_sorted = sorted(flights, key=lambda f: f.price)
        
        # Get key options - handle both round-trip and one-way
        cheapest = flights_sorted[0]
        
        # For direct flights, check based on trip type
        direct_flights = []
        for f in flights:
            if f.is_round_trip:
                # Round-trip: both outbound and return must be direct
                if f.outbound and f.return_flight and f.outbound.stops == 0 and f.return_flight.stops == 0:
                    direct_flights.append(f)
            else:
                # One-way: check stops field
                if f.stops == 0:
                    direct_flights.append(f)
        
        best_direct = direct_flights[0] if direct_flights else None
        
        # Build prompt for LLM
        cheapest_desc = self._flight_description(cheapest)
        direct_desc = self._flight_description(best_direct) if best_direct else "No direct flights available"
        
        prompt = f"""
            Based on the flight search results, provide a helpful recommendation.

            SEARCH RESULTS:
            - Total flights found: {len(flights)}
            - Price range: ${flights_sorted[0].price:.2f} - ${flights_sorted[-1].price:.2f}
            - Direct flights available: {len(direct_flights)}

            TOP OPTIONS:
            1. Cheapest: {cheapest_desc}
            2. Best direct: {direct_desc}

            USER PREFERENCES:
            - Budget: ${preferences.get('budget', 'Not specified')}
            - Cabin class: {preferences.get('cabin_class', 'economy')}
            - Max stops: {preferences.get('max_stops', 2)}

            Provide a conversational recommendation (3-4 sentences):
            - Mention how many options you reviewed
            - Recommend your top pick with specific flight number and why
            - Mention a budget alternative if relevant
            - Be friendly and helpful

            Example: "I reviewed 47 round-trip flights from NYC to London. My top recommendation is British Airways for $850 - both legs are direct with good timing. If you're looking to save money, the Air Canada option with one stop each way is only $520."
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
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="FlightAgent")
            # Fallback to template
            if cheapest.is_round_trip:
                return f"I found {len(flights)} round-trip flights. My top pick is {cheapest.airline} for ${cheapest.price:.2f}."
            else:
                return f"I found {len(flights)} flights. My top pick is {cheapest.airline} {cheapest.flight_number} for ${cheapest.price:.2f}."
    

    def _flight_description(self, flight: Flight) -> str:
        """Generate description for a flight (handles both one-way and round-trip)"""
        if flight.is_round_trip and flight.outbound and flight.return_flight:
            return (f"{flight.airline} ${flight.price:.2f} - "
                    f"Outbound: {flight.outbound.departure_airport}→{flight.outbound.arrival_airport} "
                    f"({flight.outbound.stops} stops, {flight.outbound.duration}), "
                    f"Return: {flight.return_flight.departure_airport}→{flight.return_flight.arrival_airport} "
                    f"({flight.return_flight.stops} stops, {flight.return_flight.duration})")
        else:
            # Legacy one-way format
            return (f"{flight.airline} {flight.flight_number} - ${flight.price:.2f}, "
                    f"{flight.stops} stops, {flight.duration}")


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
        from datetime import datetime, timedelta
        from models.trip import FlightSegment
        
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