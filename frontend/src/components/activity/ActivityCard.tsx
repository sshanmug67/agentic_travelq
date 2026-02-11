// frontend/src/components/activity/ActivityCard.tsx

import React from 'react';
import { motion } from 'framer-motion';

interface ActivityCardProps {
  activity: {
    id: string;
    name: string;
    rating: number;
    user_ratings_total: number;
    category: string;
    address: string;
    opening_hours?: string;
    price?: string;
    photos?: Array<{ url: string }>;
  };
  isSelected: boolean;
  onToggle: () => void;
}

export const ActivityCard: React.FC<ActivityCardProps> = ({
  activity,
  isSelected,
  onToggle,
}) => {
  const getCategoryIcon = (category: string) => {
    const icons: { [key: string]: string } = {
      museum: '🏛️',
      park: '🌳',
      landmark: '🗿',
      shopping: '🛍️',
      entertainment: '🎭',
      cultural: '🎨',
      historic: '🏰',
      religious: '⛪',
      nature: '🏞️',
      default: '📍',
    };
    return icons[category.toLowerCase()] || icons.default;
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      transition={{ duration: 0.2 }}
      className={`rounded-lg overflow-hidden cursor-pointer transition-all duration-300 ${
        isSelected
          ? 'ring-2 ring-blue-500 shadow-lg bg-gradient-to-br from-blue-50 to-indigo-50'
          : 'hover:shadow-md bg-white border border-gray-200'
      }`}
      onClick={onToggle}
    >
      <div className="flex gap-3 p-4">
        {/* Activity Photo */}
        <div className="w-24 h-24 rounded-lg overflow-hidden bg-gray-200 flex-shrink-0 relative">
          {activity.photos && activity.photos.length > 0 ? (
            <img
              src={activity.photos[0].url}
              alt={activity.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl">
              {getCategoryIcon(activity.category)}
            </div>
          )}
          {/* Category Badge Overlay */}
          <div className="absolute top-1 right-1 bg-white/90 backdrop-blur-sm rounded-full px-2 py-0.5 text-xs font-semibold">
            {getCategoryIcon(activity.category)}
          </div>
        </div>

        {/* Activity Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-base text-gray-800 truncate">
                {activity.name}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                {/* Rating */}
                <div className="flex items-center gap-1">
                  <span className="text-yellow-500">⭐</span>
                  <span className="font-semibold text-sm">{activity.rating}</span>
                </div>
                <span className="text-xs text-gray-500">
                  ({activity.user_ratings_total?.toLocaleString()})
                </span>
                {activity.price && (
                  <>
                    <span className="text-gray-400">•</span>
                    <span className="text-sm font-semibold text-green-700">
                      {activity.price === 'Free' ? '🎁 Free' : activity.price}
                    </span>
                  </>
                )}
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
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {isSelected ? '✓ Added' : '+ Add'}
            </button>
          </div>

          {/* Category & Hours */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full capitalize">
              {activity.category.replace('_', ' ')}
            </span>
            {activity.opening_hours && (
              <span className="text-xs text-gray-600 flex items-center gap-1">
                🕐 {activity.opening_hours}
              </span>
            )}
          </div>

          {/* Address */}
          <div className="text-xs text-gray-600 truncate">
            📍 {activity.address}
          </div>
        </div>
      </div>

      {/* Selected State Footer */}
      {isSelected && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="bg-blue-500 px-4 py-2 text-white text-xs font-semibold flex items-center justify-between"
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