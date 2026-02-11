"""
Booking Link Generator Utility

Generates deep links to major hotel booking websites:
- Booking.com
- Hotels.com
- Expedia
- Agoda
- TripAdvisor

These links allow users to check real prices and complete bookings.
Can include affiliate IDs for commission tracking (optional).

Location: backend/utils/booking_links.py
"""
import urllib.parse
from typing import Dict, Optional
from datetime import datetime


class BookingLinkGenerator:
    """Generate booking links for major OTA websites"""
    
    def __init__(
        self,
        booking_affiliate_id: Optional[str] = None,
        expedia_affiliate_id: Optional[str] = None,
        hotels_affiliate_id: Optional[str] = None
    ):
        """
        Initialize with optional affiliate IDs
        
        Args:
            booking_affiliate_id: Booking.com affiliate ID
            expedia_affiliate_id: Expedia affiliate ID
            hotels_affiliate_id: Hotels.com affiliate ID
        """
        self.booking_affiliate_id = booking_affiliate_id
        self.expedia_affiliate_id = expedia_affiliate_id
        self.hotels_affiliate_id = hotels_affiliate_id
    
    def generate_booking_com_link(
        self,
        hotel_name: str,
        city: str,
        check_in: str,
        check_out: str,
        adults: int = 2,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> str:
        """
        Generate Booking.com search link
        
        Args:
            hotel_name: Name of the hotel
            city: City name
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            adults: Number of adults
            latitude: Optional hotel latitude
            longitude: Optional hotel longitude
            
        Returns:
            Booking.com URL
        """
        base_url = "https://www.booking.com/searchresults.html"
        
        # Build search string (hotel name + city)
        search_query = f"{hotel_name} {city}".strip()
        
        params = {
            'ss': search_query,
            'checkin': check_in,
            'checkout': check_out,
            'group_adults': adults,
            'no_rooms': 1
        }
        
        # Add coordinates if available (more accurate)
        if latitude and longitude:
            params['latitude'] = latitude
            params['longitude'] = longitude
            params['radius'] = 1  # 1 km radius
        
        # Add affiliate ID if available
        if self.booking_affiliate_id:
            params['aid'] = self.booking_affiliate_id
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def generate_hotels_com_link(
        self,
        hotel_name: str,
        city: str,
        check_in: str,
        check_out: str,
        adults: int = 2
    ) -> str:
        """
        Generate Hotels.com search link
        
        Args:
            hotel_name: Name of the hotel
            city: City name
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            adults: Number of adults
            
        Returns:
            Hotels.com URL
        """
        base_url = "https://www.hotels.com/search.do"
        
        search_query = f"{hotel_name} {city}".strip()
        
        params = {
            'q-destination': search_query,
            'q-check-in': check_in,
            'q-check-out': check_out,
            'q-rooms': 1,
            'q-room-0-adults': adults
        }
        
        # Add affiliate ID if available
        if self.hotels_affiliate_id:
            params['pwaId'] = self.hotels_affiliate_id
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def generate_expedia_link(
        self,
        hotel_name: str,
        city: str,
        check_in: str,
        check_out: str,
        adults: int = 2
    ) -> str:
        """
        Generate Expedia search link
        
        Args:
            hotel_name: Name of the hotel
            city: City name
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            adults: Number of adults
            
        Returns:
            Expedia URL
        """
        base_url = "https://www.expedia.com/Hotel-Search"
        
        search_query = f"{hotel_name} {city}".strip()
        
        params = {
            'destination': search_query,
            'startDate': check_in,
            'endDate': check_out,
            'adults': adults,
            'rooms': 1
        }
        
        # Add affiliate ID if available
        if self.expedia_affiliate_id:
            params['semcid'] = self.expedia_affiliate_id
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def generate_agoda_link(
        self,
        hotel_name: str,
        city: str,
        check_in: str,
        check_out: str,
        adults: int = 2
    ) -> str:
        """
        Generate Agoda search link
        
        Args:
            hotel_name: Name of the hotel
            city: City name
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            adults: Number of adults
            
        Returns:
            Agoda URL
        """
        base_url = "https://www.agoda.com/search"
        
        # Convert dates to Agoda format (YYYY-MM-DD is fine)
        search_query = f"{hotel_name} {city}".strip()
        
        params = {
            'city': city,
            'checkIn': check_in,
            'checkOut': check_out,
            'rooms': 1,
            'adults': adults,
            'searchText': search_query
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def generate_tripadvisor_link(
        self,
        hotel_name: str,
        city: str,
        check_in: str,
        check_out: str
    ) -> str:
        """
        Generate TripAdvisor search link
        
        Args:
            hotel_name: Name of the hotel
            city: City name
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            
        Returns:
            TripAdvisor URL
        """
        base_url = "https://www.tripadvisor.com/Search"
        
        search_query = f"{hotel_name} {city}".strip()
        
        params = {
            'q': search_query,
            'searchSessionId': 'generated',  # Can be any value
            'geo': 1,  # Hotels filter
            'checkin': check_in,
            'checkout': check_out
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def generate_all_links(
        self,
        hotel_name: str,
        city: str,
        check_in: str,
        check_out: str,
        adults: int = 2,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Generate all booking links at once
        
        Returns:
            Dictionary with all booking links and metadata
        """
        return {
            'booking_com': {
                'name': 'Booking.com',
                'url': self.generate_booking_com_link(
                    hotel_name, city, check_in, check_out, adults, latitude, longitude
                ),
                'label': 'Check Prices on Booking.com',
                'icon': '🏨'
            },
            'hotels_com': {
                'name': 'Hotels.com',
                'url': self.generate_hotels_com_link(
                    hotel_name, city, check_in, check_out, adults
                ),
                'label': 'Check Prices on Hotels.com',
                'icon': '🏩'
            },
            'expedia': {
                'name': 'Expedia',
                'url': self.generate_expedia_link(
                    hotel_name, city, check_in, check_out, adults
                ),
                'label': 'Check Prices on Expedia',
                'icon': '✈️'
            },
            'agoda': {
                'name': 'Agoda',
                'url': self.generate_agoda_link(
                    hotel_name, city, check_in, check_out, adults
                ),
                'label': 'Check Prices on Agoda',
                'icon': '🌏'
            },
            'tripadvisor': {
                'name': 'TripAdvisor',
                'url': self.generate_tripadvisor_link(
                    hotel_name, city, check_in, check_out
                ),
                'label': 'View on TripAdvisor',
                'icon': '🦉'
            }
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_date_for_url(date_str: str, output_format: str = "%Y-%m-%d") -> str:
    """
    Convert date string to specific format for URLs
    
    Args:
        date_str: Input date (various formats accepted)
        output_format: Desired output format
        
    Returns:
        Formatted date string
    """
    try:
        # Try parsing common formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime(output_format)
            except ValueError:
                continue
        
        # If no format matched, return original
        return date_str
    except:
        return date_str


def generate_price_indicator(price_level: Optional[int]) -> str:
    """
    Convert Google Places price_level (0-4) to $ symbols
    
    Args:
        price_level: Google Places price level (0-4)
        
    Returns:
        Price indicator string (e.g., "$$$")
    """
    indicators = {
        0: "Free",
        1: "$",
        2: "$$",
        3: "$$$",
        4: "$$$$"
    }
    return indicators.get(price_level, "$$")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create default instance (can be overridden with affiliate IDs)
booking_link_generator = BookingLinkGenerator()