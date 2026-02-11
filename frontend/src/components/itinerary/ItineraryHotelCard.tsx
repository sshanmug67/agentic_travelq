// frontend/src/components/itinerary/ItineraryHotelCard.tsx

import React from 'react';
import type { Hotel } from '../../types/trip';

interface ItineraryHotelCardProps {
  hotel: Hotel & { selectedBy?: 'ai' | 'user'; priceDifference?: number };
  onDelete: () => void;
}

export const ItineraryHotelCard: React.FC<ItineraryHotelCardProps> = ({
  hotel,
  onDelete,
}) => {
  const isAiSelected = hotel.selectedBy === 'ai';

  return (
    <div className="itinerary-card">
      <div className="flex justify-between items-start mb-3">
        {isAiSelected ? (
          <span className="ai-sticker text-sm">
            🤖 AI Pick
          </span>
        ) : (
          <span className="user-badge text-sm text-white">
            👤 You Chose
          </span>
        )}
        <button
          onClick={onDelete}
          className="paper-delete"
          aria-label="Delete hotel"
        >
          ×
        </button>
      </div>

      <div className="handwritten-body">
        <div className="font-bold text-lg mb-2">{hotel.name}</div>

        <div className="flex items-center gap-2 mb-2">
          <span className="text-yellow-500">⭐ {hotel.google_rating}</span>
          {hotel.user_ratings_total && (
            <span className="text-sm text-gray-600">
              ({hotel.user_ratings_total.toLocaleString()} reviews)
            </span>
          )}
        </div>

        <div className="space-y-1 text-sm mb-3">
          <div>📍 {hotel.address}</div>
          <div>
            🗓️ {hotel.check_in_date} - {hotel.check_out_date}
          </div>
          <div>🛏️ {hotel.num_nights} night{hotel.num_nights > 1 ? 's' : ''}</div>
        </div>

        <div className="mt-4 pt-3 border-t border-dashed border-gray-300">
          <div className="font-bold text-lg text-green-700">
            💰 ${hotel.total_price}
          </div>
          <div className="text-sm text-gray-600">
            ${hotel.price_per_night}/night
          </div>
          {!isAiSelected && hotel.priceDifference !== undefined && hotel.priceDifference !== 0 && (
            <div className="text-sm text-gray-600 mt-1">
              {hotel.priceDifference > 0 ? '+' : ''}${hotel.priceDifference} vs AI
            </div>
          )}
        </div>
      </div>
    </div>
  );
};