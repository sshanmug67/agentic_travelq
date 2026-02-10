"""
Airport Lookup Service - Convert City Names to Airport Codes

Provides mapping from city names to their primary airport codes.
For cities with multiple airports, returns the primary one.
"""
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class AirportLookupService:
    """Service for looking up airport codes from city names"""
    
    # Major cities and their primary airports
    CITY_TO_AIRPORT = {
        # United States
        "new york": "JFK",
        "nyc": "JFK",
        "new york city": "JFK",
        "los angeles": "LAX",
        "la": "LAX",
        "chicago": "ORD",
        "houston": "IAH",
        "phoenix": "PHX",
        "philadelphia": "PHL",
        "san antonio": "SAT",
        "san diego": "SAN",
        "dallas": "DFW",
        "san jose": "SJC",
        "austin": "AUS",
        "jacksonville": "JAX",
        "fort worth": "DFW",
        "columbus": "CMH",
        "charlotte": "CLT",
        "san francisco": "SFO",
        "sf": "SFO",
        "indianapolis": "IND",
        "seattle": "SEA",
        "denver": "DEN",
        "washington": "IAD",
        "dc": "IAD",
        "boston": "BOS",
        "nashville": "BNA",
        "detroit": "DTW",
        "portland": "PDX",
        "las vegas": "LAS",
        "vegas": "LAS",
        "miami": "MIA",
        "atlanta": "ATL",
        "orlando": "MCO",
        "tampa": "TPA",
        "minneapolis": "MSP",
        "cleveland": "CLE",
        "pittsburgh": "PIT",
        "st louis": "STL",
        "baltimore": "BWI",
        "salt lake city": "SLC",
        "kansas city": "MCI",
        "raleigh": "RDU",
        
        # United Kingdom
        "london": "LHR",
        "manchester": "MAN",
        "birmingham": "BHX",
        "glasgow": "GLA",
        "edinburgh": "EDI",
        "liverpool": "LPL",
        "bristol": "BRS",
        "newcastle": "NCL",
        "belfast": "BFS",
        
        # Europe
        "paris": "CDG",
        "rome": "FCO",
        "madrid": "MAD",
        "barcelona": "BCN",
        "berlin": "BER",
        "amsterdam": "AMS",
        "frankfurt": "FRA",
        "munich": "MUC",
        "milan": "MXP",
        "vienna": "VIE",
        "zurich": "ZRH",
        "brussels": "BRU",
        "copenhagen": "CPH",
        "stockholm": "ARN",
        "oslo": "OSL",
        "dublin": "DUB",
        "lisbon": "LIS",
        "athens": "ATH",
        "prague": "PRG",
        "budapest": "BUD",
        "warsaw": "WAW",
        
        # Asia
        "tokyo": "NRT",
        "beijing": "PEK",
        "shanghai": "PVG",
        "hong kong": "HKG",
        "singapore": "SIN",
        "seoul": "ICN",
        "dubai": "DXB",
        "bangkok": "BKK",
        "mumbai": "BOM",
        "delhi": "DEL",
        "taipei": "TPE",
        "kuala lumpur": "KUL",
        "jakarta": "CGK",
        "manila": "MNL",
        "osaka": "KIX",
        
        # Middle East
        "tel aviv": "TLV",
        "doha": "DOH",
        "abu dhabi": "AUH",
        "riyadh": "RUH",
        "jeddah": "JED",
        "cairo": "CAI",
        "istanbul": "IST",
        
        # Oceania
        "sydney": "SYD",
        "melbourne": "MEL",
        "brisbane": "BNE",
        "perth": "PER",
        "auckland": "AKL",
        
        # Africa
        "johannesburg": "JNB",
        "cape town": "CPT",
        "lagos": "LOS",
        "nairobi": "NBO",
        "casablanca": "CMN",
        
        # South America
        "sao paulo": "GRU",
        "rio de janeiro": "GIG",
        "rio": "GIG",
        "buenos aires": "EZE",
        "lima": "LIM",
        "bogota": "BOG",
        "santiago": "SCL",
        
        # Canada
        "toronto": "YYZ",
        "vancouver": "YVR",
        "montreal": "YUL",
        "calgary": "YYC",
        "ottawa": "YOW",
        
        # Mexico
        "mexico city": "MEX",
        "cancun": "CUN",
        "guadalajara": "GDL",
        "monterrey": "MTY",
    }
    
    # Cities with multiple major airports
    MULTI_AIRPORT_CITIES = {
        "new york": ["JFK", "LGA", "EWR"],
        "london": ["LHR", "LGW", "STN", "LCY", "LTN"],
        "chicago": ["ORD", "MDW"],
        "paris": ["CDG", "ORY"],
        "milan": ["MXP", "LIN"],
        "tokyo": ["NRT", "HND"],
        "bangkok": ["BKK", "DMK"],
        "houston": ["IAH", "HOU"],
        "washington": ["IAD", "DCA", "BWI"],
        "los angeles": ["LAX", "ONT", "BUR", "SNA"],
    }
    
    def __init__(self):
        """Initialize airport lookup service"""
        logger.info("✅ AirportLookupService: Initialized")
    
    def convert_to_airport_code(
        self, 
        location: str,
        prefer_primary: bool = True
    ) -> Optional[str]:
        """
        Convert city name to airport code
        
        Args:
            location: City name or airport code
            prefer_primary: If True, return primary airport for multi-airport cities
            
        Returns:
            Airport code (IATA) or None if not found
        """
        # Clean input
        location_clean = location.strip().lower()
        
        # Check if already an airport code (3 letters, uppercase)
        if len(location) == 3 and location.isupper():
            logger.info(f"✓ '{location}' is already an airport code")
            return location
        
        # Look up in mapping
        if location_clean in self.CITY_TO_AIRPORT:
            airport_code = self.CITY_TO_AIRPORT[location_clean]
            logger.info(f"✓ Converted '{location}' → {airport_code}")
            return airport_code
        
        # Not found
        logger.warning(f"⚠️  Could not find airport for '{location}'")
        return None
    
    def get_all_airports_for_city(self, city: str) -> List[str]:
        """
        Get all airports for a city (for cities with multiple airports)
        
        Args:
            city: City name
            
        Returns:
            List of airport codes
        """
        city_clean = city.strip().lower()
        
        if city_clean in self.MULTI_AIRPORT_CITIES:
            return self.MULTI_AIRPORT_CITIES[city_clean]
        elif city_clean in self.CITY_TO_AIRPORT:
            return [self.CITY_TO_AIRPORT[city_clean]]
        else:
            return []
    
    def is_multi_airport_city(self, city: str) -> bool:
        """Check if city has multiple major airports"""
        return city.strip().lower() in self.MULTI_AIRPORT_CITIES
    
    def validate_airport_code(self, code: str) -> bool:
        """
        Validate if string is a valid airport code format
        
        Args:
            code: Potential airport code
            
        Returns:
            True if valid format (3 uppercase letters)
        """
        return len(code) == 3 and code.isalpha() and code.isupper()


# Singleton instance
_airport_lookup_instance = None


def get_airport_lookup_service() -> AirportLookupService:
    """Get singleton instance of AirportLookupService"""
    global _airport_lookup_instance
    
    if _airport_lookup_instance is None:
        _airport_lookup_instance = AirportLookupService()
    
    return _airport_lookup_instance