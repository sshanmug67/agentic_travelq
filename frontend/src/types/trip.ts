// frontend/src/types/trip.ts
//
// Changes (v3):
//   - FlightPreferences: removed `preferredCarriers` (lives in airlines chip list)
//   - ActivityPreferences: removed `interests` (lives in activities chip list)
//   - Added comments showing where each piece of data lives
//
// Data ownership rule:
//   Chip lists (airlines, hotelChains, cuisines, activities) → names + priority
//   Detailed prefs (flightPrefs, hotelPrefs, etc.)           → settings only

// ============================================================================
// RESULT TYPES (from backend API responses)
// ============================================================================

// ── NEW: Individual hop within a leg ────────────────────────────────────

export interface SegmentDetail {
  segment_id?: string;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string;
  arrival_time: string;
  departure_terminal?: string;        // "7"
  arrival_terminal?: string;          // "1"
  duration: string;                   // "1h 30m"
  marketing_carrier: string;          // "AC"
  marketing_flight_number: string;    // "AC8899"
  operating_carrier?: string;         // "AC" or "LX"
  operating_carrier_name?: string;    // "AIR CANADA EXPRESS - JAZZ"
  aircraft_code?: string;             // "E75"
  aircraft_name?: string;             // "Embraer E175"
  cabin_class?: string;               // "ECONOMY"
  branded_fare?: string;              // "BASIC"
  fare_class?: string;                // "L"
}

// ── NEW: Amenity line item ──────────────────────────────────────────────

export interface FlightAmenity {
  description: string;                // "COMPLIMENTARY MEAL"
  is_chargeable: boolean;             // false = included free
  amenity_type: string;               // "BAGGAGE", "MEAL", "BRANDED_FARES", etc.
}


export interface Flight {
  id: string;
  airline: string;
  airline_code: string;
  is_round_trip?: boolean;
  outbound: FlightLeg;
  return_flight?: FlightLeg;
  price: number;
  currency?: string;
  cabin_class: string;
  total_duration: string;
  checked_bags?: {
    quantity: number;
    weight: number;
    weight_unit: string;
  };
  cabin_bags?: {
    quantity: number;
    weight: number;
    weight_unit: string;
  };

  // v4 additions
  branded_fare?: string;              // "BASIC", "FLEX", "STANDARD"
  amenities?: FlightAmenity[];        // merged unique amenities
  last_ticketing_date?: string;       // "2026-02-16"
  seats_remaining?: number;           // 9
  price_base?: number;                // base fare before taxes
  price_taxes?: number;               // total - base
  validating_carrier?: string;        // ticketing airline

  // Frontend-only
  ai_recommended?: boolean;
  selectedBy?: 'ai' | 'user';
  priceDifference?: number;
}



export interface FlightLeg {
  flight_number: string;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string;
  arrival_time: string;
  duration: string;
  airline?: string;
  airline_code?: string;
  stops: number;
  layovers?: string[];

  // v4 additions
  segments?: SegmentDetail[];         // per-hop breakdown
  layover_durations?: string[];       // ["8h 0m"] between hops
}

export interface Hotel {
  id: string;
  name: string;
  google_rating: number;
  user_ratings_total: number;
  address: string;
  check_in_date: string;
  check_out_date: string;
  num_nights: number;
  total_price: number;
  price_per_night: number;
  photos?: Array<{ url: string }>;
  highlights?: string[];
  ai_recommended?: boolean;
  selectedBy?: 'ai' | 'user';
  priceDifference?: number;
}

export interface Restaurant {
  id: string;
  name: string;
  rating: number;
  user_ratings_total: number;
  category: string;
  address: string;
  price_level?: string;
  photos?: Array<{ url: string }>;
  estimatedCost?: number;
}

export interface Activity {
  id: string;
  name: string;
  rating: number;
  user_ratings_total: number;
  category: string;
  address: string;
  opening_hours?: string;
  price?: string;
  photos?: Array<{ url: string }>;
  estimatedCost?: number;
}

export interface Event {
  id: string;
  name: string;
  category: string;
  description?: string;
  start_time: string;
  end_time?: string;
  venue: string;
  address: string;
  image_url?: string;
  price_range?: string;
  ticket_url?: string;
}


// ============================================================================
// AI RECOMMENDATIONS
// ============================================================================

export interface AgentRecommendation {
  recommended_id: string;
  reason: string;
  metadata?: Record<string, any>;
}

export interface AgentRecommendations {
  flight?: AgentRecommendation;
  hotel?: AgentRecommendation;
  restaurant?: AgentRecommendation;
  activity?: AgentRecommendation;
}


// ============================================================================
// API RESPONSE
// ============================================================================

export interface TripPlanResponse {
  status: string;
  trip_id: string;
  tripId?: string;
  final_recommendation: string;
  options: {
    flights: Flight[];
    hotels: Hotel[];
    restaurants: Restaurant[];
    activities: Activity[];
    weather: any[];
    [key: string]: any;
  };
  results?: {
    flights?: Flight[];
    hotels?: Hotel[];
    restaurants?: Restaurant[];
    activities?: Activity[];
    weather?: any[];
    [key: string]: any;
  };
  recommendations?: AgentRecommendations;
  summary: Record<string, number>;
  processing_time: number;
  agents_used: string[];
  message?: string;
  conversation_history?: Array<{ speaker: string; message: string }>;
}


