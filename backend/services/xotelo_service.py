"""
Xotelo Hotel Pricing Service - Free Price Comparison API

Provides:
- Real-time hotel pricing from 200+ OTAs
- Price comparison across booking sites
- Day heatmap for finding cheapest dates
- Hotel search by name/location

API: https://xotelo.com/
Pricing: FREE (with rate limits)
Location: backend/services/xotelo_service.py
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from config.settings import settings

logger = logging.getLogger(__name__)


class XoteloService:
    """Service for interacting with Xotelo Hotel Pricing API"""
    
    BASE_URL = "https://data.xotelo.com/api"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Xotelo service
        
        Args:
            api_key: Xotelo API key (optional - works without for basic use)
        """
        self.api_key = api_key
        self.session = requests.Session()
        
        if self.api_key:
            logger.info("✅ Xotelo API initialized with API key")
        else:
            logger.warning("⚠️  Xotelo API initialized without API key (limited access)")
    
    def search_hotels(
        self,
        query: str,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels by name or location
        
        Args:
            query: Hotel name or location (e.g., "Grand Plaza London")
            agent_logger: Optional agent-specific logger
            
        Returns:
            List of hotel dictionaries with hotel_key and basic info
        """
        log = agent_logger or logger
        
        try:
            log.info(f"🔍 Searching Xotelo for: {query}")
            
            url = f"{self.BASE_URL}/search"
            params = {'query': query}
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                log.warning(f"⚠️  No hotels found for: {query}")
                return []
            
            log.info(f"✅ Found {len(data)} hotels in Xotelo")
            
            return data
            
        except requests.exceptions.Timeout:
            log.error(f"❌ Xotelo search timeout for: {query}")
            return []
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Xotelo search error: {e}")
            return []
        except Exception as e:
            log.error(f"❌ Unexpected error in Xotelo search: {e}")
            return []
    
    def get_hotel_rates(
        self,
        hotel_key: str,
        check_in_date: str,
        check_out_date: str,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get pricing for a specific hotel
        
        Args:
            hotel_key: Xotelo hotel key (from search results)
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with pricing information from all OTAs
        """
        log = agent_logger or logger
        
        try:
            log.info(f"💰 Getting rates for hotel_key: {hotel_key}")
            
            url = f"{self.BASE_URL}/rates"
            params = {
                'hotel_key': hotel_key,
                'chk_in': check_in_date,
                'chk_out': check_out_date
            }
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                log.warning(f"⚠️  No rates found for hotel_key: {hotel_key}")
                return None
            
            log.info(f"✅ Retrieved rates from {len(data.get('providers', []))} OTAs")
            
            return data
            
        except requests.exceptions.Timeout:
            log.error(f"❌ Xotelo rates timeout for: {hotel_key}")
            return None
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Xotelo rates error: {e}")
            return None
        except Exception as e:
            log.error(f"❌ Unexpected error getting rates: {e}")
            return None
    
    def get_price_for_hotel(
        self,
        hotel_name: str,
        check_in_date: str,
        check_out_date: str,
        location: Optional[str] = None,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Complete workflow: Search hotel + Get pricing
        
        Args:
            hotel_name: Name of the hotel
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            location: Optional location to help narrow search
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with parsed pricing information
        """
        log = agent_logger or logger
        
        # Step 1: Search for hotel
        query = f"{hotel_name} {location}" if location else hotel_name
        search_results = self.search_hotels(query, agent_logger=log)
        
        if not search_results:
            log.warning(f"⚠️  Could not find hotel: {hotel_name}")
            return None
        
        # Take first result (best match)
        hotel = search_results[0]
        hotel_key = hotel.get('hotel_key')
        
        if not hotel_key:
            log.warning(f"⚠️  No hotel_key in search results")
            return None
        
        log.info(f"✓ Found hotel: {hotel.get('name', 'Unknown')} (key: {hotel_key})")
        
        # Step 2: Get rates
        rates_data = self.get_hotel_rates(
            hotel_key=hotel_key,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            agent_logger=log
        )
        
        if not rates_data:
            return None
        
        # Step 3: Parse and return best pricing
        return self._parse_pricing_data(rates_data, check_in_date, check_out_date, log)
    
    def _parse_pricing_data(
        self,
        data: Dict[str, Any],
        check_in: str,
        check_out: str,
        log: logging.Logger
    ) -> Dict[str, Any]:
        """
        Parse Xotelo pricing response
        
        Returns structured pricing data with:
        - Best price
        - Average price
        - Price per night
        - Total price
        - Cheapest provider
        - All provider prices
        """
        try:
            # Calculate number of nights
            check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
            check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
            num_nights = (check_out_dt - check_in_dt).days
            
            if num_nights <= 0:
                log.warning("⚠️  Invalid date range")
                return None
            
            # Extract provider prices
            providers = data.get('providers', {})
            
            if not providers:
                log.warning("⚠️  No provider pricing data")
                return None
            
            # Parse all provider prices
            all_prices = []
            provider_list = []
            
            for provider_name, provider_data in providers.items():
                if isinstance(provider_data, dict) and 'price' in provider_data:
                    price = float(provider_data['price'])
                    all_prices.append(price)
                    provider_list.append({
                        'provider': provider_name,
                        'total_price': price,
                        'price_per_night': round(price / num_nights, 2),
                        'url': provider_data.get('url')
                    })
            
            if not all_prices:
                log.warning("⚠️  No valid prices found")
                return None
            
            # Calculate best and average prices
            best_price = min(all_prices)
            avg_price = sum(all_prices) / len(all_prices)
            
            # Find cheapest provider
            cheapest_provider = min(provider_list, key=lambda x: x['total_price'])
            
            pricing = {
                'total_price': round(best_price, 2),
                'price_per_night': round(best_price / num_nights, 2),
                'currency': 'USD',  # Xotelo defaults to USD
                'num_nights': num_nights,
                'price_source': 'xotelo',
                'is_estimated': False,
                
                # Additional info
                'average_price': round(avg_price, 2),
                'cheapest_provider': cheapest_provider['provider'],
                'cheapest_url': cheapest_provider.get('url'),
                'num_providers': len(all_prices),
                'all_providers': provider_list
            }
            
            log.info(f"✅ Parsed pricing: ${pricing['total_price']:.2f} total "
                    f"(${pricing['price_per_night']:.2f}/night) "
                    f"from {pricing['cheapest_provider']}")
            
            return pricing
            
        except Exception as e:
            log.error(f"❌ Error parsing pricing data: {e}")
            return None
    
    def get_price_heatmap(
        self,
        hotel_key: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get price heatmap showing cheapest/expensive days
        
        Args:
            hotel_key: Xotelo hotel key
            month: Month (1-12, optional - defaults to current)
            year: Year (optional - defaults to current)
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with heatmap data
        """
        log = agent_logger or logger
        
        try:
            log.info(f"📊 Getting price heatmap for hotel_key: {hotel_key}")
            
            url = f"{self.BASE_URL}/heatmap"
            params = {'hotel_key': hotel_key}
            
            if month:
                params['month'] = month
            if year:
                params['year'] = year
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            log.info(f"✅ Retrieved price heatmap")
            
            return data
            
        except Exception as e:
            log.error(f"❌ Error getting heatmap: {e}")
            return None


# ============================================================================
# SINGLETON INSTANCE - LAZY INITIALIZATION
# ============================================================================

_xotelo_service_instance = None


def get_xotelo_service() -> XoteloService:
    """Get singleton instance of XoteloService (lazy initialization)"""
    global _xotelo_service_instance
    
    if _xotelo_service_instance is None:
        # Xotelo API key is optional (works without it)
        api_key = getattr(settings, 'xotelo_api_key', None)
        _xotelo_service_instance = XoteloService(api_key=api_key)
    
    return _xotelo_service_instance