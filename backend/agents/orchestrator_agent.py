"""
Smart Orchestrator Agent - Dynamic Agent Selection with Storage
Location: backend/agents/orchestrator_agent.py

Changes (v5 — Async Pipeline):
  - orchestrate() accepts optional trip_id + trip_storage parameters
  - When called from Celery task, uses external Redis-backed storage
  - When called directly (legacy), creates its own InMemoryTripStorage
  - Agents write to whatever storage was injected → Redis updates in real-time
  - Removed duplicate trip_id/storage creation block

Changes (v4):
  - orchestrate() reads recommendations from storage via get_recommendations()
  - Attaches recommendations dict to the returned result
  - _generate_final_recommendation() receives recommendations for better context
  - Fixed activity_prefs.interests → preferred_interests + interested_interests
"""
from typing import List, Dict, Any, Optional

from services.storage.inmemory_storage import get_trip_storage
from services.storage.storage_base import TripStorageInterface
from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
import os
from datetime import datetime
from collections import Counter
import openai

from autogen import GroupChat, GroupChatManager

from agents.base_agent import TravelQBaseAgent
from agents.user_proxy_agent import TravelQUserProxy
from agents.flight_agent import create_flight_agent
from agents.hotel_agent import create_hotel_agent
from agents.weather_agent import create_weather_agent
from agents.places_agent import create_places_agent

