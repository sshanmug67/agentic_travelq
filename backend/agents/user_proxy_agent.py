"""
User Proxy Agent for TravelQ
Represents the user and their preferences in the multi-agent travel planning system
"""
from autogen import UserProxyAgent
from typing import Dict, Any, Optional
import json
from models.user_preferences import TravelPreferences, get_user_preferences


class TravelQUserProxy(UserProxyAgent):
    """
    Custom UserProxyAgent for TravelQ that:
    1. Holds user travel preferences
    2. Initiates the travel planning conversation
    3. Can execute code if needed
    4. Provides feedback to other agents
    """
    
    def __init__(
        self,
        name: str = "TravelUser",
        user_preferences: Optional[TravelPreferences] = None,
        human_input_mode: str = "NEVER",
        **kwargs
    ):
        """
        Initialize the TravelQ User Proxy Agent
        
        Args:
            name: Agent name
            user_preferences: TravelPreferences object with user's travel preferences
            human_input_mode: "ALWAYS", "NEVER", or "TERMINATE"
            max_consecutive_auto_reply: Maximum auto-replies before asking for human input
        """
        # Store user preferences
        self.user_preferences = user_preferences or get_user_preferences("default")
        
        # Initialize the parent UserProxyAgent
        super().__init__(
            name=name,
            human_input_mode=human_input_mode,
            max_consecutive_auto_reply=0,
            is_termination_msg=lambda msg: False,
            code_execution_config={
                "work_dir": "workspace",
                "use_docker": False,
                "last_n_messages": 3
            },
            **kwargs
        )
    
    def _is_termination_msg(self, msg: Dict[str, Any]) -> bool:
        """
        Check if the message indicates conversation should terminate
        
        Args:
            msg: Message dictionary
            
        Returns:
            True if conversation should terminate
        """
        content = msg.get("content", "").lower()
        
        # Terminate if itinerary is complete
        if "itinerary complete" in content or "trip plan finalized" in content:
            return True
        
        # Terminate if max rounds reached
        if "TERMINATE" in msg.get("content", ""):
            return True
            
        return False
    
    def get_preferences_summary(self) -> str:
        """
        Get a formatted summary of user preferences for agents
        
        Returns:
            Formatted string with user preferences
        """
        prefs = self.user_preferences
        
        summary = f"""
=== USER TRAVEL PREFERENCES ===

TRIP DETAILS:
- Destination: {prefs.destination}
- Origin: {prefs.origin}
- Dates: {prefs.departure_date} to {prefs.return_date}
- Travelers: {prefs.num_travelers} person(s)
- Purpose: {prefs.trip_purpose}

BUDGET:
- Total Budget: ${prefs.budget.total_budget:,.2f}
- Flight Budget: ${prefs.budget.flight_budget:,.2f}
- Hotel Budget: ${prefs.budget.hotel_budget_per_night:,.2f}/night
- Daily Activities: ${prefs.budget.daily_activity_budget:,.2f}
- Daily Food: ${prefs.budget.daily_food_budget:,.2f}
- Transportation: ${prefs.budget.transport_budget:,.2f}

FLIGHT PREFERENCES:
- Preferred Carriers: {', '.join(prefs.flight_prefs.preferred_carriers)}
- Max Stops: {prefs.flight_prefs.max_stops}
- Cabin Class: {prefs.flight_prefs.cabin_class}
- Time Preference: {prefs.flight_prefs.time_preference}

HOTEL PREFERENCES:
- Minimum Rating: {prefs.hotel_prefs.min_rating} stars
- Location: {prefs.hotel_prefs.preferred_location}
- Amenities: {', '.join(prefs.hotel_prefs.amenities)}
- Room Type: {prefs.hotel_prefs.room_type}

ACTIVITY PREFERENCES:
- Interests: {', '.join(prefs.activity_prefs.interests)}
- Pace: {prefs.activity_prefs.pace}
- Entertainment Hours/Day: {prefs.activity_prefs.entertainment_hours_per_day} hours
- Preferred Times: {', '.join(prefs.activity_prefs.preferred_times)}

TRANSPORT PREFERENCES:
- Preferred Modes: {', '.join(prefs.transport_prefs.preferred_modes)}
- Max Walking Distance: {prefs.transport_prefs.max_walk_distance} miles

SPECIAL REQUIREMENTS:
{prefs.special_requirements or 'None'}

================================
"""
        return summary
    
    def initiate_trip_planning(self, orchestrator_agent) -> Dict[str, Any]:
        """
        Start the trip planning process with the orchestrator
        
        Args:
            orchestrator_agent: The orchestrator agent to communicate with
            
        Returns:
            Final trip plan
        """
        initial_message = f"""
Hello! I need help planning a trip with the following preferences:

{self.get_preferences_summary()}

Please coordinate with your team to create a comprehensive itinerary that:
1. Fits within my budget
2. Respects all my preferences
3. Optimizes for a great travel experience
4. Handles all logistics (flights, hotels, activities, transportation)

Begin the planning process!
"""
        
        # Initiate the chat with the orchestrator
        self.initiate_chat(
            orchestrator_agent,
            message=initial_message
        )
        
        # Extract the final plan from the conversation
        return self._extract_final_plan()
    
    def _extract_final_plan(self) -> Dict[str, Any]:
        """
        Extract the final trip plan from the conversation history
        
        Returns:
            Dictionary containing the trip plan
        """
        # Get the last message from orchestrator
        messages = self.chat_messages
        
        # Find the final itinerary message
        final_plan = {
            "status": "planning_complete",
            "conversation_history": messages,
            "user_preferences": self.user_preferences.dict()
        }
        
        return final_plan
    
    def provide_feedback(self, feedback: str) -> str:
        """
        Provide feedback on the proposed plan
        
        Args:
            feedback: User's feedback
            
        Returns:
            Formatted feedback message
        """
        return f"USER FEEDBACK: {feedback}"
    
    def approve_plan(self) -> str:
        """User approves the plan"""
        return "I approve this itinerary. Please proceed with booking instructions. TERMINATE"
    
    def request_revision(self, reason: str) -> str:
        """
        Request revision to the plan
        
        Args:
            reason: Reason for revision
            
        Returns:
            Revision request message
        """
        return f"Please revise the plan. Reason: {reason}"


def create_user_proxy(preset: str = "default") -> TravelQUserProxy:
    """
    Factory function to create a TravelQ User Proxy Agent
    
    Args:
        preset: "default", "budget", or "luxury"
        
    Returns:
        Configured TravelQUserProxy instance
    """
    preferences = get_user_preferences(preset)
    
    return TravelQUserProxy(
        name="TravelUser",
        user_preferences=preferences,
        human_input_mode="NEVER",  # Fully automated for testing
        max_consecutive_auto_reply=50
    )


# Example usage
if __name__ == "__main__":
    # Create user proxy with default preferences
    user = create_user_proxy("default")
    
    # Print preferences summary
    print(user.get_preferences_summary())
    
    # Example of how to use with orchestrator (orchestrator would be created separately)
    # user.initiate_trip_planning(orchestrator)