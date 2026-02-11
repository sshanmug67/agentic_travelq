// frontend/src/components/itinerary/ItineraryActivityCard.tsx

import React from 'react';

interface Activity {
  id: string;
  name: string;
  rating: number;
  category: string;
  estimatedCost?: number;
}

interface ItineraryActivityCardProps {
  activity: Activity;
  onDelete: () => void;
}

export const ItineraryActivityCard: React.FC<ItineraryActivityCardProps> = ({
  activity,
  onDelete,
}) => {
  return (
    <div className="flex items-start justify-between bg-blue-50 border-2 border-blue-200 rounded-lg p-3 handwritten-body hover:shadow-md transition-shadow">
      <div className="flex-1">
        <div className="font-semibold text-base">{activity.name}</div>
        <div className="text-sm text-gray-600 flex items-center gap-2">
          <span>⭐ {activity.rating}</span>
          <span>•</span>
          <span className="capitalize">{activity.category.replace('_', ' ')}</span>
        </div>
        {activity.estimatedCost !== undefined && (
          <div className="text-sm text-green-700 mt-1">
            {activity.estimatedCost === 0 ? 'Free' : `~$${activity.estimatedCost}`}
          </div>
        )}
      </div>
      <button
        onClick={onDelete}
        className="text-red-500 hover:text-red-700 font-bold text-xl ml-2"
        aria-label="Remove activity"
      >
        ×
      </button>
    </div>
  );
};