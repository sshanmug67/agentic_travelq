"""
Hybrid Weather Service - Forecast + Historical Data

For travel planning:
- 0-16 days ahead: Real forecast from Open-Meteo
- 16+ days ahead: Historical climate averages

Perfect for advance trip planning!
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from utils.logging_config import log_agent_json
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


class HybridWeatherService:
    """
    Hybrid weather service for travel planning
    
    Uses real forecasts when available (up to 16 days)
    Falls back to historical averages for dates beyond forecast range
    """
    
    # Open-Meteo APIs (100% FREE, no key needed)
    GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_API = "https://api.open-meteo.com/v1/forecast"
    
    # Historical climate data by month and region
    CLIMATE_DATA = {
        # Format: month -> (temp_min, temp_max, rain_probability, description)
        # Northern Europe (UK, Northern France, Germany, etc.)
        'northern_europe': {
            1: (35, 45, 70, "cold and rainy"),
            2: (36, 46, 65, "cold with occasional rain"),
            3: (39, 50, 60, "cool with spring showers"),
            4: (43, 56, 55, "mild with scattered showers"),
            5: (49, 63, 50, "pleasant with occasional rain"),
            6: (55, 70, 45, "warm with some rain"),
            7: (59, 75, 40, "warm and mostly dry"),
            8: (59, 74, 45, "warm with occasional showers"),
            9: (54, 67, 50, "mild with increasing rain"),
            10: (48, 58, 60, "cool and rainy"),
            11: (41, 50, 70, "cold and rainy"),
            12: (37, 46, 70, "cold and rainy"),
        },
        # Southern Europe (Spain, Italy, Greece)
        'southern_europe': {
            1: (43, 55, 40, "mild and dry"),
            2: (45, 58, 35, "mild with occasional rain"),
            3: (48, 62, 30, "pleasant and mostly dry"),
            4: (52, 67, 25, "warm and dry"),
            5: (58, 74, 20, "warm and sunny"),
            6: (66, 82, 15, "hot and sunny"),
            7: (72, 88, 10, "hot and dry"),
            8: (72, 88, 10, "hot and dry"),
            9: (66, 80, 20, "warm with occasional rain"),
            10: (58, 70, 30, "mild with some rain"),
            11: (50, 61, 40, "mild and rainy"),
            12: (45, 56, 45, "cool and rainy"),
        },
        # USA East Coast
        'usa_east': {
            1: (25, 40, 60, "cold with snow/rain"),
            2: (28, 43, 55, "cold with occasional snow"),
            3: (35, 52, 50, "cool with spring rain"),
            4: (45, 63, 45, "mild with showers"),
            5: (55, 73, 40, "warm with occasional rain"),
            6: (65, 82, 40, "hot and humid"),
            7: (70, 86, 45, "hot and humid with storms"),
            8: (69, 84, 45, "hot and humid"),
            9: (62, 77, 40, "warm with occasional rain"),
            10: (50, 66, 35, "cool and pleasant"),
            11: (40, 54, 45, "cool with rain"),
            12: (30, 43, 55, "cold with rain/snow"),
        },
        # USA West Coast
        'usa_west': {
            1: (45, 58, 50, "cool and rainy"),
            2: (47, 61, 45, "cool with showers"),
            3: (49, 64, 40, "mild with occasional rain"),
            4: (52, 68, 30, "pleasant and mostly dry"),
            5: (56, 72, 20, "warm and dry"),
            6: (60, 76, 10, "warm and sunny"),
            7: (63, 79, 5, "warm and dry"),
            8: (63, 80, 5, "warm and dry"),
            9: (61, 77, 10, "warm and dry"),
            10: (56, 70, 20, "pleasant with some rain"),
            11: (50, 62, 40, "cool and rainy"),
            12: (46, 57, 50, "cool and rainy"),
        },
        # Asia (Japan, Korea)
        'east_asia': {
            1: (30, 45, 30, "cold and dry"),
            2: (32, 48, 30, "cold and dry"),
            3: (40, 56, 45, "cool with increasing rain"),
            4: (50, 65, 50, "mild with rain"),
            5: (59, 73, 55, "warm with rainy season"),
            6: (68, 79, 65, "hot and humid with rain"),
            7: (73, 84, 70, "hot and humid with heavy rain"),
            8: (75, 86, 65, "hot and humid"),
            9: (68, 79, 70, "warm with typhoon season"),
            10: (57, 68, 50, "cool with rain"),
            11: (46, 59, 35, "cool and dry"),
            12: (36, 50, 25, "cold and dry"),
        },
    }
    
    def __init__(self):
        """Initialize hybrid weather service"""
        logger.info("✅ Hybrid Weather Service initialized")
        logger.info("   • Forecast: Up to 16 days (Open-Meteo)")
        logger.info("   • Historical: For dates beyond 16 days")
    
    async def get_forecast(
        self,
        location: str,
        start_date: str,
        end_date: str,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Get weather forecast with hybrid approach
        
        Args:
            location: City name or airport code
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            agent_logger: Optional agent-specific logger
            
        Returns:
            List of daily weather forecasts (mix of real + historical)
        """
        log = agent_logger or logger
        
        try:
            log.info(f"🌤️  Fetching weather for: {location}")
            log.info(f"   Period: {start_date} to {end_date}")
            
            # Calculate days ahead
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            today = datetime.now()
            days_ahead_start = (start.date() - today.date()).days
            days_ahead_end = (end.date() - today.date()).days
            
            log.info(f"   Days ahead: {days_ahead_start} to {days_ahead_end}")
            
            # Geocode location
            lat, lon, city_name, country = await self._geocode_location(location, log)
            
            if not lat or not lon:
                log.warning(f"⚠️  Could not geocode '{location}'")
                return self._get_fallback_forecast(location, start_date, end_date, log)
            
            log.info(f"✓ Geocoded: {city_name}, {country} → ({lat}, {lon})")
            
            # Determine strategy
            forecasts = []
            
            # CASE 1: All dates within 16 days - use real forecast
            if days_ahead_end <= 16:
                log.info("📊 Strategy: Real forecast (all dates within 16 days)")
                forecasts = await self._fetch_real_forecast(
                    lat, lon, start_date, end_date, log
                )
            
            # CASE 2: All dates beyond 16 days - use historical only
            elif days_ahead_start > 16:
                log.info("📚 Strategy: Historical averages (all dates beyond 16 days)")
                region = self._detect_region(lat, lon)
                log.info(f"   Detected region: {region}")
                forecasts = self._get_historical_forecast(
                    location, start_date, end_date, region, log
                )
            
            # CASE 3: Mixed - some dates within 16 days, some beyond
            else:
                log.info("🔀 Strategy: Hybrid (mix of forecast + historical)")
                
                # Split date range
                forecast_end = (today + timedelta(days=16)).strftime('%Y-%m-%d')
                
                # Get real forecast for near dates
                real_forecasts = await self._fetch_real_forecast(
                    lat, lon, start_date, forecast_end, log
                )
                
                # Get historical for far dates
                region = self._detect_region(lat, lon)
                historical_start = (today + timedelta(days=17)).strftime('%Y-%m-%d')
                historical_forecasts = self._get_historical_forecast(
                    location, historical_start, end_date, region, log
                )
                
                forecasts = real_forecasts + historical_forecasts
                
                log.info(f"   Real forecast: {len(real_forecasts)} days")
                log.info(f"   Historical data: {len(historical_forecasts)} days")
            
            log.info(f"✅ Total forecast: {len(forecasts)} days")
            
            return forecasts
            
        except Exception as e:
            logger.error(f"❌ Weather service error: {e}")
            logger.exception("Full traceback:")
            log.error(f"❌ Error: {str(e)}")
            return self._get_fallback_forecast(location, start_date, end_date, log)
    
    async def _geocode_location(
        self,
        location: str,
        log: logging.Logger = None
    ) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """Geocode location to get coordinates and region info"""
        log = log or logger
        
        try:
            params = {
                'name': location,
                'count': 1,
                'language': 'en',
                'format': 'json'
            }
            
            log.info(f"🔍 Geocoding '{location}'...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.GEOCODING_API, params=params) as response:
                    if response.status != 200:
                        return None, None, None, None
                    
                    data = await response.json()
                    results = data.get('results', [])
                    
                    if not results:
                        return None, None, None, None
                    
                    result = results[0]
                    return (
                        result.get('latitude'),
                        result.get('longitude'),
                        result.get('name', location),
                        result.get('country', '')
                    )
                    
        except Exception as e:
            log.error(f"❌ Geocoding error: {e}")
            return None, None, None, None
    
    async def _fetch_real_forecast(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str,
        log: logging.Logger = None
    ) -> List[Dict[str, Any]]:
        """Fetch real forecast from Open-Meteo"""
        log = log or logger
        
        try:
            params = {
                'latitude': lat,
                'longitude': lon,
                'daily': ','.join([
                    'temperature_2m_max',
                    'temperature_2m_min',
                    'temperature_2m_mean',
                    'precipitation_probability_max',
                    'weathercode',
                    'windspeed_10m_max'
                ]),
                'temperature_unit': 'fahrenheit',
                'windspeed_unit': 'mph',
                'timezone': 'auto',
                'start_date': start_date,
                'end_date': end_date
            }
            
            log.info(f"🌐 Calling Open-Meteo API (real forecast)...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.FORECAST_API, params=params) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()

                    log_agent_json(data, agent_name="weather_agent",label="Open-Meteo API Raw Response")

                    daily = data.get('daily', {})
                    
                    forecasts = self._parse_openmeteo_data(daily, log, is_forecast=True)
                    
                    

                    return forecasts
                    
        except Exception as e:
            log.error(f"❌ Real forecast error: {e}")
            return []
    
    def _get_historical_forecast(
        self,
        location: str,
        start_date: str,
        end_date: str,
        region: str,
        log: logging.Logger = None
    ) -> List[Dict[str, Any]]:
        """Generate forecast based on historical climate averages"""
        log = log or logger
        
        log.info("📚 Using historical climate data...")
        
        climate = self.CLIMATE_DATA.get(region, self.CLIMATE_DATA['northern_europe'])
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        forecasts = []
        current = start
        
        while current <= end:
            month = current.month
            temp_min, temp_max, rain_prob, desc = climate[month]
            
            temp_avg = (temp_min + temp_max) / 2
            
            forecast = {
                "date": current.strftime('%Y-%m-%d'),
                "temperature": temp_avg,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "feels_like": temp_avg - 2,
                "condition": "Clouds" if rain_prob > 50 else "Clear",
                "description": f"typical {desc} for {current.strftime('%B')}",
                "icon": "10d" if rain_prob > 50 else "02d",
                "humidity": 70,
                "wind_speed": 10.0,
                "precipitation_probability": rain_prob,
                "is_historical": True  # Flag to indicate this is not a real forecast
            }
            
            log.info(f"   📊 {forecast['date']}: {forecast['description']}, "
                    f"{forecast['temp_min']:.0f}°F - {forecast['temp_max']:.0f}°F")
            
            forecasts.append(forecast)
            current += timedelta(days=1)
        
        return forecasts
    
    def _parse_openmeteo_data(
        self,
        daily: Dict[str, Any],
        log: logging.Logger,
        is_forecast: bool = True
    ) -> List[Dict[str, Any]]:
        """Parse Open-Meteo daily data"""
        dates = daily.get('time', [])
        temp_max = daily.get('temperature_2m_max', [])
        temp_min = daily.get('temperature_2m_min', [])
        temp_mean = daily.get('temperature_2m_mean', [])
        precipitation = daily.get('precipitation_probability_max', [])
        weathercodes = daily.get('weathercode', [])
        wind_speed = daily.get('windspeed_10m_max', [])
        
        forecasts = []
        
        for idx in range(len(dates)):
            wmo_code = weathercodes[idx] if idx < len(weathercodes) else 0
            condition, description, icon = self._wmo_code_to_weather(wmo_code)
            
            forecast = {
                "date": dates[idx],
                "temperature": temp_mean[idx] if idx < len(temp_mean) else 0,
                "temp_min": temp_min[idx] if idx < len(temp_min) else 0,
                "temp_max": temp_max[idx] if idx < len(temp_max) else 0,
                "feels_like": temp_mean[idx] - 2 if idx < len(temp_mean) else 0,
                "condition": condition,
                "description": description,
                "icon": icon,
                "humidity": 70,
                "wind_speed": wind_speed[idx] if idx < len(wind_speed) else 0,
                "precipitation_probability": precipitation[idx] if idx < len(precipitation) else 0,
                "is_historical": False  # Real forecast
            }
            
            log.info(f"   ✓ {forecast['date']}: {forecast['description']}, "
                    f"{forecast['temp_min']:.1f}°F - {forecast['temp_max']:.1f}°F")
            
            forecasts.append(forecast)
        
        return forecasts
    
    def _detect_region(self, lat: float, lon: float) -> str:
        """Detect climate region from coordinates"""
        # Northern Europe
        if 50 <= lat <= 60 and -10 <= lon <= 30:
            return 'northern_europe'
        # Southern Europe
        elif 35 <= lat < 50 and -10 <= lon <= 30:
            return 'southern_europe'
        # USA East Coast
        elif 25 <= lat <= 45 and -85 <= lon <= -65:
            return 'usa_east'
        # USA West Coast
        elif 30 <= lat <= 50 and -125 <= lon <= -115:
            return 'usa_west'
        # East Asia
        elif 25 <= lat <= 45 and 120 <= lon <= 145:
            return 'east_asia'
        else:
            return 'northern_europe'  # Default
    
    def _wmo_code_to_weather(self, code: int) -> Tuple[str, str, str]:
        """Convert WMO weather code to condition, description, icon"""
        wmo_map = {
            0: ("Clear", "clear sky", "01d"),
            1: ("Clear", "mainly clear", "01d"),
            2: ("Clouds", "partly cloudy", "02d"),
            3: ("Clouds", "overcast", "03d"),
            45: ("Fog", "foggy", "50d"),
            48: ("Fog", "depositing rime fog", "50d"),
            51: ("Drizzle", "light drizzle", "09d"),
            53: ("Drizzle", "moderate drizzle", "09d"),
            55: ("Drizzle", "dense drizzle", "09d"),
            61: ("Rain", "slight rain", "10d"),
            63: ("Rain", "moderate rain", "10d"),
            65: ("Rain", "heavy rain", "10d"),
            71: ("Snow", "slight snow", "13d"),
            73: ("Snow", "moderate snow", "13d"),
            75: ("Snow", "heavy snow", "13d"),
            80: ("Rain", "slight rain showers", "09d"),
            81: ("Rain", "moderate rain showers", "09d"),
            82: ("Rain", "violent rain showers", "09d"),
            85: ("Snow", "slight snow showers", "13d"),
            86: ("Snow", "heavy snow showers", "13d"),
            95: ("Thunderstorm", "thunderstorm", "11d"),
            96: ("Thunderstorm", "thunderstorm with slight hail", "11d"),
            99: ("Thunderstorm", "thunderstorm with heavy hail", "11d"),
        }
        return wmo_map.get(code, ("Clear", "clear sky", "01d"))
    
    def _get_fallback_forecast(
        self,
        location: str,
        start_date: str,
        end_date: str,
        log: logging.Logger = None
    ) -> List[Dict[str, Any]]:
        """Simple fallback when everything fails"""
        return self._get_historical_forecast(
            location, start_date, end_date, 'northern_europe', log
        )


# ============================================================================
# SINGLETON
# ============================================================================

_hybrid_weather_instance = None


def get_weather_service():
    """Get singleton instance"""
    global _hybrid_weather_instance
    if _hybrid_weather_instance is None:
        _hybrid_weather_instance = HybridWeatherService()
    return _hybrid_weather_instance