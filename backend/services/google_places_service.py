"""
Google Places Service - Hotel Details & Reviews
Using Places API (NEW) - Direct REST API calls - WORKING VERSION

Changes (v4):
  - Added places.reviews and places.googleMapsUri to ALL field masks
  - _parse_place_result() now extracts: website, phone_number, reviews, google_url
  - Reviews parsed inline (no separate get_place_details() call needed)
  - All data now flows through to Hotel model and frontend

Location: backend/services/google_places_service.py
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from utils.logging_config import log_agent_json
from config.settings import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Shared field mask — used by all search endpoints
# v4: Added places.reviews, places.googleMapsUri
# ─────────────────────────────────────────────────────────────────────────
SEARCH_FIELD_MASK = (
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
    "places.websiteUri,"
    "places.reviews,"
    "places.googleMapsUri"
)


class GooglePlacesService:
    """Service for interacting with Google Places API (New)"""
    
    BASE_URL = "https://places.googleapis.com/v1/places"
    
    def __init__(self, api_key: Optional[str] = None):
        logger.info("=" * 80)
        logger.info("🔧 GooglePlacesService Initialization (Places API New)")
        logger.info("=" * 80)
        
        self.api_key = api_key
        self.client = None
        
        if api_key:
            masked_key = api_key[:10] + "..." if len(api_key) > 10 else "***"
            logger.info(f"✓ API Key provided: {masked_key}")
            logger.info(f"✓ API Key length: {len(api_key)} characters")
            logger.info(f"✓ Using Places API (New) - REST API")
            self.client = True
            
            try:
                test_response = requests.get(
                    f"{self.BASE_URL}/ChIJdd4hrwug2EcRmSrV3Vo6llI",
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
        """Search for hotels using Nearby Search"""
        log = agent_logger or logger
        
        log.info("=" * 80)
        log.info("🔍 GooglePlacesService.search_hotels() - Nearby Search")
        log.info("=" * 80)
        log.info(f"   📋 Preferences used in search:")
        log.info(f"      Location: {location or f'{latitude},{longitude}'}")
        log.info(f"      Radius: {radius}m")
        log.info(f"      Min Rating: {min_rating}")
        
        if not self.client:
            log.error("❌ Google Places client not initialized")
            return []
        
        try:
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
            
            included_types = ["hotel", "resort_hotel"]
            
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
                "rankPreference": "POPULARITY"
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": SEARCH_FIELD_MASK
            }
            
            url = f"{self.BASE_URL}:searchNearby"
            response = requests.post(url, json=request_body, headers=headers, timeout=30)
            
            log.info(f"✅ API Response: {response.status_code}")
            
            if response.status_code != 200:
                log.error(f"❌ API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            places = data.get('places', [])
            log.info(f"   Results count: {len(places)}")
            
            # Retry with 'lodging' if few results
            if len(places) < 5:
                log.warning(f"⚠️  Only {len(places)} hotels, retrying with 'lodging'")
                request_body["includedTypes"] = ["lodging"]
                response = requests.post(url, json=request_body, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    places = data.get('places', [])
                    log.info(f"   Retry results: {len(places)}")
            
            if not places:
                log.warning("⚠️  No hotels found")
                return []
            
            hotels = []
            hotels_no_rating = []
            
            for idx, place in enumerate(places, 1):
                rating = place.get('rating', 0)
                name = place.get('displayName', {}).get('text', 'Unknown')
                primary_type = place.get('primaryType', '')
                
                if rating == 0:
                    hotel = self._parse_place_result(place, log)
                    if hotel and primary_type in ['hotel', 'resort_hotel', 'motel']:
                        hotels_no_rating.append(hotel)
                    continue
                
                if rating < min_rating:
                    continue
                
                hotel = self._parse_place_result(place, log)
                if hotel:
                    hotels.append(hotel)
            
            # Include unrated if needed
            if len(hotels) < 5 and hotels_no_rating:
                num_to_add = min(5 - len(hotels), len(hotels_no_rating))
                hotels.extend(hotels_no_rating[:num_to_add])
            
            log.info(f"📊 Final count: {len(hotels)} hotels")
            return hotels
            
        except Exception as e:
            log.error(f"❌ Exception: {str(e)}")
            return []

    def search_hotels_by_text(
        self,
        query: str,
        location: str = None,
        latitude: float = None,
        longitude: float = None,
        radius: int = 5000,
        min_rating: float = 3.0,
        max_results: int = 10,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """Search for hotels using Text Search (for chain-specific queries)"""
        log = agent_logger or logger
        
        log.info(f"🔎 search_hotels_by_text(): \"{query}\"")
        
        if not self.client:
            log.error("❌ Google Places client not initialized")
            return []
        
        try:
            if location and not (latitude and longitude):
                coords = self._geocode_location(location, log)
                if coords:
                    latitude, longitude = coords
            
            request_body = {
                "textQuery": query,
                "includedType": "hotel",
                "maxResultCount": min(max_results, 20),
                "rankPreference": "RELEVANCE",
            }
            
            if latitude and longitude:
                request_body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": radius
                    }
                }
            
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": SEARCH_FIELD_MASK
            }
            
            url = f"{self.BASE_URL}:searchText"
            response = requests.post(url, json=request_body, headers=headers, timeout=30)
            
            if response.status_code != 200:
                log.warning(f"⚠️  Text Search error: {response.status_code}")
                return []
            
            data = response.json()
            places = data.get('places', [])
            log.info(f"   ✓ Text Search returned {len(places)} results")
            
            if not places:
                return []
            
            hotels = []
            for place in places:
                rating = place.get('rating', 0)
                if rating > 0 and rating < min_rating:
                    continue
                parsed = self._parse_place_result(place, log)
                if parsed:
                    hotels.append(parsed)
            
            log.info(f"   ✓ After filtering: {len(hotels)} hotels")
            return hotels
            
        except Exception as e:
            log.error(f"❌ Text Search exception: {str(e)}")
            return []

    def search_places_by_text(
        self,
        query: str,
        location: str = None,
        latitude: float = None,
        longitude: float = None,
        radius: int = 5000,
        included_type: Optional[str] = None,
        min_rating: float = 3.0,
        max_results: int = 10,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """Search for places using Text Search (for cuisine/interest queries)"""
        log = agent_logger or logger

        log.info(f"🔎 search_places_by_text(): \"{query}\"")

        if not self.client:
            log.error("❌ Google Places client not initialized")
            return []

        try:
            if location and not (latitude and longitude):
                coords = self._geocode_location(location, log)
                if coords:
                    latitude, longitude = coords

            request_body = {
                "textQuery": query,
                "maxResultCount": min(max_results, 20),
                "rankPreference": "RELEVANCE",
            }

            if included_type:
                request_body["includedType"] = included_type

            if latitude and longitude:
                request_body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": radius
                    }
                }

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": SEARCH_FIELD_MASK
            }

            url = f"{self.BASE_URL}:searchText"
            response = requests.post(url, json=request_body, headers=headers, timeout=30)

            if response.status_code != 200:
                log.warning(f"⚠️  Text Search error: {response.status_code}")
                return []

            data = response.json()
            places = data.get('places', [])
            log.info(f"   ✓ Text Search returned {len(places)} results for \"{query}\"")

            if not places:
                return []

            results = []
            for place in places:
                rating = place.get('rating', 0)
                if rating > 0 and rating < min_rating:
                    continue
                parsed = self._parse_place_result(place, log)
                if parsed:
                    results.append(parsed)

            log.info(f"   ✓ After filtering: {len(results)} places")
            return results

        except Exception as e:
            log.error(f"❌ Text Search exception: {str(e)}")
            return []

    def _geocode_location(self, location: str, log: logging.Logger = None) -> Optional[tuple]:
        """Geocode location name to coordinates"""
        log = log or logger
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": location, "key": self.api_key}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()
            if data.get('status') != 'OK':
                return None
            results = data.get('results', [])
            if not results:
                return None
            loc = results[0]['geometry']['location']
            return (loc['lat'], loc['lng'])
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
        """Search for places by category using Nearby Search"""
        log = agent_logger or logger
        
        log.info("🔍 GooglePlacesService.search_places()")
        
        if not self.client:
            log.error("❌ Google Places client not initialized")
            return {}
        
        try:
            if location and not (latitude and longitude):
                coords = self._geocode_location(location, log)
                if coords:
                    latitude, longitude = coords
                else:
                    log.error(f"❌ Could not geocode: {location}")
                    return {}
            
            if not latitude or not longitude:
                log.error("❌ Must provide location name or coordinates")
                return {}
            
            if not place_types:
                place_types = ["restaurant", "tourist_attraction", "shopping_mall", "museum", "park"]
            
            results = {}
            
            for place_type in place_types:
                log.info(f"🔎 Searching: {place_type}")
                
                request_body = {
                    "includedTypes": [place_type],
                    "maxResultCount": max_results,
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": latitude, "longitude": longitude},
                            "radius": radius
                        }
                    },
                    "rankPreference": "POPULARITY"
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": SEARCH_FIELD_MASK
                }
                
                url = f"{self.BASE_URL}:searchNearby"
                response = requests.post(url, json=request_body, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    log.warning(f"   ⚠️  API error: {response.status_code}")
                    continue
                
                data = response.json()
                places = data.get('places', [])
                log.info(f"   ✓ Found {len(places)} results")
                
                filtered_places = []
                for place in places:
                    rating = place.get('rating', 0)
                    if rating == 0 or rating < min_rating:
                        continue
                    parsed = self._parse_place_result(place, log)
                    if parsed:
                        filtered_places.append(parsed)
                
                if filtered_places:
                    results[place_type] = filtered_places
            
            total_places = sum(len(p) for p in results.values())
            log.info(f"📊 Search Complete: {total_places} places across {len(results)} categories")
            return results
            
        except Exception as e:
            log.error(f"❌ Exception: {str(e)}")
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
                return None
            
            place = response.json()
            if not place:
                return None
            
            return self._parse_place_details(place, log)
            
        except Exception as e:
            log.error(f"❌ Error fetching place details: {e}")
            return None
    
    def get_photo_url(self, photo_resource_name: str, max_width: int = 400, max_height: Optional[int] = None) -> str:
        """Generate photo URL from resource name"""
        if not self.api_key:
            return ""
        base_url = f"https://places.googleapis.com/v1/{photo_resource_name}/media"
        params = [f"maxWidthPx={max_width}"]
        if max_height:
            params.append(f"maxHeightPx={max_height}")
        params.append(f"key={self.api_key}")
        return f"{base_url}?{'&'.join(params)}"
    
    # ─────────────────────────────────────────────────────────────────────
    # v4: ENRICHED PARSING — extracts all available Google Places data
    # ─────────────────────────────────────────────────────────────────────

    def _parse_place_result(self, place: Dict[str, Any], log: logging.Logger = None) -> Optional[Dict[str, Any]]:
        """
        Parse search result into a flat dict.
        
        v4: Now extracts website, phone_number, reviews, google_url
        that were previously in the field mask but discarded.
        """
        log = log or logger
        
        try:
            location = place.get('location', {})
            
            # Photos
            photos = []
            if place.get('photos'):
                for photo in place['photos'][:5]:
                    photo_url = self.get_photo_url(photo['name'], max_width=400)
                    photos.append({"url": photo_url})
            
            # Name
            display_name = place.get('displayName', {})
            name = display_name.get('text', 'Unknown Hotel') if isinstance(display_name, dict) else str(display_name)
            
            # Price level
            price_level_str = place.get('priceLevel', 'PRICE_LEVEL_MODERATE')
            price_level = self._parse_price_level(price_level_str)
            
            # Opening hours
            opening_hours = place.get('currentOpeningHours', {})
            open_now = opening_hours.get('openNow')
            
            # v4: Reviews — parse inline from search response
            reviews = []
            if place.get('reviews'):
                for review in place['reviews'][:5]:
                    review_text_obj = review.get('text', {})
                    review_text = review_text_obj.get('text', '') if isinstance(review_text_obj, dict) else str(review_text_obj)
                    
                    author_attr = review.get('authorAttribution', {})
                    author_name = author_attr.get('displayName', 'Anonymous') if isinstance(author_attr, dict) else 'Anonymous'
                    
                    if review_text:  # Only include reviews that have text
                        reviews.append({
                            'author_name': author_name,
                            'rating': review.get('rating', 0),
                            'text': review_text,
                            'relative_time_description': review.get('relativePublishTimeDescription', ''),
                        })
            
            result = {
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
                'open_now': open_now,
                # v4: Previously in field mask but not extracted
                'website': place.get('websiteUri'),
                'phone_number': place.get('internationalPhoneNumber'),
                'google_url': place.get('googleMapsUri'),
                'reviews': reviews,
            }
            
            return result
            
        except Exception as e:
            log.warning(f"⚠️  Error parsing place: {e}")
            return None
    
    def _parse_place_details(self, place: Dict[str, Any], log: logging.Logger = None) -> Dict[str, Any]:
        """Parse detailed place information"""
        log = log or logger
        
        location = place.get('location', {})
        
        photos = []
        if place.get('photos'):
            for photo in place['photos'][:10]:
                photo_url = self.get_photo_url(photo['name'], max_width=800)
                photos.append({"url": photo_url})
        
        reviews = []
        if place.get('reviews'):
            for review in place['reviews']:
                review_text_obj = review.get('text', {})
                review_text = review_text_obj.get('text', '') if isinstance(review_text_obj, dict) else str(review_text_obj)
                author_attr = review.get('authorAttribution', {})
                author_name = author_attr.get('displayName', 'Anonymous') if isinstance(author_attr, dict) else 'Anonymous'
                
                reviews.append({
                    'author_name': author_name,
                    'rating': review.get('rating'),
                    'text': review_text,
                    'time': review.get('publishTime'),
                    'relative_time_description': review.get('relativePublishTimeDescription')
                })
        
        opening_hours = None
        if place.get('currentOpeningHours'):
            hours_data = place['currentOpeningHours']
            opening_hours = {
                'open_now': hours_data.get('openNow'),
                'weekday_text': hours_data.get('weekdayDescriptions', [])
            }
        
        display_name = place.get('displayName', {})
        name = display_name.get('text', 'Unknown') if isinstance(display_name, dict) else str(display_name)
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