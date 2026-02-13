"""
User Preferences Model for TravelQ
Contains hardcoded user preferences for testing and development

Changes (v2):
  - Added preferred_chains to HotelPreferences for chain-specific hotel search

Location: backend/models/user_preferences.py
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FlightPreferences(BaseModel):
    """User's flight preferences"""
    preferred_carriers: List[str] = Field(default_factory=list, description="Preferred airline carriers")
    max_stops: int = Field(default=1, description="Maximum number of stops/layovers")
    cabin_class: str = Field(default="economy", description="economy, premium_economy, business, first")
    time_preference: str = Field(default="flexible", description="morning, afternoon, evening, night, flexible")
    seat_preference: Optional[str] = Field(default="window", description="window, aisle, middle")


class HotelPreferences(BaseModel):
    """User's hotel preferences"""
    min_rating: float = Field(default=4.0, description="Minimum hotel rating (1-5 stars)")
    preferred_location: str = Field(default="city_center", description="city_center, near_attractions, quiet_area")
    amenities: List[str] = Field(default_factory=list, description="Required amenities")
    room_type: str = Field(default="standard", description="standard, deluxe, suite")
    price_range: str = Field(default="moderate", description="budget, moderate, luxury")
    preferred_chains: List[str] = Field(default_factory=list, description="Preferred hotel chains (e.g. Marriott, Hilton)")


class ActivityPreferences(BaseModel):
    """User's activity preferences"""
    interests: List[str] = Field(default_factory=list, description="List of interests")
    pace: str = Field(default="moderate", description="relaxed, moderate, fast-paced")
    preferred_times: List[str] = Field(default_factory=list, description="morning, afternoon, evening")
    accessibility_needs: Optional[str] = None
    entertainment_hours_per_day: int = Field(default=6, description="Hours available for activities per day")


class TransportPreferences(BaseModel):
    """User's local transportation preferences"""
    preferred_modes: List[str] = Field(default_factory=list, description="metro, bus, cab, walk, bike")
    max_walk_distance: float = Field(default=1.0, description="Maximum walking distance in miles")
    comfort_level: str = Field(default="moderate", description="budget, moderate, premium")


class BudgetConstraints(BaseModel):
    """User's budget constraints"""
    total_budget: float = Field(description="Total trip budget in USD")
    flight_budget: Optional[float] = None
    hotel_budget_per_night: Optional[float] = None
    daily_activity_budget: Optional[float] = None
    daily_food_budget: Optional[float] = None
    transport_budget: Optional[float] = None


class TravelPreferences(BaseModel):
    """Complete user travel preferences"""
    # Trip basics
    destination: str
    origin: str
    departure_date: str
    return_date: str
    num_travelers: int = Field(default=1)
    
    # Preferences
    flight_prefs: FlightPreferences
    hotel_prefs: HotelPreferences
    activity_prefs: ActivityPreferences
    transport_prefs: TransportPreferences
    budget: BudgetConstraints
    
    # Additional
    special_requirements: Optional[str] = None
    trip_purpose: str = Field(default="leisure", description="leisure, business, adventure, relaxation")


# Hardcoded user preferences for testing
HARDCODED_USER_PREFERENCES = TravelPreferences(
    # Trip basics
    destination="Tokyo, Japan",
    origin="New York, NY",
    departure_date="2026-04-15",
    return_date="2026-04-22",
    num_travelers=2,
    
    # Flight preferences
    flight_prefs=FlightPreferences(
        preferred_carriers=["ANA", "JAL", "United"],
        max_stops=1,
        cabin_class="economy",
        time_preference="daytime",
        seat_preference="window"
    ),
    
    # Hotel preferences
    hotel_prefs=HotelPreferences(
        min_rating=4.0,
        preferred_location="city_center",
        amenities=["wifi", "breakfast", "gym"],
        room_type="deluxe",
        price_range="moderate"
    ),
    
    # Activity preferences
    activity_prefs=ActivityPreferences(
        interests=[
            "historical temples",
            "modern technology",
            "local cuisine",
            "traditional culture",
            "shopping",
            "cherry blossoms"
        ],
        pace="moderate",
        preferred_times=["morning", "afternoon"],
        entertainment_hours_per_day=7
    ),
    
    # Transport preferences
    transport_prefs=TransportPreferences(
        preferred_modes=["metro", "walk", "cab"],
        max_walk_distance=0.8,
        comfort_level="moderate"
    ),
    
    # Budget
    budget=BudgetConstraints(
        total_budget=5000.0,
        flight_budget=1500.0,
        hotel_budget_per_night=200.0,
        daily_activity_budget=150.0,
        daily_food_budget=100.0,
        transport_budget=300.0
    ),
    
    # Additional info
    special_requirements="One traveler is vegetarian. Interested in experiencing hanami (cherry blossom viewing).",
    trip_purpose="leisure"
)


