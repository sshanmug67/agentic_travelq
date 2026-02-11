// frontend/src/types/trip.ts

export interface Flight {
  id: string;
  airline: string;
  outbound: FlightLeg;
  return_flight?: FlightLeg;
  price: number;
  cabin_class: string;
  total_duration: string;
  cabin_bags?: {
    quantity: number;
    weight: string;
    weight_unit: string;
  };
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
  stops: number;
  layovers?: string[];
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
  photos?: Array<{ url: string }>;
  highlights?: string[];
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
}