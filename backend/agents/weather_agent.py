"""
Mock Weather Agent - Returns Structured Mock Data
Location: backend/agents/weather_agent.py
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import random

from agents.base_agent import TravelQBaseAgent
from models.trip import Weather
from utils.logging_config import log_agent_raw, log_agent_json


class WeatherAgent(TravelQBaseAgent):
    """
    Mock Weather Agent - Returns structured weather forecast data
    """
    
    def __init__(self, **kwargs):
        system_message = """
You are a Weather Forecast Agent specializing in travel weather.

Your job:
1. Provide weather forecast for destination during travel dates
2. Include: temperature, conditions, precipitation, humidity
3. Give packing recommendations based on weather
4. Highlight any weather concerns

Always return results in structured format with helpful advice.
"""
        super().__init__(
            name="WeatherAgent",
            llm_config=self.create_llm_config(),
            agent_type="WeatherAgent",
            system_message=system_message,
            description="Provides weather forecasts and packing recommendations for destinations",  # ✅ Added
            **kwargs
        )
        
        log_agent_raw("🌤️  WeatherAgent initialized (MOCK MODE)", agent_name="WeatherAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None,
    ) -> str:  # ✅ Fixed: Changed from tuple to str
        """
        Generate weather forecast results
        
        Returns structured mock data
        """
        log_agent_raw("🔍 Fetching weather forecast (mock data)...", agent_name="WeatherAgent")
        
        # ✅ ADD THIS - Log incoming message
        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name
            )


        # Get preferences from conversation
        preferences = self._extract_preferences_from_messages(messages)
        
        # Generate mock weather
        mock_weather = self._generate_mock_weather(preferences)
        
        # Create structured response
        response = self._create_structured_response(mock_weather, preferences)
        
        log_agent_json({
            "forecast_days": len(mock_weather),
            "destination": preferences.get("destination", "Unknown"),
            "start_date": preferences.get("departure_date", "Unknown")
        }, agent_name="WeatherAgent", label="Mock Weather Forecast")
        
        # ✅ ADD THIS - Log outgoing response
        self.log_conversation_message(
            message_type="OUTGOING",
            content=response,
            sender="chat_manager"
        )

        return self.signal_completion(response)  # ✅ Fixed: Return string only
    
    def _extract_preferences_from_messages(self, messages: List[Dict]) -> Dict:
        """Extract preferences from conversation"""
        return {
            "destination": "Tokyo",
            "departure_date": "2026-06-01",
            "return_date": "2026-06-08"
        }
    
    def _generate_mock_weather(self, preferences: Dict) -> List[Weather]:
        """Generate realistic mock weather data"""
        destination = preferences.get("destination", "Tokyo")
        start_date = preferences.get("departure_date", "2026-06-01")
        end_date = preferences.get("return_date", "2026-06-08")
        
        # Parse dates
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        except:
            start_dt = datetime.now() + timedelta(days=30)
            end_dt = start_dt + timedelta(days=7)
        
        # Generate weather for each day
        weather_list = []
        current_date = start_dt
        
        # Base weather conditions (simulating June in Tokyo)
        base_temp = 75  # Fahrenheit
        conditions_pool = [
            ("Partly Cloudy", "02d", 0.2),
            ("Sunny", "01d", 0.1),
            ("Cloudy", "03d", 0.3),
            ("Light Rain", "10d", 0.6),
            ("Clear", "01d", 0.05)
        ]
        
        while current_date <= end_dt:
            # Add some variation
            temp_var = random.randint(-5, 5)
            condition, icon, precip = random.choice(conditions_pool)
            
            weather = Weather(
                date=current_date.strftime("%Y-%m-%d"),
                temperature=base_temp + temp_var,
                feels_like=base_temp + temp_var - 2,
                temp_min=base_temp + temp_var - 8,
                temp_max=base_temp + temp_var + 6,
                description=condition,
                icon=icon,
                humidity=random.randint(55, 75),
                wind_speed=random.uniform(5.0, 15.0),
                precipitation_probability=precip,
                conditions=condition.lower().replace(" ", "_")
            )
            
            weather_list.append(weather)
            current_date += timedelta(days=1)
        
        return weather_list
    
    def _create_structured_response(self, weather: List[Weather], preferences: Dict) -> str:
        """Create response with structured data"""
        
        # ✅ Use model_dump() to handle any datetime objects
        weather_data = [w.model_dump(mode='json') for w in weather]
        
        # Create structured data block
        structured = {
            "agent": "WeatherAgent",
            "type": "weather_forecast",
            "data": weather_data
        }
        
        # Analyze weather patterns
        avg_temp = sum(w.temperature for w in weather) / len(weather)
        rainy_days = sum(1 for w in weather if w.precipitation_probability > 0.4)
        sunny_days = sum(1 for w in weather if "sunny" in w.description.lower() or "clear" in w.description.lower())
        
        # Create natural language summary
        summary = f"""
I've checked the weather forecast for {preferences.get('destination', 'your destination')} from {preferences.get('departure_date')} to {preferences.get('return_date')}.

**Weather Overview:**
- Average Temperature: {avg_temp:.0f}°F
- Sunny Days: {sunny_days}
- Rainy Days: {rainy_days}
- Overall: {"Pleasant weather expected!" if rainy_days <= 2 else "Some rainy days expected, pack an umbrella!"}

**Daily Forecast:**

"""
        
        for i, w in enumerate(weather, 1):
            emoji = "☀️" if "sunny" in w.description.lower() or "clear" in w.description.lower() else \
                    "🌧️" if "rain" in w.description.lower() else \
                    "⛅" if "partly" in w.description.lower() else "☁️"
            
            summary += f"""
**Day {i} - {w.date}** {emoji}
- Conditions: {w.description}
- Temperature: {w.temp_min:.0f}°F - {w.temp_max:.0f}°F
- Precipitation: {w.precipitation_probability * 100:.0f}%
- Humidity: {w.humidity}%
"""
        
        # Add packing recommendations
        summary += f"""

**Packing Recommendations:**
"""
        
        if rainy_days > 2:
            summary += "- 🌂 Umbrella or rain jacket (several rainy days expected)\n"
        elif rainy_days > 0:
            summary += "- 🌂 Light rain jacket or compact umbrella\n"
        
        if avg_temp > 80:
            summary += "- 👕 Light, breathable clothing\n- 🧴 Sunscreen\n- 🕶️ Sunglasses\n"
        elif avg_temp > 65:
            summary += "- 👕 Light layers (t-shirts + light jacket)\n- 🧴 Sunscreen for sunny days\n"
        else:
            summary += "- 🧥 Warm layers and jacket\n"
        
        summary += f"""

**Weather Insights:**
{"The weather looks great for outdoor activities!" if sunny_days >= len(weather) // 2 else "Mix of conditions - plan indoor backup activities."}

<STRUCTURED_DATA>
{json.dumps(structured, indent=2)}
</STRUCTURED_DATA>
"""
        
        return summary


def create_weather_agent() -> WeatherAgent:
    """Factory function to create WeatherAgent"""
    return WeatherAgent()