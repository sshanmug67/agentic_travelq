/**
 * Enhanced Trip Types - Matches backend TravelPreferences model
 * Location: frontend/src/types/trip.ts
 */

// === PREFERENCE TYPES ===

export interface FlightPreferences {
  preferred_carriers: string[];
  max_stops: number;
  cabin_class: 'economy' | 'premium_economy' | 'business' | 'first';
  time_preference: 'morning' | 'afternoon' | 'evening' | 'night' | 'flexible';
  seat_preference?: 'window' | 'aisle' | 'middle';
}

export interface HotelPreferences {
  min_rating: number; // 1-5
  preferred_location: 'city_center' | 'near_attractions' | 'quiet_area';
  amenities: string[];
  room_type: 'standard' | 'deluxe' | 'suite';
  price_range: 'budget' | 'moderate' | 'luxury';
}

export interface ActivityPreferences {  // ✅ Make sure this is exported!
  interests: string[];
  pace: 'relaxed' | 'moderate' | 'fast-paced';
  preferred_times: ('morning' | 'afternoon' | 'evening')[];
  entertainment_hours_per_day: number;
  accessibility_needs?: string;
}

export interface TransportPreferences {
  preferred_modes: string[];
  max_walk_distance: number; // in miles
  comfort_level: 'budget' | 'moderate' | 'premium';
}

export interface BudgetConstraints {
  total_budget: number;
  flight_budget?: number;
  hotel_budget_per_night?: number;
  daily_activity_budget?: number;
  daily_food_budget?: number;
  transport_budget?: number;
}

// === MAIN REQUEST TYPE ===

export interface TripRequest {
  // Basic trip info
  origin: string;
  destination: string;
  departure_date: string; // ISO format: YYYY-MM-DD
  return_date: string;
  num_travelers: number;
  trip_purpose?: 'leisure' | 'business' | 'adventure' | 'relaxation';
  
  // Detailed preferences
  flight_prefs: FlightPreferences;
  hotel_prefs: HotelPreferences;
  activity_prefs: ActivityPreferences;
  transport_prefs: TransportPreferences;
  budget: BudgetConstraints;
  
  // Additional info
  special_requirements?: string;
}

// === RESPONSE TYPES ===

export interface Flight {
  id: string;
  airline: string;
  airline_code?: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  duration: string;
  price: number;
  currency?: string;
  stops: number;
  cabin_class: string;
  layovers?: string[];
  booking_url?: string;
}

export interface Weather {
  date: string;
  temperature: number;
  feels_like?: number;
  temp_min: number;
  temp_max: number;
  description: string;
  icon?: string;
  humidity: number;
  wind_speed?: number;
  precipitation_probability: number;
  conditions?: string;
}

export interface Event {
  id: string;
  name: string;
  description?: string;
  venue: string;
  address?: string;
  start_time: string;
  end_time?: string;
  category: string;
  price_range?: string;
  ticket_url?: string;
  image_url?: string;
  is_free: boolean;
}

export interface Place {
  id: string;
  name: string;
  address: string;
  latitude?: number;
  longitude?: number;
  rating?: number;
  category: string;
  price_level?: number;
  opening_hours?: Record<string, string>;
  description?: string;
  photos?: string[];
  website?: string;
}

export interface TripResponse {
  status: string;
  trip_id?: string;
  flights: Flight[];
  weather_forecast: Weather[];
  events: Event[];
  places: Place[];
  preferences_summary?: string;
  processing_time?: number;
  ai_suggestions?: string;
  itinerary?: DayItinerary[];
  budget_summary?: BudgetSummary;
}

export interface DayItinerary {
  day_number: number;
  date: string;
  activities: Activity[];
  meals?: Meal[];
  transportation?: Transportation[];
}

export interface Activity {
  time: string;
  name: string;
  location: string;
  duration: string;
  cost?: number;
  notes?: string;
}

export interface Meal {
  time: string;
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  restaurant?: string;
  estimated_cost?: number;
}

export interface Transportation {
  from: string;
  to: string;
  mode: string;
  time: string;
  cost?: number;
}

export interface BudgetSummary {
  total_budget: number;
  estimated_flight_cost: number;
  estimated_hotel_cost: number;
  estimated_activity_cost: number;
  estimated_food_cost: number;
  estimated_transport_cost: number;
  remaining_budget: number;
}

// === PRESET TYPES ===

export type TripPreset = 'default' | 'budget' | 'luxury' | 'custom';

export interface PresetOption {
  id: TripPreset;
  name: string;
  description: string;
  sample_budget: number;
}

export const TRIP_PRESETS: PresetOption[] = [
  {
    id: 'budget',
    name: 'Budget Traveler',
    description: 'Economical options, hostels, local experiences',
    sample_budget: 2000
  },
  {
    id: 'default',
    name: 'Moderate',
    description: 'Balanced comfort and cost, 3-4 star hotels',
    sample_budget: 5000
  },
  {
    id: 'luxury',
    name: 'Luxury',
    description: 'Premium experiences, 5-star hotels, business class',
    sample_budget: 15000
  },
  {
    id: 'custom',
    name: 'Custom',
    description: 'Fully customize your preferences',
    sample_budget: 0
  }
];

