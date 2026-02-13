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

Changes (v4):
  - Data ownership rule: chip lists own names, detailed prefs own settings
  - FlightPrefs: removed preferredCarriers (lives in airlines chip list)
  - ActivityPrefs: removed interests (lives in activities chip list)
  - RestaurantPrefs: meals + priceLevel (cuisine names live in cuisines chip list)
  - to_request_dict(): reads names from chip lists ONLY, no fallbacks
  - Passes priority vs interested split for all categories
  - cuisine_prefs includes meals + price_level from RestaurantPrefs settings
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any


# ============================================================================
# PREFERENCES — Matches frontend UserPreferences type
# ============================================================================

class NamedPreference(BaseModel):
    """A single named preference with a preferred flag.

    Semantics (set by PreferencesPanel UI):
      - In list + preferred=True  → ⭐ Priority: agents search harder for these
      - In list + preferred=False → ☆ Interested: include if available
      - Not in list               → Not sent: user doesn't care
    """
    name: str
    preferred: bool = False


class BudgetTiers(BaseModel):
    """Budget tier display strings from the PreferencesPanel UI."""
    meals: Optional[str] = None
    accommodation: Optional[str] = None
    activities: Optional[str] = None


class FlightPrefs(BaseModel):
    """Flight settings only — carrier names live in airlines chip list.

    ❌ No preferredCarriers here (was duplicate of airlines[].name)
    """
    maxStops: int = 1
    cabinClass: str = "economy"
    timePreference: str = "flexible"
    seatPreference: str = "window"


class HotelPrefs(BaseModel):
    """Hotel settings only — chain names live in hotelChains chip list."""
    minRating: float = 3.5
    preferredLocation: str = "city_center"
    amenities: List[str] = Field(default_factory=lambda: ["wifi", "breakfast"])
    roomType: str = "standard"
    priceRange: str = "moderate"


class ActivityPrefs(BaseModel):
    """Activity settings only — interest names live in activities chip list.

    ❌ No interests here (was duplicate of activities[].name)
    """
    pace: str = "moderate"
    preferredTimes: List[str] = Field(default_factory=lambda: ["morning", "afternoon"])
    accessibilityNeeds: Optional[str] = None
    entertainmentHoursPerDay: int = 6


