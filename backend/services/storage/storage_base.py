"""
Storage Interface - Abstract base for trip storage
Location: backend/services/storage/storage_base.py

Added:
  - store_recommendation()   → agents write their top pick
  - get_recommendations()    → orchestrator reads all picks
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

class TripStorageInterface(ABC):
    """
    Abstract interface for trip storage
    Allows swapping between in-memory, Redis, or database
    """
    
    @abstractmethod
    def add_flights(
        self, 
        trip_id: str, 
        flights: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store flight options"""
        pass
    
    @abstractmethod
    def add_hotels(
        self, 
        trip_id: str, 
        hotels: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store hotel options"""
        pass
    
    @abstractmethod
    def add_weather(
        self, 
        trip_id: str, 
        weather: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store weather forecast"""
        pass

    @abstractmethod
    def add_restaurants(
        self, 
        trip_id: str, 
        restaurants: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store restaurant options"""
        pass

    @abstractmethod
    def add_activities(
        self, 
        trip_id: str, 
        activities: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store activity/attraction options"""
        pass

    @abstractmethod
    def add_places(
        self, 
        trip_id: str, 
        places: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store place/attraction options"""
        pass

    @abstractmethod
    def get_restaurants(self, trip_id: str) -> List[Dict]:
        """Get all restaurants for trip"""
        pass

    @abstractmethod
    def get_activities(self, trip_id: str) -> List[Dict]:
        """Get all activities for trip"""
        pass

    @abstractmethod
    def get_all_options(self, trip_id: str) -> Dict[str, List[Any]]:
        """Get all stored options for a trip"""
        pass
    
    @abstractmethod
    def get_summary(self, trip_id: str) -> Dict[str, int]:
        """Get count summary"""
        pass
    
    @abstractmethod
    def exists(self, trip_id: str) -> bool:
        """Check if trip exists in storage"""
        pass
    
    @abstractmethod
    def delete(self, trip_id: str):
        """Delete trip data"""
        pass
    
    @abstractmethod
    def store_preferences(self, trip_id: str, preferences: Any):
        """Store user preferences for the trip"""
        pass
    
    @abstractmethod
    def get_preferences(self, trip_id: str) -> Optional[Any]:
        """Get user preferences for the trip"""
        pass

    @abstractmethod
    def log_api_call(
        self, 
        trip_id: str, 
        agent_name: str, 
        api_name: str, 
        duration: float
    ):
        """Log API call for debugging/analytics"""
        pass

    # ─── AI Recommendations ──────────────────────────────────────────────
    # Each agent stores its top pick after deciding.
    # The orchestrator reads all picks and attaches them to the response.

    @abstractmethod
    def store_recommendation(
        self,
        trip_id: str,
        category: str,
        recommended_id: str,
        reason: str = "",
        metadata: Optional[Dict] = None
    ):
        """
        Store an agent's top-pick recommendation.

        Args:
            trip_id:        Trip identifier
            category:       One of: flight, hotel, restaurant, activity
            recommended_id: The ID of the recommended item (matches item.id in options)
            reason:         Short human-readable explanation of why this was picked
            metadata:       Optional extra data (e.g. runner_up_id, score)
        """
        pass

    @abstractmethod
    def update_agent_status_message(
        self,
        trip_id: str,
        agent_name: str,
        message: str,
    ):
        """Update granular status message for an agent (displayed in frontend)."""
        pass


    @abstractmethod
    def get_recommendations(self, trip_id: str) -> Dict[str, Any]:
        """
        Get all agent recommendations for a trip.

        Returns dict like:
            {
                "flight": {
                    "recommended_id": "1",
                    "reason": "Best price with direct route",
                    "metadata": {}
                },
                "hotel": {
                    "recommended_id": "ChIJ...",
                    "reason": "Highest rated within budget",
                    "metadata": {}
                },
                ...
            }
        """
        pass