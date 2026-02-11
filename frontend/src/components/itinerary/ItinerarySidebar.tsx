// frontend/src/components/itinerary/ItinerarySidebar.tsx

import React from 'react';
import { ItineraryFlightCard } from './ItineraryFlightCard';
import { ItineraryHotelCard } from './ItineraryHotelCard';
import { ItineraryRestaurantCard } from './ItineraryRestaurantCard';
import { ItineraryActivityCard } from './ItineraryActivityCard';
import { useItinerary } from '../../hooks/useItinerary';
import '../../styles/itinerary.css';

export const ItinerarySidebar: React.FC = () => {
  // Fix: Destructure individual properties, not an 'itinerary' object
  const { flight, hotel, restaurants, activities, removeItem, budget } = useItinerary();

  return (
    <div className="itinerary-paper h-full overflow-y-auto p-6 sticky top-0">
      {/* Header */}
      <div className="mb-6 text-center">
        <h2 className="handwritten-title text-4xl mb-2">
          Your Itinerary
        </h2>
        <div className="handwritten-subtitle text-gray-600">
          ✈️ Adventure Awaits! ✈️
        </div>
      </div>

      {/* Flight Section */}
      <div className="mb-6">
        <h3 className="handwritten-subtitle text-2xl mb-3 sketch-underline">
          ✈️ Flight
        </h3>
        {flight ? (
          <ItineraryFlightCard
            flight={flight}
            onDelete={() => removeItem('flight')}
          />
        ) : (
          <div className="empty-doodle">
            <div className="text-lg mb-2">✈️</div>
            <div>No flight selected</div>
            <button className="mt-2 text-purple-600 hover:text-purple-700">
              Browse Flights →
            </button>
          </div>
        )}
      </div>

      {/* Hotel Section */}
      <div className="mb-6">
        <h3 className="handwritten-subtitle text-2xl mb-3 sketch-underline">
          🏨 Hotel
        </h3>
        {hotel ? (
          <ItineraryHotelCard
            hotel={hotel}
            onDelete={() => removeItem('hotel')}
          />
        ) : (
          <div className="empty-doodle">
            <div className="text-lg mb-2">🏨</div>
            <div>No hotel selected</div>
            <button className="mt-2 text-purple-600 hover:text-purple-700">
              Browse Hotels →
            </button>
          </div>
        )}
      </div>

      {/* Restaurants Section */}
      <div className="mb-6">
        <h3 className="handwritten-subtitle text-2xl mb-3 sketch-underline">
          🍽️ Restaurants {restaurants.length > 0 && `(${restaurants.length})`}
        </h3>
        {restaurants.length > 0 ? (
          <div className="space-y-2">
            {restaurants.map((restaurant) => (
              <ItineraryRestaurantCard
                key={restaurant.id}
                restaurant={restaurant}
                onDelete={() => removeItem('restaurant', restaurant.id)}
              />
            ))}
            {restaurants.length < 10 && (
              <button className="w-full mt-2 text-sm text-purple-600 hover:text-purple-700 handwritten">
                + Add more restaurants
              </button>
            )}
          </div>
        ) : (
          <div className="empty-doodle">
            <div className="text-lg mb-2">🍽️</div>
            <div>Add restaurants to your trip</div>
            <button className="mt-2 text-purple-600 hover:text-purple-700">
              Browse Restaurants →
            </button>
          </div>
        )}
      </div>

      {/* Activities Section */}
      <div className="mb-6">
        <h3 className="handwritten-subtitle text-2xl mb-3 sketch-underline">
          🎭 Activities {activities.length > 0 && `(${activities.length})`}
        </h3>
        {activities.length > 0 ? (
          <div className="space-y-2">
            {activities.map((activity) => (
              <ItineraryActivityCard
                key={activity.id}
                activity={activity}
                onDelete={() => removeItem('activity', activity.id)}
              />
            ))}
            {activities.length < 10 && (
              <button className="w-full mt-2 text-sm text-purple-600 hover:text-purple-700 handwritten">
                + Add more activities
              </button>
            )}
          </div>
        ) : (
          <div className="empty-doodle">
            <div className="text-lg mb-2">🎭</div>
            <div>Add activities to your trip</div>
            <button className="mt-2 text-purple-600 hover:text-purple-700">
              Browse Activities →
            </button>
          </div>
        )}
      </div>

      {/* Budget Summary - Receipt Style */}
      <div className="budget-receipt">
        <div className="handwritten-subtitle text-xl mb-3 text-center">
          💰 Budget Summary
        </div>
        <div className="space-y-2 text-sm">
          {flight && (
            <div className="flex justify-between handwritten-body">
              <span>Flight:</span>
              <span className="font-mono">${flight.price}</span>
            </div>
          )}
          {hotel && (
            <div className="flex justify-between handwritten-body">
              <span>Hotel:</span>
              <span className="font-mono">${hotel.total_price}</span>
            </div>
          )}
          {restaurants.length > 0 && (
            <div className="flex justify-between handwritten-body">
              <span>Restaurants:</span>
              <span className="font-mono">
                ${restaurants.reduce((sum, r) => sum + (r.estimatedCost || 0), 0)}
              </span>
            </div>
          )}
          {activities.length > 0 && (
            <div className="flex justify-between handwritten-body">
              <span>Activities:</span>
              <span className="font-mono">
                ${activities.reduce((sum, a) => sum + (a.estimatedCost || 0), 0)}
              </span>
            </div>
          )}
          <div className="border-t-2 border-dashed border-gray-400 my-2"></div>
          <div className="flex justify-between handwritten-body font-semibold text-base">
            <span>Total:</span>
            <span className="font-mono">${budget.selected}</span>
          </div>
          <div className="flex justify-between handwritten-body text-gray-600">
            <span>Budget:</span>
            <span className="font-mono">${budget.total}</span>
          </div>
          <div className="flex justify-between handwritten-body font-semibold text-green-700">
            <span>Remaining:</span>
            <span className="font-mono">${budget.remaining}</span>
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="mt-3">
          <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-400 to-green-600 transition-all duration-500"
              style={{ width: `${(budget.selected / budget.total) * 100}%` }}
            ></div>
          </div>
          <div className="text-xs text-center mt-1 handwritten">
            {((budget.selected / budget.total) * 100).toFixed(0)}% used
          </div>
        </div>
      </div>

      {/* Action Buttons - Sticky Notes Style */}
      <div className="mt-6 space-y-3">
        <button className="sticky-button w-full">
          📧 Email Itinerary
        </button>
        <button className="sticky-button w-full">
          💾 Save Trip
        </button>
        <button className="sticky-button w-full">
          📤 Share with Friends
        </button>
      </div>

      {/* Little doodles at the bottom */}
      <div className="mt-6 text-center opacity-30">
        <div className="handwritten text-2xl">
          ✈️ 🌍 🗺️ 📸 ⭐
        </div>
      </div>
    </div>
  );
};