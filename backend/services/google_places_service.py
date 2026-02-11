"""
Google Places Service - Hotel Details & Reviews
Using Places API (NEW) - Direct REST API calls - WORKING VERSION

Google deprecated the legacy Places API. This uses the new REST API directly.
This version avoids unsupported types and uses only validated included types.

Documentation: https://developers.google.com/maps/documentation/places/web-service/op-overview

Location: backend/services/google_places_service.py
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from backend.utils.logging_config import log_agent_json
from config.settings import settings

logger = logging.getLogger(__name__)


class GooglePlacesService:
    """Service for interacting with Google Places API (New)"""
    
    # New API base URL
    BASE_URL = "https://places.googleapis.com/v1/places"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Google Places service"""
        logger.info("=" * 80)
        logger.info("🔧 GooglePlacesService Initialization (Places API New)")
        logger.info("=" * 80)
        
        self.api_key = api_key
        self.client = None
        
        # Diagnostic logging
        if api_key:
            masked_key = api_key[:10] + "..." if len(api_key) > 10 else "***"
            logger.info(f"✓ API Key provided: {masked_key}")
            logger.info(f"✓ API Key length: {len(api_key)} characters")
            logger.info(f"✓ Using Places API (New) - REST API")
            
            # Set client to True to indicate ready
            self.client = True
            
            # Test API connection
            try:
                test_response = requests.get(
                    f"{self.BASE_URL}/ChIJdd4hrwug2EcRmSrV3Vo6llI",  # Sample place
                    headers={"X-Goog-Api-Key": self.api_key},
                    timeout=5
                )
                if test_response.status_code == 200:
                    logger.info("✅ API connection test PASSED")
                else:
                    logger.warning(f"⚠️  API test returned status: {test_response.status_code}")
            except Exception as test_e:
                logger.warning(f"⚠️  API connection test failed: {test_e}")
                
        else:
            logger.error("❌ API Key is None or empty")
            logger.error("   Check: settings.google_places_api_key")
            logger.error("   Check: .env file has GOOGLE_PLACES_API_KEY=your_key")
            self.client = None
        
        logger.info("=" * 80)
    
    def search_hotels(
        self,
        location: str = None,
        latitude: float = None,
        longitude: float = None,
        radius: int = 5000,
        min_rating: float = 3.0,
        price_level: Optional[List[int]] = None,
        open_now: bool = False,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels using Google Places API (New) - Nearby Search
        
        Args:
            location: Location name (e.g., "London, UK")
            latitude: Latitude coordinate (alternative to location)
            longitude: Longitude coordinate (alternative to location)
            radius: Search radius in meters (max: 50000)
            min_rating: Minimum rating (0-5)
            price_level: List of price levels [0-4] (not used in new API)
            open_now: Only return hotels open now
            agent_logger: Optional agent-specific logger
            
        Returns:
            List of hotel dictionaries with basic info
        """
        log = agent_logger or logger
        
        log.info("=" * 80)
        log.info("🔍 GooglePlacesService.search_hotels() - Places API (New)")
        log.info("=" * 80)
        
        if not self.client:
            log.error("❌ Google Places client not initialized")
            log.error("   Check API key configuration")
            return []
        
        try:
            # Resolve location to coordinates if needed
            if location and not (latitude and longitude):
                log.info(f"🔍 Geocoding location: {location}")
                coords = self._geocode_location(location, log)
                if coords:
                    latitude, longitude = coords
                    log.info(f"✓ Resolved to: {latitude}, {longitude}")
                else:
                    log.error(f"❌ Could not geocode location: {location}")
                    return []
            
            if not latitude or not longitude:
                log.error("❌ Must provide either location name or coordinates")
                return []
            
            log.info(f"\n📡 Making API call to Places API (New)")
            log.info(f"   Endpoint: searchNearby")
            log.info(f"   Location: {latitude}, {longitude}")
            log.info(f"   Radius: {radius}m")
            
            # Build request body - only use validated types
            # NO excluded types to avoid compatibility issues
            included_types = [
                "hotel",           # Traditional hotels
                "resort_hotel"     # Resort properties  
            ]
            
            request_body = {
                "includedTypes": included_types,
                "maxResultCount": 20,
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": latitude,
                            "longitude": longitude
                        },
                        "radius": radius
                    }
                },
                "rankPreference": "POPULARITY"  # Get highly-rated hotels first
            }
            
            log.info(f"   Included types: {', '.join(included_types)}")
            log.info(f"   Ranking: POPULARITY")
            log.info(f"   Max results: 20")
            
            # Headers for new API
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": (
                    "places.id,"
                    "places.displayName,"
                    "places.formattedAddress,"
                    "places.location,"
                    "places.rating,"
                    "places.userRatingCount,"
                    "places.priceLevel,"
                    "places.primaryType,"
                    "places.photos,"
                    "places.types,"
                    "places.businessStatus,"
                    "places.currentOpeningHours,"
                    "places.internationalPhoneNumber,"
                    "places.websiteUri"
                )
            }
            
            # Make request
            url = f"{self.BASE_URL}:searchNearby"
            response = requests.post(url, json=request_body, headers=headers, timeout=30)
            
            log.info(f"\n✅ API Response Received")
            log.info(f"   Status: {response.status_code}")
            
            if response.status_code != 200:
                log.error(f"❌ API returned error: {response.status_code}")
                log.error(f"   Response: {response.text}")
                return []
            
            data = response.json()
            places = data.get('places', [])
            
            log.info(f"   Results count: {len(places)}")
            
            # If we got very few results, try again with lodging
            if len(places) < 5:
                log.warning(f"⚠️  Only {len(places)} hotels found with strict filters")
                log.info(f"   Retrying with 'lodging' type...")
                
                # Retry with broader type
                request_body["includedTypes"] = ["lodging"]
                request_body["maxResultCount"] = 20
                
                response = requests.post(url, json=request_body, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    places = data.get('places', [])
                    log.info(f"   Retry results: {len(places)} hotels")
            
            if not places:
                log.warning(f"⚠️  No hotels found")
                return []
            
            # Parse results
            hotels = []
            hotels_no_rating = []
            filtered_count = 0
            
            for idx, place in enumerate(places, 1):
                rating = place.get('rating', 0)
                name = place.get('displayName', {}).get('text', 'Unknown')
                primary_type = place.get('primaryType', '')
                
                log.info(f"\n   Hotel {idx}: {name}")
                log.info(f"      Rating: {rating}")
                if primary_type:
                    log.info(f"      Type: {primary_type}")
                
                # Filter by rating
                if rating == 0:
                    # No rating - keep as backup
                    hotel = self._parse_place_result(place, log)
                    if hotel and primary_type in ['hotel', 'resort_hotel', 'motel']:
                        hotels_no_rating.append(hotel)
                        log.info(f"      ℹ️  No rating - saved as backup")
                    else:
                        log.info(f"      ⚠️  No rating, not a hotel type")
                    continue
                
                if rating < min_rating:
                    log.info(f"      ⚠️  Filtered out (rating {rating} < min {min_rating})")
                    filtered_count += 1
                    continue
                
                hotel = self._parse_place_result(place, log)
                if hotel:
                    log.info(f"      ✅ Included")
                    hotels.append(hotel)
                else:
                    log.warning(f"      ⚠️  Failed to parse")
            
            # Include unrated hotels if needed
            if len(hotels) < 5 and hotels_no_rating:
                num_to_add = min(5 - len(hotels), len(hotels_no_rating))
                log.info(f"\n⚠️  Only {len(hotels)} rated hotels, adding {num_to_add} unrated")
                hotels.extend(hotels_no_rating[:num_to_add])
            
            log.info(f"\n📊 Search Summary:")
            log.info(f"   Total from API: {len(places)}")
            log.info(f"   With good ratings: {len([h for h in hotels if h.get('google_rating', 0) >= min_rating])}")
            log.info(f"   Backup (unrated): {len([h for h in hotels if h.get('google_rating', 0) == 0])}")
            log.info(f"   Final count: {len(hotels)}")
            log.info("=" * 80)
            
            return hotels
            
        except requests.exceptions.RequestException as e:
            log.error("=" * 80)
            log.error(f"❌ REQUEST EXCEPTION")
            log.error(f"   Error: {str(e)}")
            log.error("=" * 80)
            return []
        except Exception as e:
            log.error("=" * 80)
            log.error(f"❌ EXCEPTION")
            log.error(f"   Error: {str(e)}")
            log.exception("   Traceback:")
            log.error("=" * 80)
            return []
    
    def _geocode_location(
        self,
        location: str,
        log: logging.Logger = None
    ) -> Optional[tuple]:
        """Geocode location name to coordinates"""
        log = log or logger
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": location, "key": self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                log.error(f"❌ Geocoding failed: {response.status_code}")
                return None
            
            data = response.json()
            
            if data.get('status') != 'OK':
                log.error(f"❌ Geocoding status: {data.get('status')}")
                return None
            
            results = data.get('results', [])
            if not results:
                return None
            
            location_data = results[0]['geometry']['location']
            return (location_data['lat'], location_data['lng'])
            
        except Exception as e:
            log.error(f"❌ Geocoding exception: {e}")
            return None
    

    def search_places(
        self,
        location: str = None,
        latitude: float = None,
        longitude: float = None,
        radius: int = 5000,
        place_types: List[str] = None,
        min_rating: float = 3.0,
        max_results: int = 20,
        agent_logger: Optional[logging.Logger] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for places by category using Google Places API (New)
        
        Args:
            location: Location name (e.g., "Paris, France")
            latitude: Latitude coordinate (alternative to location)
            longitude: Longitude coordinate (alternative to location)
            radius: Search radius in meters (default: 5000)
            place_types: List of place types to search for
            min_rating: Minimum rating (0-5)
            max_results: Max results per category
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with place types as keys, lists of places as values
            Example: {
                "restaurant": [{...}, {...}],
                "tourist_attraction": [{...}, {...}]
            }
        """
        log = agent_logger or logger
        
        log.info("=" * 80)
        log.info("🔍 GooglePlacesService.search_places() - Places API (New)")
        log.info("=" * 80)
        
        if not self.client:
            log.error("❌ Google Places client not initialized")
            return {}
        
        try:
            # Resolve location to coordinates if needed
            if location and not (latitude and longitude):
                log.info(f"🔍 Geocoding location: {location}")
                coords = self._geocode_location(location, log)
                if coords:
                    latitude, longitude = coords
                    log.info(f"✓ Resolved to: {latitude}, {longitude}")
                else:
                    log.error(f"❌ Could not geocode location: {location}")
                    return {}
            
            if not latitude or not longitude:
                log.error("❌ Must provide either location name or coordinates")
                return {}
            
            # Default place types if not provided
            if not place_types:
                place_types = [
                    "restaurant",
                    "tourist_attraction",
                    "shopping_mall",
                    "museum",
                    "park"
                ]
            
            log.info(f"\n📋 Search Parameters:")
            log.info(f"   Location: {latitude}, {longitude}")
            log.info(f"   Radius: {radius}m")
            log.info(f"   Categories: {', '.join(place_types)}")
            log.info(f"   Min Rating: {min_rating}")
            log.info(f"   Max per category: {max_results}")
            
            results = {}
            
            # Search for each place type
            for place_type in place_types:
                log.info(f"\n🔎 Searching: {place_type}")
                log.info("-" * 80)
                
                # Build request body
                request_body = {
                    "includedTypes": [place_type],
                    "maxResultCount": max_results,
                    "locationRestriction": {
                        "circle": {
                            "center": {
                                "latitude": latitude,
                                "longitude": longitude
                            },
                            "radius": radius
                        }
                    },
                    "rankPreference": "POPULARITY"
                }
                
                # Headers
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": (
                        "places.id,"
                        "places.displayName,"
                        "places.formattedAddress,"
                        "places.location,"
                        "places.rating,"
                        "places.userRatingCount,"
                        "places.priceLevel,"
                        "places.primaryType,"
                        "places.photos,"
                        "places.types,"
                        "places.currentOpeningHours,"
                        "places.internationalPhoneNumber,"
                        "places.websiteUri,"
                        "places.businessStatus"
                    )
                }
                
                # Make request
                url = f"{self.BASE_URL}:searchNearby"
                response = requests.post(url, json=request_body, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    log.warning(f"   ⚠️  API error: {response.status_code}")
                    log.warning(f"   Response: {response.text[:200]}")
                    continue
                
                data = response.json()
                places = data.get('places', [])
                
                log.info(f"   ✓ Found {len(places)} results")
                
                # Filter by rating
                filtered_places = []
                for place in places:
                    rating = place.get('rating', 0)
                    
                    # Skip if no rating or below minimum
                    if rating == 0 or rating < min_rating:
                        continue
                    
                    parsed = self._parse_place_result(place, log)
                    
                    if parsed:
                        filtered_places.append(parsed)
                
                log.info(f"   ✓ After filtering: {len(filtered_places)} places")
                
                if filtered_places:
                    results[place_type] = filtered_places
            
            # Summary
            total_places = sum(len(places) for places in results.values())
            log.info(f"\n📊 Search Complete:")
            log.info(f"   Categories found: {len(results)}")
            log.info(f"   Total places: {total_places}")
            
            for category, places in results.items():
                log.info(f"   - {category}: {len(places)} places")
            
            log.info("=" * 80)
            
            return results
            
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Request exception: {str(e)}")
            return {}
        except Exception as e:
            log.error(f"❌ Exception: {str(e)}")
            log.exception("Traceback:")
            return {}


    def get_place_details(
        self,
        place_id: str,
        fields: Optional[List[str]] = None,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information about a place"""
        log = agent_logger or logger
        
        if not self.client:
            log.warning("⚠️  Google Places client not available")
            return None
        
        try:
            field_mask = (
                "id,displayName,formattedAddress,location,rating,userRatingCount,"
                "priceLevel,nationalPhoneNumber,websiteUri,googleMapsUri,"
                "currentOpeningHours,photos,reviews,types,businessStatus"
            )
            
            headers = {
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": field_mask
            }
            
            url = f"{self.BASE_URL}/{place_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                log.warning(f"⚠️  Place details failed: {response.status_code}")
                return None
            
            place = response.json()
            
            if not place:
                log.warning(f"⚠️  No details for place: {place_id}")
                return None
            
            log.info(f"✅ Retrieved details for: {place.get('displayName', {}).get('text', 'Unknown')}")
            
            return self._parse_place_details(place, log)
            
        except Exception as e:
            log.error(f"❌ Error fetching place details: {e}")
            return None
    
    def get_photo_url(
        self,
        photo_resource_name: str,
        max_width: int = 400,
        max_height: Optional[int] = None
    ) -> str:
        """Generate photo URL from resource name"""
        if not self.api_key:
            return ""
        
        base_url = f"https://places.googleapis.com/v1/{photo_resource_name}/media"
        
        params = [f"maxWidthPx={max_width}"]
        if max_height:
            params.append(f"maxHeightPx={max_height}")
        params.append(f"key={self.api_key}")
        
        return f"{base_url}?{'&'.join(params)}"
    
    def _parse_place_result(
        self,
        place: Dict[str, Any],
        log: logging.Logger = None
    ) -> Optional[Dict[str, Any]]:
        """Parse nearby search result"""
        log = log or logger
        
        try:
            location = place.get('location', {})
            
            # Extract photos
            photos = []
            if place.get('photos'):
                for photo in place['photos'][:5]:
                    photo_url = self.get_photo_url(photo['name'], max_width=400)
                    photos.append(photo_url)
            
            # Extract name
            display_name = place.get('displayName', {})
            name = display_name.get('text', 'Unknown Hotel') if isinstance(display_name, dict) else str(display_name)
            
            # Parse price level
            price_level_str = place.get('priceLevel', 'PRICE_LEVEL_MODERATE')
            price_level = self._parse_price_level(price_level_str)
            
            # Parse opening status
            opening_hours = place.get('currentOpeningHours', {})
            open_now = opening_hours.get('openNow')
            
            hotel = {
                'place_id': place.get('id'),
                'name': name,
                'address': place.get('formattedAddress', ''),
                'latitude': location.get('latitude'),
                'longitude': location.get('longitude'),
                'google_rating': place.get('rating'),
                'user_ratings_total': place.get('userRatingCount'),
                'price_level': price_level,
                'primary_type': place.get('primaryType', ''),
                'photos': photos,
                'types': place.get('types', []),
                'business_status': place.get('businessStatus'),
                'open_now': open_now
            }
            
            return hotel
            
        except Exception as e:
            log.warning(f"⚠️  Error parsing place: {e}")
            return None
    
    def _parse_place_details(
        self,
        place: Dict[str, Any],
        log: logging.Logger = None
    ) -> Dict[str, Any]:
        """Parse detailed place information"""
        log = log or logger
        
        location = place.get('location', {})
        
        # Extract photos
        photos = []
        if place.get('photos'):
            for photo in place['photos'][:10]:
                photo_url = self.get_photo_url(photo['name'], max_width=800)
                photos.append(photo_url)
        
        # Extract reviews
        reviews = []
        if place.get('reviews'):
            for review in place['reviews']:
                reviews.append({
                    'author_name': review.get('authorAttribution', {}).get('displayName'),
                    'rating': review.get('rating'),
                    'text': review.get('text', {}).get('text'),
                    'time': review.get('publishTime'),
                    'relative_time_description': review.get('relativePublishTimeDescription')
                })
        
        # Extract opening hours
        opening_hours = None
        if place.get('currentOpeningHours'):
            hours_data = place['currentOpeningHours']
            opening_hours = {
                'open_now': hours_data.get('openNow'),
                'weekday_text': hours_data.get('weekdayDescriptions', [])
            }
        
        # Parse name
        display_name = place.get('displayName', {})
        name = display_name.get('text', 'Unknown') if isinstance(display_name, dict) else str(display_name)
        
        # Parse price level
        price_level_str = place.get('priceLevel', 'PRICE_LEVEL_MODERATE')
        price_level = self._parse_price_level(price_level_str)
        
        return {
            'place_id': place.get('id'),
            'name': name,
            'formatted_address': place.get('formattedAddress'),
            'latitude': location.get('latitude'),
            'longitude': location.get('longitude'),
            'rating': place.get('rating'),
            'user_ratings_total': place.get('userRatingCount'),
            'price_level': price_level,
            'phone_number': place.get('nationalPhoneNumber'),
            'website': place.get('websiteUri'),
            'google_url': place.get('googleMapsUri'),
            'opening_hours': opening_hours,
            'photos': photos,
            'reviews': reviews,
            'types': place.get('types', []),
            'business_status': place.get('businessStatus')
        }
    
    def _parse_price_level(self, price_level_str: str) -> int:
        """Convert price level string to numeric value"""
        price_map = {
            'PRICE_LEVEL_FREE': 0,
            'PRICE_LEVEL_INEXPENSIVE': 1,
            'PRICE_LEVEL_MODERATE': 2,
            'PRICE_LEVEL_EXPENSIVE': 3,
            'PRICE_LEVEL_VERY_EXPENSIVE': 4,
            'PRICE_LEVEL_UNSPECIFIED': 2
        }
        return price_map.get(price_level_str, 2)


# Singleton instance
_google_places_service_instance = None


def get_google_places_service() -> GooglePlacesService:
    """Get singleton instance"""
    global _google_places_service_instance
    
    if _google_places_service_instance is None:
        logger.info("\n🔧 Initializing GooglePlacesService...")
        _google_places_service_instance = GooglePlacesService(
            api_key=settings.google_places_api_key
        )
    
    return _google_places_service_instance