import axios from 'axios';
import type { TripRequest, TripResponse } from '@/types/trip';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const tripService = {
  /**
   * Search for trip information
   */
  searchTrip: async (request: TripRequest): Promise<TripResponse> => {
    const response = await api.post<TripResponse>('/api/trips/search', request);
    return response.data;
  },

  /**
   * Health check
   */
  healthCheck: async (): Promise<{ status: string }> => {
    const response = await api.get('/api/trips/health');
    return response.data;
  },
};

export default api;
