// frontend/src/types/trip.ts
//
// Changes (v6):
//   - Added HotelProviderPrice interface for multi-OTA price comparison
//   - Hotel: added provider_prices field (all OTA prices from Xotelo)
//
// Changes (v5):
//   - Hotel: added reviews, website, phone_number, google_url, booking_url,
//     booking_links, cheapest_provider, is_estimated_price, price_level,
//     property_type, currency — all sourced from Google Places + Xotelo
//
// Changes (v4):
//   - Added SegmentDetail, FlightAmenity for enriched flight data
//   - FlightLeg: segments[], layover_durations[]
//   - Flight: branded_fare, amenities, last_ticketing_date, seats_remaining,
//     price_base, price_taxes, validating_carrier

// ============================================================================
// RESULT TYPES (from backend API responses)
// ============================================================================

// ── Individual hop within a leg ─────────────────────────────────────────

export interface SegmentDetail {
  segment_id?: string;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string;
  arrival_time: string;
  departure_terminal?: string;
  arrival_terminal?: string;
  duration: string;
  marketing_carrier: string;
  marketing_flight_number: string;
  operating_carrier?: string;
  operating_carrier_name?: string;
  aircraft_code?: string;
  aircraft_name?: string;
  cabin_class?: string;
  branded_fare?: string;
  fare_class?: string;
}

// ── Amenity line item ───────────────────────────────────────────────────

export interface FlightAmenity {
  description: string;
  is_chargeable: boolean;
  amenity_type: string;
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
  branded_fare?: string;
  amenities?: FlightAmenity[];
  last_ticketing_date?: string;
  seats_remaining?: number;
  price_base?: number;
  price_taxes?: number;
  validating_carrier?: string;

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
  segments?: SegmentDetail[];
  layover_durations?: string[];
}

// ── Hotel Review from Google Places ─────────────────────────────────────

export interface HotelReview {
  author_name: string;
  rating: number;
  text: string;
  relative_time_description?: string;
}

// ── Hotel Provider Price from Xotelo ────────────────────────────────────

export interface HotelProviderPrice {
  provider: string;          // "Booking.com", "Expedia", etc.
  price_per_night: number;   // rate_base + rate_tax (all-in nightly cost)
  total_price: number;       // price_per_night × num_nights
  rate_base?: number;        // Base rate per night (what OTAs show on search page)
  rate_tax?: number;         // Tax per night (added at checkout on most OTAs)
  url?: string;              // Direct booking link if available
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
  currency?: string;
  photos?: Array<{ url: string }>;
  highlights?: string[];

  // v5 additions — Google Places data
  reviews?: HotelReview[];              // Top guest reviews
  website?: string;                      // Hotel's own website
  phone_number?: string;                 // Contact number
  google_url?: string;                   // Google Maps link
  booking_url?: string;                  // Primary OTA link
  property_type?: string;                // "Hotel", "Resort", "B&B"
  price_level?: number;                  // Google price level 0-4

  // v5 additions — Pricing metadata
  booking_links?: Record<string, string>; // All OTA URLs: {"Booking.com": url, "Expedia": url}
  cheapest_provider?: string;             // "Booking.com", "Expedia", etc.
  is_estimated_price?: boolean;           // true = estimated, false = real Xotelo price

  // v6 addition — Multi-provider pricing from Xotelo
  provider_prices?: HotelProviderPrice[]; // All OTA prices, sorted cheapest first

  // Frontend-only
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

  // v5 additions — Google Places data
  reviews?: HotelReview[];
  website?: string;
  phone_number?: string;
  google_url?: string;
  cuisine_tag?: string;
  venue_type?: string;
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

  // v5 additions — Google Places data
  reviews?: HotelReview[];
  website?: string;
  phone_number?: string;
  google_url?: string;
  interest_tag?: string;
  venue_type?: string;
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
  pace: string;
  preferredTimes: string[];
  accessibilityNeeds?: string;
  entertainmentHoursPerDay: number;
}

export interface RestaurantPreferences {
  meals: string[];
  priceLevel: string[];
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
  airlines: NamedPreference[];
  hotelChains: NamedPreference[];
  cuisines: NamedPreference[];
  activities: NamedPreference[];
  budget: BudgetTiers;

  flightPrefs: FlightPreferences;
  hotelPrefs: HotelPreferences;
  activityPrefs: ActivityPreferences;
  restaurantPrefs: RestaurantPreferences;
  transportPrefs: TransportPreferences;
  budgetConstraints: BudgetConstraints;

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