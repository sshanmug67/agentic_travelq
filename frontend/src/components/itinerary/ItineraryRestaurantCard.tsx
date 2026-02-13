// frontend/src/components/itinerary/ItineraryRestaurantCard.tsx
//
// Changes (v2 — Compact, 2-col grid ready):
//   - Photo thumbnail from Google Places photo_url
//   - Compact card for grid-cols-2 layout in sidebar
//   - Name, rating, cuisine on tight lines
//   - Small delete button top-right

import React from 'react';

interface Restaurant {
  id: string;
  name: string;
  rating: number;
  category: string;
  estimatedCost?: number;
  photo_url?: string;
  photos?: (string | { url: string })[];
}

interface ItineraryRestaurantCardProps {
  restaurant: Restaurant;
  onDelete: () => void;
}

export const ItineraryRestaurantCard: React.FC<ItineraryRestaurantCardProps> = ({
  restaurant,
  onDelete,
}) => {
  // Resolve photo: try photo_url first, then photos array
  const rawPhotos = restaurant.photos || [];
  const photo = restaurant.photo_url
    || (rawPhotos.length > 0
      ? (typeof rawPhotos[0] === 'string' ? rawPhotos[0] : (rawPhotos[0] as any)?.url)
      : null);

  return (
    <div className="relative bg-white border-2 border-amber-400 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow group">
      {/* Delete button */}
      <button
        onClick={onDelete}
        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-400 text-white text-[12px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        aria-label="Remove restaurant"
      >
        ×
      </button>

      {/* Photo */}
      {photo ? (
        <img
          src={photo}
          alt={restaurant.name}
          className="w-full h-16 object-cover"
        />
      ) : (
        <div className="w-full h-16 bg-gradient-to-br from-orange-100 to-orange-200 flex items-center justify-center">
          <span className="text-2xl">🍽️</span>
        </div>
      )}

      {/* Info */}
      <div className="px-2.5 py-2">
        <div className="font-semibold text-[13px] text-gray-800 truncate handwritten-body">
          {restaurant.name}
        </div>
        <div className="flex items-center gap-1 text-[11px] text-gray-500 handwritten-body">
          <span>⭐ {restaurant.rating}</span>
          <span>·</span>
          <span className="capitalize truncate">{restaurant.category}</span>
        </div>
        {restaurant.estimatedCost != null && restaurant.estimatedCost > 0 && (
          <div className="text-[11px] text-green-700 font-medium handwritten-body mt-0.5">
            ~${restaurant.estimatedCost}
          </div>
        )}
      </div>
    </div>
  );
};
