// frontend/src/components/itinerary/ItineraryRestaurantCard.tsx

import React from 'react';

interface Restaurant {
  id: string;
  name: string;
  rating: number;
  category: string;
  estimatedCost?: number;
}

interface ItineraryRestaurantCardProps {
  restaurant: Restaurant;
  onDelete: () => void;
}

export const ItineraryRestaurantCard: React.FC<ItineraryRestaurantCardProps> = ({
  restaurant,
  onDelete,
}) => {
  return (
    <div className="flex items-start justify-between bg-orange-50 border-2 border-orange-200 rounded-lg p-3 handwritten-body hover:shadow-md transition-shadow">
      <div className="flex-1">
        <div className="font-semibold text-base">{restaurant.name}</div>
        <div className="text-sm text-gray-600 flex items-center gap-2">
          <span>⭐ {restaurant.rating}</span>
          <span>•</span>
          <span className="capitalize">{restaurant.category}</span>
        </div>
        {restaurant.estimatedCost && (
          <div className="text-sm text-green-700 mt-1">
            ~${restaurant.estimatedCost}
          </div>
        )}
      </div>
      <button
        onClick={onDelete}
        className="text-red-500 hover:text-red-700 font-bold text-xl ml-2"
        aria-label="Remove restaurant"
      >
        ×
      </button>
    </div>
  );
};