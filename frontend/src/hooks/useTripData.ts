// frontend/src/hooks/useTripData.ts

import { create } from 'zustand';
import type { Flight, Hotel, Restaurant, Activity, UserPreferences } from '../types/trip';


interface TripData {
  id: string | null;  // null = new trip, string = existing trip
  origin: string;
  destination: string;
  startDate: string;
  endDate: string;
  travelers: number;
  totalBudget: number;
}


// ============================================================================
// DEFAULTS — Sensible starting values until user profile DB exists
// ============================================================================

const DEFAULT_TRIP_DATA: TripData = {
  id: null,
  origin: 'New York',
  destination: 'London',
  startDate: '2026-02-20',
  endDate: '2026-02-25',
  travelers: 1,
  totalBudget: 4000,
};

/**
 * Default preferences matching backend's TravelPreferences structure.
 *
 * These serve as the "user profile" until we have DB-backed user accounts.
 * The PreferencesPanel UI modifies the top-level lists (airlines, cuisines, etc.).
 * The detailed prefs (flightPrefs, hotelPrefs, etc.) use these defaults
 * and will eventually be editable via an "Advanced Preferences" UI.
 */
const DEFAULT_PREFERENCES: UserPreferences = {
  // ── UI Preferences (shown in PreferencesPanel) ────────────────────────
  airlines: [
    { name: 'United Airlines', preferred: true },
    { name: 'British Airways', preferred: false },
    { name: 'Delta', preferred: false },
  ],
  hotelChains: [
    { name: 'Marriott', preferred: true },
    { name: 'Hilton', preferred: false },
  ],
  cuisines: [
    { name: 'British', preferred: true },
    { name: 'Indian', preferred: false },
    { name: 'Italian', preferred: false },
  ],
  activities: [
    { name: 'Museums', preferred: true },
    { name: 'Historic Landmarks', preferred: true },
    { name: 'Walking Tours', preferred: false },
    { name: 'Theater', preferred: false },
  ],
  budget: {
    meals: '$$ (Mid-range)',
    accommodation: '$$ (Mid-range)',
    activities: 'Mostly free/low-cost',
  },

  // ── Detailed Flight Preferences ───────────────────────────────────────
  // Backend: FlightPreferences in user_preferences.py
  flightPrefs: {
    preferredCarriers: ['United Airlines'],  // Matches starred airlines above
    maxStops: 1,
    cabinClass: 'economy',
    timePreference: 'flexible',
    seatPreference: 'window',
  },

  // ── Detailed Hotel Preferences ────────────────────────────────────────
  // Backend: HotelPreferences in user_preferences.py
  hotelPrefs: {
    minRating: 3.5,
    preferredLocation: 'city_center',
    amenities: ['wifi', 'breakfast'],
    roomType: 'standard',
    priceRange: 'moderate',
  },

  // ── Detailed Activity Preferences ─────────────────────────────────────
  // Backend: ActivityPreferences in user_preferences.py
  activityPrefs: {
    interests: ['Museums', 'Historic Landmarks', 'Walking Tours', 'Theater'],
    pace: 'moderate',
    preferredTimes: ['morning', 'afternoon'],
    entertainmentHoursPerDay: 6,
  },

  // ── Detailed Transport Preferences ────────────────────────────────────
  // Backend: TransportPreferences in user_preferences.py
  transportPrefs: {
    preferredModes: ['metro', 'walk', 'cab'],
    maxWalkDistance: 1.0,
    comfortLevel: 'moderate',
  },

  // ── Budget Constraints (computed from totalBudget) ────────────────────
  // Backend: BudgetConstraints in user_preferences.py
  // These are recalculated whenever totalBudget changes (see helper below)
  budgetConstraints: {
    totalBudget: 4000,
    flightBudget: 1200,            // 30%
    hotelBudgetPerNight: 280,      // 35% ÷ nights
    dailyActivityBudget: 160,      // 20% ÷ days
    dailyFoodBudget: 80,           // 10% ÷ days  (was included in activ. split)
    transportBudget: 200,          // 5%
  },

  // ── Additional ────────────────────────────────────────────────────────
  tripPurpose: 'leisure',
  specialRequirements: undefined,
};


