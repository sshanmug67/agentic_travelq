// frontend/src/types/trip.ts

// ============================================================================
// RESULT TYPES (from backend API responses)
// ============================================================================

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

export interface NamedPreference {
  name: string;
  preferred?: boolean;
}

export interface FlightPreferences {
  preferredCarriers: string[];
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
  interests: string[];
  pace: string;
  preferredTimes: string[];
  accessibilityNeeds?: string;
  entertainmentHoursPerDay: number;
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
  // ── UI Preferences (PreferencesPanel) ──────────────────────────────────
  airlines: NamedPreference[];
  hotelChains: NamedPreference[];
  cuisines: NamedPreference[];
  activities: NamedPreference[];
  budget: BudgetTiers;               // ← "budget" — matches useTripData store

  // ── Detailed Preferences ───────────────────────────────────────────────
  flightPrefs: FlightPreferences;
  hotelPrefs: HotelPreferences;
  activityPrefs: ActivityPreferences;
  transportPrefs: TransportPreferences;
  budgetConstraints: BudgetConstraints;

  // ── Additional ─────────────────────────────────────────────────────────
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