// frontend/src/types/trip.ts

// ============================================================================
// RESULT TYPES (from backend API responses)
// ============================================================================

export interface Flight {
  id: string;
  airline: string;
  outbound: FlightLeg;
  return_flight?: FlightLeg;
  price: number;
  cabin_class: string;
  total_duration: string;
  cabin_bags?: {
    quantity: number;
    weight: string;
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


// ============================================================================
// AI RECOMMENDATIONS — Structured agent picks from backend
// ============================================================================

/**
 * A single agent's top-pick recommendation for a category.
 * Stored by each agent via trip_storage.store_recommendation().
 */
export interface AgentRecommendation {
  recommended_id: string;
  reason: string;
  metadata?: Record<string, any>;
}

/**
 * All agent recommendations keyed by category.
 * Returned by the orchestrator in the API response.
 */
export interface AgentRecommendations {
  flight?: AgentRecommendation;
  hotel?: AgentRecommendation;
  restaurant?: AgentRecommendation;
  activity?: AgentRecommendation;
}


// ============================================================================
// API RESPONSE — What POST /api/trips/search returns
// ============================================================================

/**
 * Response from the trip planning backend.
 * Maps to backend TripResponse (models/trip.py).
 *
 * Supports both snake_case (trip_id, final_recommendation) from Python
 * and optional camelCase aliases (tripId) in case a serializer converts them.
 */
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
// USER PREFERENCES — Matches backend user_preferences.py
// ============================================================================

/**
 * Simple named preference with preferred flag.
 * Used in the PreferencesPanel UI for airlines, hotels, cuisines, activities.
 */
export interface NamedPreference {
  name: string;
  preferred?: boolean;
}

/**
 * Flight search preferences.
 * Maps to backend: FlightPreferences in user_preferences.py
 */
export interface FlightPreferences {
  preferredCarriers: string[];     // Populated from airlines NamedPreference list
  maxStops: number;                // 0 = direct only, 1, 2
  cabinClass: string;              // economy, premium_economy, business, first
  timePreference: string;          // morning, afternoon, evening, night, flexible
  seatPreference: string;          // window, aisle, middle
}

/**
 * Hotel search preferences.
 * Maps to backend: HotelPreferences in user_preferences.py
 */
export interface HotelPreferences {
  minRating: number;               // 1-5 stars
  preferredLocation: string;       // city_center, near_attractions, quiet_area
  amenities: string[];             // wifi, breakfast, gym, pool, spa, etc.
  roomType: string;                // standard, deluxe, suite
  priceRange: string;              // budget, moderate, luxury
}

/**
 * Activity search preferences.
 * Maps to backend: ActivityPreferences in user_preferences.py
 */
export interface ActivityPreferences {
  interests: string[];             // Populated from activities NamedPreference list
  pace: string;                    // relaxed, moderate, fast-paced
  preferredTimes: string[];        // morning, afternoon, evening
  accessibilityNeeds?: string;
  entertainmentHoursPerDay: number; // 2-12
}

/**
 * Local transport preferences.
 * Maps to backend: TransportPreferences in user_preferences.py
 */
export interface TransportPreferences {
  preferredModes: string[];        // metro, bus, cab, walk, bike
  maxWalkDistance: number;          // miles
  comfortLevel: string;            // budget, moderate, premium
}

/**
 * Budget constraints — detailed per-category budgets.
 * Maps to backend: BudgetConstraints in user_preferences.py
 */
export interface BudgetConstraints {
  totalBudget: number;
  flightBudget: number;
  hotelBudgetPerNight: number;
  dailyActivityBudget: number;
  dailyFoodBudget: number;
  transportBudget: number;
}

/**
 * Budget tier labels used in the PreferencesPanel UI.
 * These are display strings, not numeric values.
 */
export interface BudgetTiers {
  meals: string;                   // "$ (Budget)", "$$ (Mid-range)", "$$$ (Fine dining)"
  accommodation: string;
  activities: string;
}


// ============================================================================
// COMBINED PREFERENCES — What lives in the Zustand store
// ============================================================================

/**
 * Complete user preferences combining:
 *   1. UI preferences (named lists the user can add/remove/star in PreferencesPanel)
 *   2. Detailed preferences (structured settings, initially from defaults)
 *
 * The UI preferences (airlines, hotelChains, cuisines, activities, budgetTiers)
 * are what the user interacts with in the PreferencesPanel.
 *
 * The detailed preferences (flightPrefs, hotelPrefs, etc.) hold the full
 * settings that match the backend. They're initialized with sensible defaults
 * and will eventually come from a user profile DB.
 *
 * When sending to the backend, the bridge merges them:
 *   - airlines[].name where preferred → flightPrefs.preferredCarriers
 *   - activities[].name where preferred → activityPrefs.interests
 *   - etc.
 */
export interface UserPreferences {
  // ── UI Preferences (PreferencesPanel) ──────────────────────────────────
  airlines: NamedPreference[];
  hotelChains: NamedPreference[];
  cuisines: NamedPreference[];
  activities: NamedPreference[];
  budget: BudgetTiers;             // Named "budget" to match PreferencesPanel's interface

  // ── Detailed Preferences (defaults until user changes them) ────────────
  flightPrefs: FlightPreferences;
  hotelPrefs: HotelPreferences;
  activityPrefs: ActivityPreferences;
  transportPrefs: TransportPreferences;
  budgetConstraints: BudgetConstraints;

  // ── Additional ─────────────────────────────────────────────────────────
  tripPurpose: string;             // leisure, business, adventure, relaxation
  specialRequirements?: string;
}


// ============================================================================
// LEGACY TYPES — Kept for backward compatibility with TripSearchForm
// ============================================================================

export type TripPreset = 'default' | 'budget' | 'luxury' | 'business';

export interface TripRequest {
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string;
  num_travelers: number;
  trip_purpose: string;
  flight_prefs: any;
  hotel_prefs: any;
  activity_prefs: any;
  transport_prefs: any;
  budget: any;
}

export const TRIP_PRESETS: Array<{ id: TripPreset; name: string; description: string }> = [
  { id: 'default', name: 'Balanced', description: 'Good mix of comfort & value' },
  { id: 'budget', name: 'Budget', description: 'Maximum savings' },
  { id: 'luxury', name: 'Luxury', description: 'Premium everything' },
  { id: 'business', name: 'Business', description: 'Efficient & professional' },
];

export function getDefaultFlightPrefs(_preset: TripPreset): any {
  return { max_stops: 1, cabin_class: 'economy', time_preference: 'flexible' };
}

export function getDefaultHotelPrefs(_preset: TripPreset): any {
  return { min_rating: 3.5, preferred_location: 'city_center' };
}

export function getDefaultActivityPrefs(_preset: TripPreset): any {
  return { interests: [], pace: 'moderate', entertainment_hours_per_day: 6 };
}

export function getDefaultBudget(_preset: TripPreset, _days?: number): any {
  return { total_budget: 4000, flight_budget: 1200, hotel_budget_per_night: 280 };
}