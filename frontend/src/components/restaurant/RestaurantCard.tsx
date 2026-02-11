// frontend/src/components/restaurant/RestaurantCard.tsx

import React from 'react';
import { motion } from 'framer-motion';

interface RestaurantCardProps {
  restaurant: {
    id: string;
    name: string;
    rating: number;
    user_ratings_total: number;
    category: string;
    address: string;
    price_level?: string;
    photos?: Array<{ url: string }>;
  };
  isSelected: boolean;
  onToggle: () => void;
}

export const RestaurantCard: React.FC<RestaurantCardProps> = ({
  restaurant,
  isSelected,
  onToggle,
}) => {
  const getPriceLevelDisplay = (level?: string) => {
    if (!level) return '$$';
    return level === 'PRICE_LEVEL_INEXPENSIVE'
      ? '$'
      : level === 'PRICE_LEVEL_MODERATE'
      ? '$$'
      : level === 'PRICE_LEVEL_EXPENSIVE'
      ? '$$$'
      : level === 'PRICE_LEVEL_VERY_EXPENSIVE'
      ? '$$$$'
      : '$$';
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      transition={{ duration: 0.2 }}
      className={`rounded-lg overflow-hidden cursor-pointer transition-all duration-300 ${
        isSelected
          ? 'ring-2 ring-orange-500 shadow-lg bg-gradient-to-br from-orange-50 to-red-50'
          : 'hover:shadow-md bg-white border border-gray-200'
      }`}
      onClick={onToggle}
    >
      <div className="flex gap-3 p-4">
        {/* Restaurant Photo */}
        <div className="w-24 h-24 rounded-lg overflow-hidden bg-gray-200 flex-shrink-0">
          {restaurant.photos && restaurant.photos.length > 0 ? (
            <img
              src={restaurant.photos[0].url}
              alt={restaurant.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl">
              🍽️
            </div>
          )}
        </div>

        {/* Restaurant Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-base text-gray-800 truncate">
                {restaurant.name}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                {/* Rating */}
                <div className="flex items-center gap-1">
                  <span className="text-yellow-500">⭐</span>
                  <span className="font-semibold text-sm">{restaurant.rating}</span>
                </div>
                <span className="text-xs text-gray-500">
                  ({restaurant.user_ratings_total?.toLocaleString()})
                </span>
                <span className="text-gray-400">•</span>
                {/* Price Level */}
                <span className="text-sm font-semibold text-green-700">
                  {getPriceLevelDisplay(restaurant.price_level)}
                </span>
              </div>
            </div>
            
            {/* Add/Remove Button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggle();
              }}
              className={`flex-shrink-0 px-3 py-1 rounded-full text-sm font-semibold transition-all ${
                isSelected
                  ? 'bg-orange-600 text-white hover:bg-orange-700'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {isSelected ? '✓ Added' : '+ Add'}
            </button>
          </div>

          {/* Cuisine Badge */}
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-orange-100 text-orange-700 text-xs px-2 py-1 rounded-full capitalize">
              {restaurant.category.replace('_', ' ')}
            </span>
          </div>

          {/* Address */}
          <div className="text-xs text-gray-600 truncate">
            📍 {restaurant.address}
          </div>
        </div>
      </div>

      {/* Selected State Footer */}
      {isSelected && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="bg-orange-500 px-4 py-2 text-white text-xs font-semibold flex items-center justify-between"
        >
          <span>✓ Added to your itinerary</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              // Add to specific day
            }}
            className="hover:underline"
          >
            Assign to Day →
          </button>
        </motion.div>
      )}
    </motion.div>
  );
};