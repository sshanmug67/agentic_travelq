"""
Main execution script for TravelQ Multi-Agent System - UPDATED
Coordinates UserProxy, Orchestrator, and specialized agents

Uses:
- logging_config.py for all logging
- settings.py for configuration
- Existing agent infrastructure
"""
import os
import sys
from autogen import GroupChat, GroupChatManager
from agents.user_proxy_agent import create_user_proxy
from agents.orchestrator_agent import create_orchestrator
from agents.base_agent import create_llm_config
from typing import Optional
from datetime import datetime

# Import existing infrastructure
from utils.logging_config import (
    setup_logging, 
    log_raw, 
    log_json_raw,
    log_info_raw,
    log_warning_raw,
    log_error_raw
)
from config.settings import settings

# Setup logging using existing infrastructure
# This creates logs in project_root/logs/
setup_logging(
    log_file_name="travel_dashboard",
    console_level=20,  # INFO level
    enable_console=True,
    fresh_start=False  # Don't delete existing logs
)

log_info_raw("=" * 80)
log_info_raw("TravelQ Multi-Agent Travel Planning System")
log_info_raw("=" * 80)


def create_specialized_agents():
    """
    Create all specialized agents using existing infrastructure
    
    Returns:
        Dictionary of agent name -> agent instance
    """
    from agents.base_agent import TravelQBaseAgent
    
    log_info_raw("Creating specialized agents...")
    
    # LLM config from settings
    llm_config = create_llm_config()
    
    agents = {}
    
    # FlightAgent
    if settings.flight_agent_enabled:
        flight_agent = TravelQBaseAgent(
            name="FlightAgent",
            system_message="""You are the Flight Expert for TravelQ.

Your expertise:
- Finding optimal flight options using flight search APIs
- Considering carrier preferences, stops, timing, and budget
- Explaining trade-offs (direct vs cheaper with stops)
- Providing detailed flight information

When asked to find flights:
1. Call the flight search tool with provided criteria
2. Analyze results for best matches
3. Present top 3 options with:
   - Airline and flight numbers
   - Departure/arrival times
   - Duration and layovers
   - Price breakdown
   - Why it matches user preferences

Always respect:
- Maximum stops limit
- Carrier preferences
- Time preferences (morning/evening/red-eye)
- Budget constraints

If no perfect match exists, explain trade-offs and suggest alternatives.""",
            llm_config=llm_config,
            description="Finds and recommends flights"
        )
        agents["flight"] = flight_agent
        log_info_raw("✅ FlightAgent created")
    
    # HotelAgent - similar pattern
    # (You would have this from your existing code)
    
    # PlacesAgent
    if settings.places_agent_enabled:
        places_agent = TravelQBaseAgent(
            name="PlacesAgent",
            system_message="""You are the Activities & Attractions Expert for TravelQ.

Your expertise:
- Discovering activities, attractions, and experiences
- Matching activities to user interests
- Considering operating hours, entry fees, and duration

When asked to find activities:
1. Search for places matching interests
2. Verify operating hours and accessibility
3. Organize by:
   - Must-see attractions
   - Local experiences
   - Hidden gems
   - By location/neighborhood

For each activity provide:
- Name and description
- Location and how to get there
- Operating hours
- Entry fees/costs
- Time needed
- Best time to visit
- Why it matches user interests

Consider:
- Daily time budget
- Activity pace preference
- Weather conditions
- Proximity to hotel

Create a balanced mix of activities.""",
            llm_config=llm_config,
            description="Discovers places and activities"
        )
        agents["places"] = places_agent
        log_info_raw("✅ PlacesAgent created")
    
    # WeatherAgent
    if settings.weather_agent_enabled:
        weather_agent = TravelQBaseAgent(
            name="WeatherAgent",
            system_message="""You are the Weather Expert for TravelQ.

Your expertise:
- Providing accurate weather forecasts
- Recommending what to pack
- Advising on weather-appropriate activities

When asked for weather:
1. Get forecast for destination and dates
2. Provide day-by-day summary
3. Highlight:
   - Temperature ranges
   - Precipitation chances
   - Weather patterns
   - Special considerations (humidity, wind, etc.)

Weather-based recommendations:
- Best days for outdoor activities
- Days for indoor/museum visits
- What to pack
- Activity timing suggestions

Be specific about impact on trip planning.""",
            llm_config=llm_config,
            description="Provides weather forecasts and recommendations"
        )
        agents["weather"] = weather_agent
        log_info_raw("✅ WeatherAgent created")
    
    # EventsAgent
    if settings.events_agent_enabled:
        events_agent = TravelQBaseAgent(
            name="EventsAgent",
            system_message="""You are the Events & Entertainment Expert for TravelQ.

Your expertise:
- Finding concerts, theater, festivals, sports events
- Matching events to user interests
- Providing booking information

When asked to find events:
1. Search events during trip dates
2. Filter by user interests
3. Present events with:
   - Event name and type
   - Date, time, venue
   - Ticket prices and availability
   - How to book
   - Why it's recommended

Prioritize:
- Events matching stated interests
- Unique/special events during trip
- Events at convenient times
- Good value tickets

Note any booking deadlines or sellout risks.""",
            llm_config=llm_config,
            description="Finds events and entertainment"
        )
        agents["events"] = events_agent
        log_info_raw("✅ EventsAgent created")
    
    log_json_raw({
        "total_agents": len(agents),
        "enabled_agents": list(agents.keys())
    }, label="Agent Creation Summary")
    
    return agents


