"""
In-Memory Storage Implementation
Location: backend/services/storage/memory_storage.py
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from threading import Lock
from services.storage.storage_base import TripStorageInterface
from utils.logging_config import log_info_raw

class InMemoryTripStorage(TripStorageInterface):
    """
    In-memory storage for trip planning (Phase 1)
    Thread-safe for concurrent requests
    """
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        log_info_raw("💾 InMemoryTripStorage initialized")
    
    def store_preferences(self, trip_id: str, preferences: Any):
        """Store user preferences"""
        with self._lock:
            if trip_id not in self._storage:
                self._init_trip(trip_id)
            
            self._storage[trip_id]["preferences"] = preferences
            log_info_raw(f"💾 Stored preferences for trip {trip_id}")
    
    def get_preferences(self, trip_id: str) -> Optional[Any]:
        """Get user preferences"""
        with self._lock:
            if trip_id in self._storage:
                return self._storage[trip_id].get("preferences")
            return None
            
    def add_flights(
        self, 
        trip_id: str, 
        flights: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store flight options"""
        with self._lock:
            if trip_id not in self._storage:
                self._init_trip(trip_id)
            
            self._storage[trip_id]["flights"].extend(flights)
            
            if metadata:
                self._storage[trip_id]["metadata"]["flights"] = metadata
            
            log_info_raw(f"💾 Stored {len(flights)} flights for trip {trip_id}")
    
    def add_hotels(
        self, 
        trip_id: str, 
        hotels: List[Dict], 
        metadata: Optional[Dict] = None
    ):
        """Store hotel options"""
        with self._lock:
            if trip_id not in self._storage:
                self._init_trip(trip_id)
            
            self._storage[trip_id]["hotels"].extend(hotels)
            
            if metadata:
                self._storage[trip_id]["metadata"]["hotels"] = metadata
            
            log_info_raw(f"💾 Stored {len(hotels)} hotels for trip {trip_id}")
    
    def get_all_options(self, trip_id: str) -> Dict[str, List[Any]]:
        """Get all stored options"""
        with self._lock:
            if trip_id not in self._storage:
                return self._empty_options()
            
            return {
                "flights": self._storage[trip_id]["flights"].copy(),
                "hotels": self._storage[trip_id]["hotels"].copy(),
                "cars": self._storage[trip_id]["cars"].copy(),
                "restaurants": self._storage[trip_id]["restaurants"].copy(),
                "activities": self._storage[trip_id]["activities"].copy(),
                "weather": self._storage[trip_id]["weather"].copy()
            }
    
    def get_summary(self, trip_id: str) -> Dict[str, int]:
        """Get count summary"""
        options = self.get_all_options(trip_id)
        return {k: len(v) for k, v in options.items()}
    
    def exists(self, trip_id: str) -> bool:
        """Check if trip exists"""
        return trip_id in self._storage
    
    def delete(self, trip_id: str):
        """Delete trip data"""
        with self._lock:
            if trip_id in self._storage:
                del self._storage[trip_id]
                log_info_raw(f"🗑️ Deleted trip {trip_id} from storage")
    
    def log_api_call(
        self, 
        trip_id: str, 
        agent_name: str, 
        api_name: str, 
        duration: float
    ):
        """Log API call"""
        with self._lock:
            if trip_id not in self._storage:
                self._init_trip(trip_id)
            
            self._storage[trip_id]["api_calls"].append({
                "agent": agent_name,
                "api": api_name,
                "duration": duration,
                "timestamp": datetime.now().isoformat()
            })
    
    def _init_trip(self, trip_id: str):
        """Initialize storage for a new trip"""
        self._storage[trip_id] = {
            "flights": [],
            "hotels": [],
            "cars": [],
            "restaurants": [],
            "activities": [],
            "weather": [],
            "metadata": {},
            "api_calls": [],
            "created_at": datetime.now().isoformat()
        }
    
    def _empty_options(self) -> Dict[str, List]:
        """Return empty options structure"""
        return {
            "flights": [],
            "hotels": [],
            "cars": [],
            "restaurants": [],
            "activities": [],
            "weather": []
        }


# Singleton instance
_storage_instance = None

def get_trip_storage() -> TripStorageInterface:
    """Get storage instance (singleton)"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = InMemoryTripStorage()
    return _storage_instance