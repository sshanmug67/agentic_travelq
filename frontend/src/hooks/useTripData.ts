// frontend/src/hooks/useTripData.ts

import { create } from 'zustand';
import type { Flight, Hotel, Restaurant, Activity } from '../types/trip';


interface TripData {
  id: string;
  origin?: string;  // ← Add this
  destination: string;
  startDate: string;
  endDate: string;
  travelers: number;
  totalBudget: number;
}

interface Preferences {
  airlines: Array<{ name: string; preferred?: boolean }>;
  hotelChains: Array<{ name: string; preferred?: boolean }>;
  cuisines: Array<{ name: string; preferred?: boolean }>;
  activities: Array<{ name: string; preferred?: boolean }>;
  budget: {
    meals: string;
    accommodation: string;
    activities: string;
  };
}

interface TripDataState {
  tripData: TripData;
  flights: Flight[];
  hotels: Hotel[];
  restaurants: Restaurant[];
  activities: Activity[];
  weather: any[];
  preferences: Preferences;
  isLoading: boolean;
  error: string | null;

  setTripData: (data: Partial<TripData>) => void;
  setFlights: (flights: Flight[]) => void;
  setHotels: (hotels: Hotel[]) => void;
  setRestaurants: (restaurants: Restaurant[]) => void;
  setActivities: (activities: Activity[]) => void;
  setWeather: (weather: any[]) => void;
  updatePreferences: (category: keyof Preferences, value: any) => void;
  fetchTripData: (tripId: string) => Promise<void>;
}

export const useTripData = create<TripDataState>((set) => ({
  tripData: {
    id: 'trip_20260211_130210',
    origin: '',  // ← Add this
    destination: 'London, UK',
    startDate: '2026-02-16',
    endDate: '2026-02-20',
    travelers: 1,
    totalBudget: 4110,
  },
  flights: [],
  hotels: [],
  restaurants: [],
  activities: [],
  weather: [],
  preferences: {
    airlines: [
      { name: 'Air Canada', preferred: true },
      { name: 'United Airlines', preferred: false },
    ],
    hotelChains: [],
    cuisines: [
      { name: 'Indian', preferred: true },
      { name: 'Italian', preferred: false },
    ],
    activities: [
      { name: 'Museums', preferred: true },
      { name: 'Historic Landmarks', preferred: false },
    ],
    budget: {
      meals: '$$ (Mid-range)',
      accommodation: '$$ (Mid-range)',
      activities: 'Mostly free/low-cost',
    },
  },
  isLoading: false,
  error: null,

  setTripData: (data) => {
    set((state) => ({
      tripData: { ...state.tripData, ...data },
    }));
  },

  setFlights: (flights) => set({ flights }),
  setHotels: (hotels) => set({ hotels }),
  setRestaurants: (restaurants) => set({ restaurants }),
  setActivities: (activities) => set({ activities }),
  setWeather: (weather) => set({ weather }),

  updatePreferences: (category, value) => {
    set((state) => ({
      preferences: {
        ...state.preferences,
        [category]: value,
      },
    }));
  },

  fetchTripData: async (tripId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`/api/trip/${tripId}`);
      if (!response.ok) throw new Error('Failed to fetch trip data');
      
      const data = await response.json();
      
      set({
        tripData: data.trip,
        flights: data.flights || [],
        hotels: data.hotels || [],
        restaurants: data.restaurants || [],
        activities: data.activities || [],
        weather: data.weather || [],
        isLoading: false,
      });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
}));