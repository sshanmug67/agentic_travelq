// frontend/src/services/api.ts
//
// Changes (v5 — Async Pipeline):
//   - planTrip() now returns HTTP 202 with {trip_id, status: "queued"} (instant)
//   - New pollTripStatus() for GET /api/trips/{trip_id}/status
//   - Timeout reduced since planTrip returns immediately now
//
// Changes (v4):
//   - Timeout increased from 60s to 180s to accommodate multi-agent pipeline

import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000, // v5: 30s is plenty — POST returns instantly, polling is fast
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

// ── Request/Response types ──────────────────────────────────────────────────

interface PlanTripPreferences {
  airlines: NamedPreference[];
  hotelChains: NamedPreference[];
  cuisines: NamedPreference[];
  activities: NamedPreference[];
  budget: BudgetTiers;
  flightPrefs?: FlightPrefs;
  hotelPrefs?: HotelPrefs;
  activityPrefs?: ActivityPrefs;
  restaurantPrefs?: RestaurantPrefs;
  transportPrefs?: TransportPrefs;
  budgetConstraints?: BudgetConstraints;
  tripPurpose?: string;
  specialRequirements?: string;
}

interface PlanTripRequest {
  tripId: string | null;
  userRequest: string;
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

// v5: POST /search now returns this (HTTP 202 — instant)
export interface TripSubmitResponse {
  trip_id: string;
  status: string;
  message: string;
  poll_url: string;
}

// v5: GET /{trip_id}/status returns this (polling)
export interface TripPollResponse {
  trip_id: string;
  status: 'queued' | 'preprocessing' | 'in_progress' | 'completed' | 'failed';
  agents: Record<string, 'pending' | 'in_progress' | 'completed' | 'failed'>;
  preference_changes?: Array<{
    field: string;
    action: string;
    old: string;
    new: string;
  }>;
  created_at?: string;
  updated_at?: string;
  results?: any;
  error?: string;
}

// v4 legacy type — kept for backward compatibility with Dashboard/types
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
   * v5: Submit trip planning request. Returns IMMEDIATELY with trip_id.
   * The actual planning happens in a Celery worker.
   * Use pollTripStatus() to track progress.
   */
  planTrip: async (request: PlanTripRequest): Promise<TripSubmitResponse> => {
    const response = await api.post('/trips/search', request);
    return response.data;
  },

  /**
   * v5: Poll trip planning progress.
   * Returns agent-by-agent status and final results when complete.
   */
  pollTripStatus: async (tripId: string): Promise<TripPollResponse> => {
    const response = await api.get(`/trips/${tripId}/status`);
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