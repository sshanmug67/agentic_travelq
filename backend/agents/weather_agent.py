"""
Weather Agent - Real API with Centralized Storage
Location: backend/agents/weather_agent.py

Changes (v3 — Granular Status Messages):
  - Added _update_status() helper for real-time progress to Redis
  - Status calls at: init, API call, parsing, storage, LLM recommendation, completion

Changes (v2):
  - Added store_recommendation() call after generating weather recommendation
  - Weather recommendation now appears in response.recommendations.weather
  - Frontend can display it alongside Flight/Hotel picks
"""
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from services.weather_service import get_weather_service
from models.trip import Weather

from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import openai
import nest_asyncio

class WeatherAgent(TravelQBaseAgent):
    """
    Weather Agent v3 — real Open-Meteo API + centralized storage
    + granular real-time status messages
    """
    
    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """
            You are a helpful Weather Forecast Assistant.

            Your job:
            1. Provide accurate weather forecasts for travel destinations
            2. Analyze weather patterns and trends
            3. Give practical packing recommendations
            4. Highlight weather concerns or optimal conditions

            Be friendly and helpful. Focus on actionable insights.
            """
        
        super().__init__(
            name="WeatherAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="WeatherAgent",
            system_message=system_message,
            description="Provides weather forecasts and travel recommendations",
            **kwargs
        )
        
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        self.weather_service = get_weather_service()
        
        log_agent_raw("🌤️  WeatherAgent v3 initialized (with granular status)", agent_name="WeatherAgent")

    # ─────────────────────────────────────────────────────────────────────
    # v3: Granular status helper
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, message: str):
        """Send a granular status message to Redis for the frontend."""
        try:
            self.trip_storage.update_agent_status_message(
                self.trip_id, "weather", message
            )
        except Exception as e:
            log_agent_raw(f"Status update failed: {e}", agent_name="WeatherAgent")

    # ─────────────────────────────────────────────────────────────────────
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        log_agent_raw("🔍 WeatherAgent v3 processing request...", agent_name="WeatherAgent")
        
        # v3: Init status
        self._update_status("Initializing weather forecast...")

        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name,
                truncate=500
            )
        
        # v3: Load preferences
        self._update_status("Loading travel preferences...")
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            self._update_status("Error: preferences not found")
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="WeatherAgent")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences from storage for trip {self.trip_id}", 
                     agent_name="WeatherAgent")
        
        search_params = {
            "destination": preferences.destination,
            "start_date": preferences.departure_date,
            "end_date": preferences.return_date,
        }
        
        log_agent_json(search_params, label="Weather Search Parameters (from storage)", 
                      agent_name="WeatherAgent")
        
        try:
            # v3: API call status
            self._update_status(
                f"Fetching forecast for {search_params['destination']} "
                f"({search_params['start_date']} to {search_params['end_date']})..."
            )

            start_time = time.time()
            
            weather_forecasts = self._fetch_weather_api(
                location=search_params["destination"],
                start_date=search_params["start_date"],
                end_date=search_params["end_date"]
            )
            
            api_duration = time.time() - start_time
            
            log_agent_raw(f"✅ API returned {len(weather_forecasts)} day forecast in {api_duration:.2f}s", 
                         agent_name="WeatherAgent")

            if not weather_forecasts:
                self._update_status("No forecast data received — using general info")
                return self.signal_completion(
                    f"I couldn't fetch weather data for {search_params['destination']}. "
                    "Please check back later for forecast updates."
                )

            # v3: Parsing status
            self._update_status(f"Received {len(weather_forecasts)}-day forecast — processing...")
            
            # Store forecasts
            weather_dict = [self._weather_to_dict(w) for w in weather_forecasts]
            
            self._update_status(f"Saving {len(weather_forecasts)}-day forecast...")

            self.trip_storage.add_weather(
                trip_id=self.trip_id,
                weather=weather_dict,
                metadata={
                    "destination": search_params["destination"],
                    "start_date": search_params["start_date"],
                    "end_date": search_params["end_date"],
                    "search_time": datetime.now().isoformat(),
                    "total_days": len(weather_forecasts),
                    "api_duration": api_duration
                }
            )
            
            self.trip_storage.log_api_call(
                trip_id=self.trip_id,
                agent_name="WeatherAgent",
                api_name="OpenMeteo",
                duration=api_duration
            )
            
            log_agent_raw(f"💾 Stored {len(weather_forecasts)} weather forecasts in centralized storage", 
                         agent_name="WeatherAgent")

            # v3: Analyze weather for status display
            temps = [f.temperature for f in weather_forecasts]
            min_temp = min(f.temp_min for f in weather_forecasts)
            max_temp = max(f.temp_max for f in weather_forecasts)
            rainy_days = sum(1 for f in weather_forecasts if (f.precipitation_probability or 0) > 50)

            self._update_status(
                f"AI generating travel weather advisory ({min_temp:.0f}°F–{max_temp:.0f}°F, "
                f"{rainy_days} rainy day{'s' if rainy_days != 1 else ''})..."
            )
            
            recommendation = self._generate_recommendation(weather_forecasts, search_params)
            
            # v2: Store recommendation
            try:
                self.trip_storage.store_recommendation(
                    trip_id=self.trip_id,
                    category="weather",
                    recommended_id="weather_forecast",
                    reason=recommendation,
                    metadata={
                        "destination": search_params["destination"],
                        "num_days": len(weather_forecasts),
                        "temp_min": round(min_temp, 1),
                        "temp_max": round(max_temp, 1),
                        "avg_temp": round(sum(temps) / len(temps), 1),
                        "rainy_days": rainy_days,
                    },
                )
                log_agent_raw(
                    f"⭐ Weather recommendation stored ({len(weather_forecasts)} day forecast)",
                    agent_name="WeatherAgent",
                )
            except Exception as e:
                log_agent_raw(
                    f"⚠️ Failed to store weather recommendation: {e}",
                    agent_name="WeatherAgent",
                )

            # v3: Completion status
            self._update_status(
                f"Weather forecast complete — {len(weather_forecasts)} days, "
                f"{min_temp:.0f}°F–{max_temp:.0f}°F"
            )
            
            self.log_conversation_message(
                message_type="OUTGOING",
                content=recommendation,
                sender="chat_manager",
                truncate=1000
            )
            
            return self.signal_completion(recommendation)
            
        except Exception as e:
            log_agent_raw(f"❌ Weather forecast failed: {str(e)}", agent_name="WeatherAgent")
            self._update_status(f"Error: {str(e)[:80]}")
            error_msg = f"I encountered an error fetching weather: {str(e)}. Using general seasonal information."
            return self.signal_completion(error_msg)
    
    def _fetch_weather_api(
        self,
        location: str,
        start_date: str,
        end_date: str
    ) -> List[Weather]:
        """
        Call Open-Meteo API to get weather forecast
        Handles async service properly
        """
        log_agent_raw("=" * 80, agent_name="WeatherAgent")
        log_agent_raw("📡 Calling Open-Meteo Weather API", agent_name="WeatherAgent")
        log_agent_raw("=" * 80, agent_name="WeatherAgent")
        
        log_agent_raw(f"📍 Location: {location}", agent_name="WeatherAgent")
        log_agent_raw(f"📅 Start Date: {start_date}", agent_name="WeatherAgent")
        log_agent_raw(f"📅 End Date: {end_date}", agent_name="WeatherAgent")
        log_agent_raw("-" * 80, agent_name="WeatherAgent")
        
        try:
            try:
                loop = asyncio.get_running_loop()
                log_agent_raw("🔄 Detected existing event loop - applying nest_asyncio", agent_name="WeatherAgent")
                nest_asyncio.apply()
                
                weather_data = asyncio.run(
                    self.weather_service.get_forecast(
                        location=location,
                        start_date=start_date,
                        end_date=end_date
                    )
                )

            except RuntimeError:
                log_agent_raw("🆕 No existing event loop - creating new one", agent_name="WeatherAgent")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    weather_data = loop.run_until_complete(
                        self.weather_service.get_forecast(
                            location=location,
                            start_date=start_date,
                            end_date=end_date
                        )
                    )
                finally:
                    loop.close()
            
            log_agent_raw(f"✅ Open-Meteo returned {len(weather_data)} day forecast", 
                        agent_name="WeatherAgent")
            
            # Parse into Weather objects
            forecasts = []
            for idx, forecast_dict in enumerate(weather_data, 1):
                forecast = self._parse_weather_data(forecast_dict)
                if forecast:
                    forecasts.append(forecast)
            
            log_agent_raw(f"✅ Parsed {len(forecasts)}/{len(weather_data)} forecasts", 
                        agent_name="WeatherAgent")
            
            return forecasts
            
        except Exception as e:
            log_agent_raw(f"❌ WEATHER API CALL FAILED: {type(e).__name__}: {str(e)}", 
                        agent_name="WeatherAgent")
            import traceback
            log_agent_raw(traceback.format_exc(), agent_name="WeatherAgent")
            return []
    
    def _parse_weather_data(self, data: Dict) -> Optional[Weather]:
        try:
            return Weather(
                date=data["date"],
                temperature=data.get("temperature", 0),
                feels_like=data.get("feels_like", 0),
                temp_min=data.get("temp_min", 0),
                temp_max=data.get("temp_max", 0),
                description=data.get("description", ""),
                icon=data.get("icon"),
                humidity=data.get("humidity"),
                wind_speed=data.get("wind_speed"),
                precipitation_probability=data.get("precipitation_probability"),
                conditions=data.get("condition")
            )
        except Exception as e:
            log_agent_raw(f"⚠️ Failed to parse weather forecast: {str(e)}", agent_name="WeatherAgent")
            return None
    
    def _generate_recommendation(
        self,
        forecasts: List[Weather],
        preferences: Dict[str, Any]
    ) -> str:
        if not forecasts:
            return f"I couldn't fetch weather data for {preferences.get('destination')}. Please check back later."
        
        temps = [f.temperature for f in forecasts]
        avg_temp = sum(temps) / len(temps)
        min_temp = min(f.temp_min for f in forecasts)
        max_temp = max(f.temp_max for f in forecasts)
        rainy_days = sum(1 for f in forecasts if (f.precipitation_probability or 0) > 50)
        sunny_days = sum(1 for f in forecasts if "clear" in (f.description or "").lower() or "sunny" in (f.description or "").lower())
        
        forecast_summary = "\n".join([
            f"Day {i+1} ({f.date}): {f.description}, {f.temp_min:.0f}°F - {f.temp_max:.0f}°F, {(f.precipitation_probability or 0):.0f}% rain"
            for i, f in enumerate(forecasts[:7])
        ])
        
        prompt = f"""
            Based on the weather forecast, provide helpful travel recommendations.

            DESTINATION: {preferences.get('destination')}
            TRAVEL DATES: {preferences.get('start_date')} to {preferences.get('end_date')}

            WEATHER SUMMARY:
            - Total days: {len(forecasts)}
            - Temperature range: {min_temp:.0f}°F - {max_temp:.0f}°F
            - Average temperature: {avg_temp:.0f}°F
            - Rainy days (>50% chance): {rainy_days}
            - Sunny/Clear days: {sunny_days}

            DAILY FORECAST:
            {forecast_summary}

            Provide a conversational weather recommendation (3-4 sentences):
            - Summarize overall weather conditions
            - Highlight best/worst days if relevant
            - Give specific packing recommendations
            - Mention any weather concerns or optimal conditions
            """
        
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            log_agent_raw(f"⚠️ LLM recommendation failed: {str(e)}", agent_name="WeatherAgent")
            return f"Weather forecast for {preferences.get('destination')}: Temperatures ranging from {min_temp:.0f}°F to {max_temp:.0f}°F over {len(forecasts)} days. {rainy_days} rainy days expected."
    
    def _weather_to_dict(self, weather: Weather) -> Dict:
        return weather.model_dump(mode='json')


def create_weather_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> WeatherAgent:
    return WeatherAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)