// ============================================================================
// USER PREFERENCES — camelCase (Dashboard flow, Zustand store)
// ============================================================================
//
// Data ownership:
//   ┌───────────────────────────────────────────────────────────────────┐
//   │ Chip Lists (PreferencesPanel)     │ What they own               │
//   │ airlines[]                        │ airline names + ⭐/☆ flag    │
//   │ hotelChains[]                     │ chain names + ⭐/☆ flag      │
//   │ cuisines[]                        │ cuisine names + ⭐/☆ flag    │
//   │ activities[]                      │ activity names + ⭐/☆ flag   │
//   ├───────────────────────────────────┼─────────────────────────────┤
//   │ Detailed Prefs                    │ What they own (settings)    │
//   │ flightPrefs                       │ maxStops, cabin, time, seat │
//   │ hotelPrefs                        │ rating, location, amenities │
//   │ activityPrefs                     │ pace, times, hours/day      │
//   │ restaurantPrefs                   │ meals, priceLevel           │
//   │ transportPrefs                    │ modes, walk distance, comfort│
//   └───────────────────────────────────┴─────────────────────────────┘
//
// NO field in detailed prefs duplicates data from the chip lists.

export interface NamedPreference {
  name: string;
  preferred?: boolean;  // true = ⭐ priority, false = ☆ interested
}

export interface FlightPreferences {
  // ❌ NO preferredCarriers here — lives in airlines chip list
  maxStops: number;
  cabinClass: string;
  timePreference: string;
  seatPreference: string;
}

export interface HotelPreferences {
  minRating: number;
  preferredLocation: string;
  amenities: string[];
  roomType: string;
  priceRange: string;
}

export interface ActivityPreferences {
  // ❌ NO interests here — lives in activities chip list
  pace: string;
  preferredTimes: string[];
  accessibilityNeeds?: string;
  entertainmentHoursPerDay: number;
}

export interface RestaurantPreferences {
  // ❌ NO cuisine names here — lives in cuisines chip list
  meals: string[];         // e.g. ['lunch', 'dinner'] — which meal slots to fill
  priceLevel: string[];    // e.g. ['moderate', 'upscale'] — maps to Google price_level
}

export interface TransportPreferences {
  preferredModes: string[];
  maxWalkDistance: number;
  comfortLevel: string;
}

export interface BudgetConstraints {
  totalBudget: number;
  flightBudget: number;
  hotelBudgetPerNight: number;
  dailyActivityBudget: number;
  dailyFoodBudget: number;
  transportBudget: number;
}

export interface BudgetTiers {
  meals: string;
  accommodation: string;
  activities: string;
}

export interface UserPreferences {
  // ── Chip Lists (PreferencesPanel) — owns NAMES + PRIORITY ─────────────
  airlines: NamedPreference[];
  hotelChains: NamedPreference[];
  cuisines: NamedPreference[];
  activities: NamedPreference[];
  budget: BudgetTiers;

  // ── Detailed Preferences — owns SETTINGS ONLY, no name lists ──────────
  flightPrefs: FlightPreferences;
  hotelPrefs: HotelPreferences;
  activityPrefs: ActivityPreferences;
  restaurantPrefs: RestaurantPreferences;
  transportPrefs: TransportPreferences;
  budgetConstraints: BudgetConstraints;

  // ── Additional ────────────────────────────────────────────────────────
  tripPurpose: string;
  specialRequirements?: string;
}


// ============================================================================
// LEGACY TYPES — snake_case (TripSearchForm, direct backend payloads)
// ============================================================================

export type TripPreset = 'default' | 'budget' | 'luxury' | 'business';

export interface LegacyFlightPrefs {
  preferred_carriers?: string[];
  max_stops: number;
  cabin_class: string;
  time_preference: string;
  seat_preference?: string;
}

export interface LegacyHotelPrefs {
  min_rating: number;
  preferred_location: string;
  amenities?: string[];
  room_type?: string;
  price_range?: string;
}

export interface LegacyActivityPrefs {
  interests: string[];
  pace: string;
  entertainment_hours_per_day: number;
  preferred_times?: string[];
}

export interface LegacyBudget {
  total_budget: number;
  flight_budget: number;
  hotel_budget_per_night: number;
  daily_activity_budget?: number;
  daily_food_budget?: number;
  transport_budget?: number;
  currency?: string;
}

export interface TripRequest {
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string;
  num_travelers: number;
  trip_purpose: string;
  flight_prefs: LegacyFlightPrefs;
  hotel_prefs: LegacyHotelPrefs;
  activity_prefs: LegacyActivityPrefs;
  transport_prefs: any;
  budget: LegacyBudget;
}

export const TRIP_PRESETS: Array<{ id: TripPreset; name: string; description: string }> = [
  { id: 'default', name: 'Balanced', description: 'Good mix of comfort & value' },
  { id: 'budget', name: 'Budget', description: 'Maximum savings' },
  { id: 'luxury', name: 'Luxury', description: 'Premium everything' },
  { id: 'business', name: 'Business', description: 'Efficient & professional' },
];

export function getDefaultFlightPrefs(_preset: TripPreset): LegacyFlightPrefs {
  return { max_stops: 1, cabin_class: 'economy', time_preference: 'flexible' };
}

export function getDefaultHotelPrefs(_preset: TripPreset): LegacyHotelPrefs {
  return { min_rating: 3.5, preferred_location: 'city_center' };
}

export function getDefaultActivityPrefs(_preset: TripPreset): LegacyActivityPrefs {
  return { interests: [], pace: 'moderate', entertainment_hours_per_day: 6 };
}

export function getDefaultBudget(_preset: TripPreset, _days?: number): LegacyBudget {
  return { total_budget: 4000, flight_budget: 1200, hotel_budget_per_night: 280 };
}