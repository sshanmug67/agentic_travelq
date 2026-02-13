"""
Request Converter - Converts frontend TripRequest to backend TravelPreferences
Location: backend/utils/request_converter.py

Uses logging_config.py for consistent logging to travel_dashboard_*.log files.

Changes (v4):
  - FlightPreferences: populates preferred_carriers + interested_carriers
  - HotelPreferences: populates preferred_chains + interested_chains
  - ActivityPreferences: populates preferred_interests (⭐) + interested_interests (☆)
  - RestaurantPreferences: populates preferred_cuisines (⭐) + interested_cuisines (☆) + meals + price_level
  - Consistent structure: every category uses preferred/interested split, no redundant "all" lists
"""
from typing import Dict, Any, Tuple, List
from datetime import datetime

from models.user_preferences import (
    TravelPreferences,
    FlightPreferences,
    HotelPreferences,
    ActivityPreferences,
    RestaurantPreferences,
    TransportPreferences,
    BudgetConstraints
)
from utils.logging_config import log_info_raw, log_error_raw, log_warning_raw, log_json_raw


def convert_trip_request_to_preferences(request_data: Dict[str, Any]) -> TravelPreferences:
    """
    Convert frontend TripRequest (legacy dict) to backend TravelPreferences.

    The input dict comes from TripSearchRequest.to_legacy_trip_request() which
    has already split chip-list names into preferred/interested tiers and
    merged settings from detailed prefs.

    Args:
        request_data: Dictionary from to_legacy_trip_request()

    Returns:
        TravelPreferences object for use with agents

    Raises:
        ValueError: If request data is invalid
    """
    log_info_raw("🔄 Converting frontend request to TravelPreferences...")

    try:
        # ── Flight Preferences ─────────────────────────────────────────
        flight_data = request_data.get('flight_prefs', {})
        preferred_carriers = flight_data.get('preferred_carriers', [])
        interested_carriers = flight_data.get('interested_carriers', [])

        log_info_raw(f"   ✓ Flight preferences: {flight_data.get('cabin_class', 'economy')}, "
                     f"max stops: {flight_data.get('max_stops', 1)}")
        if preferred_carriers:
            log_info_raw(f"   ⭐ Priority airlines: {', '.join(preferred_carriers)}")
        if interested_carriers:
            log_info_raw(f"   ☆ Interested airlines: {', '.join(interested_carriers)}")

        flight_prefs = FlightPreferences(
            preferred_carriers=preferred_carriers,
            interested_carriers=interested_carriers,
            max_stops=flight_data.get('max_stops', 1),
            cabin_class=flight_data.get('cabin_class', 'economy'),
            time_preference=flight_data.get('time_preference', 'flexible'),
            seat_preference=flight_data.get('seat_preference'),
        )

        # ── Hotel Preferences ──────────────────────────────────────────
        hotel_data = request_data.get('hotel_prefs', {})
        preferred_chains = hotel_data.get('preferred_chains', [])
        interested_chains = hotel_data.get('interested_chains', [])

        if preferred_chains:
            log_info_raw(f"   ⭐ Priority hotel chains: {', '.join(preferred_chains)}")
        if interested_chains:
            log_info_raw(f"   ☆ Interested hotel chains: {', '.join(interested_chains)}")

        log_info_raw(f"   ✓ Hotel preferences: {hotel_data.get('min_rating', 4.0)} stars, "
                     f"{hotel_data.get('price_range', 'moderate')}, "
                     f"location: {hotel_data.get('preferred_location', 'city_center')}")

        hotel_prefs = HotelPreferences(
            min_rating=hotel_data.get('min_rating', 4.0),
            preferred_location=hotel_data.get('preferred_location', 'city_center'),
            amenities=hotel_data.get('amenities', ['wifi']),
            room_type=hotel_data.get('room_type', 'standard'),
            price_range=hotel_data.get('price_range', 'moderate'),
            preferred_chains=preferred_chains,
            interested_chains=interested_chains,
        )

        log_json_raw({
            "min_rating": hotel_prefs.min_rating,
            "preferred_location": hotel_prefs.preferred_location,
            "amenities": hotel_prefs.amenities,
            "room_type": hotel_prefs.room_type,
            "price_range": hotel_prefs.price_range,
            "preferred_chains": hotel_prefs.preferred_chains,
            "interested_chains": hotel_prefs.interested_chains,
        }, label="🏨 Hotel Preferences for Search", include_borders=False)

        # ── Activity Preferences ───────────────────────────────────────
        activity_data = request_data.get('activity_prefs', {})
        preferred_interests = activity_data.get('preferred_interests', [])
        interested_interests = activity_data.get('interested_interests', [])

        log_info_raw(f"   ✓ Activity preferences: {activity_data.get('pace', 'moderate')} pace, "
                     f"{len(preferred_interests)} priority, {len(interested_interests)} interested")
        if preferred_interests:
            log_info_raw(f"   ⭐ Priority activities: {', '.join(preferred_interests)}")
        if interested_interests:
            log_info_raw(f"   ☆ Interested activities: {', '.join(interested_interests)}")

        activity_prefs = ActivityPreferences(
            preferred_interests=preferred_interests,
            interested_interests=interested_interests,
            pace=activity_data.get('pace', 'moderate'),
            preferred_times=activity_data.get('preferred_times', ['morning', 'afternoon']),
            entertainment_hours_per_day=activity_data.get('entertainment_hours_per_day', 6),
            accessibility_needs=activity_data.get('accessibility_needs'),
        )

        # ── Restaurant Preferences ─────────────────────────────────────
        cuisine_data = request_data.get('cuisine_prefs', {})
        preferred_cuisines = cuisine_data.get('preferred_cuisines', [])
        interested_cuisines = cuisine_data.get('interested_cuisines', [])
        meals = cuisine_data.get('meals', ['lunch', 'dinner'])
        price_level = cuisine_data.get('price_level', ['moderate'])

        log_info_raw(f"   ✓ Restaurant preferences: "
                     f"{len(preferred_cuisines)} priority, {len(interested_cuisines)} interested, "
                     f"meals: {', '.join(meals)}, price: {', '.join(price_level)}")
        if preferred_cuisines:
            log_info_raw(f"   ⭐ Priority cuisines: {', '.join(preferred_cuisines)}")
        if interested_cuisines:
            log_info_raw(f"   ☆ Interested cuisines: {', '.join(interested_cuisines)}")

        restaurant_prefs = RestaurantPreferences(
            preferred_cuisines=preferred_cuisines,
            interested_cuisines=interested_cuisines,
            meals=meals,
            price_level=price_level,
        )

        log_json_raw({
            "preferred_cuisines": restaurant_prefs.preferred_cuisines,
            "interested_cuisines": restaurant_prefs.interested_cuisines,
            "meals": restaurant_prefs.meals,
            "price_level": restaurant_prefs.price_level,
        }, label="🍽️ Restaurant Preferences for Search", include_borders=False)

        # ── Transport Preferences ──────────────────────────────────────
        transport_data = request_data.get('transport_prefs', {})
        log_info_raw(f"   ✓ Transport preferences: {transport_data.get('comfort_level', 'moderate')} comfort")

        transport_prefs = TransportPreferences(
            preferred_modes=transport_data.get('preferred_modes', ['metro', 'walk']),
            max_walk_distance=transport_data.get('max_walk_distance', 1.0),
            comfort_level=transport_data.get('comfort_level', 'moderate'),
        )

        # ── Budget ─────────────────────────────────────────────────────
        budget_data = request_data.get('budget', {})
        total_budget = budget_data.get('total_budget', 5000.0)
        log_info_raw(f"   ✓ Budget: ${total_budget:,.2f}")

        budget = BudgetConstraints(
            total_budget=total_budget,
            flight_budget=budget_data.get('flight_budget'),
            hotel_budget_per_night=budget_data.get('hotel_budget_per_night'),
            daily_activity_budget=budget_data.get('daily_activity_budget'),
            daily_food_budget=budget_data.get('daily_food_budget'),
            transport_budget=budget_data.get('transport_budget'),
        )

        # ── Build TravelPreferences ────────────────────────────────────
        preferences = TravelPreferences(
            destination=request_data.get('destination', ''),
            origin=request_data.get('origin', ''),
            departure_date=request_data.get('departure_date', ''),
            return_date=request_data.get('return_date', ''),
            num_travelers=request_data.get('num_travelers', 1),
            flight_prefs=flight_prefs,
            hotel_prefs=hotel_prefs,
            activity_prefs=activity_prefs,
            restaurant_prefs=restaurant_prefs,
            transport_prefs=transport_prefs,
            budget=budget,
            special_requirements=request_data.get('special_requirements'),
            trip_purpose=request_data.get('trip_purpose', 'leisure'),
        )

        # ── Summary Log ────────────────────────────────────────────────
        log_json_raw({
            "destination": preferences.destination,
            "origin": preferences.origin,
            "dates": f"{preferences.departure_date} to {preferences.return_date}",
            "travelers": preferences.num_travelers,
            "budget": preferences.budget.total_budget,
            "hotel_budget_per_night": preferences.budget.hotel_budget_per_night,
            "preferred_interests": preferences.activity_prefs.preferred_interests,
            "interested_interests": preferences.activity_prefs.interested_interests,
            "preferred_cuisines": preferences.restaurant_prefs.preferred_cuisines,
            "interested_cuisines": preferences.restaurant_prefs.interested_cuisines,
            "meals": preferences.restaurant_prefs.meals,
            "price_level": preferences.restaurant_prefs.price_level,
            "cabin_class": preferences.flight_prefs.cabin_class,
            "hotel_rating": preferences.hotel_prefs.min_rating,
            "hotel_chains": preferences.hotel_prefs.preferred_chains,
            "hotel_location": preferences.hotel_prefs.preferred_location,
            "hotel_amenities": preferences.hotel_prefs.amenities,
            "pace": preferences.activity_prefs.pace,
        }, label="✅ Converted Preferences Summary", include_borders=False)

        log_info_raw("✅ Conversion completed successfully")

        return preferences

    except KeyError as e:
        log_error_raw(f"❌ Missing required field during conversion: {str(e)}")
        raise ValueError(f"Missing required field: {str(e)}")

    except Exception as e:
        log_error_raw(f"❌ Error converting request: {str(e)}")
        import traceback
        log_error_raw(traceback.format_exc())
        raise ValueError(f"Invalid request data: {str(e)}")


