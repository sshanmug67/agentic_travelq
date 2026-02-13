"""
Trip Search Request Models — Matches Frontend Payload
Location: backend/models/trip_search_request.py

These models mirror exactly what the frontend sends via POST /api/trips/search.
The frontend payload has 5 top-level fields:
  1. tripId        — null for new trips, string for existing trips
  2. userRequest   — natural language query from the user
  3. tripDetails   — the Summary Bar data (destination, dates, budget, travelers)
  4. preferences   — user preferences (both UI lists and detailed settings)
  5. currentItinerary — what the user has already selected (flight, hotel, restaurants, activities)

Changes (v2):
  - Fixed: to_legacy_trip_request() now extracts hotelChains → hotel_chains
    so preferred hotel chains flow through to HotelAgent's text search
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any


# ============================================================================
# PREFERENCES — Matches frontend UserPreferences type
# ============================================================================

class NamedPreference(BaseModel):
    """A single named preference with a preferred flag."""
    name: str
    preferred: bool = False


class BudgetTiers(BaseModel):
    """Budget tier display strings from the PreferencesPanel UI."""
    meals: Optional[str] = None
    accommodation: Optional[str] = None
    activities: Optional[str] = None


class FlightPrefs(BaseModel):
    """Detailed flight preferences."""
    preferredCarriers: List[str] = Field(default_factory=list)
    maxStops: int = 1
    cabinClass: str = "economy"
    timePreference: str = "flexible"
    seatPreference: str = "window"


class HotelPrefs(BaseModel):
    """Detailed hotel preferences."""
    minRating: float = 3.5
    preferredLocation: str = "city_center"
    amenities: List[str] = Field(default_factory=lambda: ["wifi", "breakfast"])
    roomType: str = "standard"
    priceRange: str = "moderate"


class ActivityPrefs(BaseModel):
    """Detailed activity preferences."""
    interests: List[str] = Field(default_factory=list)
    pace: str = "moderate"
    preferredTimes: List[str] = Field(default_factory=lambda: ["morning", "afternoon"])
    accessibilityNeeds: Optional[str] = None
    entertainmentHoursPerDay: int = 6


class TransportPrefs(BaseModel):
    """Detailed transport preferences."""
    preferredModes: List[str] = Field(default_factory=lambda: ["metro", "walk", "cab"])
    maxWalkDistance: float = 1.0
    comfortLevel: str = "moderate"


class BudgetConstraints(BaseModel):
    """Per-category budget constraints."""
    totalBudget: float = 0
    flightBudget: float = 0
    hotelBudgetPerNight: float = 0
    dailyActivityBudget: float = 0
    dailyFoodBudget: float = 0
    transportBudget: float = 0


class Preferences(BaseModel):
    """
    All user preferences from the frontend.
    Combines UI lists (airlines, cuisines, etc.) + detailed settings.
    Every field has defaults so partial payloads are fine.
    """
    # UI Preferences (PreferencesPanel)
    airlines: List[NamedPreference] = Field(default_factory=list)
    hotelChains: List[NamedPreference] = Field(default_factory=list)
    cuisines: List[NamedPreference] = Field(default_factory=list)
    activities: List[NamedPreference] = Field(default_factory=list)
    budget: Optional[BudgetTiers] = None          # Tier labels from PreferencesPanel UI

    # Detailed Preferences
    flightPrefs: Optional[FlightPrefs] = None
    hotelPrefs: Optional[HotelPrefs] = None
    activityPrefs: Optional[ActivityPrefs] = None
    transportPrefs: Optional[TransportPrefs] = None
    budgetConstraints: Optional[BudgetConstraints] = None  # Numeric budget splits

    # Additional
    tripPurpose: str = "leisure"
    specialRequirements: Optional[str] = None

    class Config:
        extra = "allow"  # Accept fields we don't know about yet


# ============================================================================
# TRIP DETAILS (from the Summary Bar)
# ============================================================================

class TripDetails(BaseModel):
    """Core trip parameters from the Summary Bar."""
    origin: Optional[str] = Field(default="", description="Origin city/airport")
    destination: str = Field(..., description="Destination city/airport")
    startDate: str = Field(..., description="Departure date YYYY-MM-DD")
    endDate: str = Field(..., description="Return date YYYY-MM-DD")
    travelers: int = Field(default=1, ge=1, le=10)
    budget: Optional[float] = Field(default=None, description="Total trip budget in USD")


# ============================================================================
# CURRENT ITINERARY (user's current selections)
# ============================================================================

class CurrentItinerary(BaseModel):
    """What the user has already selected / pinned in their itinerary."""
    flight: Optional[Any] = Field(default=None)
    hotel: Optional[Any] = Field(default=None)
    restaurants: List[Any] = Field(default_factory=list)
    activities: List[Any] = Field(default_factory=list)


# ============================================================================
# TOP-LEVEL REQUEST — POST /api/trips/search
# ============================================================================

class TripSearchRequest(BaseModel):
    """
    Top-level request model for POST /api/trips/search.
    Mirrors the exact payload the frontend sends.
    """
    tripId: Optional[str] = Field(default=None)
    userRequest: str = Field(default="")
    tripDetails: TripDetails
    preferences: Optional[Preferences] = Field(default=None)
    currentItinerary: Optional[CurrentItinerary] = Field(default=None)

    # --- Helper properties ---------------------------------------------------

    @property
    def is_new_trip(self) -> bool:
        return not self.tripId

    @property
    def has_user_query(self) -> bool:
        return bool(self.userRequest and self.userRequest.strip())

    @property
    def has_selections(self) -> bool:
        if not self.currentItinerary:
            return False
        itin = self.currentItinerary
        return bool(itin.flight or itin.hotel or itin.restaurants or itin.activities)

    @property
    def preferred_airlines(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.airlines if a.preferred]

    @property
    def preferred_hotel_chains(self) -> List[str]:
        """Extract preferred hotel chain names from UI hotelChains list."""
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.hotelChains if c.preferred]

    @property
    def preferred_cuisines(self) -> List[str]:
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.cuisines if c.preferred]

    @property
    def preferred_activities(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.activities if a.preferred]

    @property
    def all_activity_names(self) -> List[str]:
        """All activity names (not just preferred), for interests list."""
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.activities]

    # --- Bridge to legacy TravelPreferences ----------------------------------

    def to_legacy_trip_request(self) -> dict:
        """
        Convert to the old TripRequest-compatible dict that feeds into
        trip_planning_service → user_proxy_agent → orchestrator.

        This bridge merges:
          - tripDetails (dates, destination, budget)
          - preferences.airlines/hotelChains/activities/cuisines (UI lists)
          - preferences.flightPrefs/hotelPrefs/etc. (detailed settings)

        into the flat structure that TravelPreferences expects.

        All fields are guaranteed non-None so downstream code
        (user_proxy_agent.get_preferences_summary) won't crash.
        """
        td = self.tripDetails
        prefs = self.preferences or Preferences()
        total = td.budget or 0

        # ── Compute trip duration for per-day/per-night splits ──────────
        num_days = 5  # fallback
        if td.startDate and td.endDate:
            from datetime import datetime
            try:
                start = datetime.strptime(td.startDate, "%Y-%m-%d")
                end = datetime.strptime(td.endDate, "%Y-%m-%d")
                num_days = max((end - start).days, 1)
            except ValueError:
                num_days = 5

        # ── Read detailed prefs with safe defaults ─────────────────────
        fp = prefs.flightPrefs or FlightPrefs()
        hp = prefs.hotelPrefs or HotelPrefs()
        ap = prefs.activityPrefs or ActivityPrefs()
        tp = prefs.transportPrefs or TransportPrefs()
        bc = prefs.budgetConstraints or BudgetConstraints()

        # ── Merge: preferred airline names into carriers list ──────────
        carriers = self.preferred_airlines
        if fp.preferredCarriers and not carriers:
            carriers = fp.preferredCarriers

        # ── Merge: all activity names into interests list ──────────────
        interests = self.all_activity_names
        if ap.interests and not interests:
            interests = ap.interests

        # ── Extract preferred hotel chains from UI list ────────────────
        # Frontend sends: hotelChains: [{name: "Marriott", preferred: true}, ...]
        # We convert to a list of dicts for the converter to extract names.
        hotel_chains = [
            {"name": c.name, "preferred": c.preferred}
            for c in prefs.hotelChains
        ]

        # ── Budget: use frontend-computed constraints if available,
        #    otherwise compute from total ───────────────────────────────
        flight_budget = bc.flightBudget if bc.flightBudget > 0 else round(total * 0.30, 2)
        hotel_per_night = bc.hotelBudgetPerNight if bc.hotelBudgetPerNight > 0 else (
            round((total * 0.35) / num_days, 2) if num_days else 0
        )
        daily_activity = bc.dailyActivityBudget if bc.dailyActivityBudget > 0 else (
            round((total * 0.15) / num_days, 2) if num_days else 0
        )
        daily_food = bc.dailyFoodBudget if bc.dailyFoodBudget > 0 else (
            round((total * 0.15) / num_days, 2) if num_days else 0
        )
        transport = bc.transportBudget if bc.transportBudget > 0 else round(total * 0.05, 2)

        return {
            "origin": td.origin or "",
            "destination": td.destination,
            "departure_date": td.startDate,
            "return_date": td.endDate,
            "num_travelers": td.travelers,
            "trip_purpose": prefs.tripPurpose or "leisure",
            "budget": {
                "total_budget": total,
                "flight_budget": flight_budget,
                "hotel_budget_per_night": hotel_per_night,
                "daily_activity_budget": daily_activity,
                "daily_food_budget": daily_food,
                "transport_budget": transport,
                "currency": "USD",
            },
            "flight_prefs": {
                "preferred_carriers": carriers,
                "max_stops": fp.maxStops,
                "cabin_class": fp.cabinClass,
                "time_preference": fp.timePreference,
                "seat_preference": fp.seatPreference,
            },
            "hotel_prefs": {
                "min_rating": hp.minRating,
                "preferred_location": hp.preferredLocation,
                "amenities": hp.amenities,
                "room_type": hp.roomType,
                "price_range": hp.priceRange,
                "preferred_chains": [
                    c.name for c in prefs.hotelChains if c.preferred
                ],
            },
            "activity_prefs": {
                "interests": interests,
                "pace": ap.pace,
                "preferred_times": ap.preferredTimes,
                "entertainment_hours_per_day": ap.entertainmentHoursPerDay,
            },
            "transport_prefs": {
                "preferred_modes": tp.preferredModes,
                "max_walk_distance": tp.maxWalkDistance,
                "comfort_level": tp.comfortLevel,
            },
            "special_requirements": self.userRequest or prefs.specialRequirements or None,
        }