// ============================================================================
// HELPER: Recompute budget constraints from total + trip dates
// ============================================================================

function computeBudgetConstraints(
  totalBudget: number,
  startDate: string,
  endDate: string
): UserPreferences['budgetConstraints'] {
  let numDays = 5; // fallback
  if (startDate && endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diff = Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    if (diff > 0) numDays = diff;
  }

  return {
    totalBudget,
    flightBudget: Math.round(totalBudget * 0.30),
    hotelBudgetPerNight: Math.round((totalBudget * 0.35) / numDays),
    dailyActivityBudget: Math.round((totalBudget * 0.15) / numDays),
    dailyFoodBudget: Math.round((totalBudget * 0.15) / numDays),
    transportBudget: Math.round(totalBudget * 0.05),
  };
}


// ============================================================================
// ZUSTAND STORE
// ============================================================================

interface TripDataState {
  tripData: TripData;
  flights: Flight[];
  hotels: Hotel[];
  restaurants: Restaurant[];
  activities: Activity[];
  weather: any[];
  preferences: UserPreferences;
  isLoading: boolean;
  error: string | null;

  setTripData: (data: Partial<TripData>) => void;
  setFlights: (flights: Flight[]) => void;
  setHotels: (hotels: Hotel[]) => void;
  setRestaurants: (restaurants: Restaurant[]) => void;
  setActivities: (activities: Activity[]) => void;
  setWeather: (weather: any[]) => void;
  updatePreferences: (category: keyof UserPreferences, value: any) => void;
  resetTrip: () => void;
  fetchTripData: (tripId: string) => Promise<void>;
}

export const useTripData = create<TripDataState>((set) => ({
  tripData: { ...DEFAULT_TRIP_DATA },
  flights: [],
  hotels: [],
  restaurants: [],
  activities: [],
  weather: [],
  preferences: {
    ...DEFAULT_PREFERENCES,
    budgetConstraints: computeBudgetConstraints(
      DEFAULT_TRIP_DATA.totalBudget,
      DEFAULT_TRIP_DATA.startDate,
      DEFAULT_TRIP_DATA.endDate
    ),
  },
  isLoading: false,
  error: null,

  setTripData: (data) => {
    set((state) => {
      const newTripData = { ...state.tripData, ...data };

      // If budget or dates changed, recompute budget constraints
      const budgetChanged = data.totalBudget !== undefined;
      const datesChanged = data.startDate !== undefined || data.endDate !== undefined;

      let newPreferences = state.preferences;
      if (budgetChanged || datesChanged) {
        newPreferences = {
          ...state.preferences,
          budgetConstraints: computeBudgetConstraints(
            newTripData.totalBudget,
            newTripData.startDate,
            newTripData.endDate
          ),
        };
      }

      return {
        tripData: newTripData,
        preferences: newPreferences,
      };
    });
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

  resetTrip: () => {
    set({
      tripData: { ...DEFAULT_TRIP_DATA },
      flights: [],
      hotels: [],
      restaurants: [],
      activities: [],
      weather: [],
      preferences: {
        ...DEFAULT_PREFERENCES,
        budgetConstraints: computeBudgetConstraints(
          DEFAULT_TRIP_DATA.totalBudget,
          DEFAULT_TRIP_DATA.startDate,
          DEFAULT_TRIP_DATA.endDate
        ),
      },
      error: null,
    });
  },

  fetchTripData: async (tripId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`/api/trips/${tripId}`);
      if (!response.ok) throw new Error('Failed to fetch trip data');
      
      const data = await response.json();
      
      set({
        tripData: { ...data.trip, id: tripId },
        flights: data.flights || [],
        hotels: data.hotels || [],
        restaurants: data.restaurants || [],
        activities: data.activities || [],
        weather: data.weather || [],
        preferences: data.preferences || { ...DEFAULT_PREFERENCES },
        isLoading: false,
      });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
}));