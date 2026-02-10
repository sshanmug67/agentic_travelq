"""
Weather Agent - With Real OpenWeather API Integration

Fetches real weather forecasts using OpenWeather One Call API 3.0.
"""
import logging
from typing import Dict, Any
from agents.base_agent_old import BaseAgent
from services.weather_service import get_weather_service
from config.settings import settings

# Setup regular logger
logger = logging.getLogger(__name__)

# Setup dedicated agent logger
from utils.logging_config import setup_agent_logging
agent_logger = setup_agent_logging("weather_agent", fresh_start=True)


class WeatherAgent(BaseAgent):
    """Agent responsible for fetching and processing weather forecasts"""
    
    def __init__(self):
        super().__init__(
            name="WeatherAgent",
            system_message="""You are a weather forecast expert. Your role is to:
            1. Provide accurate weather forecasts for travel destinations
            2. Highlight important weather conditions (rain, extreme temperatures, etc.)
            3. Give practical travel advice based on weather conditions
            4. Suggest appropriate clothing and activities based on forecast""",
            llm_config={"config_list": settings.autogen_config_list if hasattr(settings, 'autogen_config_list') else []}
        )
        
        # Get service
        self.weather_service = get_weather_service()
        
        # Check service type (works with any weather service)
        service_type = type(self.weather_service).__name__
        logger.info(f"✅ WeatherAgent: Initialized with {service_type}")
        agent_logger.info(f"✅ Initialized with {service_type}")
    
    async def process_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process weather forecast request
        
        Args:
            data: Request data containing:
                - destination: Destination city or airport code
                - start_date: Trip start date
                - end_date: Trip end date
                
        Returns:
            Dictionary with weather forecast
        """
        logger.info("=" * 70)
        logger.info("🌤️  WeatherAgent: Processing request")
        logger.info("=" * 70)
        
        agent_logger.info("=" * 70)
        agent_logger.info("🌤️  Processing Weather Forecast Request")
        agent_logger.info("=" * 70)
        
        try:
            destination = data.get("destination", "")
            start_date = data.get("start_date", "")
            end_date = data.get("end_date", "")
            
            # Validate inputs
            if not destination or not start_date or not end_date:
                logger.error("❌ Missing required parameters")
                agent_logger.error("❌ Missing required parameters")
                agent_logger.info("=" * 70)
                return {
                    "forecast": [],
                    "error": "Missing required parameters: destination, start_date, end_date"
                }
            
            agent_logger.info(f"📍 Forecast Parameters:")
            agent_logger.info(f"   Destination: {destination}")
            agent_logger.info(f"   Start Date: {start_date}")
            agent_logger.info(f"   End Date: {end_date}")
            agent_logger.info("")
            
            logger.info(f"🔍 Getting forecast for: {destination}")
            
            # Fetch weather forecast
            agent_logger.info("🔍 Initiating weather service call...")
            forecast = await self.weather_service.get_forecast(
                location=destination,
                start_date=start_date,
                end_date=end_date,
                agent_logger=agent_logger
            )
            
            logger.info(f"✅ Retrieved {len(forecast)} day forecast")
            agent_logger.info("")
            agent_logger.info(f"✅ Forecast complete: {len(forecast)} days")
            
            # Analyze forecast
            if forecast:
                agent_logger.info("")
                agent_logger.info("📊 Weather Summary:")
                
                temps = [day.get('temperature', 0) for day in forecast]
                rain_days = sum(1 for day in forecast if day.get('precipitation_probability', 0) > 50)
                
                agent_logger.info(f"   Total days: {len(forecast)}")
                agent_logger.info(f"   Temp range: {min(temps):.1f}°F - {max(temps):.1f}°F")
                agent_logger.info(f"   Average temp: {sum(temps)/len(temps):.1f}°F")
                agent_logger.info(f"   Rain days (>50%): {rain_days}")
                
                # Weather warnings
                warnings = []
                if rain_days > 0:
                    warnings.append(f"☔ Rain expected on {rain_days} day(s)")
                    agent_logger.info(f"   ⚠️  Rain expected on {rain_days} day(s)")
                
                if min(temps) < 40:
                    warnings.append("🧥 Cold weather - pack warm clothes")
                    agent_logger.info("   ⚠️  Cold weather expected")
                
                if max(temps) > 85:
                    warnings.append("🌡️ Hot weather - stay hydrated")
                    agent_logger.info("   ⚠️  Hot weather expected")
            
            logger.info("=" * 70)
            
            # Generate AI suggestions
            suggestions = []
            if self.llm_enabled and forecast:
                agent_logger.info("")
                agent_logger.info("💡 Generating AI suggestions...")
                suggestions = self._generate_weather_suggestions(forecast)
                if suggestions:
                    agent_logger.info("💡 AI Suggestions:")
                    for suggestion in suggestions:
                        agent_logger.info(f"   {suggestion}")
            
            agent_logger.info("=" * 70)
            
            return {
                "forecast": forecast,
                "suggestions": suggestions,
                "warnings": warnings if forecast else [],
                "search_params": {
                    "destination": destination,
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
            
        except Exception as e:
            logger.error(f"❌ WeatherAgent error: {str(e)}")
            logger.exception("Full traceback:")
            
            agent_logger.error(f"❌ ERROR: {str(e)}")
            agent_logger.error("Full traceback:", exc_info=True)
            agent_logger.info("=" * 70)
            
            logger.info("=" * 70)
            
            return {
                "forecast": [],
                "error": str(e),
                "suggestions": [],
                "warnings": []
            }
    
    def _generate_weather_suggestions(self, forecast: list) -> list:
        """Generate intelligent weather-based suggestions"""
        if not forecast:
            return []
        
        suggestions = []
        
        # Temperature analysis
        temps = [day.get('temperature', 0) for day in forecast]
        avg_temp = sum(temps) / len(temps)
        
        if avg_temp < 50:
            suggestions.append("🧥 Pack warm layers - temperatures will be cool")
        elif avg_temp > 75:
            suggestions.append("👕 Light clothing recommended - warm weather ahead")
        else:
            suggestions.append("👕 Mild weather - pack versatile layers")
        
        # Rain analysis
        rainy_days = [day for day in forecast if day.get('precipitation_probability', 0) > 50]
        if rainy_days:
            suggestions.append(f"☔ Rain expected on {len(rainy_days)} day(s) - pack umbrella")
        
        # Wind analysis
        windy_days = [day for day in forecast if day.get('wind_speed', 0) > 15]
        if windy_days:
            suggestions.append("🌬️ Windy conditions expected - pack a windbreaker")
        
        return suggestions


# Create singleton instance
weather_agent = WeatherAgent()