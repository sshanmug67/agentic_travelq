"""
Smart Orchestrator Agent - Parallel Agent Execution with Storage
Location: backend/agents/orchestrator_agent.py

Changes (v7 — Parallel Execution):
  - Replaced AutoGen GroupChat (sequential) with concurrent.futures.ThreadPoolExecutor
  - Three parallel paths: PlacesAgent + FlightAgent + HotelAgent
  - PlacesAgent now handles weather internally (no separate WeatherAgent)
  - Removed GroupChat, GroupChatManager, setup_group_chat() entirely
  - Removed WeatherAgent import and creation
  - orchestrate() now runs agents in parallel threads, collects results
  - log_parallel_conversation() replaces log_group_conversation()
  - Expected speedup: 87s → ~36s (agents overlap instead of waiting in queue)

Changes (v6 — Logging Cleanup):
  - Removed separate orchestrator_messages.log / conversations/ directory
  - All orchestrator output lives in one place: logs/agents/OrchestratorAgent.log

Changes (v5 — Async Pipeline):
  - orchestrate() accepts optional trip_id + trip_storage parameters
  - When called from Celery task, uses external Redis-backed storage

Changes (v4):
  - orchestrate() reads recommendations from storage via get_recommendations()
  - Attaches recommendations dict to the returned result
"""
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

from services.storage.inmemory_storage import get_trip_storage
from services.storage.storage_base import TripStorageInterface
from utils.logging_config import log_agent_raw, log_agent_json
from config.settings import settings
from datetime import datetime
from collections import Counter
import openai

from agents.base_agent import TravelQBaseAgent
from agents.user_proxy_agent import TravelQUserProxy
from agents.flight_agent import create_flight_agent
from agents.hotel_agent import create_hotel_agent
from agents.places_agent import create_places_agent


