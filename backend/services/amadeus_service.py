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

    #------------------------------------------------------------------#
    #      HOTELS API                                                  #
    #------------------------------------------------------------------#

    def search_hotels(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        radius: int = 5,
        radius_unit: str = "KM",
        ratings: Optional[List[str]] = None,
        max_results: int = 20,
        agent_logger: Optional[logging.Logger] = None  # ✅ ADD THIS
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels using Amadeus Hotel API (2-step process)
        
        Step 1: Get hotel IDs by location (Hotel List API)
        Step 2: Get prices for those hotels (Hotel Offers API)
        """
        # ✅ Use agent logger if provided
        log = agent_logger or logger
        
        if not self.client:
            log.warning("⚠️ Amadeus client not available - returning mock hotels")
            return self._get_mock_hotels(city_code, check_in_date, check_out_date, log)
        
        try:
            log.info(f"🏨 Searching hotels in {city_code} ({check_in_date} to {check_out_date})")
            
            # ✅ STEP 1: Get coordinates for the city
            lat, lon = self._get_city_coordinates(city_code, log)
            
            if not lat or not lon:
                log.warning(f"⚠️ Could not get coordinates for {city_code}, using mock data")
                return self._get_mock_hotels(city_code, check_in_date, check_out_date, log)
            
            log.info(f"📍 Coordinates: {lat}, {lon}")
            
            # ✅ STEP 2: Get hotel IDs by location (Hotel List API)
            log.info(f"🔍 Step 1/2: Finding hotels by location...")
            
            hotel_list_params = {
                'latitude': lat,
                'longitude': lon,
                'radius': radius,
                'radiusUnit': radius_unit
            }
            
            # Add ratings filter if provided
            if ratings:
                hotel_list_params['ratings'] = ','.join(ratings)
            
            log.info(f"📋 Hotel List API parameters:")
            for key, value in hotel_list_params.items():
                log.info(f"   {key}: {value}")
            
            # Call Hotel List API to get hotel IDs
            hotel_list_response = self.client.reference_data.locations.hotels.by_geocode.get(
                **hotel_list_params
            )
            
            # ✅ LOG RAW HOTEL LIST RESPONSE
            # log.info("=" * 80)
            # log.info("📋 RAW HOTEL LIST API RESPONSE:")
            # log_agent_json(
            #     hotel_list_response.data, 
            #     agent_name="HotelAgent",
            #     label="Hotel List API - Full Response"
            # )
            # log.info(f"   Total hotels returned: {len(hotel_list_response.data)}")
            # log.info("=" * 80)
            
            if not hotel_list_response.data:
                log.warning(f"⚠️ No hotels found at location, using mock data")
                return self._get_mock_hotels(city_code, check_in_date, check_out_date, log)
            
            log.info(f"✅ Found {len(hotel_list_response.data)} hotels at location")
            
            # ✅ LOG FIRST 3 HOTELS IN DETAIL
            log.info("📋 Sample hotels from list (first 3):")
            for idx, hotel in enumerate(hotel_list_response.data[:3], 1):
                log.info(f"   Hotel {idx}:")
                log.info(f"      hotelId: {hotel.get('hotelId')}")
                log.info(f"      name: {hotel.get('name')}")
                distance = hotel.get('distance', {})
                log.info(f"      distance: {distance.get('value')} {distance.get('unit')}")
                log.info(f"      rating: {hotel.get('rating')}")
            




            # ✅ STEP 3: Get offers for hotels in BATCHES with throttling
            log.info(f"💰 Step 2/2: Getting prices for hotels (batch processing with throttling)...")

            all_hotel_ids = [hotel['hotelId'] for hotel in hotel_list_response.data]
            log.info(f"📋 Total hotel IDs available: {len(all_hotel_ids)}")

            BATCH_SIZE = 5  # Reduced from 30 to be more conservative
            TARGET_HOTELS = 20  # Stop when we have this many
            MAX_BATCHES = 10  # Safety limit
            BATCH_DELAY = 10  # Seconds between batches to avoid rate limiting

            all_offers = []
            batch_num = 0

            for i in range(0, len(all_hotel_ids), BATCH_SIZE):
                batch_num += 1
                
                # Check if we've reached our limits
                if len(all_offers) >= TARGET_HOTELS:
                    log.info(f"✅ Target reached: {len(all_offers)} hotels found")
                    break
                
                if batch_num > MAX_BATCHES:
                    log.warning(f"⚠️ Max batches ({MAX_BATCHES}) reached, stopping search")
                    break
                
                # Add delay between batches (skip for first batch)
                if batch_num > 1:
                    log.info(f"⏳ Waiting {BATCH_DELAY}s before next batch...")
                    import time
                    time.sleep(BATCH_DELAY)
                
                # Get batch of hotel IDs
                batch_hotel_ids = all_hotel_ids[i:i + BATCH_SIZE]
                log.info(f"🔄 Batch {batch_num}: Processing {len(batch_hotel_ids)} hotels (IDs {i+1}-{i+len(batch_hotel_ids)})")
                
                try:
                    offers_params = {
                        'hotelIds': ','.join(batch_hotel_ids),
                        'checkInDate': check_in_date,
                        'checkOutDate': check_out_date,
                        'adults': adults,
                        'currency': 'USD',
                        'bestRateOnly': True
                    }
                    
                    # Call Hotel Offers API for this batch
                    offers_response = self.client.shopping.hotel_offers_search.get(**offers_params)
                    
                    if offers_response.data:
                        log.info(f"   ✓ Batch {batch_num}: Found {len(offers_response.data)} offers")
                        all_offers.extend(offers_response.data)
                        log.info(f"   ✓ Total Hotels Found {len(all_offers)} offers")
                    else:
                        log.info(f"   ⚠️ Batch {batch_num}: No offers found")
                
                except Exception as batch_error:
                    log.warning(f"   ⚠️ Batch {batch_num} failed: {batch_error}")
                    
                    # Check if it's a rate limit error
                    error_msg = str(batch_error)
                    if "500" in error_msg or "429" in error_msg or "rate" in error_msg.lower():
                        log.warning(f"   ⏳ Rate limit detected, waiting {BATCH_DELAY * 2}s before continuing...")
                        import time
                        time.sleep(BATCH_DELAY * 2)  # Double the wait time on rate limit
                    
                    continue

            # ✅ LOG FINAL RESULTS
            log.info("=" * 80)
            log.info("💰 BATCH PROCESSING COMPLETE:")
            log.info(f"   Batches processed: {batch_num}")
            log.info(f"   Total offers found: {len(all_offers)}")
            if all_offers:
                log_agent_json(
                    all_offers, 
                    agent_name="HotelAgent",
                    label="Hotel Offers API - All Batches Combined"
                )
            log.info("=" * 80)

            if not all_offers:
                log.warning(f"⚠️ No offers found after {batch_num} batches, using mock data")
                return self._get_mock_hotels(city_code, check_in_date, check_out_date, log)

            log.info(f"📊 Total offers collected: {len(all_offers)}")

            # ✅ LOG EACH OFFER IN DETAIL
            log.info("📋 Analyzing each returned offer:")
            for idx, offer in enumerate(all_offers[:20], 1):  # Log first 20
                hotel_info = offer.get('hotel', {})
                offers_list = offer.get('offers', [])
                
                log.info(f"   Offer {idx}:")
                log.info(f"      hotelId: {hotel_info.get('hotelId')}")
                log.info(f"      name: {hotel_info.get('name')}")
                log.info(f"      rating: {hotel_info.get('rating')}")
                log.info(f"      number of rate options: {len(offers_list)}")
                
                if offers_list:
                    best_offer = offers_list[0]
                    price_info = best_offer.get('price', {})
                    room_info = best_offer.get('room', {})
                    
                    log.info(f"      price: {price_info.get('currency')} {price_info.get('total')}")
                    log.info(f"      room type: {room_info.get('typeEstimated', {}).get('category')}")
                    description = room_info.get('description', {}).get('text', '')
                    log.info(f"      description: {description[:100]}...")

            # Parse response
            hotels = self._parse_hotel_response(
                all_offers,
                check_in_date,
                check_out_date,
                log
            )

            log.info(f"✅ Parsed {len(hotels)} hotels")

            # ✅ LOG FINAL PARSED HOTELS
            log.info("=" * 80)
            log.info("📋 FINAL PARSED HOTELS:")
            log_agent_json(
                hotels, 
                agent_name="HotelAgent",
                label="Parsed Hotels - Final Output"
            )
            log.info("=" * 80)

            # Limit results
            return hotels[:max_results]


            

            
        except Exception as e:
            log.error(f"❌ Amadeus Hotels API error: {e}")
            
            # Try to get detailed error info
            if hasattr(e, 'response'):
                log.error(f"   Status Code: {getattr(e.response, 'status_code', 'Unknown')}")
                try:
                    error_body = getattr(e.response, 'body', {})
                    if error_body:
                        log.error(f"   Response Body: {error_body}")
                    if hasattr(e.response, 'result'):
                        log.error(f"   Error Details: {e.response.result}")
                except:
                    pass
            
            log.exception("Full traceback:")
            log.info("⚠️ Falling back to mock hotel data")
            return self._get_mock_hotels(city_code, check_in_date, check_out_date, log)


    def _parse_hotel_response(
        self,
        data: List[Dict],
        check_in: str,
        check_out: str,
        log: logging.Logger = None  # ✅ ADD THIS
    ) -> List[Dict[str, Any]]:
        """Parse Amadeus hotel response into simplified format"""
        log = log or logger  # ✅ ADD THIS
        
        if not data:
            return []
        
        from datetime import datetime
        
        # Calculate number of nights
        check_in_dt = datetime.fromisoformat(check_in)
        check_out_dt = datetime.fromisoformat(check_out)
        num_nights = (check_out_dt - check_in_dt).days
        
        hotels = []
        
        for offer in data:
            try:
                hotel_info = offer.get('hotel', {})
                offer_info = offer.get('offers', [{}])[0]
                price_info = offer_info.get('price', {})
                
                # Extract amenities
                amenities_raw = hotel_info.get('amenities', [])
                amenities = {
                    "wifi": "WIFI" in amenities_raw or "INTERNET" in amenities_raw,
                    "parking": "PARKING" in amenities_raw,
                    "pool": "SWIMMING_POOL" in amenities_raw or "POOL" in amenities_raw,
                    "gym": "FITNESS_CENTER" in amenities_raw or "GYM" in amenities_raw,
                    "restaurant": "RESTAURANT" in amenities_raw,
                    "room_service": "ROOM_SERVICE" in amenities_raw,
                    "air_conditioning": "AIR_CONDITIONING" in amenities_raw,
                    "spa": "SPA" in amenities_raw,
                    "bar": "BAR" in amenities_raw,
                    "breakfast": "BREAKFAST" in amenities_raw
                }
                
                hotel = {
                    "id": offer.get('id', str(uuid.uuid4())),
                    "name": hotel_info.get('name', 'Unknown Hotel'),
                    "hotel_code": hotel_info.get('hotelId', ''),
                    "latitude": float(hotel_info.get('latitude', 0)),
                    "longitude": float(hotel_info.get('longitude', 0)),
                    "address": hotel_info.get('address', {}).get('lines', [''])[0] if hotel_info.get('address') else '',
                    "city": hotel_info.get('address', {}).get('cityName', ''),
                    "distance_from_center": hotel_info.get('distanceFromCenter'),
                    "rating": hotel_info.get('rating'),
                    "price_per_night": float(price_info.get('total', 0)) / num_nights if num_nights > 0 else 0,
                    "total_price": float(price_info.get('total', 0)),
                    "currency": price_info.get('currency', 'USD'),
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "num_nights": num_nights,
                    "room_type": offer_info.get('room', {}).get('typeEstimated', {}).get('category'),
                    "amenities": amenities,
                    "description": offer_info.get('room', {}).get('description', {}).get('text'),
                    "property_type": hotel_info.get('type')
                }
                
                hotels.append(hotel)
                log.info(f"   ✓ {hotel['name']} - ${hotel['total_price']:.2f} ({num_nights} nights)")
                
            except Exception as e:
                log.warning(f"⚠️ Error parsing hotel offer: {e}")
                continue
        
        return hotels

    def _get_city_coordinates(self, city_code: str, log: logging.Logger = None) -> tuple:  # ✅ ADD log parameter
        """Get lat/lon coordinates for a city code"""
        log = log or logger  # ✅ ADD THIS
        
        city_coords = {
            'LON': (51.5074, -0.1278),
            'PAR': (48.8566, 2.3522),
            'NYC': (40.7128, -74.0060),
            'TYO': (35.6762, 139.6503),
            'DXB': (25.2048, 55.2708),
            'SIN': (1.3521, 103.8198),
            'HKG': (22.3193, 114.1694),
            'BCN': (41.3874, 2.1686),
            'ROM': (41.9028, 12.4964),
            'AMS': (52.3676, 4.9041),
            'MAD': (40.4168, -3.7038),
            'BER': (52.5200, 13.4050),
            'SYD': (-33.8688, 151.2093),
            'MEL': (-37.8136, 144.9631),
            'LAX': (34.0522, -118.2437),
            'SFO': (37.7749, -122.4194),
            'MIA': (25.7617, -80.1918),
            'LAS': (36.1699, -115.1398),
            'CHI': (41.8781, -87.6298),
            'BOS': (42.3601, -71.0589),
            'LHR': (51.5074, -0.1278),
            'JFK': (40.7128, -74.0060),
        }
        
        coords = city_coords.get(city_code.upper())
        if coords:
            log.info(f"✓ Found coordinates for {city_code}: {coords}")
            return coords
        
        log.warning(f"⚠️ No coordinates found for city code: {city_code}")
        return None, None

    


    def _get_mock_hotels(
        self,
        city_code: str,
        check_in: str,
        check_out: str,
        log: logging.Logger = None  # ✅ ADD THIS
    ) -> List[Dict[str, Any]]:
        """Generate mock hotel data"""
        log = log or logger  # ✅ ADD THIS
        
        from datetime import datetime
        
        log.info("📝 Generating mock hotel data")
        
        # Calculate nights
        check_in_dt = datetime.fromisoformat(check_in)
        check_out_dt = datetime.fromisoformat(check_out)
        num_nights = (check_out_dt - check_in_dt).days
        
        mock_hotels = [
            {
                "id": str(uuid.uuid4()),
                "name": "Grand Plaza Hotel",
                "hotel_code": "HOTEL001",
                "latitude": 51.5074,
                "longitude": -0.1278,
                "address": "123 Main Street",
                "city": city_code,
                "distance_from_center": 2.5,
                "rating": 4.5,
                "price_per_night": 150.0,
                "total_price": 150.0 * num_nights,
                "currency": "USD",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "num_nights": num_nights,
                "room_type": "Deluxe Room",
                "amenities": {
                    "wifi": True,
                    "parking": True,
                    "pool": True,
                    "gym": True,
                    "restaurant": True,
                    "room_service": True,
                    "air_conditioning": True,
                    "spa": False,
                    "bar": True,
                    "breakfast": True
                },
                "description": "Luxury hotel in the heart of the city",
                "property_type": "HOTEL"
            },
            {
                "id": str(uuid.uuid4()),
                "name": "City View Inn",
                "hotel_code": "HOTEL002",
                "latitude": 51.5074,
                "longitude": -0.1278,
                "address": "456 Park Avenue",
                "city": city_code,
                "distance_from_center": 1.2,
                "rating": 4.0,
                "price_per_night": 120.0,
                "total_price": 120.0 * num_nights,
                "currency": "USD",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "num_nights": num_nights,
                "room_type": "Standard Room",
                "amenities": {
                    "wifi": True,
                    "parking": False,
                    "pool": False,
                    "gym": True,
                    "restaurant": True,
                    "room_service": False,
                    "air_conditioning": True,
                    "spa": False,
                    "bar": False,
                    "breakfast": True
                },
                "description": "Modern hotel with city views",
                "property_type": "HOTEL"
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Budget Stay Suites",
                "hotel_code": "HOTEL003",
                "latitude": 51.5074,
                "longitude": -0.1278,
                "address": "789 Budget Street",
                "city": city_code,
                "distance_from_center": 5.0,
                "rating": 3.5,
                "price_per_night": 80.0,
                "total_price": 80.0 * num_nights,
                "currency": "USD",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "num_nights": num_nights,
                "room_type": "Economy Room",
                "amenities": {
                    "wifi": True,
                    "parking": True,
                    "pool": False,
                    "gym": False,
                    "restaurant": False,
                    "room_service": False,
                    "air_conditioning": True,
                    "spa": False,
                    "bar": False,
                    "breakfast": False
                },
                "description": "Affordable accommodation",
                "property_type": "HOTEL"
            }
        ]
        
        logger.info(f"✅ Generated {len(mock_hotels)} mock hotels")
        return mock_hotels



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