class RestaurantPrefs(BaseModel):
    """Restaurant settings only — cuisine names live in cuisines chip list.

    ❌ No cuisine names here (those live in cuisines[].name)
    """
    meals: List[str] = Field(default_factory=lambda: ["lunch", "dinner"])
    priceLevel: List[str] = Field(default_factory=lambda: ["moderate"])


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

    Data ownership:
      Chip lists (airlines, hotelChains, cuisines, activities)
        → Own NAMES + ⭐/☆ priority flags
      Detailed prefs (flightPrefs, hotelPrefs, activityPrefs, restaurantPrefs, transportPrefs)
        → Own SETTINGS ONLY (maxStops, pace, amenities, meals, priceLevel, etc.)
        → NO duplicate name lists

    Every field has defaults so partial payloads are fine.
    """
    # ── Chip Lists — own NAMES + PRIORITY ────────────────────────────────
    airlines: List[NamedPreference] = Field(default_factory=list)
    hotelChains: List[NamedPreference] = Field(default_factory=list)
    cuisines: List[NamedPreference] = Field(default_factory=list)
    activities: List[NamedPreference] = Field(default_factory=list)
    budget: Optional[BudgetTiers] = None

    # ── Detailed Prefs — own SETTINGS ONLY ───────────────────────────────
    flightPrefs: Optional[FlightPrefs] = None
    hotelPrefs: Optional[HotelPrefs] = None
    activityPrefs: Optional[ActivityPrefs] = None
    restaurantPrefs: Optional[RestaurantPrefs] = None
    transportPrefs: Optional[TransportPrefs] = None
    budgetConstraints: Optional[BudgetConstraints] = None

    # ── Additional ───────────────────────────────────────────────────────
    tripPurpose: str = "leisure"
    specialRequirements: Optional[str] = None

    class Config:
        extra = "allow"


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

    # ── Helper properties ────────────────────────────────────────────────

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

    # ── Chip list extractors (⭐ priority vs ☆ interested) ───────────────

    @property
    def preferred_airlines(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.airlines if a.preferred]

    @property
    def interested_airlines(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.airlines if not a.preferred]

    @property
    def all_airline_names(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.airlines]

    @property
    def preferred_hotel_chains(self) -> List[str]:
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.hotelChains if c.preferred]

    @property
    def interested_hotel_chains(self) -> List[str]:
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.hotelChains if not c.preferred]

    @property
    def preferred_cuisines(self) -> List[str]:
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.cuisines if c.preferred]

    @property
    def interested_cuisines(self) -> List[str]:
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.cuisines if not c.preferred]

    @property
    def all_cuisine_names(self) -> List[str]:
        if not self.preferences:
            return []
        return [c.name for c in self.preferences.cuisines]

    @property
    def preferred_activities(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.activities if a.preferred]

    @property
    def interested_activities(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.activities if not a.preferred]

    @property
    def all_activity_names(self) -> List[str]:
        if not self.preferences:
            return []
        return [a.name for a in self.preferences.activities]

    # ── Convert to search dict ───────────────────────────────────────────

    def to_request_dict(self) -> dict:
        """
        Convert frontend camelCase payload to snake_case dict for the
        request converter and planning service.

        Data sources (no duplication):
          Names      → from chip lists ONLY (airlines, hotelChains, cuisines, activities)
          Settings   → from detailed prefs ONLY (flightPrefs, hotelPrefs, etc.)
          Budget     → from budgetConstraints or computed from total

        Each category carries two name lists for agents to weight:
          preferred_*   → ⭐ starred items  → search harder, rank higher
          interested_*  → ☆ unstarred items → include but lower weight
        """
        td = self.tripDetails
        prefs = self.preferences or Preferences()
        total = td.budget or 0

        # ── Compute trip duration ───────────────────────────────────────
        num_days = 5  # fallback
        if td.startDate and td.endDate:
            from datetime import datetime
            try:
                start = datetime.strptime(td.startDate, "%Y-%m-%d")
                end = datetime.strptime(td.endDate, "%Y-%m-%d")
                num_days = max((end - start).days, 1)
            except ValueError:
                num_days = 5

        # ── Settings from detailed prefs (no name lists here) ──────────
        fp = prefs.flightPrefs or FlightPrefs()
        hp = prefs.hotelPrefs or HotelPrefs()
        ap = prefs.activityPrefs or ActivityPrefs()
        rp = prefs.restaurantPrefs or RestaurantPrefs()
        tp = prefs.transportPrefs or TransportPrefs()
        bc = prefs.budgetConstraints or BudgetConstraints()

        # ── Names from chip lists ONLY ─────────────────────────────────
        priority_carriers = self.preferred_airlines
        interested_carriers = self.interested_airlines

        priority_chains = self.preferred_hotel_chains
        interested_chains = self.interested_hotel_chains

        priority_interests = self.preferred_activities
        interested_interests = self.interested_activities

        priority_cuisines = self.preferred_cuisines
        interested_cuisines = self.interested_cuisines

        # ── Budget ─────────────────────────────────────────────────────
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
                "preferred_carriers": priority_carriers,       # ⭐ from chip list
                "interested_carriers": interested_carriers,    # ☆ from chip list
                "max_stops": fp.maxStops,                      # from settings
                "cabin_class": fp.cabinClass,
                "time_preference": fp.timePreference,
                "seat_preference": fp.seatPreference,
            },
            "hotel_prefs": {
                "preferred_chains": priority_chains,           # ⭐ from chip list
                "interested_chains": interested_chains,        # ☆ from chip list
                "min_rating": hp.minRating,                    # from settings
                "preferred_location": hp.preferredLocation,
                "amenities": hp.amenities,
                "room_type": hp.roomType,
                "price_range": hp.priceRange,
            },
            "activity_prefs": {
                "preferred_interests": priority_interests,     # ⭐ from chip list
                "interested_interests": interested_interests,  # ☆ from chip list
                "pace": ap.pace,                               # from settings
                "preferred_times": ap.preferredTimes,
                "entertainment_hours_per_day": ap.entertainmentHoursPerDay,
            },
            "cuisine_prefs": {
                "preferred_cuisines": priority_cuisines,        # ⭐ from chip list
                "interested_cuisines": interested_cuisines,     # ☆ from chip list
                "meals": rp.meals,                              # from settings
                "price_level": rp.priceLevel,                   # from settings
            },
            "transport_prefs": {
                "preferred_modes": tp.preferredModes,
                "max_walk_distance": tp.maxWalkDistance,
                "comfort_level": tp.comfortLevel,
            },
            "special_requirements": self.userRequest or prefs.specialRequirements or None,
        }