class TravelOrchestratorAgent(TravelQBaseAgent):
    """
    Smart Orchestrator that runs specialized agents in parallel.

    v7: Replaces AutoGen GroupChat (sequential, ~87s) with
    ThreadPoolExecutor (parallel, ~36s):

        Path 1: PlacesAgent  (weather + restaurants + activities + daily plan)
        Path 2: FlightAgent  (search + curate flights)
        Path 3: HotelAgent   (search + price + curate hotels)

    All three paths run simultaneously. Each agent reads preferences
    from shared storage and writes results back independently.
    """

    def __init__(self, **kwargs):
        system_message = """
You are the Travel Planning Orchestrator.

Your role:
1. Analyze user travel preferences
2. Coordinate with specialized agents (Flight, Hotel, Places)
3. Ensure all agents work together to create a comprehensive trip plan
4. Synthesize results into a coherent itinerary

You don't search for flights, weather, hotels, or places yourself.
Instead, you delegate to specialized agents and coordinate their results.
"""

        super().__init__(
            name="TravelOrchestrator",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="OrchestratorAgent",
            system_message=system_message,
            description="Coordinates multi-agent trip planning",
            **kwargs,
        )

        log_agent_raw(
            "🎯 TravelOrchestratorAgent v7 initialized (parallel execution)",
            agent_name="OrchestratorAgent",
        )

    # ─────────────────────────────────────────────────────────────────────
    # REQUIREMENT ANALYSIS
    # ─────────────────────────────────────────────────────────────────────

    def analyze_requirements(self, preferences) -> List[str]:
        """
        Analyze user preferences and decide which agents are needed.

        Note: "weather" is no longer a separate agent — PlacesAgent handles it.
        We still include "weather" in the list for status tracking purposes.
        """
        log_agent_raw(
            "📊 Analyzing requirements to determine needed agents...",
            agent_name="OrchestratorAgent",
        )

        agents_needed = []
        trip_duration = self.calculate_trip_duration(preferences)

        # Weather: Always needed (handled by PlacesAgent internally)
        if settings.weather_agent_enabled:
            agents_needed.append("weather")
            log_agent_raw(
                "  ✓ Weather: NEEDED (handled by PlacesAgent)",
                agent_name="OrchestratorAgent",
            )

        # Flights
        if settings.flight_agent_enabled and self.needs_flights(preferences):
            agents_needed.append("flight")
            log_agent_raw(
                "  ✓ Flight agent: NEEDED (long-distance trip)",
                agent_name="OrchestratorAgent",
            )
        else:
            log_agent_raw(
                "  ✗ Flight agent: SKIPPED (short trip or disabled)",
                agent_name="OrchestratorAgent",
            )

        # Hotels
        if settings.hotel_agent_enabled and trip_duration >= 1:
            agents_needed.append("hotel")
            log_agent_raw(
                f"  ✓ Hotel agent: NEEDED ({trip_duration} night stay)",
                agent_name="OrchestratorAgent",
            )
        else:
            log_agent_raw(
                "  ✗ Hotel agent: SKIPPED (day trip or disabled)",
                agent_name="OrchestratorAgent",
            )

        # Events (for status row tracking; PlacesAgent searches festivals)
        if settings.events_agent_enabled and trip_duration >= 3:
            agents_needed.append("events")
            log_agent_raw(
                f"  ✓ Events: NEEDED ({trip_duration} day trip, handled by PlacesAgent)",
                agent_name="OrchestratorAgent",
            )

        # Places: Always needed (restaurants + activities + weather + daily plan)
        if settings.places_agent_enabled:
            agents_needed.append("places")
            log_agent_raw(
                "  ✓ Places agent: NEEDED (restaurants, activities, weather, daily plan)",
                agent_name="OrchestratorAgent",
            )

        log_agent_json(
            {
                "agents_needed": agents_needed,
                "trip_duration_days": trip_duration,
                "destination": preferences.destination,
                "execution_mode": "parallel",
            },
            agent_name="OrchestratorAgent",
            label="Agent Selection Decision",
        )

        return agents_needed

    # ─────────────────────────────────────────────────────────────────────
    # AGENT CREATION
    # ─────────────────────────────────────────────────────────────────────

    def create_specialized_agents_with_storage(
        self,
        agents_needed: List[str],
        trip_id: str,
        trip_storage: Any,
    ) -> List[TravelQBaseAgent]:
        """
        Create only the agents that are needed with shared storage.

        v7: No WeatherAgent — PlacesAgent handles weather internally.
        """
        log_agent_raw(
            "🏗️  Creating specialized agents...",
            agent_name="OrchestratorAgent",
        )

        agents = []

        if "flight" in agents_needed:
            agents.append(
                create_flight_agent(trip_id=trip_id, trip_storage=trip_storage)
            )
            log_agent_raw(
                "  ✓ FlightAgent created with storage",
                agent_name="OrchestratorAgent",
            )

        if "hotel" in agents_needed:
            agents.append(
                create_hotel_agent(trip_id=trip_id, trip_storage=trip_storage)
            )
            log_agent_raw(
                "  ✓ HotelAgent created with storage",
                agent_name="OrchestratorAgent",
            )

        if "places" in agents_needed:
            agents.append(
                create_places_agent(trip_id=trip_id, trip_storage=trip_storage)
            )
            log_agent_raw(
                "  ✓ PlacesAgent created (proxies: Weather, Restaurant, Activities, Planner)",
                agent_name="OrchestratorAgent",
            )

        log_agent_raw(
            f"✅ Created {len(agents)} specialized agents",
            agent_name="OrchestratorAgent",
        )

        return agents

    # ─────────────────────────────────────────────────────────────────────
    # PARALLEL AGENT EXECUTION
    # ─────────────────────────────────────────────────────────────────────

    def _run_single_agent(
        self,
        agent: TravelQBaseAgent,
        initial_message: str,
        user_proxy: TravelQUserProxy,
    ) -> Dict[str, Any]:
        """
        Run a single agent in its own thread.

        Each agent's generate_reply() reads preferences from shared storage
        and writes results back. This method wraps it with timing and
        error handling.

        Returns:
            Dict with agent_name, response, duration, status
        """
        agent_name = agent.name
        start_time = datetime.now()

        log_agent_raw(
            f"🚀 Starting {agent_name} (thread)",
            agent_name="OrchestratorAgent",
        )

        try:
            # Build minimal message context for generate_reply
            messages = [
                {
                    "content": initial_message,
                    "role": "user",
                    "name": "APIUser",
                }
            ]

            # Call agent's generate_reply — this is the main work
            response = agent.generate_reply(
                messages=messages,
                sender=user_proxy,
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Check for completion signal
            completed = TravelQBaseAgent.TASK_COMPLETED in (response or "")

            log_agent_raw(
                f"✅ {agent_name} completed in {duration:.1f}s "
                f"(signal={'yes' if completed else 'NO'})",
                agent_name="OrchestratorAgent",
            )

            return {
                "agent_name": agent_name,
                "response": response or "",
                "duration": duration,
                "status": "completed" if completed else "completed_no_signal",
                "error": None,
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            log_agent_raw(
                f"❌ {agent_name} FAILED after {duration:.1f}s: "
                f"{type(e).__name__}: {e}",
                agent_name="OrchestratorAgent",
            )
            log_agent_raw(traceback.format_exc(), agent_name="OrchestratorAgent")

            return {
                "agent_name": agent_name,
                "response": f"Error: {str(e)}",
                "duration": duration,
                "status": "failed",
                "error": str(e),
            }

    def run_agents_parallel(
        self,
        specialized_agents: List[TravelQBaseAgent],
        initial_message: str,
        user_proxy: TravelQUserProxy,
    ) -> List[Dict[str, Any]]:
        """
        Run all agents in parallel using ThreadPoolExecutor.

        Each agent gets its own thread. They share storage (thread-safe
        via Redis) and run independently.

        Args:
            specialized_agents: List of agent instances to run
            initial_message: The opening message with preferences
            user_proxy: User proxy (passed as sender context)

        Returns:
            List of result dicts, one per agent, in completion order
        """
        num_agents = len(specialized_agents)
        agent_names = [a.name for a in specialized_agents]

        log_agent_raw(
            f"🚀 PARALLEL EXECUTION: Launching {num_agents} agents: "
            f"{', '.join(agent_names)}",
            agent_name="OrchestratorAgent",
        )
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")

        results = []
        parallel_start = datetime.now()

        with ThreadPoolExecutor(
            max_workers=num_agents,
            thread_name_prefix="agent",
        ) as executor:
            # Submit all agents simultaneously
            future_to_agent = {
                executor.submit(
                    self._run_single_agent, agent, initial_message, user_proxy
                ): agent
                for agent in specialized_agents
            }

            # Collect results as they complete
            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    result = future.result()
                    results.append(result)
                    log_agent_raw(
                        f"  ✅ {result['agent_name']} finished "
                        f"({result['duration']:.1f}s) — {result['status']}",
                        agent_name="OrchestratorAgent",
                    )
                except Exception as e:
                    log_agent_raw(
                        f"  ❌ {agent.name} thread error: {e}",
                        agent_name="OrchestratorAgent",
                    )
                    results.append({
                        "agent_name": agent.name,
                        "response": f"Thread error: {str(e)}",
                        "duration": 0,
                        "status": "failed",
                        "error": str(e),
                    })

        parallel_duration = (datetime.now() - parallel_start).total_seconds()

        # Stats
        succeeded = sum(1 for r in results if r["status"] != "failed")
        failed = num_agents - succeeded
        individual_total = sum(r["duration"] for r in results)

        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")
        log_agent_raw(
            f"✅ PARALLEL EXECUTION COMPLETE: "
            f"{succeeded}/{num_agents} succeeded, {failed} failed",
            agent_name="OrchestratorAgent",
        )
        if parallel_duration > 0:
            log_agent_raw(
                f"   Wall-clock: {parallel_duration:.1f}s | "
                f"Sequential would be: {individual_total:.1f}s | "
                f"Speedup: {individual_total / parallel_duration:.1f}x",
                agent_name="OrchestratorAgent",
            )
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")

        return results

    # ─────────────────────────────────────────────────────────────────────
    # CONVERSATION LOGGING (adapted for parallel results)
    # ─────────────────────────────────────────────────────────────────────

    def log_parallel_conversation(
        self,
        agent_results: List[Dict[str, Any]],
        trip_id: str = None,
    ):
        """
        Log the parallel agent results to OrchestratorAgent.log.

        v7: Replaces log_group_conversation() — adapted for parallel
        execution where we have agent result dicts instead of GroupChat messages.
        """
        agent = "OrchestratorAgent"

        # Header
        log_agent_raw("=" * 100, agent_name=agent)
        log_agent_raw("PARALLEL AGENT EXECUTION LOG", agent_name=agent)
        log_agent_raw("=" * 100, agent_name=agent)
        log_agent_raw(f"Timestamp: {datetime.now().isoformat()}", agent_name=agent)
        if trip_id:
            log_agent_raw(f"Trip ID: {trip_id}", agent_name=agent)
        log_agent_raw(
            f"Total Agents: {len(agent_results)}", agent_name=agent
        )
        log_agent_raw("=" * 100, agent_name=agent)

        # Execution statistics
        log_agent_raw("EXECUTION STATISTICS:", agent_name=agent)
        log_agent_raw("-" * 100, agent_name=agent)
        for result in sorted(agent_results, key=lambda r: r["duration"]):
            status_icon = "✅" if result["status"] != "failed" else "❌"
            log_agent_raw(
                f"  {status_icon} {result['agent_name']}: "
                f"{result['duration']:.1f}s — {result['status']}",
                agent_name=agent,
            )

        # Agent responses
        log_agent_raw("=" * 100, agent_name=agent)
        log_agent_raw("AGENT RESPONSES", agent_name=agent)
        log_agent_raw("=" * 100, agent_name=agent)

        for i, result in enumerate(agent_results, 1):
            log_agent_raw(
                f"[Agent {i}/{len(agent_results)}] "
                f"{result['agent_name']} ({result['duration']:.1f}s)",
                agent_name=agent,
            )

            # Clean up completion signal for display
            response = result["response"]
            if TravelQBaseAgent.TASK_COMPLETED in response:
                response = response.replace(
                    TravelQBaseAgent.TASK_COMPLETED, ""
                ).strip()

            log_agent_raw(f"{response}", agent_name=agent)
            log_agent_raw("-" * 100, agent_name=agent)

        # Footer
        log_agent_raw("=" * 100, agent_name=agent)
        log_agent_raw(
            f"END OF PARALLEL LOG — {len(agent_results)} agents",
            agent_name=agent,
        )
        log_agent_raw(f"Timestamp: {datetime.now().isoformat()}", agent_name=agent)
        log_agent_raw("=" * 100, agent_name=agent)

        log_agent_raw(
            f"📝 Parallel execution logged ({len(agent_results)} agents)",
            agent_name=agent,
        )

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ORCHESTRATION
    # ─────────────────────────────────────────────────────────────────────

    async def orchestrate(
        self,
        user_proxy: TravelQUserProxy,
        trip_id: Optional[str] = None,
        trip_storage: Optional[TripStorageInterface] = None,
    ) -> Dict[str, Any]:
        """
        Main orchestration method with parallel agent execution.

        v7 Three-phase orchestration:
        1. Setup: Create agents, prepare message
        2. Parallel execution: All agents run simultaneously
        3. Closing: Collect results, generate final recommendation

        Args:
            user_proxy: User proxy agent with preferences
            trip_id: Optional external trip ID (from Celery/Redis pipeline)
            trip_storage: Optional external storage backend

        Returns:
            Dictionary with conversation history and results
        """
        log_agent_raw(
            "🤖 STARTING PARALLEL MULTI-AGENT ORCHESTRATION",
            agent_name="OrchestratorAgent",
        )
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")

        preferences = user_proxy.user_preferences

        # ── Storage setup ─────────────────────────────────────────────
        if trip_id and trip_storage:
            log_agent_raw(
                f"📦 Using EXTERNAL storage (injected by Celery task) — trip_id={trip_id}",
                agent_name="OrchestratorAgent",
            )
            log_agent_raw(
                f"   Storage type: {type(trip_storage).__name__}",
                agent_name="OrchestratorAgent",
            )
        else:
            trip_id = f"trip_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            trip_storage = get_trip_storage()
            log_agent_raw(
                f"📦 Using DEFAULT InMemoryTripStorage — trip_id={trip_id}",
                agent_name="OrchestratorAgent",
            )

        trip_storage.store_preferences(trip_id, preferences)
        log_agent_raw(
            f"📦 Stored preferences for: {trip_id}",
            agent_name="OrchestratorAgent",
        )

        # ── Step 1: Analyze requirements ──────────────────────────────
        agents_needed = self.analyze_requirements(preferences)

        # ── Step 2: Generate opening message ──────────────────────────
        opening_message = self._generate_opening_message(
            preferences, agents_needed, trip_id
        )
        log_agent_raw(
            f"📢 Opening message generated",
            agent_name="OrchestratorAgent",
        )

        # ── Step 3: Create agents ─────────────────────────────────────
        specialized_agents = self.create_specialized_agents_with_storage(
            agents_needed=agents_needed,
            trip_id=trip_id,
            trip_storage=trip_storage,
        )

        # Build the initial message that agents receive
        full_initial_message = f"""
        {opening_message}

        {user_proxy.get_preferences_summary()}
        """

        log_agent_raw(
            f"📨 Initial message prepared for {len(specialized_agents)} agents",
            agent_name="OrchestratorAgent",
        )

        # ── Step 4: PARALLEL EXECUTION ────────────────────────────────
        agent_results = self.run_agents_parallel(
            specialized_agents=specialized_agents,
            initial_message=full_initial_message,
            user_proxy=user_proxy,
        )

        # ── Step 5: Log parallel conversation ─────────────────────────
        self.log_parallel_conversation(
            agent_results=agent_results,
            trip_id=trip_id,
        )

        # ── Step 6: Collect results from storage ──────────────────────
        all_options = trip_storage.get_all_options(trip_id)
        summary = trip_storage.get_summary(trip_id)

        log_agent_json(
            summary,
            label="Options Collected from Storage",
            agent_name="OrchestratorAgent",
        )

        recommendations = trip_storage.get_recommendations(trip_id)

        # Build conversation history from parallel results
        conversation_history = [
            {
                "speaker": "APIUser",
                "message": full_initial_message,
            }
        ]
        for result in agent_results:
            conversation_history.append({
                "speaker": result["agent_name"],
                "message": result["response"],
            })

        # ── Step 7: Generate final recommendation ─────────────────────
        final_recommendation = self._generate_final_recommendation(
            all_options,
            conversation_history,
            preferences,
            recommendations,
        )

        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")
        log_agent_raw(
            f"✅ Parallel orchestration complete "
            f"({len(conversation_history)} messages, "
            f"{len(specialized_agents)} agents)",
            agent_name="OrchestratorAgent",
        )
        log_agent_raw("=" * 80, agent_name="OrchestratorAgent")

        return {
            "trip_id": trip_id,
            "opening_message": opening_message,
            "final_recommendation": final_recommendation,
            "recommendations": recommendations,
            "all_options": all_options,
            "conversation_history": conversation_history,
            "summary": summary,
            "agents_used": [agent.name for agent in specialized_agents],
            "execution_mode": "parallel",
            "agent_timings": {
                r["agent_name"]: r["duration"] for r in agent_results
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # OPENING MESSAGE
    # ─────────────────────────────────────────────────────────────────────

    def _generate_opening_message(
        self, preferences, agents_needed: List[str], trip_id: str
    ) -> str:
        """Generate orchestrator's opening message with trip_id reference."""

        def format_budget(value):
            return f"${value:.0f}" if value else "unspecified"

        all_interests = (
            preferences.activity_prefs.preferred_interests
            + preferences.activity_prefs.interested_interests
        )
        interests_display = (
            ", ".join(all_interests) if all_interests else "general sightseeing"
        )

        agent_descriptions = {
            "flight": (
                f"FlightAgent will find flights from {preferences.origin} "
                f"to {preferences.destination} within "
                f"{format_budget(preferences.budget.flight_budget)} budget"
            ),
            "hotel": (
                f"HotelAgent will find hotels in {preferences.destination} "
                f"meeting {preferences.hotel_prefs.min_rating}-star requirement "
                f"at {format_budget(preferences.budget.hotel_budget_per_night)}/night"
            ),
            "weather": (
                f"WeatherAgent will provide "
                f"{self.calculate_trip_duration(preferences)}-day weather "
                f"forecast for {preferences.destination}"
            ),
            "events": (
                f"EventsAgent will find events and activities matching "
                f"interests: {interests_display}"
            ),
            "places": (
                f"PlacesAgent will recommend restaurants and attractions "
                f"for: {interests_display}"
            ),
        }

        active_agents = [
            agent_descriptions[agent]
            for agent in agents_needed
            if agent in agent_descriptions
        ]

        message = f"""
    ┌─────────────────────────────────────────────────────────────┐
    │  🎯 TRAVEL PLANNING SYSTEM - PARALLEL EXECUTION             │
    └─────────────────────────────────────────────────────────────┘

    Trip to: {preferences.destination}
    Dates: {preferences.departure_date} to {preferences.return_date}
    Travelers: {preferences.num_travelers}

    The following specialized agents will work IN PARALLEL on your trip:

    """
        for i, desc in enumerate(active_agents, 1):
            message += f"  {i}. {desc}\n"

        message += f"""
            ────────────────────────────────────────────────────────────────

            🔑 **Trip Reference ID:** `{trip_id}`

            📌 **Note to Agents:** Use this trip_id to access full structured
            preferences from shared storage for 100% accurate data extraction.

            ⚡ **Execution Mode:** PARALLEL — all agents run simultaneously

            ────────────────────────────────────────────────────────────────

            """

        return message

    # ─────────────────────────────────────────────────────────────────────
    # FINAL RECOMMENDATION
    # ─────────────────────────────────────────────────────────────────────

    def _generate_final_recommendation(
        self,
        all_options: Dict[str, List],
        conversation_history: List[Dict],
        preferences: Any,
        recommendations: Dict[str, Any] = None,
    ) -> str:
        """
        Generate final recommendation summary.
        
        v7.1: No LLM call — agents already wrote their summaries.
        The frontend renders structured data directly from Redis,
        so this is just a text fallback that's rarely displayed.
        """
        flights = all_options.get("flights", [])
        hotels = all_options.get("hotels", [])
        restaurants = all_options.get("restaurants", [])
        activities = all_options.get("activities", [])
        weather = all_options.get("weather", [])

        lines = [f"### Your {preferences.destination} Trip Summary\n"]

        if flights:
            lines.append(f"✅ **Flights**: {len(flights)} options reviewed")
        if hotels:
            lines.append(f"✅ **Hotels**: {len(hotels)} options reviewed")
        if restaurants:
            lines.append(f"✅ **Restaurants**: {len(restaurants)} options reviewed")
        if activities:
            lines.append(f"✅ **Activities**: {len(activities)} options reviewed")
        if weather:
            lines.append(f"✅ **Weather**: {len(weather)} day forecast")

        if recommendations:
            lines.append("\n**Top Picks:**")
            for category, rec in recommendations.items():
                reason = rec.get("reason", "")
                if reason:
                    lines.append(f"- **{category.capitalize()}**: {reason[:150]}")

        lines.append("\nCheck the detailed options below for all available choices.")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────────────

    def calculate_trip_duration(self, preferences) -> int:
        """Calculate trip duration in days."""
        try:
            dep = datetime.fromisoformat(preferences.departure_date)
            ret = datetime.fromisoformat(preferences.return_date)
            return (ret - dep).days
        except Exception:
            return 7

    def needs_flights(self, preferences) -> bool:
        """Determine if flights are needed based on distance."""
        return preferences.origin.lower() != preferences.destination.lower()

    def trip_complexity(self, preferences) -> str:
        """Determine trip complexity (simple, moderate, complex)."""
        duration = self.calculate_trip_duration(preferences)
        if duration <= 3:
            return "simple"
        elif duration <= 7:
            return "moderate"
        else:
            return "complex"


# ============================================================================
# FACTORY
# ============================================================================


def create_orchestrator() -> TravelOrchestratorAgent:
    """Factory function to create orchestrator."""
    return TravelOrchestratorAgent()