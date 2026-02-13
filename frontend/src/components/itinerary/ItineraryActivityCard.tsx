// frontend/src/components/itinerary/ItineraryActivityCard.tsx
//
// Changes (v2 — Compact, 2-col grid ready):
//   - Photo thumbnail from Google Places photo_url
//   - Compact card for grid-cols-2 layout in sidebar
//   - Name, rating, interest type on tight lines
//   - Small delete button top-right (hover reveal)

import React from 'react';

interface Activity {
  id: string;
  name: string;
  rating: number;
  category: string;
  estimatedCost?: number;
  photo_url?: string;
  photos?: (string | { url: string })[];
}

interface ItineraryActivityCardProps {
  activity: Activity;
  onDelete: () => void;
}

export const ItineraryActivityCard: React.FC<ItineraryActivityCardProps> = ({
  activity,
  onDelete,
}) => {
  const rawPhotos = activity.photos || [];
  const photo = activity.photo_url
    || (rawPhotos.length > 0
      ? (typeof rawPhotos[0] === 'string' ? rawPhotos[0] : (rawPhotos[0] as any)?.url)
      : null);

  return (
    <div className="relative bg-blue-50 border-2 border-blue-300 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow group">
      {/* Delete button */}
      <button
        onClick={onDelete}
        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-400 text-white text-[12px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        aria-label="Remove activity"
      >
        ×
      </button>

      {/* Photo */}
      {photo ? (
        <img
          src={photo}
          alt={activity.name}
          className="w-full h-16 object-cover"
        />
      ) : (
        <div className="w-full h-16 bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center">
          <span className="text-2xl">🎭</span>
        </div>
      )}

      {/* Info */}
      <div className="px-2.5 py-2">
        <div className="font-semibold text-[13px] text-gray-800 truncate handwritten-body">
          {activity.name}
        </div>
        <div className="flex items-center gap-1 text-[11px] text-gray-500 handwritten-body">
          <span>⭐ {activity.rating}</span>
          <span>·</span>
          <span className="capitalize truncate">{activity.category}</span>
        </div>
        {activity.estimatedCost != null && activity.estimatedCost > 0 && (
          <div className="text-[11px] text-green-700 font-medium handwritten-body mt-0.5">
            ~${activity.estimatedCost}
          </div>
        )}
      </div>
    </div>
  );
};