def validate_trip_request(request_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate trip request data

    Args:
        request_data: Request dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    log_info_raw("🔍 Validating trip request...")

    # Required fields
    required = ['origin', 'destination', 'departure_date', 'return_date']

    for field in required:
        if not request_data.get(field):
            error_msg = f"Missing required field: {field}"
            log_error_raw(f"❌ Validation failed: {error_msg}")
            return False, error_msg

    # Validate dates
    try:
        dep_date = datetime.fromisoformat(request_data['departure_date'])
        ret_date = datetime.fromisoformat(request_data['return_date'])

        if ret_date <= dep_date:
            error_msg = "Return date must be after departure date"
            log_error_raw(f"❌ Validation failed: {error_msg}")
            return False, error_msg

        if dep_date.date() < datetime.now().date():
            error_msg = "Departure date must be in the future"
            log_warning_raw(f"⚠️  Warning: {error_msg}")

    except ValueError as e:
        error_msg = f"Invalid date format: {str(e)}"
        log_error_raw(f"❌ Validation failed: {error_msg}")
        return False, error_msg

    # Validate num_travelers
    num_travelers = request_data.get('num_travelers', 1)
    if not isinstance(num_travelers, int) or num_travelers < 1 or num_travelers > 10:
        error_msg = "Number of travelers must be between 1 and 10"
        log_error_raw(f"❌ Validation failed: {error_msg}")
        return False, error_msg

    # Validate budget if provided
    if 'budget' in request_data:
        budget = request_data['budget']
        if 'total_budget' in budget and budget['total_budget'] <= 0:
            error_msg = "Total budget must be positive"
            log_error_raw(f"❌ Validation failed: {error_msg}")
            return False, error_msg

    log_info_raw("✅ Validation passed")
    log_json_raw({
        "origin": request_data['origin'],
        "destination": request_data['destination'],
        "departure": request_data['departure_date'],
        "return": request_data['return_date'],
        "travelers": num_travelers,
        "status": "valid"
    }, label="Validation Results", include_borders=False)

    return True, ""