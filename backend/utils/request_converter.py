"""
Request Converter - Converts frontend TripRequest to backend TravelPreferences
Location: backend/utils/request_converter.py

Uses logging_config.py for consistent logging to travel_dashboard_*.log files.

Changes (v2):
  - Fixed: preferred_chains now extracted from frontend hotelChains payload
    Frontend sends: hotelChains: [{name: "Marriott", preferred: true}, ...]
    Converter now filters preferred=true and passes names to HotelPreferences
  - Added: Detailed logging of all hotel preferences used in search
"""
from typing import Dict, Any, Tuple, List
from datetime import datetime

from models.user_preferences import (
    TravelPreferences,
    FlightPreferences,
    HotelPreferences,
    ActivityPreferences,
    TransportPreferences,
    BudgetConstraints
)
from utils.logging_config import log_info_raw, log_error_raw, log_warning_raw, log_json_raw


def _extract_preferred_chains(request_data: Dict[str, Any]) -> List[str]:
    """
    Extract preferred hotel chain names from frontend hotelChains payload.
    
    Frontend sends:
        hotelChains: [
            {name: "Marriott", preferred: true},
            {name: "Hilton", preferred: false}
        ]
    
    Returns: ["Marriott"]  (only chains with preferred=true)
    """
    hotel_chains = request_data.get('hotel_chains', [])
    
    if not hotel_chains:
        return []
    
    preferred = [
        chain.get('name', '')
        for chain in hotel_chains
        if isinstance(chain, dict) and chain.get('preferred', False)
    ]
    
    # Filter out empty names
    preferred = [name for name in preferred if name]
    
    if preferred:
        log_info_raw(f"   🏷️  Preferred hotel chains: {', '.join(preferred)}")
    else:
        all_chains = [c.get('name', '') for c in hotel_chains if isinstance(c, dict)]
        log_info_raw(f"   ℹ️  Hotel chains present ({', '.join(all_chains)}) but none marked preferred")
    
    return preferred


def convert_trip_request_to_preferences(request_data: Dict[str, Any]) -> TravelPreferences:
    """
    Convert frontend TripRequest to backend TravelPreferences
    
    Args:
        request_data: Dictionary from frontend TripRequest
        
    Returns:
        TravelPreferences object for use with agents
        
    Raises:
        ValueError: If request data is invalid
    """
    log_info_raw("🔄 Converting frontend request to TravelPreferences...")
    
    try:
        # Extract flight preferences
        flight_data = request_data.get('flight_prefs', {})
        log_info_raw(f"   ✓ Flight preferences: {flight_data.get('cabin_class', 'economy')}, max stops: {flight_data.get('max_stops', 1)}")
        
        flight_prefs = FlightPreferences(
            preferred_carriers=flight_data.get('preferred_carriers', []),
            max_stops=flight_data.get('max_stops', 1),
            cabin_class=flight_data.get('cabin_class', 'economy'),
            time_preference=flight_data.get('time_preference', 'flexible'),
            seat_preference=flight_data.get('seat_preference')
        )
        
        # Extract hotel preferences
        hotel_data = request_data.get('hotel_prefs', {})
        
        # preferred_chains lives inside hotel_prefs (embedded by to_legacy_trip_request)
        preferred_chains = hotel_data.get('preferred_chains', [])
        if preferred_chains:
            log_info_raw(f"   🏷️  Preferred hotel chains: {', '.join(preferred_chains)}")
        else:
            log_info_raw(f"   ℹ️  No preferred hotel chains specified")
        
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
        )
        
        # Log ALL hotel preferences that will be used in search
        log_json_raw({
            "min_rating": hotel_prefs.min_rating,
            "preferred_location": hotel_prefs.preferred_location,
            "amenities": hotel_prefs.amenities,
            "room_type": hotel_prefs.room_type,
            "price_range": hotel_prefs.price_range,
            "preferred_chains": hotel_prefs.preferred_chains,
        }, label="🏨 Hotel Preferences for Search", include_borders=False)
        
        # Extract activity preferences
        activity_data = request_data.get('activity_prefs', {})
        interests = activity_data.get('interests', [])
        log_info_raw(f"   ✓ Activity preferences: {activity_data.get('pace', 'moderate')} pace, {len(interests)} interests")
        
        activity_prefs = ActivityPreferences(
            interests=interests,
            pace=activity_data.get('pace', 'moderate'),
            preferred_times=activity_data.get('preferred_times', ['morning', 'afternoon']),
            entertainment_hours_per_day=activity_data.get('entertainment_hours_per_day', 6),
            accessibility_needs=activity_data.get('accessibility_needs')
        )
        
        # Extract transport preferences
        transport_data = request_data.get('transport_prefs', {})
        log_info_raw(f"   ✓ Transport preferences: {transport_data.get('comfort_level', 'moderate')} comfort")
        
        transport_prefs = TransportPreferences(
            preferred_modes=transport_data.get('preferred_modes', ['metro', 'walk']),
            max_walk_distance=transport_data.get('max_walk_distance', 1.0),
            comfort_level=transport_data.get('comfort_level', 'moderate')
        )
        
        # Extract budget
        budget_data = request_data.get('budget', {})
        total_budget = budget_data.get('total_budget', 5000.0)
        log_info_raw(f"   ✓ Budget: ${total_budget:,.2f}")
        
        budget = BudgetConstraints(
            total_budget=total_budget,
            flight_budget=budget_data.get('flight_budget'),
            hotel_budget_per_night=budget_data.get('hotel_budget_per_night'),
            daily_activity_budget=budget_data.get('daily_activity_budget'),
            daily_food_budget=budget_data.get('daily_food_budget'),
            transport_budget=budget_data.get('transport_budget')
        )
        
        # Create TravelPreferences object
        preferences = TravelPreferences(
            destination=request_data.get('destination', ''),
            origin=request_data.get('origin', ''),
            departure_date=request_data.get('departure_date', ''),
            return_date=request_data.get('return_date', ''),
            num_travelers=request_data.get('num_travelers', 1),
            flight_prefs=flight_prefs,
            hotel_prefs=hotel_prefs,
            activity_prefs=activity_prefs,
            transport_prefs=transport_prefs,
            budget=budget,
            special_requirements=request_data.get('special_requirements'),
            trip_purpose=request_data.get('trip_purpose', 'leisure')
        )
        
        # Log the converted preferences summary
        log_json_raw({
            "destination": preferences.destination,
            "origin": preferences.origin,
            "dates": f"{preferences.departure_date} to {preferences.return_date}",
            "travelers": preferences.num_travelers,
            "budget": preferences.budget.total_budget,
            "hotel_budget_per_night": preferences.budget.hotel_budget_per_night,
            "interests": preferences.activity_prefs.interests,
            "cabin_class": preferences.flight_prefs.cabin_class,
            "hotel_rating": preferences.hotel_prefs.min_rating,
            "hotel_chains": preferences.hotel_prefs.preferred_chains,
            "hotel_location": preferences.hotel_prefs.preferred_location,
            "hotel_amenities": preferences.hotel_prefs.amenities,
            "pace": preferences.activity_prefs.pace
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
        
        # Check if dates are in the future
        if dep_date.date() < datetime.now().date():
            error_msg = "Departure date must be in the future"
            log_warning_raw(f"⚠️  Warning: {error_msg}")
            # Don't fail validation, just warn (useful for testing with past dates)
            
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