// === HELPER FUNCTIONS ===

export const getDefaultFlightPrefs = (preset: TripPreset): FlightPreferences => {
  const defaults: Record<TripPreset, FlightPreferences> = {
    budget: {
      preferred_carriers: [],
      max_stops: 2,
      cabin_class: 'economy',
      time_preference: 'flexible',
    },
    default: {
      preferred_carriers: [],
      max_stops: 1,
      cabin_class: 'economy',
      time_preference: 'flexible',  // ✅ Fixed from 'daytime'
    },
    luxury: {
      preferred_carriers: [],
      max_stops: 0,
      cabin_class: 'business',
      time_preference: 'morning',
      seat_preference: 'aisle',
    },
    custom: {
      preferred_carriers: [],
      max_stops: 1,
      cabin_class: 'economy',
      time_preference: 'flexible',
    },
  };
  
  return defaults[preset];
};

export const getDefaultHotelPrefs = (preset: TripPreset): HotelPreferences => {
  const defaults: Record<TripPreset, HotelPreferences> = {
    budget: {
      min_rating: 3.0,
      preferred_location: 'near_attractions',
      amenities: ['wifi'],
      room_type: 'standard',
      price_range: 'budget',
    },
    default: {
      min_rating: 4.0,
      preferred_location: 'city_center',
      amenities: ['wifi', 'breakfast'],
      room_type: 'standard',
      price_range: 'moderate',
    },
    luxury: {
      min_rating: 5.0,
      preferred_location: 'city_center',
      amenities: ['wifi', 'spa', 'gym', 'room_service'],
      room_type: 'suite',
      price_range: 'luxury',
    },
    custom: {
      min_rating: 3.5,
      preferred_location: 'city_center',
      amenities: ['wifi'],
      room_type: 'standard',
      price_range: 'moderate',
    },
  };
  
  return defaults[preset];
};

export const getDefaultActivityPrefs = (preset: TripPreset): ActivityPreferences => {
  const defaults: Record<TripPreset, ActivityPreferences> = {
    budget: {
      interests: ['local_culture', 'street_food', 'free_activities'],
      pace: 'fast-paced',
      preferred_times: ['morning', 'afternoon', 'evening'],
      entertainment_hours_per_day: 10,
    },
    default: {
      interests: ['culture', 'food', 'sightseeing'],
      pace: 'moderate',
      preferred_times: ['morning', 'afternoon'],
      entertainment_hours_per_day: 7,
    },
    luxury: {
      interests: ['fine_dining', 'spa', 'exclusive_experiences'],
      pace: 'relaxed',
      preferred_times: ['afternoon', 'evening'],
      entertainment_hours_per_day: 5,
    },
    custom: {
      interests: [],
      pace: 'moderate',
      preferred_times: ['morning', 'afternoon'],
      entertainment_hours_per_day: 6,
    },
  };
  
  return defaults[preset];
};

export const getDefaultBudget = (preset: TripPreset, days: number = 7): BudgetConstraints => {
  // Base daily costs per preset
  const dailyCosts: Record<TripPreset, {
    hotel_per_night: number;
    daily_activity: number;
    daily_food: number;
  }> = {
    budget: {
      hotel_per_night: 50,
      daily_activity: 40,
      daily_food: 30,
    },
    default: {
      hotel_per_night: 150,
      daily_activity: 100,
      daily_food: 80,
    },
    luxury: {
      hotel_per_night: 500,
      daily_activity: 300,
      daily_food: 200,
    },
    custom: {
      hotel_per_night: 150,
      daily_activity: 100,
      daily_food: 80,
    },
  };

  // Fixed costs
  const fixedCosts: Record<TripPreset, {
    flight_budget: number;
    transport_budget: number;
  }> = {
    budget: {
      flight_budget: 600,
      transport_budget: 100,
    },
    default: {
      flight_budget: 1500,
      transport_budget: 300,
    },
    luxury: {
      flight_budget: 5000,
      transport_budget: 500,
    },
    custom: {
      flight_budget: 1500,
      transport_budget: 300,
    },
  };

  const daily = dailyCosts[preset];
  const fixed = fixedCosts[preset];

  // Calculate total based on trip duration
  const total_budget = 
    fixed.flight_budget +
    (daily.hotel_per_night * days) +
    (daily.daily_activity * days) +
    (daily.daily_food * days) +
    fixed.transport_budget;

  return {
    total_budget,
    flight_budget: fixed.flight_budget,
    hotel_budget_per_night: daily.hotel_per_night,
    daily_activity_budget: daily.daily_activity,
    daily_food_budget: daily.daily_food,
    transport_budget: fixed.transport_budget,
  };
};