"""
Trip Models - Enhanced for Multi-Agent System
Location: backend/models/trip.py

Changes (v4):
  - Added SegmentDetail model (per-hop: terminal, aircraft, operating carrier)
  - Added FlightAmenity model (included vs paid amenities)
  - FlightSegment: added segments[] and layover_durations[]
  - Flight: added branded_fare, amenities, last_ticketing_date, seats_remaining,
            price_base, price_taxes, validating_carrier

Previous changes:
  - TripResponse: added `recommendations` field for structured agent picks
  - v2: Added PhotoItem model; Hotel.photos and Place.photos now accept
        both {"url": "..."} dicts and plain strings for backward compat
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


# ============================================================================
# REQUEST MODELS (Enhanced for Multi-Agent System)
# ============================================================================

class TripRequest(BaseModel):
    """
    Enhanced trip request from frontend
    
    Includes comprehensive preferences for multi-agent planning
    """
    # Basic trip info
    origin: str = Field(..., description="Origin city/airport")
    destination: str = Field(..., description="Destination city/airport")
    departure_date: str = Field(..., description="Departure date (YYYY-MM-DD)")
    return_date: str = Field(..., description="Return date (YYYY-MM-DD)")
    num_travelers: int = Field(default=1, ge=1, le=10, description="Number of travelers")
    trip_purpose: str = Field(default="leisure", description="leisure|business|adventure|relaxation")
    
    # Detailed preferences (optional - will use defaults if not provided)
    flight_prefs: Dict[str, Any] = Field(default_factory=dict, description="Flight preferences")
    hotel_prefs: Dict[str, Any] = Field(default_factory=dict, description="Hotel preferences")
    activity_prefs: Dict[str, Any] = Field(default_factory=dict, description="Activity preferences")
    transport_prefs: Dict[str, Any] = Field(default_factory=dict, description="Transport preferences")
    budget: Dict[str, Any] = Field(default_factory=dict, description="Budget constraints")
    
    # Additional info
    special_requirements: Optional[str] = Field(default=None, description="Special requirements or notes")
    
    # Legacy support (for backward compatibility with simple requests)
    start_date: Optional[str] = None  # Maps to departure_date
    end_date: Optional[str] = None    # Maps to return_date
    interests: Optional[List[str]] = None  # Maps to activity_prefs.interests
    
    def __init__(self, **data):
        # Handle legacy field mappings
        if 'start_date' in data and 'departure_date' not in data:
            data['departure_date'] = data['start_date']
        if 'end_date' in data and 'return_date' not in data:
            data['return_date'] = data['end_date']
        if 'interests' in data and data['interests']:
            if 'activity_prefs' not in data:
                data['activity_prefs'] = {}
            data['activity_prefs']['interests'] = data['interests']
        
        super().__init__(**data)


# ============================================================================
# SHARED MODELS
# ============================================================================

class PhotoItem(BaseModel):
    """
    Photo URL wrapper — matches frontend Array<{ url: string }> type.
    
    Google Places service returns these; Pydantic validates them before
    the data reaches the frontend.
    """
    url: str


# ============================================================================
# FLIGHT MODELS (v4 — enriched with Amadeus segment details)
# ============================================================================

class SegmentDetail(BaseModel):
    """
    One physical hop within a leg — e.g. JFK → YUL on AC8899.
    
    Extracted from Amadeus itineraries[].segments[] and merged with
    fare details from travelerPricings[].fareDetailsBySegment[].
    """
    segment_id: Optional[str] = None             # Amadeus segment id ("3")
    departure_airport: str
    arrival_airport: str
    departure_time: str                          # ISO datetime string
    arrival_time: str                            # ISO datetime string
    departure_terminal: Optional[str] = None     # "7"
    arrival_terminal: Optional[str] = None       # "1"
    duration: str                                # "1h 30m"
    marketing_carrier: str                       # "AC"
    marketing_flight_number: str                 # "AC8899"
    operating_carrier: Optional[str] = None      # "AC" or "LX"
    operating_carrier_name: Optional[str] = None # "AIR CANADA EXPRESS - JAZZ"
    aircraft_code: Optional[str] = None          # "E75", "789"
    aircraft_name: Optional[str] = None          # "Embraer E175", "Boeing 787-9 Dreamliner"
    cabin_class: Optional[str] = None            # "ECONOMY"
    branded_fare: Optional[str] = None           # "BASIC", "BASIC ECONOMY"
    fare_class: Optional[str] = None             # "L"


class FlightAmenity(BaseModel):
    """
    One amenity line from Amadeus fareDetailsBySegment.amenities[].
    
    Deduplicated across all segments in a flight offer so the frontend
    gets a single merged list of what's included vs paid.
    """
    description: str            # "COMPLIMENTARY MEAL"
    is_chargeable: bool         # false = included free
    amenity_type: str           # "BAGGAGE", "MEAL", "BRANDED_FARES", "PRE_RESERVED_SEAT", etc.


class BaggageAllowance(BaseModel):
    """Baggage allowance details"""
    quantity: Optional[int] = Field(default=None, description="Number of bags allowed")
    weight: Optional[int] = Field(default=None, description="Weight limit in kg")
    weight_unit: Optional[str] = Field(default="KG", description="Weight unit")


class FlightSegment(BaseModel):
    """
    One leg of the journey (outbound or return) — summary + per-hop details.
    
    v4: Now carries segments[] (per-hop breakdown) and layover_durations[]
    (calculated wait times between hops).
    """
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    duration: str
    airline: str
    airline_code: str
    flight_number: str
    stops: int
    layovers: List[str] = Field(default_factory=list)

    # v4 additions
    segments: Optional[List[SegmentDetail]] = Field(
        default=None,
        description="Per-hop breakdown with terminals, aircraft, operating carrier"
    )
    layover_durations: Optional[List[str]] = Field(
        default=None,
        description="Calculated layover durations between consecutive hops, e.g. ['8h 0m']"
    )


class Flight(BaseModel):
    """
    Flight information model - supports both one-way and round-trip.
    
    v4: Enriched with segment details, amenities, fare info, and booking metadata
    extracted from Amadeus API response.
    """
    id: str
    airline: str
    airline_code: str
    
    # Trip type
    is_round_trip: bool = Field(default=False, description="True if round-trip flight")
    
    # One-way flight fields (legacy - for backward compatibility)
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    duration: Optional[str] = None
    flight_number: Optional[str] = None
    stops: Optional[int] = None
    layovers: Optional[List[str]] = None
    
    # Round-trip fields
    outbound: Optional[FlightSegment] = Field(default=None, description="Outbound flight segment")
    return_flight: Optional[FlightSegment] = Field(default=None, description="Return flight segment")
    total_duration: Optional[str] = Field(default=None, description="Total travel time (outbound + return)")
    
    # Common fields
    price: Optional[float] = None
    currency: Optional[str] = "USD"
    cabin_class: Optional[str] = "economy"
    booking_url: Optional[str] = None
    
    # Baggage
    checked_bags: Optional[BaggageAllowance] = Field(
        default=None, 
        description="Checked baggage allowance"
    )
    cabin_bags: Optional[BaggageAllowance] = Field(
        default=None, 
        description="Cabin baggage allowance"
    )

    # ── v4 additions ─────────────────────────────────────────────────────
    branded_fare: Optional[str] = Field(
        default=None,
        description="Branded fare label, e.g. 'BASIC', 'FLEX', 'STANDARD'"
    )
    amenities: Optional[List[FlightAmenity]] = Field(
        default=None,
        description="Merged unique amenities across all segments (included vs paid)"
    )
    last_ticketing_date: Optional[str] = Field(
        default=None,
        description="Last date to purchase this fare, e.g. '2026-02-16'"
    )
    seats_remaining: Optional[int] = Field(
        default=None,
        description="Number of bookable seats remaining at this fare"
    )
    price_base: Optional[float] = Field(
        default=None,
        description="Base fare before taxes and fees"
    )
    price_taxes: Optional[float] = Field(
        default=None,
        description="Taxes and fees (total - base)"
    )
    validating_carrier: Optional[str] = Field(
        default=None,
        description="Ticketing/validating airline code"
    )


# ============================================================================
# HOTEL MODELS - Enhanced with Google Places
# ============================================================================

class HotelAmenities(BaseModel):
    """Hotel amenities details"""
    wifi: bool = False
    parking: bool = False
    pool: bool = False
    gym: bool = False
    restaurant: bool = False
    room_service: bool = False
    air_conditioning: bool = False
    spa: bool = False
    bar: bool = False
    breakfast: bool = False


class HotelReview(BaseModel):
    """Individual hotel review from Google Places"""
    author_name: str
    rating: float
    text: str
    time: Optional[int] = None
    relative_time_description: Optional[str] = None


class Hotel(BaseModel):
    """Hotel information model - Enhanced with Google Places data"""
    id: str
    name: str
    hotel_code: str
    
    # Location
    latitude: float
    longitude: float
    address: str
    city: Optional[str] = None
    distance_from_center: Optional[float] = None  # km
    
    # Ratings & Reviews (Amadeus + Google Places)
    rating: Optional[float] = None  # Amadeus rating (0-5 stars)
    review_count: Optional[int] = None  # Amadeus review count
    
    # Google Places specific ratings
    place_id: Optional[str] = None  # Google Place ID
    google_rating: Optional[float] = None  # Google rating (0-5)
    user_ratings_total: Optional[int] = None  # Total Google reviews
    reviews: Optional[List[HotelReview]] = []  # Top reviews from Google
    
    # Pricing
    price_per_night: float
    total_price: float
    currency: str = "USD"
    
    # Stay details
    check_in_date: str
    check_out_date: str
    num_nights: int
    room_type: Optional[str] = None
    
    # Details
    amenities: Optional[HotelAmenities] = None
    description: Optional[str] = None
    photos: Optional[List[PhotoItem]] = []
    booking_url: Optional[str] = None
    
    # Google Places additional info
    website: Optional[str] = None
    phone_number: Optional[str] = None
    google_url: Optional[str] = None  # Google Maps URL
    business_status: Optional[str] = None
    
    # Additional info
    property_type: Optional[str] = None  # hotel, resort_hotel, lodging, etc.
    
    highlights: Optional[List[str]] = Field(
        default=None,
        description="Key highlights for display (e.g. 'Great location', 'Free breakfast')"
    )

    # ── v4 additions (Google Places + Xotelo enrichment) ─────────────────
    booking_links: Optional[Dict[str, str]] = Field(
        default=None,
        description="All OTA booking URLs: {'booking_com': url, 'expedia': url, ...}"
    )
    cheapest_provider: Optional[str] = Field(
        default=None,
        description="OTA with the lowest price from Xotelo, e.g. 'Booking.com'"
    )
    is_estimated_price: Optional[bool] = Field(
        default=None,
        description="True if price is estimated from Google price_level, False if from Xotelo"
    )
    price_level: Optional[int] = Field(
        default=None,
        description="Google price level 0-4 (Free to Very Expensive)"
    )
    
    @field_validator('photos', mode='before')
    @classmethod
    def coerce_photos(cls, v):
        """Accept both plain strings and {"url": "..."} dicts"""
        if v is None:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"url": item})
            elif isinstance(item, dict):
                result.append(item)
            else:
                result.append(item)
        return result


class Weather(BaseModel):
    """Weather forecast model"""
    date: str
    temperature: float
    feels_like: Optional[float] = None
    temp_min: float
    temp_max: float
    description: str
    icon: Optional[str] = None
    humidity: Optional[int] = None
    wind_speed: Optional[float] = None
    precipitation_probability: Optional[float] = None
    conditions: Optional[str] = None  # sunny, rainy, cloudy, etc.


class Event(BaseModel):
    """Event information model"""
    id: str
    name: str
    description: Optional[str] = None
    venue: str
    address: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    category: str
    price_range: Optional[str] = None
    ticket_url: Optional[str] = None
    image_url: Optional[str] = None
    is_free: Optional[bool] = False


class Place(BaseModel):
    """Place/attraction model"""
    id: str
    name: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    category: str
    description: Optional[str] = None
    photos: Optional[List[PhotoItem]] = []
    opening_hours: Optional[Dict[str, Any]] = None
    price_level: Optional[int] = None  # 0-4 scale
    website: Optional[str] = None
    
    @field_validator('photos', mode='before')
    @classmethod
    def coerce_photos(cls, v):
        """Accept both plain strings and {"url": "..."} dicts"""
        if v is None:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"url": item})
            elif isinstance(item, dict):
                result.append(item)
            else:
                result.append(item)
        return result


# ============================================================================
# ITINERARY MODELS (Multi-Agent Output)
# ============================================================================

class Activity(BaseModel):
    """Single activity in itinerary"""
    time: str
    name: str
    location: str
    duration: str
    cost: Optional[float] = None
    notes: Optional[str] = None
    place_id: Optional[str] = None


class Meal(BaseModel):
    """Meal recommendation"""
    time: str
    type: str  # breakfast, lunch, dinner, snack
    restaurant: Optional[str] = None
    cuisine: Optional[str] = None
    estimated_cost: Optional[float] = None
    address: Optional[str] = None


class Transportation(BaseModel):
    """Transportation between locations"""
    from_location: str
    to_location: str
    mode: str  # metro, bus, cab, walk, etc.
    time: str
    duration: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None


class DayItinerary(BaseModel):
    """Daily itinerary"""
    day_number: int
    date: str
    title: Optional[str] = None
    activities: List[Activity]
    meals: Optional[List[Meal]] = []
    transportation: Optional[List[Transportation]] = []
    weather: Optional[Weather] = None
    notes: Optional[str] = None


class BudgetSummary(BaseModel):
    """Budget breakdown"""
    total_budget: float
    estimated_flight_cost: float
    estimated_hotel_cost: float
    estimated_activity_cost: float
    estimated_food_cost: float
    estimated_transport_cost: float
    remaining_budget: float
    currency: str = "USD"


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class TripResponse(BaseModel):
    """Response model for trip planning"""
    status: str
    trip_id: str
    final_recommendation: str
    options: Dict[str, List[Any]]  # {flights: [...], hotels: [...], etc}
    summary: Dict[str, int]  # {flights: 5, hotels: 3, etc}
    processing_time: float
    agents_used: List[str]
    
    # ✅ Structured AI recommendations from agents
    # Each agent stores its top pick; orchestrator collects them here.
    # Shape: { "flight": { "recommended_id": "1", "reason": "...", "metadata": {...} }, ... }
    recommendations: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured AI recommendations from agents. "
                    "Keys are categories (flight, hotel, restaurant, activity). "
                    "Values contain recommended_id, reason, and metadata."
    )
    
    # Optional fields
    conversation_history: Optional[List[Dict]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "trip_id": "trip_20260210_133901",
                "final_recommendation": "Based on 47 flights reviewed...",
                "options": {
                    "flights": [],
                    "hotels": []
                },
                "summary": {
                    "flights": 47,
                    "hotels": 0
                },
                "recommendations": {
                    "flight": {
                        "recommended_id": "1",
                        "reason": "Direct flight (no stops); Lowest price",
                        "metadata": {
                            "airline": "BA",
                            "price": 431.11,
                            "is_direct": True,
                            "total_options_reviewed": 5
                        }
                    }
                },
                "processing_time": 102.57,
                "agents_used": ["FlightAgent", "WeatherAgent"]
            }
        }


class SimpleTripResponse(BaseModel):
    """
    Simplified response for basic searches
    (Backward compatibility)
    """
    trip_id: str
    flights: List[Flight]
    weather_forecast: List[Weather]
    events: List[Event]
    places: List[Place]
    ai_suggestions: Optional[str] = None
    created_at: datetime


# ============================================================================
# AGENT COMMUNICATION MODELS
# ============================================================================

class AgentRequest(BaseModel):
    """Request to a specific agent"""
    agent_name: str
    parameters: Dict[str, Any]
    user_preferences: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    """Response from a specific agent"""
    agent_name: str
    status: str
    data: Dict[str, Any]
    execution_time: Optional[float] = None
    error: Optional[str] = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def convert_to_simple_response(enhanced_response: TripResponse) -> SimpleTripResponse:
    """
    Convert enhanced TripResponse to simple format
    For backward compatibility with existing frontend
    """
    return SimpleTripResponse(
        trip_id=enhanced_response.trip_id or "generated",
        flights=enhanced_response.flights,
        weather_forecast=enhanced_response.weather_forecast,
        events=enhanced_response.events,
        places=enhanced_response.places,
        ai_suggestions=enhanced_response.ai_suggestions,
        created_at=enhanced_response.created_at
    )