class TravelOrchestratorAgent(TravelQBaseAgent):
    """
    Smart Orchestrator that dynamically decides which agents to use
    """
    
    def __init__(self, **kwargs):
        system_message = """
You are the Travel Planning Orchestrator.

Your role:
1. Analyze user travel preferences
2. Coordinate with specialized agents (Flight, Weather, Events, Places)
3. Ensure all agents work together to create a comprehensive trip plan
4. Synthesize results into a coherent itinerary

You don't search for flights, weather, events, or places yourself.
Instead, you delegate to specialized agents and coordinate their results.
"""
        
        # ✅ FIX: Call create_llm_config() on the CLASS, not on self
        super().__init__(
            name="TravelOrchestrator",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="OrchestratorAgent",
            system_message=system_message,
            description="Coordinates multi-agent trip planning",
            **kwargs
        )
        
        log_agent_raw("🎯 TravelOrchestratorAgent initialized", agent_name="OrchestratorAgent")
    
    def analyze_requirements(self, preferences) -> List[str]:
        """
        Analyze user preferences and decide which agents are needed
        
        Args:
            preferences: TravelPreferences object
            
        Returns:
            List of agent types needed (e.g., ['flight', 'weather', 'events'])
        """
        log_agent_raw("📊 Analyzing requirements to determine needed agents...", agent_name="OrchestratorAgent")
        
        agents_needed = []
        
        trip_duration = self.calculate_trip_duration(preferences)

        # Weather: Always useful if enabled
        if settings.weather_agent_enabled:
            agents_needed.append("weather")
            log_agent_raw("  ✓ Weather agent: NEEDED (always useful)", agent_name="OrchestratorAgent")
        
        # Flights: Needed for long-distance trips
        if settings.flight_agent_enabled and self.needs_flights(preferences):
            agents_needed.append("flight")
            log_agent_raw("  ✓ Flight agent: NEEDED (long-distance trip)", agent_name="OrchestratorAgent")
        else:
            log_agent_raw("  ✗ Flight agent: SKIPPED (short trip or disabled)", agent_name="OrchestratorAgent")
        

        # Hotels: Needed for overnight stays
        if settings.hotel_agent_enabled and trip_duration >= 1:
            agents_needed.append("hotel")
            log_agent_raw(f"  ✓ Hotel agent: NEEDED ({trip_duration} night stay)", agent_name="OrchestratorAgent")
        else:
            log_agent_raw("  ✗ Hotel agent: SKIPPED (day trip or disabled)", agent_name="OrchestratorAgent")


        # Events: Useful for trips >= 3 days
        if settings.events_agent_enabled and trip_duration >= 3:
            agents_needed.append("events")
            log_agent_raw(f"  ✓ Events agent: NEEDED ({trip_duration} day trip)", agent_name="OrchestratorAgent")
        else:
            log_agent_raw("  ✗ Events agent: SKIPPED (short trip or disabled)", agent_name="OrchestratorAgent")
        
        # Places: Always useful if enabled
        if settings.places_agent_enabled:
            agents_needed.append("places")
            log_agent_raw("  ✓ Places agent: NEEDED (attractions & dining)", agent_name="OrchestratorAgent")
        
        log_agent_json({
            "agents_needed": agents_needed,
            "trip_duration_days": trip_duration,
            "destination": preferences.destination
        }, agent_name="OrchestratorAgent", label="Agent Selection Decision")
        
        return agents_needed
    
    def create_specialized_agents_with_storage(
        self,
        agents_needed: List[str],
        trip_id: str,
        trip_storage: Any
    ) -> List[TravelQBaseAgent]:
        """
        Create only the agents that are needed with shared storage
        
        Args:
            agents_needed: List of agent types to create
            trip_id: Trip ID for storage
            trip_storage: Storage instance
            
        Returns:
            List of instantiated agent objects
        """
        log_agent_raw("🏗️  Creating specialized agents...", agent_name="OrchestratorAgent")
        
        agents = []
        
        if "flight" in agents_needed:
            agents.append(create_flight_agent(trip_id=trip_id, trip_storage=trip_storage))
            log_agent_raw("  ✓ FlightAgent created with storage", agent_name="OrchestratorAgent")
        
        if "hotel" in agents_needed:
            agents.append(create_hotel_agent(trip_id=trip_id, trip_storage=trip_storage))
            log_agent_raw("  ✓ HotelAgent created with storage", agent_name="OrchestratorAgent")

        if "weather" in agents_needed:
            agents.append(create_weather_agent(trip_id=trip_id, trip_storage=trip_storage))
            log_agent_raw("  ✓ WeatherAgent created with storage", agent_name="OrchestratorAgent")
        
        if "places" in agents_needed:
            agents.append(create_places_agent(trip_id=trip_id, trip_storage=trip_storage))
            log_agent_raw("  ✓ PlacesAgent created with storage", agent_name="OrchestratorAgent")

        # if "events" in agents_needed:
        #     from agents.events_agent import create_events_agent
        #     agents.append(create_events_agent())
        #     log_agent_raw("  ✓ EventsAgent created", agent_name="OrchestratorAgent")
        
        # if "places" in agents_needed:
        #     from agents.places_agent import create_places_agent
        #     agents.append(create_places_agent())
        #     log_agent_raw("  ✓ PlacesAgent created", agent_name="OrchestratorAgent")
        
        log_agent_raw(f"✅ Created {len(agents)} specialized agents", agent_name="OrchestratorAgent")
        
        return agents
    
    
    def log_group_conversation(self, groupchat, trip_id: str = None):
        """
        Log the entire multi-agent conversation to a single file
        
        Args:
            groupchat: The GroupChat object with message history
            trip_id: Optional trip ID for the log filename
        """
        conversations_dir = "logs/conversations"
        os.makedirs(conversations_dir, exist_ok=True)
        
        log_filename = f"{conversations_dir}/orchestrator_messages.log"
        messages = groupchat.messages
        
        # Collect statistics
        speaker_counts = Counter()
        for msg in messages:
            speaker = msg.get('name', msg.get('role', 'Unknown'))
            speaker_counts[speaker] += 1
        
        # Write to file
        with open(log_filename, 'w', encoding='utf-8') as f:
            # Header
            f.write("=" * 100 + "\n")
            f.write("MULTI-AGENT CONVERSATION LOG\n")
            f.write("=" * 100 + "\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            if trip_id:
                f.write(f"Trip ID: {trip_id}\n")
            f.write(f"Total Messages: {len(messages)}\n")
            f.write("=" * 100 + "\n\n")
            
            # Statistics
            f.write("CONVERSATION STATISTICS:\n")
            f.write("-" * 100 + "\n")
            for speaker, count in speaker_counts.most_common():
                f.write(f"  {speaker}: {count} messages\n")
            f.write("\n")
            
            # Full conversation
            f.write("=" * 100 + "\n")
            f.write("FULL CONVERSATION TRANSCRIPT\n")
            f.write("=" * 100 + "\n\n")
            
            for i, message in enumerate(messages, 1):
                sender = message.get('name', message.get('role', 'Unknown'))
                content = message.get('content', '')
                
                f.write(f"\n{'=' * 100}\n")
                f.write(f"[Message {i}/{len(messages)}] {sender}\n")
                f.write(f"{'=' * 100}\n")
                f.write(f"{content}\n")
                f.write(f"{'-' * 100}\n")
            
            # Footer
            f.write(f"\n{'=' * 100}\n")
            f.write(f"END OF CONVERSATION\n")
            f.write(f"Total Messages: {len(messages)}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"{'=' * 100}\n")
        
        log_agent_raw(f"📝 Full conversation logged to: {log_filename}", agent_name="OrchestratorAgent")
        return log_filename


    async def orchestrate(
        self,
        user_proxy: TravelQUserProxy,
        trip_id: Optional[str] = None,
        trip_storage: Optional[TripStorageInterface] = None,
    ) -> Dict[str, Any]:
        """
        Main orchestration method with centralized storage
        
        Three-phase orchestration:
        1. Opening (orchestrator speaks)
        2. Agent execution (orchestrator silent)
        3. Closing (orchestrator speaks)

        Args:
            user_proxy: User proxy agent with preferences
            trip_id: Optional external trip ID (from Celery/Redis pipeline).
                     If None, generates a new one (legacy behavior).
            trip_storage: Optional external storage backend (e.g. _RedisBackedTripStorage).
                          If None, creates InMemoryTripStorage (legacy behavior).
            
        Returns:
            Dictionary with conversation history and results
        """
        log_agent_raw("🤖 STARTING MULTI-AGENT CONVERSATION", agent_name="OrchestratorAgent")
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")
        
        preferences = user_proxy.user_preferences
        
        # ═══════════════════════════════════════════════════════════════════
        # v5: Use injected trip_id + storage if provided (async pipeline),
        #     otherwise create defaults (legacy / direct call)
        # ═══════════════════════════════════════════════════════════════════
        if trip_id and trip_storage:
            log_agent_raw(
                f"📦 Using EXTERNAL storage (injected by Celery task) — trip_id={trip_id}",
                agent_name="OrchestratorAgent"
            )
            log_agent_raw(
                f"   Storage type: {type(trip_storage).__name__}",
                agent_name="OrchestratorAgent"
            )
        else:
            # Legacy path: create our own trip_id + in-memory storage
            trip_id = f"trip_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            trip_storage = get_trip_storage()
            log_agent_raw(
                f"📦 Using DEFAULT InMemoryTripStorage — trip_id={trip_id}",
                agent_name="OrchestratorAgent"
            )
        
        # ✅ STORE PREFERENCES in whatever storage backend we have
        trip_storage.store_preferences(trip_id, preferences)
        log_agent_raw(f"📦 Stored preferences for: {trip_id}", agent_name="OrchestratorAgent")
    
        # Step 1: Decide which agents are needed
        agents_needed = self.analyze_requirements(preferences)
        
        # Step 1.5:  PHASE 1: Orchestrator creates opening message
        opening_message = self._generate_opening_message(preferences, agents_needed, trip_id)
        log_agent_raw(f"📢 Opening message: {opening_message}", agent_name="OrchestratorAgent")

        # Step 2: Create agents with storage
        specialized_agents = self.create_specialized_agents_with_storage(
            agents_needed=agents_needed,
            trip_id=trip_id,
            trip_storage=trip_storage
        )

        # Step 2.5:  PHASE 2: Setup chat WITHOUT orchestrator
        manager, group_chat = self.setup_group_chat(user_proxy, specialized_agents)
        
        # Combine opening message with user preferences
        full_initial_message = f"""
        {opening_message}

        {user_proxy.get_preferences_summary()}
        """

        log_agent_raw(f"📨 Sending Full Initial message to group chat: {full_initial_message}...", 
                     agent_name="OrchestratorAgent")
        
        # Initiate chat
        user_proxy.initiate_chat(manager, message=full_initial_message)
        
        # Log conversation
        log_file = self.log_group_conversation(groupchat=group_chat, trip_id=trip_id)
        
        # ✅ Step 5: Collect results from centralized storage
        all_options = trip_storage.get_all_options(trip_id)
        summary = trip_storage.get_summary(trip_id)
        
        log_agent_json(summary, label="Options Collected from Storage", agent_name="OrchestratorAgent")
        
        # ✅ NEW: Collect AI recommendations from storage
        recommendations = trip_storage.get_recommendations(trip_id)
        
        log_agent_json(
            recommendations, 
            label="⭐ AI Recommendations from Agents", 
            agent_name="OrchestratorAgent"
        )
        
        # Extract conversation history
        conversation_history = []
        for msg in group_chat.messages:
            conversation_history.append({
                "speaker": msg.get("name", "unknown"),
                "message": msg.get("content", "")
            })
        
        # ✅ Generate final recommendation (now with structured recommendations)
        final_recommendation = self._generate_final_recommendation(
            all_options,
            conversation_history,
            preferences,
            recommendations  # ← NEW: pass recommendations for better context
        )
        
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")
        log_agent_raw(f"✅ Multi-agent conversation complete ({len(conversation_history)} messages)", 
                     agent_name="OrchestratorAgent")
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")
        
        return {
            "trip_id": trip_id,
            "opening_message": opening_message,
            "final_recommendation": final_recommendation,
            "recommendations": recommendations,   # ← NEW: structured recommendations
            "all_options": all_options,
            "conversation_history": conversation_history,
            "summary": summary,
            "agents_used": [agent.name for agent in specialized_agents]
        }
    

    def setup_group_chat(self, user_proxy, specialized_agents):
        """
        Setup AutoGen GroupChat with completion tracking
        """
        
        # ✅ Track which agents need to complete
        expected_agents = {agent.name for agent in specialized_agents}
        completed_agents = set()
        
        log_agent_raw(f"📋 Expecting completion from: {expected_agents}", 
                    agent_name="OrchestratorAgent")
        
        # ✅ Custom termination checker
        def check_termination(msg: Dict) -> bool:
            """
            Terminate when all expected agents have completed their tasks
            """
            content = msg.get("content", "")
            sender = msg.get("name", "")
            
            # Check for completion signal
            if TravelQBaseAgent.TASK_COMPLETED in content:
                completed_agents.add(sender)
                log_agent_raw(
                    f"✅ {sender} completed ({len(completed_agents)}/{len(expected_agents)})", 
                    agent_name="OrchestratorAgent"
                )
            
            # Terminate if all agents done
            if completed_agents >= expected_agents:
                log_agent_raw("🎉 All agents completed - terminating conversation", 
                            agent_name="OrchestratorAgent")
                return True
            
            # Also terminate on explicit TERMINATE keyword (fallback)
            if "TERMINATE" in content.upper():
                log_agent_raw("🛑 TERMINATE keyword detected", agent_name="OrchestratorAgent")
                return True
            
            return False
        
        # Setup group chat WITHOUT orchestrator
        all_agents = [user_proxy] + specialized_agents
        
        group_chat = GroupChat(
            agents=all_agents,
            messages=[],
            max_round=20,
            speaker_selection_method="auto"
        )
        
        manager = GroupChatManager(
            groupchat=group_chat,
            llm_config=TravelQBaseAgent.create_llm_config(),
            is_termination_msg=check_termination  # ✅ Use custom termination
        )
        
        return manager, group_chat


    def _generate_opening_message(self, preferences, agents_needed: List[str], trip_id: str) -> str:
        """
        Generate orchestrator's opening message with trip_id reference
        """
        # Helper to safely format budget
        def format_budget(value):
            return f"${value:.0f}" if value else "unspecified"

        # Combine preferred + interested for display
        all_interests = preferences.activity_prefs.preferred_interests + preferences.activity_prefs.interested_interests
        interests_display = ', '.join(all_interests) if all_interests else 'general sightseeing'

        agent_descriptions = {
            "flight": f"FlightAgent will find flights from {preferences.origin} to {preferences.destination} within {format_budget(preferences.budget.flight_budget)} budget",
            "hotel": f"HotelAgent will find hotels in {preferences.destination} meeting {preferences.hotel_prefs.min_rating}-star requirement at {format_budget(preferences.budget.hotel_budget_per_night)}/night",
            "weather": f"WeatherAgent will provide {self.calculate_trip_duration(preferences)}-day weather forecast for {preferences.destination}",
            "events": f"EventsAgent will find events and activities matching interests: {interests_display}",
            "places": f"PlacesAgent will recommend restaurants and attractions for: {interests_display}"
        }
        
        active_agents = [agent_descriptions[agent] for agent in agents_needed if agent in agent_descriptions]
        
        message = f"""
    ┌─────────────────────────────────────────────────────────────┐
    │  🎯 TRAVEL PLANNING SYSTEM - COORDINATION INITIATED         │
    └─────────────────────────────────────────────────────────────┘

    Trip to: {preferences.destination}
    Dates: {preferences.departure_date} to {preferences.return_date}
    Travelers: {preferences.num_travelers}

    The following specialized agents will work on your trip:

    """
        for i, desc in enumerate(active_agents, 1):
            message += f"  {i}. {desc}\n"
        
        # ✅ ADD THIS - Include trip_id for agents
        message += f"""
            ────────────────────────────────────────────────────────────────

            🔑 **Trip Reference ID:** `{trip_id}`

            📌 **Note to Agents:** Use this trip_id to access full structured 
            preferences from shared storage for 100% accurate data extraction.

            ────────────────────────────────────────────────────────────────

            """
        
        return message

    def _generate_final_recommendation(
        self,
        all_options: Dict[str, List],
        conversation_history: List[Dict],
        preferences: Any,
        recommendations: Dict[str, Any] = None
    ) -> str:
        """
        Generate comprehensive final recommendation using LLM.
        
        Now receives structured recommendations from agents for better context.
        """
        # Extract agent recommendations from conversation
        agent_recs = []
        for msg in conversation_history:
            if msg["speaker"] not in ["APIUser", "TravelOrchestrator"]:
                # Clean up the completion signal before adding
                content = msg["message"].replace(self.TASK_COMPLETED, "").strip()
                agent_recs.append(f"**{msg['speaker']}**: {content}")
        
        flights = all_options.get("flights", [])
        hotels = all_options.get("hotels", [])
        events = all_options.get("events", [])
        places = all_options.get("places", [])
        weather = all_options.get("weather", [])
        
        # ✅ NEW: Build structured picks section
        structured_picks = ""
        if recommendations:
            structured_picks = "\nSTRUCTURED AGENT PICKS:\n"
            for category, rec in recommendations.items():
                structured_picks += (
                    f"- {category.upper()}: ID={rec['recommended_id']}, "
                    f"Reason: {rec.get('reason', 'N/A')}\n"
                )
        
        prompt = f"""
            Create a comprehensive trip itinerary based ONLY on data that was actually collected.

            TRIP DETAILS:
            - Destination: {preferences.destination}
            - Dates: {preferences.departure_date} to {preferences.return_date}
            - Budget: ${preferences.budget.total_budget}
            - Travelers: {preferences.num_travelers}

            DATA COLLECTED:
            - Flights: {len(flights)} options reviewed
            - Hotels: {len(hotels)} options reviewed
            - Events: {len(events)} options reviewed
            - Places: {len(places)} options reviewed
            - Weather: {len(weather)} forecasts
            {structured_picks}

            AGENT RECOMMENDATIONS:
            {chr(10).join(agent_recs) if agent_recs else "No agent recommendations available"}

            INSTRUCTIONS:
            1. **Only include sections for data that exists**
            - If flights were reviewed, include flight recommendation
            - If hotels were reviewed, include hotel recommendation
            - If NO data exists for a category, skip that section entirely

            2. For each category WITH data:
            - Provide specific recommendation with details
            - Explain why it's the best choice
            - Include pricing if available

            3. Budget breakdown:
            - Only include items that have actual data
            - Note which items still need to be booked

            4. Travel tips:
            - General helpful advice for {preferences.destination}
            - Best practices for the trip dates

            5. Format professionally with headers and bullet points

            CRITICAL: Do NOT invent data. If hotels weren't reviewed, don't recommend a hotel. 
            If no events were collected, don't suggest events. Only use actual data from agents.
            """
        
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "You are a professional travel planner who ONLY uses provided data and never invents information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # ✅ Lower temperature = less creative/hallucinatory
                max_tokens=1500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            log_agent_raw(f"⚠️ Final recommendation generation failed: {str(e)}", 
                        agent_name="OrchestratorAgent")
            
            # ✅ Better fallback that doesn't hallucinate
            fallback = f"""
            ### Your {preferences.destination} Trip Summary

            """

            if flights:
                fallback += f"✅ **Flights**: {len(flights)} options reviewed\n"
            if hotels:
                fallback += f"✅ **Hotels**: {len(hotels)} options reviewed\n"
            if events:
                fallback += f"✅ **Events**: {len(events)} options reviewed\n"
            if places:
                fallback += f"✅ **Places**: {len(places)} options reviewed\n"
            
            fallback += "\nCheck the detailed options below for all available choices."
            
            return fallback
    
    # Helper methods
    
    def calculate_trip_duration(self, preferences) -> int:
        """Calculate trip duration in days"""
        from datetime import datetime
        
        try:
            dep = datetime.fromisoformat(preferences.departure_date)
            ret = datetime.fromisoformat(preferences.return_date)
            return (ret - dep).days
        except:
            return 7  # Default
    
    def needs_flights(self, preferences) -> bool:
        """Determine if flights are needed based on distance"""
        return preferences.origin.lower() != preferences.destination.lower()
    
    def trip_complexity(self, preferences) -> str:
        """Determine trip complexity (simple, moderate, complex)"""
        duration = self.calculate_trip_duration(preferences)
        
        if duration <= 3:
            return "simple"
        elif duration <= 7:
            return "moderate"
        else:
            return "complex"


def create_orchestrator() -> TravelOrchestratorAgent:
    """
    Factory function to create orchestrator
    
    Returns:
        Configured TravelOrchestratorAgent instance
    """
    return TravelOrchestratorAgent()