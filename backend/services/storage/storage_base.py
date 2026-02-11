"""
Storage Interface - Abstract base for trip storage
Location: backend/services/storage/base.py
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
    def add_weather(
        self, 
        trip_id: str, 
        weather: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store weather forecast"""
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