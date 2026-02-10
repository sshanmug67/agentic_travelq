"""
Amadeus Flight Search Service - Async-Compatible with Thread Executor

Uses asyncio thread executor to run synchronous Amadeus SDK calls properly.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.logging_config import log_agent_json
from config.settings import settings
from amadeus import Client
import logging
import uuid
import asyncio

logger = logging.getLogger(__name__)


class AmadeusService:
    """Service for interacting with Amadeus Flight API"""
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """Initialize Amadeus service"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = None
        
        # Only initialize if credentials are provided
        if self.client_id and self.client_secret:
            try:
                self.client = Client(
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                logger.info("✅ Amadeus API client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Amadeus client: {e}")
                self.client = None
        else:
            logger.warning("⚠️  Amadeus credentials not provided - service will use mock data")
    
    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        max_results: int = 10,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for flights between two locations (async-compatible)
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date (YYYY-MM-DD)
            adults: Number of passengers
            max_results: Maximum results to return
            agent_logger: Optional agent-specific logger for detailed logging
            
        Returns:
            List of flight dictionaries
        """
        # Use agent logger if provided, otherwise regular logger
        log = agent_logger or logger
        
        if not self.client:
            logger.warning("⚠️  Amadeus client not available - returning mock data")
            log.warning("⚠️  Amadeus client not available - using mock data")
            return self._get_mock_flights(origin, destination, departure_date, log)
        
        try:
            logger.info(f"🔍 Searching Amadeus API: {origin} → {destination} on {departure_date}")
            log.info(f"🔍 Calling Amadeus API (async with thread executor):")
            log.info(f"   API: flight_offers_search")
            log.info(f"   Origin: {origin}")
            log.info(f"   Destination: {destination}")
            log.info(f"   Date: {departure_date}")
            log.info(f"   Passengers: {adults}")
            log.info(f"   Max Results: {max_results}")
            

            # Run synchronous Amadeus SDK call in thread executor
            # This prevents blocking the async event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,  # Use default executor
                lambda: self.client.shopping.flight_offers_search.get(
                    originLocationCode=origin,
                    destinationLocationCode=destination,
                    departureDate=departure_date,
                    adults=adults,
                    max=max_results
                )
            )
            
            log_agent_json(response.data, agent_name="flight_agent",label="Amadeus Raw Response")

            log.info(f"✅ Amadeus API response received")
            log.info(f"   Raw offers: {len(response.data) if response.data else 0}")
            

            # Parse and format results
            flights = self._parse_amadeus_response(response.data, origin, destination, log)
            
            logger.info(f"✅ Found {len(flights)} flights from Amadeus API")
            log.info(f"✅ Parsing complete: {len(flights)} flights extracted")
            
            return flights
            
        except Exception as e:
            logger.error(f"❌ Amadeus API error: {e}")
            logger.exception("Full traceback:")
            log.error(f"❌ Amadeus API Error: {str(e)}")
            log.info("⚠️  Falling back to mock data")
            logger.info("⚠️  Falling back to mock data")
            return self._get_mock_flights(origin, destination, departure_date, log)
    
    def _parse_amadeus_response(
        self, 
        data: List[Dict], 
        origin: str, 
        destination: str,
        log: logging.Logger = None
    ) -> List[Dict[str, Any]]:
        """Parse Amadeus API response into simplified flight format"""
        log = log or logger
        log.info("📋 Parsing Amadeus response...")
        
        if not data:
            log.warning("⚠️  No flight data returned from API")
            return []
        
        flights = []
        
        for idx, offer in enumerate(data, 1):
            try:
                # Extract first itinerary (outbound)
                itinerary = offer['itineraries'][0]
                segments = itinerary['segments']
                first_segment = segments[0]
                last_segment = segments[-1]
                
                # Extract price
                price_info = offer['price']
                
                flight = {
                    "id": offer.get('id', str(uuid.uuid4())),
                    "flight_number": first_segment['carrierCode'] + first_segment['number'],
                    "airline": self._get_airline_name(first_segment['carrierCode']),
                    "airline_code": first_segment['carrierCode'],
                    "origin": origin,
                    "destination": destination,
                    "departure_time": first_segment['departure']['at'],
                    "arrival_time": last_segment['arrival']['at'],
                    "duration": itinerary['duration'],
                    "price": float(price_info['total']),
                    "currency": price_info['currency'],
                    "number_of_stops": len(segments) - 1,
                    "cabin_class": segments[0].get('cabin', 'ECONOMY')
                }
                
                log.info(f"   ✓ Flight {idx}: {flight['airline']} {flight['flight_number']} - {flight['currency']} {flight['price']:.2f} ({flight['number_of_stops']} stops)")
                flights.append(flight)
                
            except (KeyError, IndexError) as e:
                logger.warning(f"⚠️  Error parsing flight offer {idx}: {e}")
                log.warning(f"⚠️  Skipping offer {idx}: {str(e)}")
                continue
        
        return flights
    
    def _get_airline_name(self, code: str) -> str:
        """Get airline name from code (basic mapping)"""
        airline_map = {
            'AA': 'American Airlines',
            'UA': 'United Airlines',
            'DL': 'Delta Air Lines',
            'BA': 'British Airways',
            'LH': 'Lufthansa',
            'AF': 'Air France',
            'KL': 'KLM',
            'IB': 'Iberia',
            'EK': 'Emirates',
            'QR': 'Qatar Airways',
            'SQ': 'Singapore Airlines',
            'NH': 'ANA',
            'JL': 'Japan Airlines',
            'CX': 'Cathay Pacific',
            'TK': 'Turkish Airlines',
        }
        return airline_map.get(code, code)
    
    def _get_mock_flights(
        self, 
        origin: str, 
        destination: str, 
        date: str,
        log: logging.Logger = None
    ) -> List[Dict[str, Any]]:
        """Generate mock flight data matching Pydantic model requirements"""
        log = log or logger
        
        logger.info("📝 Generating mock flight data")
        log.info("📝 Generating mock flight data...")
        log.info(f"   Route: {origin} → {destination}")
        log.info(f"   Date: {date}")
        
        mock_flights = [
            {
                "id": str(uuid.uuid4()),
                "flight_number": "AA101",
                "airline": "American Airlines",
                "airline_code": "AA",
                "origin": origin,
                "destination": destination,
                "departure_time": f"{date}T08:00:00",
                "arrival_time": f"{date}T16:00:00",
                "duration": "PT8H0M",
                "price": 299.99,
                "currency": "USD",
                "number_of_stops": 0,
                "cabin_class": "ECONOMY"
            },
            {
                "id": str(uuid.uuid4()),
                "flight_number": "UA202",
                "airline": "United Airlines",
                "airline_code": "UA",
                "origin": origin,
                "destination": destination,
                "departure_time": f"{date}T10:30:00",
                "arrival_time": f"{date}T18:30:00",
                "duration": "PT8H0M",
                "price": 349.99,
                "currency": "USD",
                "number_of_stops": 0,
                "cabin_class": "ECONOMY"
            },
            {
                "id": str(uuid.uuid4()),
                "flight_number": "DL303",
                "airline": "Delta Air Lines",
                "airline_code": "DL",
                "origin": origin,
                "destination": destination,
                "departure_time": f"{date}T14:15:00",
                "arrival_time": f"{date}T22:15:00",
                "duration": "PT8H0M",
                "price": 279.99,
                "currency": "USD",
                "number_of_stops": 1,
                "cabin_class": "ECONOMY"
            },
            {
                "id": str(uuid.uuid4()),
                "flight_number": "BA404",
                "airline": "British Airways",
                "airline_code": "BA",
                "origin": origin,
                "destination": destination,
                "departure_time": f"{date}T19:45:00",
                "arrival_time": f"{date}T03:45:00",
                "duration": "PT8H0M",
                "price": 399.99,
                "currency": "USD",
                "number_of_stops": 0,
                "cabin_class": "BUSINESS"
            },
            {
                "id": str(uuid.uuid4()),
                "flight_number": "LH505",
                "airline": "Lufthansa",
                "airline_code": "LH",
                "origin": origin,
                "destination": destination,
                "departure_time": f"{date}T22:00:00",
                "arrival_time": f"{date}T06:00:00",
                "duration": "PT8H0M",
                "price": 329.99,
                "currency": "USD",
                "number_of_stops": 1,
                "cabin_class": "ECONOMY"
            }
        ]
        
        log.info(f"✅ Generated {len(mock_flights)} mock flights:")
        for idx, flight in enumerate(mock_flights, 1):
            log.info(f"   {idx}. {flight['airline']} {flight['flight_number']} - ${flight['price']:.2f}")
        
        return mock_flights


# ============================================================================
# SINGLETON INSTANCE - LAZY INITIALIZATION
# ============================================================================

_amadeus_service_instance = None


def get_amadeus_service() -> AmadeusService:
    """Get singleton instance of AmadeusService (lazy initialization)"""
    global _amadeus_service_instance
    
    if _amadeus_service_instance is None:
        _amadeus_service_instance = AmadeusService(
            client_id=settings.amadeus_client_id,
            client_secret=settings.amadeus_client_secret
        )
    
    return _amadeus_service_instance


# For backward compatibility
amadeus_service = None