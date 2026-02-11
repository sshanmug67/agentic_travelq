// frontend/src/services/api.ts

import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000, // 60 seconds for AI processing
  headers: {
    'Content-Type': 'application/json',
  },
});

export const tripApi = {
  // Single endpoint for trip planning
  planTrip: async (request: {
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
    preferences: any;
    currentItinerary: any;
  }) => {
    const response = await api.post('/trip/plan', request);
    return response.data;
  },

  // Save itinerary
  saveItinerary: async (tripId: string, itinerary: any) => {
    const response = await api.post(`/trip/${tripId}/itinerary`, itinerary);
    return response.data;
  },

  // Get saved trips
  getMyTrips: async () => {
    const response = await api.get('/trips');
    return response.data;
  },
};

export default api;