def setup_group_chat(user_proxy, orchestrator, specialized_agents):
    """
    Setup GroupChat with all agents
    
    Args:
        user_proxy: User proxy agent
        orchestrator: Orchestrator agent
        specialized_agents: Dictionary of specialized agents
        
    Returns:
        GroupChatManager instance
    """
    log_info_raw("Setting up GroupChat...")
    
    # Collect all agents
    all_agents = [user_proxy, orchestrator] + list(specialized_agents.values())
    
    log_json_raw({
        "total_agents": len(all_agents),
        "agent_names": [agent.name for agent in all_agents]
    }, label="GroupChat Configuration")
    
    # Create GroupChat
    groupchat = GroupChat(
        agents=all_agents,
        messages=[],
        max_round=50,  # Maximum conversation rounds
        speaker_selection_method="auto"  # LLM decides who speaks next
    )
    
    # Create manager
    manager = GroupChatManager(
        groupchat=groupchat,
        llm_config=create_llm_config()
    )
    
    log_info_raw("✅ GroupChat configured with auto speaker selection")
    
    return manager


def run_travel_planning(
    preset: str = "default",
    save_output: bool = True
):
    """
    Main function to run the travel planning process
    
    Args:
        preset: User preference preset ("default", "budget", "luxury")
        save_output: Whether to save the output to a file
        
    Returns:
        Final trip plan
    """
    log_info_raw("=" * 80)
    log_info_raw(f"Starting TravelQ planning with preset: {preset}")
    log_info_raw("=" * 80)
    
    # Validate settings
    if not settings.openai_api_key:
        log_error_raw("❌ OPENAI_API_KEY not found in settings")
        log_error_raw("   Please set it in .env or app_config.yaml")
        raise ValueError("OPENAI_API_KEY not configured")
    
    try:
        # 1. Create user proxy with preferences
        log_info_raw("Creating user proxy agent...")
        user_proxy = create_user_proxy(preset=preset)
        
        preferences_summary = user_proxy.get_preferences_summary()
        log_raw(preferences_summary)
        
        # 2. Create orchestrator
        log_info_raw("Creating orchestrator agent...")
        orchestrator = create_orchestrator()
        
        # 3. Create specialized agents
        log_info_raw("Creating specialized agents...")
        specialized_agents = create_specialized_agents()
        log_info_raw(f"Created {len(specialized_agents)} specialized agents")
        
        # 4. Setup group chat
        log_info_raw("Setting up group chat...")
        manager = setup_group_chat(user_proxy, orchestrator, specialized_agents)
        
        # 5. Start the planning process
        log_info_raw("=" * 80)
        log_info_raw("STARTING TRAVEL PLANNING CONVERSATION")
        log_info_raw("=" * 80)
        
        result = user_proxy.initiate_trip_planning(manager)
        
        log_info_raw("=" * 80)
        log_info_raw("TRAVEL PLANNING COMPLETE")
        log_info_raw("=" * 80)
        
        # 6. Save output if requested
        if save_output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save to project_root/output/
            output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, f"trip_plan_{preset}_{timestamp}.json")
            
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, default=str)
            
            log_info_raw(f"✅ Trip plan saved to: {output_file}")
        
        return result
        
    except Exception as e:
        log_error_raw(f"❌ Error during travel planning: {str(e)}")
        import traceback
        log_error_raw(traceback.format_exc())
        raise


def run_interactive_mode():
    """
    Run in interactive mode where user can provide input
    """
    print("\n" + "=" * 80)
    print("TRAVELQ - AI-Powered Travel Planning")
    print("=" * 80)
    
    print("\nConfiguration:")
    print(f"- LLM Model: {settings.llm_model}")
    print(f"- OpenAI API Key: {'✓ Configured' if settings.openai_api_key else '✗ Missing'}")
    print(f"- Weather API: {'✓ Configured' if settings.weather_api_key else '✗ Missing'}")
    print(f"- Amadeus API: {'✓ Configured' if settings.amadeus_client_id else '✗ Missing'}")
    
    print("\nAvailable presets:")
    print("1. default - Moderate budget Tokyo trip")
    print("2. budget - Budget backpacker Bangkok trip")
    print("3. luxury - Luxury Paris getaway")
    
    choice = input("\nSelect preset (1-3) or press Enter for default: ").strip()
    
    preset_map = {
        "1": "default",
        "2": "budget",
        "3": "luxury",
        "": "default"
    }
    
    preset = preset_map.get(choice, "default")
    
    print(f"\n✓ Starting with '{preset}' preset...")
    print("This may take several minutes as agents coordinate...")
    print("Check logs at: logs/travel_dashboard_all_messages.log")
    print("Agent logs at: logs/agents/\n")
    
    result = run_travel_planning(preset=preset)
    
    print("\n" + "=" * 80)
    print("PLANNING COMPLETE!")
    print("=" * 80)
    print(f"\n✓ Full conversation saved to output folder.")
    print(f"✓ Check logs for detailed execution trace")


if __name__ == "__main__":
    # Ensure output directory exists
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Run in interactive mode
    run_interactive_mode()
    
    # Or run directly with a preset:
    # run_travel_planning(preset="default")