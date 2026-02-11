"""
Weather Agent - Real API with Centralized Storage
Location: backend/agents/weather_agent.py
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
    Weather Agent with real Open-Meteo API + centralized storage
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
        
        # Storage
        self.trip_id = trip_id
        self.trip_storage = trip_storage
        
        # Weather service
        self.weather_service = get_weather_service()
        
        log_agent_raw("🌤️  WeatherAgent initialized (REAL API MODE)", agent_name="WeatherAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """
        Generate reply: Call API, store forecast, return recommendation
        """
        log_agent_raw("🔍 WeatherAgent processing request...", agent_name="WeatherAgent")
        
        # Log incoming message
        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name,
                truncate=500
            )
        
        # Get preferences from storage
        preferences = self.trip_storage.get_preferences(self.trip_id)
        
        if not preferences:
            error_msg = f"Could not find preferences for trip {self.trip_id}"
            log_agent_raw(f"❌ {error_msg}", agent_name="WeatherAgent")
            return self.signal_completion(f"Error: {error_msg}")
        
        log_agent_raw(f"✅ Retrieved preferences from storage for trip {self.trip_id}", 
                     agent_name="WeatherAgent")
        
        # Build search parameters
        search_params = {
            "destination": preferences.destination,
            "start_date": preferences.departure_date,
            "end_date": preferences.return_date,
        }
        
        log_agent_json(search_params, label="Weather Search Parameters (from storage)", 
                      agent_name="WeatherAgent")
        
        try:
            # Call Weather API
            start_time = time.time()
            
            weather_forecasts = self._fetch_weather_api(
                location=search_params["destination"],
                start_date=search_params["start_date"],
                end_date=search_params["end_date"]
            )
            
            api_duration = time.time() - start_time
            
            log_agent_raw(f"✅ API returned {len(weather_forecasts)} day forecast in {api_duration:.2f}s", 
                         agent_name="WeatherAgent")
            
            # Store ALL forecasts in centralized storage
            weather_dict = [self._weather_to_dict(w) for w in weather_forecasts]
            
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
            
            # Generate conversational recommendation
            recommendation = self._generate_recommendation(weather_forecasts, search_params)
            
            # Log outgoing
            self.log_conversation_message(
                message_type="OUTGOING",
                content=recommendation,
                sender="chat_manager",
                truncate=1000
            )
            
            return self.signal_completion(recommendation)
            
        except Exception as e:
            log_agent_raw(f"❌ Weather forecast failed: {str(e)}", agent_name="WeatherAgent")
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
        log_agent_raw("📡 Calling Open-Meteo Weather API1", agent_name="WeatherAgent")
        log_agent_raw("=" * 80, agent_name="WeatherAgent")
        
        # ✅ Log input parameters
        log_agent_raw(f"📍 Location: {location}", agent_name="WeatherAgent")
        log_agent_raw(f"📅 Start Date: {start_date}", agent_name="WeatherAgent")
        log_agent_raw(f"📅 End Date: {end_date}", agent_name="WeatherAgent")
        log_agent_raw("-" * 80, agent_name="WeatherAgent")
        
        try:
            # ✅ Check if event loop is already running
            try:
                loop = asyncio.get_running_loop()
                log_agent_raw("🔄 Detected existing event loop - applying nest_asyncio", agent_name="WeatherAgent")
                
                # Event loop exists - we're in async context already
                # Use nest_asyncio to allow nested event loops
                nest_asyncio.apply()
                
                log_agent_raw("🌐 Calling weather_service.get_forecast()...", agent_name="WeatherAgent")
                log_agent_raw(f"   → location: '{location}'", agent_name="WeatherAgent")
                log_agent_raw(f"   → start_date: '{start_date}'", agent_name="WeatherAgent")
                log_agent_raw(f"   → end_date: '{end_date}'", agent_name="WeatherAgent")
                
                weather_data = asyncio.run(
                    self.weather_service.get_forecast(
                        location=location,
                        start_date=start_date,
                        end_date=end_date
                    )
                )
                
                log_agent_raw(f"✅ API call completed successfully", agent_name="WeatherAgent")
                log_agent_raw(f"📊 Received {len(weather_data)} forecast entries", agent_name="WeatherAgent")
                log_agent_json(weather_data, label="Complete Weather Forecast Array", agent_name="WeatherAgent")
                log_agent_raw("-" * 80, agent_name="WeatherAgent")
                
                # ✅ Log sample of received data
                if weather_data and len(weather_data) > 0:
                    log_agent_raw("-" * 80, agent_name="WeatherAgent")
                    log_agent_raw("📋 Sample weather data (first entry):", agent_name="WeatherAgent")
                    log_agent_json(weather_data[0], label="First Forecast Entry", agent_name="WeatherAgent")
                    
                    if len(weather_data) > 1:
                        log_agent_raw(f"   ... and {len(weather_data) - 1} more entries", agent_name="WeatherAgent")
                else:
                    log_agent_raw("⚠️  Received empty weather data array", agent_name="WeatherAgent")

            except RuntimeError as re:
                # No event loop running - create a new one
                log_agent_raw("🆕 No existing event loop detected - creating new one", agent_name="WeatherAgent")
                log_agent_raw(f"   RuntimeError: {str(re)}", agent_name="WeatherAgent")
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                log_agent_raw("🌐 Calling weather_service.get_forecast()...", agent_name="WeatherAgent")
                log_agent_raw(f"   → location: '{location}'", agent_name="WeatherAgent")
                log_agent_raw(f"   → start_date: '{start_date}'", agent_name="WeatherAgent")
                log_agent_raw(f"   → end_date: '{end_date}'", agent_name="WeatherAgent")
                
                try:
                    weather_data = loop.run_until_complete(
                        self.weather_service.get_forecast(
                            location=location,
                            start_date=start_date,
                            end_date=end_date
                        )
                    )
                    
                    log_agent_raw(f"✅ API call completed successfully", agent_name="WeatherAgent")
                    log_agent_raw(f"📊 Received {len(weather_data)} forecast entries", agent_name="WeatherAgent")

                    # ✅ ADD THIS - Log ALL weather data
                    log_agent_raw("-" * 80, agent_name="WeatherAgent")
                    log_agent_raw("📋 FULL WEATHER DATA RECEIVED FROM API:", agent_name="WeatherAgent")
                    log_agent_json(weather_data, label="Complete Weather Forecast Array", agent_name="WeatherAgent")
                    log_agent_raw("-" * 80, agent_name="WeatherAgent")
                        
                finally:
                    loop.close()
                    log_agent_raw("🔒 Event loop closed", agent_name="WeatherAgent")
            
            log_agent_raw("=" * 80, agent_name="WeatherAgent")
            log_agent_raw(f"✅ Open-Meteo Weather API SUCCESS - Received {len(weather_data)} day forecast", 
                        agent_name="WeatherAgent")
            log_agent_raw("=" * 80, agent_name="WeatherAgent")
            
            # Parse into Weather objects
            log_agent_raw(f"📋 Parsing {len(weather_data)} weather forecasts...", agent_name="WeatherAgent")
            forecasts = []
            
            for idx, forecast_dict in enumerate(weather_data, 1):
                date_str = forecast_dict.get('date', 'Unknown')
                temp_str = f"{forecast_dict.get('temp_min', '?')}°F - {forecast_dict.get('temp_max', '?')}°F"
                
                log_agent_raw(f"   [{idx}/{len(weather_data)}] Parsing: {date_str} ({temp_str})", 
                            agent_name="WeatherAgent")
                
                forecast = self._parse_weather_data(forecast_dict)
                if forecast:
                    forecasts.append(forecast)
                    log_agent_raw(f"      ✓ SUCCESS: {forecast.description}", agent_name="WeatherAgent")
                else:
                    log_agent_raw(f"      ✗ FAILED to parse", agent_name="WeatherAgent")
                    log_agent_json(forecast_dict, label=f"Failed Entry {idx}", agent_name="WeatherAgent")
            
            log_agent_raw("-" * 80, agent_name="WeatherAgent")
            log_agent_raw(f"✅ Successfully parsed {len(forecasts)}/{len(weather_data)} forecasts", 
                        agent_name="WeatherAgent")
            log_agent_raw("=" * 80, agent_name="WeatherAgent")
            
            return forecasts
            
        except Exception as e:
            log_agent_raw("=" * 80, agent_name="WeatherAgent")
            log_agent_raw(f"❌ WEATHER API CALL FAILED", agent_name="WeatherAgent")
            log_agent_raw("=" * 80, agent_name="WeatherAgent")
            log_agent_raw(f"🔴 Error Type: {type(e).__name__}", agent_name="WeatherAgent")
            log_agent_raw(f"🔴 Error Message: {str(e)}", agent_name="WeatherAgent")
            log_agent_raw("-" * 80, agent_name="WeatherAgent")
            log_agent_raw(f"📍 Failed Request Details:", agent_name="WeatherAgent")
            log_agent_raw(f"   Location: {location}", agent_name="WeatherAgent")
            log_agent_raw(f"   Start Date: {start_date}", agent_name="WeatherAgent")
            log_agent_raw(f"   End Date: {end_date}", agent_name="WeatherAgent")
            log_agent_raw("-" * 80, agent_name="WeatherAgent")
            
            import traceback
            log_agent_raw(f"📚 Full Traceback:", agent_name="WeatherAgent")
            log_agent_raw(traceback.format_exc(), agent_name="WeatherAgent")
            
            log_agent_raw("=" * 80, agent_name="WeatherAgent")
            
            # Return empty list on error
            log_agent_raw("⚠️  Returning empty forecast list", agent_name="WeatherAgent")
            return []
    
    def _parse_weather_data(self, data: Dict) -> Optional[Weather]:
        """Parse weather data dict into Weather object"""
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
        """
        Use LLM to generate conversational weather recommendation
        """
        if not forecasts:
            return f"I couldn't fetch weather data for {preferences.get('destination')}. Please check back later for forecast updates."
        
        # Analyze weather patterns
        temps = [f.temperature for f in forecasts]
        avg_temp = sum(temps) / len(temps)
        min_temp = min(f.temp_min for f in forecasts)
        max_temp = max(f.temp_max for f in forecasts)
        
        rainy_days = sum(1 for f in forecasts if (f.precipitation_probability or 0) > 50)
        sunny_days = sum(1 for f in forecasts if "clear" in (f.description or "").lower() or "sunny" in (f.description or "").lower())
        
        # Build forecast summary
        forecast_summary = "\n".join([
            f"Day {i+1} ({f.date}): {f.description}, {f.temp_min:.0f}°F - {f.temp_max:.0f}°F, {(f.precipitation_probability or 0):.0f}% rain"
            for i, f in enumerate(forecasts[:7])  # Max 7 days for summary
        ])
        
        # Build prompt
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

            Example: "The weather in London looks mostly mild with temperatures between 55-68°F throughout your stay. You'll experience some rain on 3 days, so pack an umbrella and light rain jacket. The weekend looks particularly nice with clear skies - perfect for outdoor sightseeing!"
            """
        
        # Call LLM
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
            # Fallback
            return f"Weather forecast for {preferences.get('destination')}: Temperatures ranging from {min_temp:.0f}°F to {max_temp:.0f}°F over {len(forecasts)} days. {rainy_days} rainy days expected."
    
    def _weather_to_dict(self, weather: Weather) -> Dict:
        """Convert Weather object to dict for storage"""
        return weather.model_dump(mode='json')


def create_weather_agent(trip_id: str, trip_storage: TripStorageInterface, **kwargs) -> WeatherAgent:
    """Factory function to create WeatherAgent"""
    return WeatherAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)