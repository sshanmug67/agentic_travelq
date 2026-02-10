import { useState } from 'react';
import { tripService } from '@/services/api';
import type { TripRequest, TripResponse } from '@/types/trip';

export const useTripData = () => {
  const [tripData, setTripData] = useState<TripResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const searchTrip = async (request: TripRequest) => {
    setLoading(true);
    setError(null);

    try {
      const data = await tripService.searchTrip(request);
      setTripData(data);
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to search trip';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const clearTrip = () => {
    setTripData(null);
    setError(null);
  };

  return {
    tripData,
    loading,
    error,
    searchTrip,
    clearTrip,
  };
};
