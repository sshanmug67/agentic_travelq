// frontend/src/services/api.ts

import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000, // 60 seconds for AI processing
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request/Response types (match backend TripSearchRequest) ────────────────

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
  preferences: {
    airlines: Array<{ name: string; preferred?: boolean }>;
    hotelChains: Array<{ name: string; preferred?: boolean }>;
    cuisines: Array<{ name: string; preferred?: boolean }>;
    activities: Array<{ name: string; preferred?: boolean }>;
    budget: {
      meals: string;
      accommodation: string;
      activities: string;
    };
  };
  currentItinerary: {
    flight: any | null;
    hotel: any | null;
    restaurants: any[];
    activities: any[];
  };
}

interface PlanTripResponse {
  status: string;
  tripId: string;              // Backend always returns a tripId
  final_recommendation: string;
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