// frontend/src/services/api.ts
//
// Changes (v4):
//   - Timeout increased from 60s to 180s to accommodate multi-agent pipeline
//     (WeatherAgent + PlacesAgent with ~10 Google Places API calls + LLM)

import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 180000, // 180 seconds — multi-agent pipeline needs headroom
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Shared sub-types ────────────────────────────────────────────────────────

interface NamedPreference {
  name: string;
  preferred?: boolean;
}

interface BudgetTiers {
  meals: string;
  accommodation: string;
  activities: string;
}

interface FlightPrefs {
  maxStops: number;
  cabinClass: string;
  timePreference: string;
  seatPreference: string;
}

interface HotelPrefs {
  minRating: number;
  preferredLocation: string;
  amenities: string[];
  roomType: string;
  priceRange: string;
}

interface ActivityPrefs {
  pace: string;
  preferredTimes: string[];
  accessibilityNeeds?: string;
  entertainmentHoursPerDay: number;
}

interface RestaurantPrefs {
  meals: string[];
  priceLevel: string[];
}

interface TransportPrefs {
  preferredModes: string[];
  maxWalkDistance: number;
  comfortLevel: string;
}

interface BudgetConstraints {
  totalBudget: number;
  flightBudget: number;
  hotelBudgetPerNight: number;
  dailyActivityBudget: number;
  dailyFoodBudget: number;
  transportBudget: number;
}

// ── Request/Response types (match backend TripSearchRequest) ────────────────

interface PlanTripPreferences {
  // UI Preferences (PreferencesPanel chip lists)
  airlines: NamedPreference[];
  hotelChains: NamedPreference[];
  cuisines: NamedPreference[];
  activities: NamedPreference[];
  budget: BudgetTiers;

  // Detailed preferences (Advanced settings, sent alongside UI lists)
  flightPrefs?: FlightPrefs;
  hotelPrefs?: HotelPrefs;
  activityPrefs?: ActivityPrefs;
  restaurantPrefs?: RestaurantPrefs;
  transportPrefs?: TransportPrefs;
  budgetConstraints?: BudgetConstraints;

  // Additional
  tripPurpose?: string;
  specialRequirements?: string;
}

interface PlanTripRequest {
  tripId: string | null;     // null = new trip, string = existing trip
  userRequest: string;       // NL query (can be empty)
  tripDetails: {
    origin?: string;
    destination: string;
    startDate: string;
    endDate: string;
    travelers: number;
    budget: number;
  };
  preferences: PlanTripPreferences;
  currentItinerary: {
    flight: any | null;
    hotel: any | null;
    restaurants: any[];
    activities: any[];
  };
}

interface PlanTripResponse {
  status: string;
  tripId: string;
  trip_id?: string;
  final_recommendation: string;
  recommendations?: Record<string, any>;
  message?: string;
  options?: Record<string, any[]>;
  results?: Record<string, any[]>;
  summary?: Record<string, number>;
  processing_time: number;
  agents_used: string[];
}

// ── API methods ─────────────────────────────────────────────────────────────

export const tripApi = {
  /**
   * Single endpoint for all trip planning:
   *  - New trip search (tripId = null)
   *  - Refine existing trip (tripId set, query/prefs changed)
   *  - Save selections (tripId set, itinerary changed)
   *
   * The preferences object carries both the UI chip lists (with preferred
   * flags) and the detailed prefs. The backend uses `preferred: true` items
   * as priority search targets and `preferred: false` as secondary interests.
   */
  planTrip: async (request: PlanTripRequest): Promise<PlanTripResponse> => {
    const response = await api.post('/trips/search', request);
    return response.data;
  },

  /**
   * Explicitly save the user's itinerary selections
   */
  saveItinerary: async (tripId: string, itinerary: any) => {
    const response = await api.post(`/trips/${tripId}/itinerary`, itinerary);
    return response.data;
  },

  /**
   * Get all saved trips for the current user
   */
  getMyTrips: async () => {
    const response = await api.get('/trips');
    return response.data;
  },
};

export default api;