// frontend/src/hooks/useItinerary.ts

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Flight, Hotel, Restaurant, Activity } from '../types/trip';

interface ItineraryState {
  flight: (Flight & { selectedBy?: 'ai' | 'user'; priceDifference?: number }) | null;
  hotel: (Hotel & { selectedBy?: 'ai' | 'user'; priceDifference?: number }) | null;
  restaurants: Restaurant[];
  activities: Activity[];
  budget: {
    total: number;
    selected: number;
    remaining: number;
  };
  
  selectFlight: (flight: Flight, selectedBy?: 'ai' | 'user') => void;
  selectHotel: (hotel: Hotel, selectedBy?: 'ai' | 'user') => void;
  toggleRestaurant: (restaurant: Restaurant) => void;
  toggleActivity: (activity: Activity) => void;
  removeItem: (type: 'flight' | 'hotel' | 'restaurant' | 'activity', id?: string) => void;
  clearItinerary: () => void;
  setBudget: (total: number) => void;
}

export const useItinerary = create<ItineraryState>()(
  persist(
    (set, get) => ({
      flight: null,
      hotel: null,
      restaurants: [],
      activities: [],
      budget: {
        total: 4110,
        selected: 0,
        remaining: 4110,
      },

      selectFlight: (flight, selectedBy = 'user') => {
        const state = get();
        const currentFlight = state.flight;
        
        let priceDifference = 0;
        if (selectedBy === 'user' && currentFlight?.selectedBy === 'ai') {
          priceDifference = flight.price - currentFlight.price;
        }

        const newFlight = {
          ...flight,
          selectedBy,
          priceDifference: selectedBy === 'user' ? priceDifference : undefined,
        };

        set((state) => {
          const oldPrice = state.flight?.price || 0;
          const newPrice = newFlight.price;
          const selected = state.budget.selected - oldPrice + newPrice;
          
          return {
            flight: newFlight,
            budget: {
              ...state.budget,
              selected,
              remaining: state.budget.total - selected,
            },
          };
        });
      },

      selectHotel: (hotel, selectedBy = 'user') => {
        const state = get();
        const currentHotel = state.hotel;
        
        let priceDifference = 0;
        if (selectedBy === 'user' && currentHotel?.selectedBy === 'ai') {
          priceDifference = hotel.total_price - currentHotel.total_price;
        }

        const newHotel = {
          ...hotel,
          selectedBy,
          priceDifference: selectedBy === 'user' ? priceDifference : undefined,
        };

        set((state) => {
          const oldPrice = state.hotel?.total_price || 0;
          const newPrice = newHotel.total_price;
          const selected = state.budget.selected - oldPrice + newPrice;
          
          return {
            hotel: newHotel,
            budget: {
              ...state.budget,
              selected,
              remaining: state.budget.total - selected,
            },
          };
        });
      },

      toggleRestaurant: (restaurant) => {
        set((state) => {
          const exists = state.restaurants.find((r) => r.id === restaurant.id);
          let newRestaurants: Restaurant[];
          let priceChange = 0;

          if (exists) {
            newRestaurants = state.restaurants.filter((r) => r.id !== restaurant.id);
            priceChange = -(restaurant.estimatedCost || 0);
          } else {
            if (state.restaurants.length >= 10) {
              return state;
            }
            newRestaurants = [...state.restaurants, restaurant];
            priceChange = restaurant.estimatedCost || 0;
          }

          const selected = state.budget.selected + priceChange;

          return {
            restaurants: newRestaurants,
            budget: {
              ...state.budget,
              selected,
              remaining: state.budget.total - selected,
            },
          };
        });
      },

      toggleActivity: (activity) => {
        set((state) => {
          const exists = state.activities.find((a) => a.id === activity.id);
          let newActivities: Activity[];
          let priceChange = 0;

          if (exists) {
            newActivities = state.activities.filter((a) => a.id !== activity.id);
            priceChange = -(activity.estimatedCost || 0);
          } else {
            if (state.activities.length >= 10) {
              return state;
            }
            newActivities = [...state.activities, activity];
            priceChange = activity.estimatedCost || 0;
          }

          const selected = state.budget.selected + priceChange;

          return {
            activities: newActivities,
            budget: {
              ...state.budget,
              selected,
              remaining: state.budget.total - selected,
            },
          };
        });
      },

      removeItem: (type, id) => {
        set((state) => {
          let priceChange = 0;
          const updates: Partial<ItineraryState> = {};

          switch (type) {
            case 'flight':
              priceChange = -(state.flight?.price || 0);
              updates.flight = null;
              break;
            case 'hotel':
              priceChange = -(state.hotel?.total_price || 0);
              updates.hotel = null;
              break;
            case 'restaurant':
              if (id) {
                const restaurant = state.restaurants.find((r) => r.id === id);
                priceChange = -(restaurant?.estimatedCost || 0);
                updates.restaurants = state.restaurants.filter((r) => r.id !== id);
              }
              break;
            case 'activity':
              if (id) {
                const activity = state.activities.find((a) => a.id === id);
                priceChange = -(activity?.estimatedCost || 0);
                updates.activities = state.activities.filter((a) => a.id !== id);
              }
              break;
          }

          const selected = state.budget.selected + priceChange;

          return {
            ...updates,
            budget: {
              ...state.budget,
              selected,
              remaining: state.budget.total - selected,
            },
          };
        });
      },

      clearItinerary: () => {
        set({
          flight: null,
          hotel: null,
          restaurants: [],
          activities: [],
          budget: {
            total: get().budget.total,
            selected: 0,
            remaining: get().budget.total,
          },
        });
      },

      setBudget: (total) => {
        set((state) => ({
          budget: {
            total,
            selected: state.budget.selected,
            remaining: total - state.budget.selected,
          },
        }));
      },
    }),
    {
      name: 'itinerary-storage',
    }
  )
);