# Alternative preset: Budget Backpacker
BUDGET_BACKPACKER_PREFERENCES = TravelPreferences(
    destination="Bangkok, Thailand",
    origin="Los Angeles, CA",
    departure_date="2026-05-10",
    return_date="2026-05-24",
    num_travelers=1,
    
    flight_prefs=FlightPreferences(
        preferred_carriers=["AirAsia", "Thai Airways", "EVA Air"],
        max_stops=2,
        cabin_class="economy",
        time_preference="flexible"
    ),
    
    hotel_prefs=HotelPreferences(
        min_rating=3.0,
        preferred_location="near_attractions",
        amenities=["wifi", "air_conditioning"],
        room_type="standard",
        price_range="budget"
    ),
    
    activity_prefs=ActivityPreferences(
        interests=["street food", "temples", "markets", "nightlife", "cultural experiences"],
        pace="fast-paced",
        preferred_times=["morning", "afternoon", "evening"],
        entertainment_hours_per_day=10
    ),
    
    transport_prefs=TransportPreferences(
        preferred_modes=["metro", "bus", "walk", "tuk-tuk"],
        max_walk_distance=2.0,
        comfort_level="budget"
    ),
    
    budget=BudgetConstraints(
        total_budget=2000.0,
        flight_budget=600.0,
        hotel_budget_per_night=30.0,
        daily_activity_budget=40.0,
        daily_food_budget=20.0,
        transport_budget=100.0
    ),
    
    trip_purpose="adventure"
)


# Alternative preset: Luxury Getaway
LUXURY_GETAWAY_PREFERENCES = TravelPreferences(
    destination="Paris, France",
    origin="San Francisco, CA",
    departure_date="2026-06-20",
    return_date="2026-06-27",
    num_travelers=2,
    
    flight_prefs=FlightPreferences(
        preferred_carriers=["Air France", "United", "Delta"],
        max_stops=0,
        cabin_class="business",
        time_preference="morning",
        seat_preference="aisle"
    ),
    
    hotel_prefs=HotelPreferences(
        min_rating=5.0,
        preferred_location="city_center",
        amenities=["spa", "michelin_restaurant", "concierge", "room_service", "champagne"],
        room_type="suite",
        price_range="luxury"
    ),
    
    activity_prefs=ActivityPreferences(
        interests=[
            "fine dining",
            "art museums",
            "wine tasting",
            "fashion shopping",
            "historical landmarks",
            "theater"
        ],
        pace="relaxed",
        preferred_times=["afternoon", "evening"],
        entertainment_hours_per_day=5
    ),
    
    transport_prefs=TransportPreferences(
        preferred_modes=["cab", "private_car"],
        max_walk_distance=0.3,
        comfort_level="premium"
    ),
    
    budget=BudgetConstraints(
        total_budget=15000.0,
        flight_budget=5000.0,
        hotel_budget_per_night=800.0,
        daily_activity_budget=500.0,
        daily_food_budget=300.0,
        transport_budget=500.0
    ),
    
    special_requirements="Anniversary trip. Interested in private tours and exclusive experiences.",
    trip_purpose="relaxation"
)


def get_user_preferences(preset: str = "default") -> TravelPreferences:
    """
    Get user preferences by preset name
    
    Args:
        preset: "default", "budget", or "luxury"
    
    Returns:
        TravelPreferences object
    """
    presets = {
        "default": HARDCODED_USER_PREFERENCES,
        "budget": BUDGET_BACKPACKER_PREFERENCES,
        "luxury": LUXURY_GETAWAY_PREFERENCES
    }
    
    return presets.get(preset, HARDCODED_USER_PREFERENCES)